"""Tests for the ADBC extension methods on ReplayCursor (ADBCX-01..04)."""

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
from pytest_adbc_replay._cursor import ReplayCursor
from pytest_adbc_replay._exceptions import CassetteMissError
from pytest_adbc_replay._normaliser import normalise_sql

if TYPE_CHECKING:
    from pathlib import Path


def _populate_cassette(cassette: Path, sql: str, table: pa.Table, *, count: int = 1) -> None:
    """Pre-populate a cassette directory with ``count`` interactions of one query."""
    cassette.mkdir(parents=True, exist_ok=True)
    canonical = normalise_sql(sql)
    for index in range(count):
        sql_path, arrow_path, params_path = interaction_file_paths(cassette, index)
        write_sql_file(canonical, sql_path)
        write_arrow_table(table, arrow_path)
        write_params_json(None, params_path)


def _replay_cursor(tmp_path: Path, table: pa.Table, sql: str = "SELECT 1") -> ReplayCursor:
    """Build a replay-mode cursor with a populated cassette (not yet executed)."""
    cassette = tmp_path / "test"
    _populate_cassette(cassette, sql, table)
    return ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)


def _record_cursor_with_mock(tmp_path: Path, mode: str = "once") -> tuple[ReplayCursor, MagicMock]:
    """
    Build a record-mode ReplayCursor backed by a MagicMock real cursor.

    The cassette directory does not exist, so any record-mode dispatch takes the
    delegate-to-real-cursor branch.
    """
    mock = MagicMock()
    cursor = ReplayCursor(real_cursor=mock, mode=mode, cassette_path=tmp_path / "rec")
    return cursor, mock


# ---------------------------------------------------------------------------
# ADBCX-02 / D-02: adbc_execute_schema — replay-derive (peek-don't-pop) + record delegate
# ---------------------------------------------------------------------------


class TestAdbcExecuteSchema:
    def test_replay_returns_recorded_schema(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1, 2], "name": ["a", "b"]})
        cursor = _replay_cursor(tmp_path, table)
        schema = cursor.adbc_execute_schema("SELECT 1")
        assert schema == table.schema

    def test_replay_peek_does_not_consume_queue(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1, 2, 3]})
        cursor = _replay_cursor(tmp_path, table)
        # Peek the schema...
        cursor.adbc_execute_schema("SELECT 1")
        # ...a subsequent execute() of the same query must still return its rows.
        cursor.execute("SELECT 1")
        assert cursor.fetchall() == [(1,), (2,), (3,)]

    def test_replay_peek_leaves_fetch_state_untouched(self, tmp_path: Path) -> None:
        # Two recorded interactions of the same query: one is consumed by
        # execute(), one remains in the queue for the post-execute peek.
        table = pa.table({"id": [10, 20]})
        cassette = tmp_path / "test"
        _populate_cassette(cassette, "SELECT 1", table, count=2)
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        cursor.execute("SELECT 1")
        # Peek after execute() but before fetch — must not touch _pending/_fetch_offset.
        cursor.adbc_execute_schema("SELECT 1")
        assert cursor.fetchone() == (10,)
        assert cursor.fetchone() == (20,)

    def test_replay_directory_missing_raises_cassette_miss(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(
            real_cursor=None, mode="none", cassette_path=tmp_path / "does_not_exist"
        )
        with pytest.raises(CassetteMissError):
            cursor.adbc_execute_schema("SELECT 1")

    def test_replay_query_never_recorded_raises_cassette_miss(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1]})
        cursor = _replay_cursor(tmp_path, table, sql="SELECT 1")
        with pytest.raises(CassetteMissError):
            cursor.adbc_execute_schema("SELECT 999")

    def test_record_delegates_to_real_cursor(self, tmp_path: Path) -> None:
        cursor, mock = _record_cursor_with_mock(tmp_path)
        result = cursor.adbc_execute_schema("SELECT 1", None)
        mock.adbc_execute_schema.assert_called_once_with("SELECT 1", None)
        assert result is mock.adbc_execute_schema.return_value

    def test_record_without_real_cursor_raises_runtime_error(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="once", cassette_path=tmp_path / "c")
        with pytest.raises(RuntimeError):
            cursor.adbc_execute_schema("SELECT 1")


# ---------------------------------------------------------------------------
# ADBCX-03 / D-03: adbc_cancel — replay no-op + record delegate
# ---------------------------------------------------------------------------


class TestAdbcCancel:
    def test_replay_noop_returns_none(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=tmp_path / "c")
        assert cursor.adbc_cancel() is None

    def test_record_delegates(self, tmp_path: Path) -> None:
        cursor, mock = _record_cursor_with_mock(tmp_path, mode="all")
        cursor.adbc_cancel()
        mock.adbc_cancel.assert_called_once_with()

    def test_record_without_real_cursor_raises_runtime_error(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="all", cassette_path=tmp_path / "c")
        with pytest.raises(RuntimeError):
            cursor.adbc_cancel()


# ---------------------------------------------------------------------------
# ADBCX-03 / D-04: adbc_prepare — replay pure no-op (None) + record delegate
# ---------------------------------------------------------------------------


class TestAdbcPrepare:
    def test_replay_returns_none_even_when_recorded(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1]})
        cursor = _replay_cursor(tmp_path, table, sql="SELECT 1")
        assert cursor.adbc_prepare("SELECT 1") is None

    def test_record_delegates(self, tmp_path: Path) -> None:
        cursor, mock = _record_cursor_with_mock(tmp_path, mode="all")
        result = cursor.adbc_prepare("SELECT 1")
        mock.adbc_prepare.assert_called_once_with("SELECT 1")
        assert result is mock.adbc_prepare.return_value

    def test_record_without_real_cursor_raises_runtime_error(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="all", cassette_path=tmp_path / "c")
        with pytest.raises(RuntimeError):
            cursor.adbc_prepare("SELECT 1")


# ---------------------------------------------------------------------------
# ADBCX-04 / D-05: adbc_ingest / adbc_execute_partitions / adbc_read_partition
#                  -> NotSupportedError in replay + record delegate
# ---------------------------------------------------------------------------


class TestAdbcNotSupported:
    def test_ingest_replay_raises_not_supported(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=tmp_path / "c")
        with pytest.raises(NotSupportedError, match="adbc_ingest"):
            cursor.adbc_ingest("t", pa.table({"x": [1]}))

    def test_execute_partitions_replay_raises_not_supported(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=tmp_path / "c")
        with pytest.raises(NotSupportedError, match="adbc_execute_partitions"):
            cursor.adbc_execute_partitions("SELECT 1")

    def test_read_partition_replay_raises_not_supported(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=tmp_path / "c")
        with pytest.raises(NotSupportedError, match="adbc_read_partition"):
            cursor.adbc_read_partition(b"x")

    def test_ingest_record_delegates(self, tmp_path: Path) -> None:
        cursor, mock = _record_cursor_with_mock(tmp_path, mode="all")
        data = pa.table({"x": [1]})
        result = cursor.adbc_ingest("t", data, "create")
        mock.adbc_ingest.assert_called_once_with(
            "t", data, "create", catalog_name=None, db_schema_name=None, temporary=False
        )
        assert result is mock.adbc_ingest.return_value

    def test_execute_partitions_record_delegates(self, tmp_path: Path) -> None:
        cursor, mock = _record_cursor_with_mock(tmp_path, mode="all")
        result = cursor.adbc_execute_partitions("SELECT 1", None)
        mock.adbc_execute_partitions.assert_called_once_with("SELECT 1", None)
        assert result is mock.adbc_execute_partitions.return_value

    def test_read_partition_record_delegates(self, tmp_path: Path) -> None:
        cursor, mock = _record_cursor_with_mock(tmp_path, mode="all")
        cursor.adbc_read_partition(b"abc")
        mock.adbc_read_partition.assert_called_once_with(b"abc")

    def test_ingest_record_without_real_cursor_raises_runtime_error(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="all", cassette_path=tmp_path / "c")
        with pytest.raises(RuntimeError):
            cursor.adbc_ingest("t", pa.table({"x": [1]}))

    def test_execute_partitions_record_without_real_cursor_raises(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="all", cassette_path=tmp_path / "c")
        with pytest.raises(RuntimeError):
            cursor.adbc_execute_partitions("SELECT 1")

    def test_read_partition_record_without_real_cursor_raises(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="all", cassette_path=tmp_path / "c")
        with pytest.raises(RuntimeError):
            cursor.adbc_read_partition(b"x")


# ---------------------------------------------------------------------------
# ADBCX-04 / D-06: adbc_statement — PROPERTY raising NotSupportedError on access
# ---------------------------------------------------------------------------


class TestAdbcStatement:
    def test_replay_access_raises_not_supported_not_attribute_error(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=tmp_path / "c")
        with pytest.raises(NotSupportedError):
            _ = cursor.adbc_statement
        # Explicitly assert it is NOT a bare AttributeError.
        try:
            _ = cursor.adbc_statement
        except NotSupportedError:
            pass
        except AttributeError:  # pragma: no cover - guard
            pytest.fail("adbc_statement raised a bare AttributeError, not NotSupportedError")

    def test_record_returns_real_cursor_statement(self, tmp_path: Path) -> None:
        cursor, mock = _record_cursor_with_mock(tmp_path, mode="all")
        assert cursor.adbc_statement is mock.adbc_statement

    def test_record_without_real_cursor_raises_runtime_error(self, tmp_path: Path) -> None:
        cursor = ReplayCursor(real_cursor=None, mode="all", cassette_path=tmp_path / "c")
        with pytest.raises(RuntimeError):
            _ = cursor.adbc_statement
