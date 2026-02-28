"""ReplayCursor: ADBC cursor proxy for record/replay testing."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Any

import pyarrow as pa

from pytest_adbc_replay._exceptions import CassetteMissError

if TYPE_CHECKING:
    from types import TracebackType


class ReplayCursor:
    """
    ADBC cursor proxy implementing the full ADBC cursor protocol.

    In replay mode (none): reads from cassette storage (Phase 2).
    In Phase 1: execute() in replay mode stores the SQL and sets _pending to
    an empty Arrow table, allowing the full protocol to be exercised in tests.
    In record modes: delegates to the real ADBC cursor (_real_cursor).

    Phase 2 will replace the placeholder cassette load/store logic with
    real Arrow IPC file reads/writes.
    """

    def __init__(
        self,
        real_cursor: Any,  # adbc_driver_manager.dbapi.Cursor or None
        mode: str,
        cassette_path: Path,
        dialect: str | None = None,
    ) -> None:
        self._real_cursor = real_cursor
        self._mode = mode
        self._cassette_path = cassette_path
        self._dialect = dialect
        # Pending result from execute(); replaced per call
        self._pending: pa.Table = pa.table({})
        # Offset for DBAPI2 fetch methods
        self._fetch_offset: int = 0

    def execute(self, operation: str, parameters: Any = None, **kwargs: Any) -> None:
        """
        Execute a query.

        In replay mode: loads from cassette (Phase 2 placeholder: stores empty table).
        In record mode: delegates to real cursor and records result.
        """
        if self._mode == "none":
            # Phase 1 placeholder: in Phase 2 this will load from cassette files.
            # For now, set _pending to empty table so fetch methods work without error.
            # CassetteMissError would be raised here if the cassette is missing (Phase 2).
            self._pending = pa.table({})
            self._fetch_offset = 0
        else:
            # Record mode: delegate to real cursor
            if self._real_cursor is None:
                raise RuntimeError(
                    "ReplayCursor has no real cursor — cannot execute in record mode."
                )
            self._real_cursor.execute(operation, parameters, **kwargs)
            # Phase 2: record result to cassette here
            self._pending = self._real_cursor.fetch_arrow_table()
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


# Reference CassetteMissError to satisfy import — will be used in Phase 2
__all__ = ["ReplayCursor", "CassetteMissError"]
