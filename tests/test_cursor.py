"""Tests for ReplayCursor protocol compliance and ReplayConnection."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa

from pytest_adbc_replay._connection import ReplayConnection
from pytest_adbc_replay._cursor import ReplayCursor
from pytest_adbc_replay._exceptions import CassetteMissError

_CASSETTE = Path("tests/cassettes/test")


class TestReplayCursorProtocol:
    """ReplayCursor must implement the full ADBC cursor protocol (PROXY-05)."""

    def _make_cursor(self) -> ReplayCursor:
        return ReplayCursor(real_cursor=None, mode="none", cassette_path=_CASSETTE)

    def test_execute_does_not_raise(self) -> None:
        """execute() in replay mode does not raise AttributeError."""
        cursor = self._make_cursor()
        cursor.execute("SELECT 1")  # must not raise

    def test_fetch_arrow_table_returns_table(self) -> None:
        """fetch_arrow_table() returns a pyarrow.Table."""
        cursor = self._make_cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetch_arrow_table()
        assert isinstance(result, pa.Table)

    def test_fetchall_returns_list(self) -> None:
        """fetchall() returns a list (of tuples)."""
        cursor = self._make_cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchall()
        assert isinstance(result, list)

    def test_fetchone_returns_tuple_or_none(self) -> None:
        """fetchone() returns a tuple or None."""
        cursor = self._make_cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result is None or isinstance(result, tuple)

    def test_fetchmany_returns_list(self) -> None:
        """fetchmany() returns a list (of tuples)."""
        cursor = self._make_cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchmany(5)
        assert isinstance(result, list)

    def test_description_property_exists(self) -> None:
        """Description property is accessible without AttributeError."""
        cursor = self._make_cursor()
        cursor.execute("SELECT 1")
        _ = cursor.description  # must not raise AttributeError

    def test_rowcount_property_is_int(self) -> None:
        """Rowcount property returns an int."""
        cursor = self._make_cursor()
        cursor.execute("SELECT 1")
        assert isinstance(cursor.rowcount, int)

    def test_close_does_not_raise(self) -> None:
        """close() does not raise."""
        cursor = self._make_cursor()
        cursor.execute("SELECT 1")
        cursor.close()  # must not raise

    def test_context_manager_protocol(self) -> None:
        """Cursor works as context manager (__enter__ and __exit__)."""
        with ReplayCursor(real_cursor=None, mode="none", cassette_path=_CASSETTE) as cursor:
            cursor.execute("SELECT 1")
            _ = cursor.fetchall()
        # After __exit__, cursor is closed — verify no error raised

    def test_all_methods_exist_without_attribute_error(self) -> None:
        """PROXY-05: all required methods exist (no AttributeError for any)."""
        cursor = self._make_cursor()
        required_methods = [
            "execute",
            "fetch_arrow_table",
            "fetchall",
            "fetchone",
            "fetchmany",
            "close",
            "__enter__",
            "__exit__",
        ]
        required_properties = ["description", "rowcount"]
        for method_name in required_methods:
            assert hasattr(cursor, method_name), (
                f"ReplayCursor missing required method: {method_name}"
            )
        for prop_name in required_properties:
            assert hasattr(cursor, prop_name), (
                f"ReplayCursor missing required property: {prop_name}"
            )


class TestReplayConnectionDriverGuard:
    """ReplayConnection must not import ADBC driver in replay mode (PROXY-02)."""

    def test_replay_mode_no_driver_import(self) -> None:
        """PROXY-02: mode='none' never imports the driver module."""
        # 'adbc_driver_completely_nonexistent' does not exist.
        # If it were imported, ModuleNotFoundError would be raised here.
        conn = ReplayConnection(
            driver_module_name="adbc_driver_completely_nonexistent",
            db_kwargs={},
            mode="none",
            cassette_path=_CASSETTE,
        )
        # Must not raise ModuleNotFoundError
        cursor = conn.cursor()
        assert isinstance(cursor, ReplayCursor)
        conn.close()

    def test_cursor_returns_replay_cursor(self) -> None:
        """PROXY-01: ReplayConnection.cursor() returns ReplayCursor."""
        conn = ReplayConnection(
            driver_module_name="adbc_driver_completely_nonexistent",
            db_kwargs={},
            mode="none",
            cassette_path=_CASSETTE,
        )
        cursor = conn.cursor()
        assert isinstance(cursor, ReplayCursor)
        conn.close()

    def test_connection_context_manager(self) -> None:
        """ReplayConnection works as context manager."""
        with ReplayConnection(
            driver_module_name="adbc_driver_completely_nonexistent",
            db_kwargs={},
            mode="none",
            cassette_path=_CASSETTE,
        ) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")


class TestCassetteMissError:
    """CassetteMissError must be raised (not KeyError or FileNotFoundError) on miss (PROXY-06)."""

    def test_is_exception_subclass(self) -> None:
        """CassetteMissError is a Python Exception."""
        assert issubclass(CassetteMissError, Exception)

    def test_directory_missing_message(self) -> None:
        """directory_missing() creates error with cassette path in message."""
        err = CassetteMissError.directory_missing(
            raw_sql="SELECT * FROM foo",
            normalised_sql="SELECT * FROM foo",
            cassette_path=Path("tests/cassettes/my_test"),
        )
        assert isinstance(err, CassetteMissError)
        assert "tests/cassettes/my_test" in str(err)
        assert "record first" in str(err).lower() or "does not exist" in str(err).lower()

    def test_interaction_missing_message(self) -> None:
        """interaction_missing() creates error with interaction index in message."""
        err = CassetteMissError.interaction_missing(
            interaction_index=2,
            raw_sql="SELECT id FROM users",
            normalised_sql="SELECT id FROM users",
            cassette_path=Path("tests/cassettes/my_test"),
        )
        assert isinstance(err, CassetteMissError)
        assert "2" in str(err)  # interaction index visible
        assert "tests/cassettes/my_test" in str(err)

    def test_not_key_error(self) -> None:
        """CassetteMissError is not a KeyError."""
        assert not issubclass(CassetteMissError, KeyError)

    def test_not_file_not_found_error(self) -> None:
        """CassetteMissError is not a FileNotFoundError."""
        assert not issubclass(CassetteMissError, FileNotFoundError)

    def test_raw_and_normalised_sql_in_message(self) -> None:
        """Both raw and normalised SQL appear in the error message."""
        raw = "select  *  from users"
        normalised = "SELECT * FROM users"
        err = CassetteMissError.directory_missing(
            raw_sql=raw,
            normalised_sql=normalised,
            cassette_path=Path("cassettes/test"),
        )
        assert raw in str(err)
        assert normalised in str(err)
