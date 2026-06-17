"""Tests for the remaining DBAPI2 cursor surface on ReplayCursor (DBAPI-01..07)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pyarrow as pa
import pytest
from adbc_driver_manager.dbapi import NotSupportedError

from pytest_adbc_replay._cassette_io import (
    interaction_file_paths,
    write_arrow_table,
    write_params_json,
    write_sql_file,
)
from pytest_adbc_replay._connection import ReplayConnection
from pytest_adbc_replay._cursor import ReplayCursor
from pytest_adbc_replay._normaliser import normalise_sql

if TYPE_CHECKING:
    from pathlib import Path


def _populate_cassette(cassette: Path, sql: str, table: pa.Table) -> None:
    """Pre-populate a cassette directory with one interaction."""
    cassette.mkdir(parents=True, exist_ok=True)
    canonical = normalise_sql(sql)
    sql_path, arrow_path, params_path = interaction_file_paths(cassette, 0)
    write_sql_file(canonical, sql_path)
    write_arrow_table(table, arrow_path)
    write_params_json(None, params_path)


def _executed_cursor(tmp_path: Path, table: pa.Table, sql: str = "SELECT 1") -> ReplayCursor:
    """Build a cursor with a populated cassette and call execute() to load _pending."""
    cassette = tmp_path / "test"
    _populate_cassette(cassette, sql, table)
    cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
    cursor.execute(sql)
    return cursor


def _unexecuted_cursor(tmp_path: Path, table: pa.Table, sql: str = "SELECT 1") -> ReplayCursor:
    """Build a populated cursor that has NOT been executed yet."""
    cassette = tmp_path / "test"
    _populate_cassette(cassette, sql, table)
    return ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)


# ---------------------------------------------------------------------------
# DBAPI-01: iteration (next / __next__ / __iter__)
# ---------------------------------------------------------------------------


class TestIteration:
    def test_list_yields_rows_in_order(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1, 2, 3]})
        cursor = _executed_cursor(tmp_path, table)
        assert list(cursor) == [(1,), (2,), (3,)]

    def test_iter_returns_self(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1]})
        cursor = _executed_cursor(tmp_path, table)
        assert iter(cursor) is cursor

    def test_next_returns_rows_then_stops(self, tmp_path: Path) -> None:
        table = pa.table({"id": [10, 20]})
        cursor = _executed_cursor(tmp_path, table)
        assert next(cursor) == (10,)
        assert next(cursor) == (20,)
        with pytest.raises(StopIteration):
            next(cursor)

    def test_cursor_next_method_on_exhausted_raises(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1]})
        cursor = _executed_cursor(tmp_path, table)
        assert cursor.next() == (1,)
        with pytest.raises(StopIteration):
            cursor.next()


# ---------------------------------------------------------------------------
# DBAPI-03: rownumber
#
# ADBC-ACCURATE / INTENTIONAL DIVERGENCE from the literal REQUIREMENTS/ROADMAP
# wording "None before the first fetch". Real ADBC returns None ONLY before
# execute(), and 0 (not None) after execute() but before any fetch. These tests
# assert the ADBC behavior; the verifier must check ADBC semantics, not the
# literal "before first fetch" wording.
# ---------------------------------------------------------------------------


class TestRownumber:
    def test_none_before_execute(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1, 2, 3]})
        cursor = _unexecuted_cursor(tmp_path, table)
        assert cursor.rownumber is None

    def test_zero_after_execute_before_fetch(self, tmp_path: Path) -> None:
        # ADBC-accurate: 0 (NOT None) after execute() pre-fetch.
        table = pa.table({"id": [1, 2, 3]})
        cursor = _executed_cursor(tmp_path, table)
        assert cursor.rownumber == 0

    def test_increments_per_fetchone(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1, 2, 3]})
        cursor = _executed_cursor(tmp_path, table)
        cursor.fetchone()
        assert cursor.rownumber == 1
        cursor.fetchone()
        assert cursor.rownumber == 2

    def test_equals_k_after_fetchmany(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1, 2, 3, 4]})
        cursor = _executed_cursor(tmp_path, table)
        cursor.fetchmany(3)
        assert cursor.rownumber == 3


# ---------------------------------------------------------------------------
# DBAPI-04: connection back-reference
# ---------------------------------------------------------------------------


def _replay_connection(tmp_path: Path) -> ReplayConnection:
    """Build a replay-mode ReplayConnection (no real driver imported)."""
    return ReplayConnection(
        driver_module_name="adbc_driver_sqlite",
        db_kwargs={},
        mode="none",
        cassette_path=tmp_path / "cass",
    )


class TestConnection:
    def test_cursor_connection_is_owning_connection(self, tmp_path: Path) -> None:
        conn = _replay_connection(tmp_path)
        cursor = conn.cursor()
        assert cursor.connection is conn

    def test_direct_construction_connection_is_none(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=tmp_path / "c")
        assert cursor.connection is None

    def test_clone_cursor_connection_is_clone(self, tmp_path: Path) -> None:
        conn = _replay_connection(tmp_path)
        clone = conn.adbc_clone()
        cursor = clone.cursor()
        assert cursor.connection is clone
        assert cursor.connection is not conn


# ---------------------------------------------------------------------------
# Record-mode helper: a cursor wrapping a MagicMock real cursor.
# ---------------------------------------------------------------------------


def _record_cursor_with_mock(tmp_path: Path, mode: str = "once") -> tuple[ReplayCursor, MagicMock]:
    """Build a record-mode ReplayCursor backed by a MagicMock real cursor."""
    mock = MagicMock()
    cursor = ReplayCursor(real_cursor=mock, mode=mode, cassette_path=tmp_path / "rec")
    return cursor, mock


# ---------------------------------------------------------------------------
# DBAPI-02: nextset() -> NotSupportedError (both modes, no delegation)
# ---------------------------------------------------------------------------


class TestNextset:
    def test_replay_raises_not_supported(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=tmp_path / "c")
        with pytest.raises(NotSupportedError, match="Cursor.nextset"):
            cursor.nextset()

    def test_record_raises_without_delegation(self, tmp_path: Path) -> None:
        cursor, mock = _record_cursor_with_mock(tmp_path)
        with pytest.raises(NotSupportedError, match="Cursor.nextset"):
            cursor.nextset()
        mock.nextset.assert_not_called()


# ---------------------------------------------------------------------------
# DBAPI-06: callproc() -> NotSupportedError (both modes, no delegation)
# ---------------------------------------------------------------------------


class TestCallproc:
    def test_replay_raises_not_supported(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=tmp_path / "c")
        with pytest.raises(NotSupportedError, match="Cursor.callproc"):
            cursor.callproc("some_proc", [])

    def test_record_raises_without_delegation(self, tmp_path: Path) -> None:
        cursor, mock = _record_cursor_with_mock(tmp_path)
        with pytest.raises(NotSupportedError, match="Cursor.callproc"):
            cursor.callproc("some_proc", [1, 2])
        mock.callproc.assert_not_called()


# ---------------------------------------------------------------------------
# DBAPI-05: setinputsizes / setoutputsize (replay no-op; record delegates)
# ---------------------------------------------------------------------------


class TestSizeHints:
    def test_setinputsizes_replay_noop_returns_none(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=tmp_path / "c")
        assert cursor.setinputsizes([10, 20]) is None

    def test_setoutputsize_replay_noop_returns_none(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=tmp_path / "c")
        assert cursor.setoutputsize(100) is None
        assert cursor.setoutputsize(100, 2) is None

    def test_setinputsizes_record_delegates(self, tmp_path: Path) -> None:
        cursor, mock = _record_cursor_with_mock(tmp_path)
        cursor.setinputsizes([1, 2, 3])
        mock.setinputsizes.assert_called_once_with([1, 2, 3])

    def test_setoutputsize_record_delegates(self, tmp_path: Path) -> None:
        cursor, mock = _record_cursor_with_mock(tmp_path)
        cursor.setoutputsize(50, 1)
        mock.setoutputsize.assert_called_once_with(50, 1)


# ---------------------------------------------------------------------------
# DBAPI-07: executescript (replay silent no-op; record delegates)
# ---------------------------------------------------------------------------


class TestExecutescript:
    def test_replay_noop_returns_none_and_writes_nothing(self, tmp_path: Path) -> None:
        cassette = tmp_path / "cass"
        cassette.mkdir(parents=True, exist_ok=True)
        before = set(cassette.iterdir())
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        assert cursor.executescript("CREATE TABLE t (id INT); INSERT INTO t VALUES (1);") is None
        after = set(cassette.iterdir())
        assert before == after  # nothing written to the cassette dir

    def test_record_delegates_to_real_cursor(self, tmp_path: Path) -> None:
        cursor, mock = _record_cursor_with_mock(tmp_path)
        script = "CREATE TABLE t (id INT);"
        cursor.executescript(script)
        mock.executescript.assert_called_once_with(script)

    def test_record_mode_without_real_cursor_raises_runtime_error(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="once", cassette_path=tmp_path / "c")
        with pytest.raises(RuntimeError):
            cursor.executescript("CREATE TABLE t (id INT);")
