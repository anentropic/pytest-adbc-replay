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
        scrub_keys_global: list[str] | None = None,
        scrub_keys_per_driver: dict[str, list[str]] | None = None,
        scrubber: object = None,
    ) -> None:
        self._driver_module_name = driver_module_name
        self._db_kwargs = db_kwargs
        self._mode = mode
        self._cassette_path = cassette_path
        self._dialect = dialect
        self._param_serialisers = param_serialisers
        self._scrub_keys_global: list[str] = scrub_keys_global or []
        self._scrub_keys_per_driver: dict[str, list[str]] = scrub_keys_per_driver or {}
        self._scrubber = scrubber
        self._real_conn: Any = None  # adbc_driver_manager.dbapi.Connection or None

        # CLONE-SYNC: update adbc_clone() when adding attributes
        self._wipe_state: dict[str, bool] = {"wiped": False}

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

    def adbc_clone(self) -> ReplayConnection:
        """
        Create a cloned connection sharing the same cassette and config.

        Mirrors the ADBC spec: clones share the underlying database handle.
        In record mode, delegates to the real connection's adbc_clone().
        In replay mode, creates a new ReplayConnection with no real connection.

        All clones share the same cassette path and wipe state.
        Clone-of-clone is supported.
        """
        real_clone = self._real_conn.adbc_clone() if self._real_conn is not None else None
        clone = ReplayConnection.__new__(ReplayConnection)
        clone._driver_module_name = self._driver_module_name
        clone._db_kwargs = self._db_kwargs
        clone._mode = self._mode
        clone._cassette_path = self._cassette_path
        clone._dialect = self._dialect
        clone._param_serialisers = self._param_serialisers
        clone._scrub_keys_global = self._scrub_keys_global
        clone._scrub_keys_per_driver = self._scrub_keys_per_driver
        clone._scrubber = self._scrubber
        clone._real_conn = real_clone
        clone._wipe_state = self._wipe_state
        return clone

    def cursor(self) -> ReplayCursor:
        """
        Return a ReplayCursor for this connection.

        In replay mode: returns a cursor with no backing real cursor.
        In record mode: wraps the real cursor.
        """
        real_cursor = self._real_conn.cursor() if self._real_conn is not None else None
        return ReplayCursor(
            real_cursor=real_cursor,
            connection=self,
            mode=self._mode,
            cassette_path=self._cassette_path,
            dialect=self._dialect,
            param_serialisers=self._param_serialisers,
            scrub_keys_global=self._scrub_keys_global,
            scrub_keys_per_driver=self._scrub_keys_per_driver,
            driver_name=self._driver_module_name,
            scrubber=self._scrubber,
            wipe_state=self._wipe_state,
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
