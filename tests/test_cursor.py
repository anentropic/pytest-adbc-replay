"""Tests for ReplayCursor protocol compliance and ReplayConnection."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pytest

from pytest_adbc_replay._cassette_io import (
    interaction_file_paths,
    write_arrow_table,
    write_params_json,
    write_sql_file,
)
from pytest_adbc_replay._connection import ReplayConnection
from pytest_adbc_replay._cursor import ReplayCursor
from pytest_adbc_replay._exceptions import CassetteMissError
from pytest_adbc_replay._normaliser import normalise_sql


def _populate_cassette(cassette: Path, sql: str, table: pa.Table) -> None:
    """Pre-populate a cassette directory with one interaction."""
    cassette.mkdir(parents=True, exist_ok=True)
    canonical = normalise_sql(sql)
    sql_path, arrow_path, params_path = interaction_file_paths(cassette, 0)
    write_sql_file(canonical, sql_path)
    write_arrow_table(table, arrow_path)
    write_params_json(None, params_path)


class TestReplayCursorProtocol:
    """ReplayCursor must implement the full ADBC cursor protocol (PROXY-05)."""

    def _make_cursor(self, tmp_path: Path) -> ReplayCursor:
        """Create a cursor with a pre-populated cassette for testing protocol methods."""
        cassette = tmp_path / "test"
        table = pa.table({"id": [1], "name": ["test"]})
        _populate_cassette(cassette, "SELECT 1", table)
        return ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)

    def test_execute_does_not_raise(self, tmp_path: Path) -> None:
        """execute() in replay mode does not raise AttributeError."""
        cursor = self._make_cursor(tmp_path)
        cursor.execute("SELECT 1")  # must not raise

    def test_fetch_arrow_table_returns_table(self, tmp_path: Path) -> None:
        """fetch_arrow_table() returns a pyarrow.Table."""
        cursor = self._make_cursor(tmp_path)
        cursor.execute("SELECT 1")
        result = cursor.fetch_arrow_table()
        assert isinstance(result, pa.Table)

    def test_fetchall_returns_list(self, tmp_path: Path) -> None:
        """fetchall() returns a list (of tuples)."""
        cursor = self._make_cursor(tmp_path)
        cursor.execute("SELECT 1")
        result = cursor.fetchall()
        assert isinstance(result, list)

    def test_fetchone_returns_tuple_or_none(self, tmp_path: Path) -> None:
        """fetchone() returns a tuple or None."""
        cursor = self._make_cursor(tmp_path)
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result is None or isinstance(result, tuple)

    def test_fetchmany_returns_list(self, tmp_path: Path) -> None:
        """fetchmany() returns a list (of tuples)."""
        cursor = self._make_cursor(tmp_path)
        cursor.execute("SELECT 1")
        result = cursor.fetchmany(5)
        assert isinstance(result, list)

    def test_description_property_exists(self, tmp_path: Path) -> None:
        """Description property is accessible without AttributeError."""
        cursor = self._make_cursor(tmp_path)
        cursor.execute("SELECT 1")
        _ = cursor.description  # must not raise AttributeError

    def test_rowcount_property_is_int(self, tmp_path: Path) -> None:
        """Rowcount property returns an int."""
        cursor = self._make_cursor(tmp_path)
        cursor.execute("SELECT 1")
        assert isinstance(cursor.rowcount, int)

    def test_close_does_not_raise(self, tmp_path: Path) -> None:
        """close() does not raise."""
        cursor = self._make_cursor(tmp_path)
        cursor.execute("SELECT 1")
        cursor.close()  # must not raise

    def test_context_manager_protocol(self, tmp_path: Path) -> None:
        """Cursor works as context manager (__enter__ and __exit__)."""
        cassette = tmp_path / "test"
        table = pa.table({"id": [1]})
        _populate_cassette(cassette, "SELECT 1", table)
        with ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette) as cursor:
            cursor.execute("SELECT 1")
            _ = cursor.fetchall()
        # After __exit__, cursor is closed — verify no error raised

    def test_all_methods_exist_without_attribute_error(self, tmp_path: Path) -> None:
        """PROXY-05: all required methods exist (no AttributeError for any)."""
        cassette = tmp_path / "test"
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
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

    def test_replay_mode_no_driver_import(self, tmp_path: Path) -> None:
        """PROXY-02: mode='none' never imports the driver module."""
        cassette = tmp_path / "test"
        # 'adbc_driver_completely_nonexistent' does not exist.
        # If it were imported, ModuleNotFoundError would be raised here.
        conn = ReplayConnection(
            driver_module_name="adbc_driver_completely_nonexistent",
            db_kwargs={},
            mode="none",
            cassette_path=cassette,
        )
        # Must not raise ModuleNotFoundError
        cursor = conn.cursor()
        assert isinstance(cursor, ReplayCursor)
        conn.close()

    def test_cursor_returns_replay_cursor(self, tmp_path: Path) -> None:
        """PROXY-01: ReplayConnection.cursor() returns ReplayCursor."""
        cassette = tmp_path / "test"
        conn = ReplayConnection(
            driver_module_name="adbc_driver_completely_nonexistent",
            db_kwargs={},
            mode="none",
            cassette_path=cassette,
        )
        cursor = conn.cursor()
        assert isinstance(cursor, ReplayCursor)
        conn.close()

    def test_connection_context_manager(self, tmp_path: Path) -> None:
        """ReplayConnection works as context manager."""
        cassette = tmp_path / "test"
        table = pa.table({"id": [1]})
        _populate_cassette(cassette, "SELECT 1", table)
        with ReplayConnection(
            driver_module_name="adbc_driver_completely_nonexistent",
            db_kwargs={},
            mode="none",
            cassette_path=cassette,
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

    def test_raised_on_missing_cassette(self, tmp_path: Path) -> None:
        """PROXY-06: CassetteMissError raised on missing cassette in none mode."""
        cassette = tmp_path / "nonexistent"
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        with pytest.raises(CassetteMissError):
            cursor.execute("SELECT 1")
