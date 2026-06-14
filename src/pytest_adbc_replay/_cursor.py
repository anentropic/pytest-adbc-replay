"""ReplayCursor: ADBC cursor proxy for record/replay testing."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict, deque
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Any, NoReturn

import pyarrow as pa
from adbc_driver_manager import AdbcStatusCode
from adbc_driver_manager.dbapi import NotSupportedError, ProgrammingError

from pytest_adbc_replay._cassette_io import (
    cassette_has_interactions,
    interaction_file_paths,
    load_all_interactions,
    write_arrow_table,
    write_params_json,
    write_sql_file,
)
from pytest_adbc_replay._exceptions import CassetteMissError
from pytest_adbc_replay._normaliser import normalise_sql
from pytest_adbc_replay._params import build_registry, params_to_cache_key, serialise_params

if TYPE_CHECKING:
    from types import TracebackType

    from pytest_adbc_replay._connection import ReplayConnection


# ---------------------------------------------------------------------------
# Scrubbing helpers
# ---------------------------------------------------------------------------


def _apply_config_scrubbing(
    params_raw: Any,
    global_keys: list[str],
    per_driver_keys: dict[str, list[str]],
    driver_name: str | None,
) -> Any:
    """
    Apply config-based key scrubbing to serialised parameters.

    Replaces the value of each matched key with the fixed sentinel ``"REDACTED"``.
    Only dict params are affected; list/tuple/None params are returned unchanged.

    Args:
        params_raw: Serialised parameter structure from ``serialise_params()``.
        global_keys: Key names to redact for all drivers.
        per_driver_keys: Mapping of driver module name → keys to redact for that driver only.
        driver_name: ADBC driver module name (e.g. ``"adbc_driver_snowflake"``).

    Returns:
        Scrubbed parameters (new dict) or the original value unchanged if not a dict.
    """
    if not isinstance(params_raw, dict):
        return params_raw
    keys_to_redact = set(global_keys) | set(per_driver_keys.get(driver_name or "", []))
    if not keys_to_redact:
        return params_raw
    result = dict(params_raw)
    for key in keys_to_redact:
        if key in result:
            result[key] = "REDACTED"
    return result


def apply_scrubbing(
    params_raw: Any,
    global_keys: list[str],
    per_driver_keys: dict[str, list[str]],
    driver_name: str | None,
    scrubber: object,
) -> Any:
    """
    Apply the full scrubbing pipeline to serialised parameters.

    Pipeline order:
    1. Config-based scrubbing (``global_keys`` + ``per_driver_keys``).
    2. Fixture callable ``scrubber(params, driver_name)`` — receives already-config-scrubbed params.
       If the callable returns ``None``, the config-scrubbed params are used unchanged.
       If the callable returns a dict, that dict replaces the config-scrubbed params.

    Args:
        params_raw: Serialised parameter structure from ``serialise_params()``.
        global_keys: Key names to redact for all drivers.
        per_driver_keys: Mapping of driver module name → keys to redact for that driver only.
        driver_name: ADBC driver module name (e.g. ``"adbc_driver_snowflake"``).
        scrubber: Callable ``scrub(params, driver_name) -> dict | None`` or ``None``.

    Returns:
        Scrubbed parameters ready for ``write_params_json()``.
    """
    result = _apply_config_scrubbing(params_raw, global_keys, per_driver_keys, driver_name)
    if scrubber is not None and callable(scrubber):
        fixture_result: Any = scrubber(result, driver_name)  # type: ignore[call-arg]
        if fixture_result is not None:
            result = fixture_result
    return result


class ReplayCursor:
    """
    ADBC cursor proxy implementing the full ADBC cursor protocol.

    In replay mode (none): reads from cassette files written in a previous record run.
    In record modes: delegates to the real ADBC cursor and writes cassette files.
    In all modes: SQL is normalised via sqlglot for stable cassette keys.
    """

    def __init__(
        self,
        real_cursor: Any,  # adbc_driver_manager.dbapi.Cursor or None
        mode: str,
        cassette_path: Path,
        dialect: str | None = None,
        param_serialisers: dict[Any, dict[str, Any]] | None = None,
        scrub_keys_global: list[str] | None = None,
        scrub_keys_per_driver: dict[str, list[str]] | None = None,
        driver_name: str | None = None,
        scrubber: object = None,
        wipe_state: dict[str, bool] | None = None,
        connection: ReplayConnection | None = None,
    ) -> None:
        self._real_cursor = real_cursor
        self._connection = connection
        self._mode = mode
        self._cassette_path = cassette_path
        self._dialect = dialect
        self._registry = build_registry(param_serialisers)
        self._scrub_keys_global: list[str] = scrub_keys_global or []
        self._scrub_keys_per_driver: dict[str, list[str]] = scrub_keys_per_driver or {}
        self._driver_name = driver_name
        self._scrubber = scrubber
        # Pending result from execute(); replaced per call
        self._pending: pa.Table = pa.table({})
        # Cassette key of the most recent successful execute(); lets
        # adbc_execute_schema() recover the schema of a just-executed query whose
        # single recorded interaction was already consumed off the replay queue.
        self._last_executed_key: tuple[str, str] | None = None
        # Offset for DBAPI2 fetch methods
        self._fetch_offset: int = 0
        # DBAPI2 fetchmany() default batch size — read/write to match real
        # ADBC's writable Cursor.arraysize property.
        self._arraysize: int = 1
        # Per-result consumption state for the NEW strict fetch methods only
        # (fetch_record_batch/fetch_arrow/fetch_df/fetch_polars). Existing
        # permissive methods do not read these. Reset at the end of execute().
        self._executed: bool = False
        self._arrow_consumed: bool = False
        self._result_consumed: bool = False
        # Lazy init flag — cassette is scanned on first execute() call
        self._initialised: bool = False
        # Ordered-queue replay: key -> deque of pa.Table results (CASS-06)
        self._replay_queue: dict[tuple[str, str], deque[pa.Table]] = defaultdict(deque)
        # Next interaction index to write when recording
        self._record_index: int = 0
        # For 'all' mode: shared mutable container tracking whether cassette dir was wiped.
        # When shared across clones, only the first cursor to execute() triggers rmtree.
        self._wipe_state: dict[str, bool] = (
            wipe_state if wipe_state is not None else {"wiped": False}
        )

    def _ensure_initialised(self) -> None:
        """Lazy initialisation: populate replay queue from existing cassette on first execute()."""
        if self._initialised:
            return
        self._initialised = True
        # 'all' mode: wipe the cassette directory on first execute() (not at fixture init)
        if self._mode == "all" and not self._wipe_state["wiped"]:
            if self._cassette_path.exists():
                shutil.rmtree(self._cassette_path)
            self._wipe_state["wiped"] = True
            return  # Don't load from a directory we just deleted
        # Load existing cassette into replay queue (for none/once/new_episodes)
        interactions = load_all_interactions(self._cassette_path)
        for canonical_sql, table, params_raw in interactions:
            key = self._make_key_from_canonical(canonical_sql, params_raw)
            self._replay_queue[key].append(table)
        # Record index = next index to write after existing ones
        self._record_index = len(interactions)

    def _make_key(self, canonical_sql: str, params: Any) -> tuple[str, str]:
        """Make a hashable cassette key from canonical SQL and raw params."""
        return (canonical_sql, params_to_cache_key(params, self._registry))

    def _make_key_from_canonical(self, canonical_sql: str, params_raw: Any) -> tuple[str, str]:
        """Make cassette key from already-canonical SQL and already-serialised params."""
        return (canonical_sql, json.dumps(params_raw, sort_keys=True))

    def _record_interaction(
        self,
        canonical_sql: str,
        params: Any,
        table: pa.Table,
    ) -> None:
        """Write a new interaction to the cassette directory."""
        self._cassette_path.mkdir(parents=True, exist_ok=True)
        sql_path, arrow_path, params_path = interaction_file_paths(
            self._cassette_path, self._record_index
        )
        write_sql_file(canonical_sql, sql_path)
        write_arrow_table(table, arrow_path)
        params_raw = serialise_params(params, self._registry)
        params_raw = apply_scrubbing(
            params_raw,
            self._scrub_keys_global,
            self._scrub_keys_per_driver,
            self._driver_name,
            self._scrubber,
        )
        write_params_json(params_raw, params_path)
        self._record_index += 1

    def _raise_cassette_miss(self, raw_sql: str, canonical_sql: str) -> NoReturn:
        """
        Raise the appropriate CassetteMissError for a missing interaction.

        Three-way selection (shared by _load_from_queue and adbc_execute_schema):
        directory-missing / empty-directory / interaction-missing. Carries only
        raw/normalised SQL and the cassette path — never recorded row data or
        param values (T-03-01).
        """
        if not self._cassette_path.exists():
            raise CassetteMissError.directory_missing(
                raw_sql=raw_sql,
                normalised_sql=canonical_sql,
                cassette_path=self._cassette_path,
            )
        if not cassette_has_interactions(self._cassette_path):
            raise CassetteMissError(
                f"Cassette directory is empty — run with --adbc-record=once to record.\n"
                f"  Cassette path: {self._cassette_path}\n"
                f"  SQL: {raw_sql!r}"
            )
        raise CassetteMissError.interaction_missing(
            interaction_index=self._record_index,
            raw_sql=raw_sql,
            normalised_sql=canonical_sql,
            cassette_path=self._cassette_path,
        )

    def _load_from_queue(self, key: tuple[str, str], raw_sql: str, canonical_sql: str) -> pa.Table:
        """Pop the next result from the replay queue for this key, or raise CassetteMissError."""
        queue = self._replay_queue.get(key)
        if queue:
            result = queue.popleft()
            return result
        # Nothing in queue — determine appropriate error
        self._raise_cassette_miss(raw_sql, canonical_sql)

    def execute(self, operation: str, parameters: Any = None, **kwargs: Any) -> None:
        """
        Execute a query.

        Dispatches to record or replay logic based on mode. SQL is normalised
        via sqlglot before computing the cassette key. Lazy cassette init
        happens on first execute() call.
        """
        self._ensure_initialised()
        canonical = normalise_sql(operation, self._dialect)
        key = self._make_key(canonical, parameters)

        if self._mode == "none":
            self._pending = self._load_from_queue(key, operation, canonical)
            self._fetch_offset = 0

        elif self._mode == "once":
            if cassette_has_interactions(self._cassette_path):
                # Cassette exists with interactions — replay
                self._pending = self._load_from_queue(key, operation, canonical)
            else:
                # No cassette (or empty dir) — record using real cursor
                if self._real_cursor is None:
                    raise RuntimeError(
                        "ReplayCursor has no real cursor — cannot record in 'once' mode."
                    )
                self._real_cursor.execute(operation, parameters, **kwargs)
                table: pa.Table = self._real_cursor.fetch_arrow_table()
                self._record_interaction(canonical, parameters, table)
                self._pending = table
            self._fetch_offset = 0

        elif self._mode == "new_episodes":
            queue = self._replay_queue.get(key)
            if queue:
                # Existing interaction — replay
                self._pending = queue.popleft()
            else:
                # New interaction — record
                if self._real_cursor is None:
                    raise RuntimeError(
                        "ReplayCursor has no real cursor — cannot record in 'new_episodes' mode."
                    )
                self._real_cursor.execute(operation, parameters, **kwargs)
                new_table: pa.Table = self._real_cursor.fetch_arrow_table()
                self._record_interaction(canonical, parameters, new_table)
                self._pending = new_table
            self._fetch_offset = 0

        elif self._mode == "all":
            # 'all' mode: cassette dir was wiped in _ensure_initialised on first call
            if self._real_cursor is None:
                raise RuntimeError("ReplayCursor has no real cursor — cannot record in 'all' mode.")
            self._real_cursor.execute(operation, parameters, **kwargs)
            all_table: pa.Table = self._real_cursor.fetch_arrow_table()
            self._record_interaction(canonical, parameters, all_table)
            self._pending = all_table
            self._fetch_offset = 0

        # Reset per-result consumption state for the NEW strict fetch methods.
        # Placed at method-body level (un-indented) AFTER the whole mode
        # if/elif chain so it applies to all four modes (none/once/
        # new_episodes/all). All branches fall through here with no early
        # return, so a single trailing block resets consistently.
        self._executed = True
        self._last_executed_key = key
        self._arrow_consumed = False
        self._result_consumed = False

    def executemany(self, operation: str, seq_of_parameters: Any) -> None:
        """Execute a query with multiple parameter sets."""
        if self._real_cursor is not None:
            self._real_cursor.executemany(operation, seq_of_parameters)
        # In replay mode: no-op (not typically used for replay)

    def executescript(self, operation: str) -> None:
        """
        Execute a multi-statement script (DBAPI2 extension).

        Record mode: delegate to the real cursor (DDL side effects are baked into
        subsequently recorded SELECT results). Replay mode: silent no-op — the
        script's effects are already captured in the cassette and there is no live
        connection to run against. Writes nothing to the cassette (DBAPI-07).
        """
        if self._mode == "none":
            return  # replay: silent no-op
        if self._real_cursor is None:
            raise RuntimeError("ReplayCursor has no real cursor — cannot record executescript().")
        self._real_cursor.executescript(operation)

    # -----------------------------------------------------------------------
    # ADBC extension methods (ADBCX-01..04).
    #
    # Guiding principle: record mode delegates to the real cursor; replay mode
    # derives from the cassette where possible, no-ops where safe, or raises an
    # actionable NotSupportedError. All members mirror the executescript()
    # dispatch precedent (replay branch when _mode == "none", else delegate
    # with a RuntimeError guard when _real_cursor is None).
    # -----------------------------------------------------------------------

    def adbc_execute_schema(self, operation: str, parameters: Any = None) -> pa.Schema:
        """
        Return the result schema for a query without executing it (ADBCX-02).

        Replay: derive the schema from the matching recorded result table. PEEK
        the front of the replay queue first — this does NOT consume the queue or
        disturb _pending / _fetch_offset, so a schema-before-execute() call leaves
        the recorded rows intact for a later execute() (D-02 LOCKED). If the queue
        is empty because execute() already drained this query's single recorded
        interaction, fall back to the just-executed _pending result's schema, so
        the common execute()-then-adbc_execute_schema() ordering works the way it
        does in real ADBC (where adbc_execute_schema is independent of execute()).
        Raises CassetteMissError only when the query was never recorded. Record:
        delegate to the real cursor.
        """
        if self._mode == "none":
            self._ensure_initialised()
            canonical = normalise_sql(operation, self._dialect)
            key = self._make_key(canonical, parameters)
            queue = self._replay_queue.get(key)
            if queue:
                # Peek the front entry's schema — do NOT popleft (peek-don't-pop).
                return queue[0].schema
            if self._executed and key == self._last_executed_key:
                # This query was just executed; its single recording was already
                # popped off the queue but its schema is still in _pending.
                return self._pending.schema
            # No matching interaction — raise the same error _load_from_queue would.
            self._raise_cassette_miss(operation, canonical)
        if self._real_cursor is None:
            raise RuntimeError(
                "ReplayCursor has no real cursor — cannot record adbc_execute_schema()."
            )
        return self._real_cursor.adbc_execute_schema(operation, parameters)

    def adbc_cancel(self) -> None:
        """
        Cancel the in-progress operation (ADBCX-03).

        Replay: safe no-op returning None (nothing is running). Record: delegate
        to the real cursor's adbc_cancel.
        """
        if self._mode == "none":
            return  # replay: nothing is running
        if self._real_cursor is None:
            raise RuntimeError("ReplayCursor has no real cursor — cannot record adbc_cancel().")
        self._real_cursor.adbc_cancel()

    def adbc_prepare(self, operation: str) -> pa.Schema | None:
        """
        Prepare a query, returning its bind-parameter schema (ADBCX-03).

        Replay: pure no-op returning None — preparation is implicit and None is
        always a valid return (D-04 LOCKED; no schema derivation). Record:
        delegate to the real cursor's adbc_prepare and return its result.
        """
        if self._mode == "none":
            return None  # replay: preparation is implicit; None is always valid
        if self._real_cursor is None:
            raise RuntimeError("ReplayCursor has no real cursor — cannot record adbc_prepare().")
        return self._real_cursor.adbc_prepare(operation)

    def adbc_ingest(
        self,
        table_name: str,
        data: Any,
        mode: str = "create",
        *,
        catalog_name: str | None = None,
        db_schema_name: str | None = None,
        temporary: bool = False,
    ) -> int:
        """
        Ingest a table of Arrow data into the database (ADBCX-04).

        Replay: raises NotSupportedError — ingest writes data to a live database,
        which a cassette cannot reconstruct. Record: delegate to the real cursor
        and return the real row count.
        """
        if self._mode == "none":
            raise NotSupportedError(
                "adbc_ingest() is not supported in replay — it writes data to a live "
                "database, which a cassette cannot reconstruct."
            )
        if self._real_cursor is None:
            raise RuntimeError("ReplayCursor has no real cursor — cannot record adbc_ingest().")
        return self._real_cursor.adbc_ingest(
            table_name,
            data,
            mode,
            catalog_name=catalog_name,
            db_schema_name=db_schema_name,
            temporary=temporary,
        )

    def adbc_execute_partitions(
        self, operation: str, parameters: Any = None
    ) -> tuple[list[bytes], pa.Schema]:
        """
        Execute a query returning distributed result partitions (ADBCX-04).

        Replay: raises NotSupportedError — partitions stream live distributed
        results that a cassette cannot reconstruct. Record: delegate to the real
        cursor.
        """
        if self._mode == "none":
            raise NotSupportedError(
                "adbc_execute_partitions() is not supported in replay — partitions stream "
                "live distributed results that a cassette cannot reconstruct."
            )
        if self._real_cursor is None:
            raise RuntimeError(
                "ReplayCursor has no real cursor — cannot record adbc_execute_partitions()."
            )
        return self._real_cursor.adbc_execute_partitions(operation, parameters)

    def adbc_read_partition(self, partition: bytes) -> None:
        """
        Read a single distributed result partition (ADBCX-04).

        Replay: raises NotSupportedError — there is no live partition stream to
        read; a cassette cannot reconstruct it. Record: delegate to the real
        cursor.
        """
        if self._mode == "none":
            raise NotSupportedError(
                "adbc_read_partition() is not supported in replay — there is no live "
                "partition stream to read; a cassette cannot reconstruct it."
            )
        if self._real_cursor is None:
            raise RuntimeError(
                "ReplayCursor has no real cursor — cannot record adbc_read_partition()."
            )
        self._real_cursor.adbc_read_partition(partition)

    def nextset(self) -> None:
        """Move to the next result set — not supported (DBAPI2, DBAPI-02)."""
        raise NotSupportedError("Cursor.nextset")

    def callproc(self, procname: str, parameters: Any) -> None:
        """Call a stored procedure — not supported (DBAPI2, DBAPI-06)."""
        raise NotSupportedError("Cursor.callproc")

    def setinputsizes(self, sizes: Any) -> None:
        """Preallocate parameter memory — no-op in replay, delegates in record (DBAPI-05)."""
        if self._real_cursor is not None:
            self._real_cursor.setinputsizes(sizes)

    def setoutputsize(self, size: Any, column: Any = None) -> None:
        """Preallocate result memory — no-op in replay, delegates in record (DBAPI-05)."""
        if self._real_cursor is not None:
            self._real_cursor.setoutputsize(size, column)

    def fetch_arrow_table(self) -> pa.Table:
        """Fetch all rows of the result as a PyArrow Table."""
        self._require_executed("fetch_arrow_table")
        return self._pending

    # -----------------------------------------------------------------------
    # Arrow & DataFrame fetch methods (FETCH-01..05) + legacy DBAPI fetches.
    #
    # Strict-vs-lenient reconciliation (Phase 4 / PARITY-01, D-02):
    #
    # Dimension 1 (pre-execute) — FIXED. ALL fetch methods now share one
    # uniform pre-execute contract via _require_executed(): calling any of
    # fetch_arrow_table/fetchall/fetchone/fetchmany (and fetchallarrow, which
    # inherits the guard through its fetch_arrow_table() delegation), plus the
    # strict fetch_record_batch/fetch_arrow/fetch_df/fetch_polars methods,
    # before execute() raises ProgrammingError, matching real ADBC.
    #
    # Dimension 2 (re-consumption) — intentionally left LENIENT. The
    # materialized _pending table makes the legacy fetches re-readable, unlike
    # real ADBC's consume-once stream. Faithful single-stream simulation is
    # awkward under this model, so it is documented as a known deviation in
    # DOC-01 (docs/src/reference/cursor-surface.md) rather than enforced here.
    # -----------------------------------------------------------------------

    def _require_executed(self, method_name: str) -> None:
        """Raise ADBC's ProgrammingError if called before execute() (D4)."""
        if not self._executed:
            raise ProgrammingError(
                f"Cannot {method_name}() before execute()",
                status_code=AdbcStatusCode.INVALID_STATE,
            )

    def fetch_record_batch(self) -> pa.RecordBatchReader:
        """Fetch the recorded result as a pyarrow.RecordBatchReader (FETCH-01)."""
        self._require_executed("fetch_record_batch")
        self._result_consumed = True
        return self._pending.to_reader()

    def fetch_arrow(self) -> object:
        """
        Fetch the recorded result as a raw __arrow_c_stream__ PyCapsule (FETCH-02 / D5).

        Reproduces ADBC's single-consumption contract: can only be called once,
        and must be called before any other method that consumes data (D4).
        """
        self._require_executed("fetch_arrow")
        if self._arrow_consumed:
            raise ProgrammingError(
                "fetch_arrow() can only be called once",
                status_code=AdbcStatusCode.INVALID_STATE,
            )
        if self._result_consumed:
            raise ProgrammingError(
                "fetch_arrow() must be called before any other method that consumes data",
                status_code=AdbcStatusCode.INVALID_STATE,
            )
        self._arrow_consumed = True
        self._result_consumed = True
        return self._pending.__arrow_c_stream__()

    def fetchallarrow(self) -> pa.Table:
        """Silent alias of fetch_arrow_table() (FETCH-03 / D3) — no warning, lenient."""
        return self.fetch_arrow_table()

    def fetch_df(self) -> object:
        """
        Fetch the recorded result as a pandas.DataFrame (FETCH-04).

        Lazily imports pandas inside the method (no module-level import, no
        packaging extra). Raises an actionable error naming pandas if absent.
        """
        self._require_executed("fetch_df")
        try:
            import pandas  # noqa: PLC0415  (lazy import by design)
        except ImportError as exc:
            raise ModuleNotFoundError(
                "fetch_df() requires pandas, which is not installed. "
                "Install it with: pip install pandas"
            ) from exc
        self._result_consumed = True
        # Convert via the imported pandas module so the import is genuinely used
        # (pa.Table.to_pandas() yields a pandas.DataFrame once pandas is present).
        return pandas.DataFrame(self._pending.to_pandas())

    def fetch_polars(self) -> object:
        """
        Fetch the recorded result as a polars.DataFrame (FETCH-05).

        Lazily imports polars inside the method (no module-level import, no
        packaging extra). Raises an actionable error naming polars if absent.
        """
        self._require_executed("fetch_polars")
        try:
            import polars  # noqa: PLC0415  (lazy import by design)
        except ImportError as exc:
            raise ModuleNotFoundError(
                "fetch_polars() requires polars, which is not installed. "
                "Install it with: pip install polars"
            ) from exc
        self._result_consumed = True
        return polars.from_arrow(self._pending)

    def fetchall(self) -> list[tuple[object, ...]]:
        """Fetch all rows of the result as a list of tuples (DBAPI2)."""
        self._require_executed("fetchall")
        if self._pending.num_rows == 0:
            return []
        rows = self._pending.to_pydict()
        columns = list(rows.keys())
        return [tuple(rows[col][i] for col in columns) for i in range(self._pending.num_rows)]

    def fetchone(self) -> tuple[object, ...] | None:
        """Fetch the next row from the result (DBAPI2)."""
        self._require_executed("fetchone")
        if self._fetch_offset >= self._pending.num_rows:
            return None
        row_table = self._pending.slice(self._fetch_offset, 1)
        self._fetch_offset += 1
        row_dict = row_table.to_pydict()
        columns = list(row_dict.keys())
        return tuple(row_dict[col][0] for col in columns)

    def fetchmany(self, size: int | None = None) -> list[tuple[object, ...]]:
        """Fetch up to `size` rows from the result (DBAPI2)."""
        self._require_executed("fetchmany")
        if size is None:
            size = self.arraysize
        remaining = self._pending.num_rows - self._fetch_offset
        batch_size = min(size, remaining)
        if batch_size <= 0:
            return []
        batch = self._pending.slice(self._fetch_offset, batch_size)
        self._fetch_offset += batch_size
        batch_dict = batch.to_pydict()
        columns = list(batch_dict.keys())
        return [tuple(batch_dict[col][i] for col in columns) for i in range(batch_size)]

    def next(self) -> tuple[object, ...]:
        """Fetch the next row, or raise StopIteration (DBAPI2 extension)."""
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row

    def __next__(self) -> tuple[object, ...]:
        return self.next()

    def __iter__(self) -> ReplayCursor:
        return self

    @property
    def description(self) -> list[tuple[object, ...]] | None:
        """DBAPI2 description: sequence of 7-item sequences describing result columns."""
        if self._pending.num_rows == 0 and self._pending.num_columns == 0:
            return None
        schema = self._pending.schema
        return [(field.name, None, None, None, None, None, None) for field in schema]

    @property
    def rowcount(self) -> int:
        """Number of rows in the result, or -1 if unknown."""
        return self._pending.num_rows

    @property
    def arraysize(self) -> int:
        """Number of rows to fetch at a time with fetchmany() (DBAPI2)."""
        return self._arraysize

    @arraysize.setter
    def arraysize(self, value: int) -> None:
        """Set the default fetchmany() batch size (read/write, matches real ADBC)."""
        self._arraysize = value

    @property
    def rownumber(self) -> int | None:
        """
        Index of the next row to fetch, or None before execute() (DBAPI2).

        ADBC-accurate semantics: None only before execute(); 0 immediately after
        execute() (before any fetch); N after N rows consumed. This INTENTIONALLY
        diverges from the literal REQUIREMENTS/ROADMAP wording "None before the
        first fetch" — real ADBC returns 0 (not None) post-execute pre-fetch.
        """
        return None if not self._executed else self._fetch_offset

    @property
    def connection(self) -> ReplayConnection | None:
        """The ReplayConnection that created this cursor (DBAPI2 extension)."""
        return self._connection

    @property
    def adbc_statement(self) -> Any:  # real type: adbc_driver_manager.AdbcStatement
        """
        The underlying ADBC statement (ADBCX-04).

        Replay: raises NotSupportedError — there is no live statement to expose.
        This intentional raise is NOT a bare AttributeError, so it satisfies the
        Phase 4 PARITY-01 introspection test (D-06). Record: return the real
        cursor's adbc_statement.
        """
        if self._mode == "none":
            raise NotSupportedError(
                "adbc_statement is not available in replay — there is no live statement to expose."
            )
        if self._real_cursor is None:
            raise RuntimeError("ReplayCursor has no real cursor — cannot access adbc_statement.")
        return self._real_cursor.adbc_statement

    def close(self) -> None:
        """Close the cursor and free resources."""
        if self._real_cursor is not None:
            self._real_cursor.close()
        self._pending = pa.table({})

    def __enter__(self) -> ReplayCursor:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()


__all__ = ["ReplayCursor"]
