"""ReplayCursor: ADBC cursor proxy for record/replay testing."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict, deque
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Any

import pyarrow as pa

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
    ) -> None:
        self._real_cursor = real_cursor
        self._mode = mode
        self._cassette_path = cassette_path
        self._dialect = dialect
        self._registry = build_registry(param_serialisers)
        # Pending result from execute(); replaced per call
        self._pending: pa.Table = pa.table({})
        # Offset for DBAPI2 fetch methods
        self._fetch_offset: int = 0
        # Lazy init flag — cassette is scanned on first execute() call
        self._initialised: bool = False
        # Ordered-queue replay: key -> deque of pa.Table results (CASS-06)
        self._replay_queue: dict[tuple[str, str], deque[pa.Table]] = defaultdict(deque)
        # Next interaction index to write when recording
        self._record_index: int = 0
        # For 'all' mode: tracks whether we've wiped the cassette dir yet
        self._wiped: bool = False

    def _ensure_initialised(self) -> None:
        """Lazy initialisation: populate replay queue from existing cassette on first execute()."""
        if self._initialised:
            return
        self._initialised = True
        # 'all' mode: wipe the cassette directory on first execute() (not at fixture init)
        if self._mode == "all" and not self._wiped:
            if self._cassette_path.exists():
                shutil.rmtree(self._cassette_path)
            self._wiped = True
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
        write_params_json(params_raw, params_path)
        self._record_index += 1

    def _load_from_queue(self, key: tuple[str, str], raw_sql: str, canonical_sql: str) -> pa.Table:
        """Pop the next result from the replay queue for this key, or raise CassetteMissError."""
        queue = self._replay_queue.get(key)
        if queue:
            result = queue.popleft()
            return result
        # Nothing in queue — determine appropriate error
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

    def executemany(self, operation: str, seq_of_parameters: Any) -> None:
        """Execute a query with multiple parameter sets."""
        if self._real_cursor is not None:
            self._real_cursor.executemany(operation, seq_of_parameters)
        # In replay mode: no-op (not typically used for replay)

    def fetch_arrow_table(self) -> pa.Table:
        """Fetch all rows of the result as a PyArrow Table."""
        return self._pending

    def fetchall(self) -> list[tuple[object, ...]]:
        """Fetch all rows of the result as a list of tuples (DBAPI2)."""
        if self._pending.num_rows == 0:
            return []
        rows = self._pending.to_pydict()
        columns = list(rows.keys())
        return [tuple(rows[col][i] for col in columns) for i in range(self._pending.num_rows)]

    def fetchone(self) -> tuple[object, ...] | None:
        """Fetch the next row from the result (DBAPI2)."""
        if self._fetch_offset >= self._pending.num_rows:
            return None
        row_table = self._pending.slice(self._fetch_offset, 1)
        self._fetch_offset += 1
        row_dict = row_table.to_pydict()
        columns = list(row_dict.keys())
        return tuple(row_dict[col][0] for col in columns)

    def fetchmany(self, size: int | None = None) -> list[tuple[object, ...]]:
        """Fetch up to `size` rows from the result (DBAPI2)."""
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
        return 1

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
