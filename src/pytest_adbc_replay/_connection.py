"""ReplayConnection: ADBC connection proxy for record/replay testing."""

from __future__ import annotations

import importlib
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Any

from pytest_adbc_replay._cursor import ReplayCursor

if TYPE_CHECKING:
    from types import TracebackType


class ReplayConnection:
    """
    ADBC connection proxy.

    In replay mode (none): never imports or opens a real ADBC driver.
    In record modes: imports the driver module and opens a real connection.

    PROXY-02 compliance: the import_module call is inside an `if mode != "none"` guard.
    No driver import occurs at class definition time or in __init__ for replay mode.
    """

    def __init__(
        self,
        driver_module_name: str,
        db_kwargs: dict[str, object],
        mode: str,
        cassette_path: Path,
        dialect: str | None = None,
        param_serialisers: dict[Any, dict[str, Any]] | None = None,
        connect_fn: Any = None,
    ) -> None:
        self._driver_module_name = driver_module_name
        self._db_kwargs = db_kwargs
        self._mode = mode
        self._cassette_path = cassette_path
        self._dialect = dialect
        self._param_serialisers = param_serialisers
        self._real_conn: Any = None  # adbc_driver_manager.dbapi.Connection or None

        if mode != "none":
            # Only in record modes: import the driver and open a real connection.
            # This will fail loudly if the driver is not installed — expected.
            if connect_fn is not None:
                # Use the provided callable (bypasses any monkeypatching of driver.connect)
                self._real_conn = connect_fn(**db_kwargs)
            else:
                driver = importlib.import_module(driver_module_name)
                # ADBC drivers expose connect(**db_kwargs)
                self._real_conn = driver.connect(**db_kwargs)

    def cursor(self) -> ReplayCursor:
        """
        Return a ReplayCursor for this connection.

        In replay mode: returns a cursor with no backing real cursor.
        In record mode: wraps the real cursor.
        """
        real_cursor = self._real_conn.cursor() if self._real_conn is not None else None
        return ReplayCursor(
            real_cursor=real_cursor,
            mode=self._mode,
            cassette_path=self._cassette_path,
            dialect=self._dialect,
            param_serialisers=self._param_serialisers,
        )

    def close(self) -> None:
        """Close the connection."""
        if self._real_conn is not None:
            self._real_conn.close()

    def commit(self) -> None:
        """Commit the current transaction (DBAPI2 compat)."""
        if self._real_conn is not None:
            self._real_conn.commit()

    def rollback(self) -> None:
        """Roll back the current transaction (DBAPI2 compat)."""
        if self._real_conn is not None:
            self._real_conn.rollback()

    def __enter__(self) -> ReplayConnection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
