"""Tests for the Arrow & DataFrame fetch methods on ReplayCursor (FETCH-01..05)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyarrow as pa
import pytest
from adbc_driver_manager.dbapi import ProgrammingError

from pytest_adbc_replay._cassette_io import (
    interaction_file_paths,
    write_arrow_table,
    write_params_json,
    write_sql_file,
)
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


class _CapsuleShim:
    """
    Wraps a raw __arrow_c_stream__ PyCapsule so pyarrow can import it.

    pa.RecordBatchReader.from_stream / pa.table() want an object that HAS
    __arrow_c_stream__, not the raw capsule. This shim re-exposes the capsule.
    """

    def __init__(self, capsule: object) -> None:
        self._capsule = capsule

    def __arrow_c_stream__(self, requested_schema: object = None) -> object:
        return self._capsule


# ---------------------------------------------------------------------------
# FETCH-01: fetch_record_batch
# ---------------------------------------------------------------------------


class TestFetchRecordBatch:
    def test_returns_record_batch_reader(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        cursor = _executed_cursor(tmp_path, table)
        reader = cursor.fetch_record_batch()
        assert isinstance(reader, pa.RecordBatchReader)
        assert reader.read_all().equals(table)

    def test_empty_result_valid_reader(self, tmp_path: Path) -> None:
        table = pa.table({"id": pa.array([], type=pa.int64())})
        cursor = _executed_cursor(tmp_path, table)
        reader = cursor.fetch_record_batch()
        assert isinstance(reader, pa.RecordBatchReader)
        assert reader.read_all().num_rows == 0

    def test_before_execute_raises(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1]})
        cursor = _unexecuted_cursor(tmp_path, table)
        with pytest.raises(ProgrammingError) as exc_info:
            cursor.fetch_record_batch()
        msg = str(exc_info.value)
        assert "fetch_record_batch" in msg
        assert "before execute" in msg


# ---------------------------------------------------------------------------
# FETCH-02 / D5: fetch_arrow
# ---------------------------------------------------------------------------


class TestFetchArrow:
    def test_returns_consumable_capsule(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1, 2, 3]})
        cursor = _executed_cursor(tmp_path, table)
        capsule = cursor.fetch_arrow()
        result = pa.RecordBatchReader.from_stream(_CapsuleShim(capsule)).read_all()
        assert result.equals(table)

    def test_empty_result_valid_capsule(self, tmp_path: Path) -> None:
        table = pa.table({"id": pa.array([], type=pa.int64())})
        cursor = _executed_cursor(tmp_path, table)
        capsule = cursor.fetch_arrow()
        result = pa.RecordBatchReader.from_stream(_CapsuleShim(capsule)).read_all()
        assert result.num_rows == 0

    def test_before_execute_raises(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1]})
        cursor = _unexecuted_cursor(tmp_path, table)
        with pytest.raises(ProgrammingError) as exc_info:
            cursor.fetch_arrow()
        msg = str(exc_info.value)
        assert "fetch_arrow" in msg
        assert "before execute" in msg

    def test_second_call_raises(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1]})
        cursor = _executed_cursor(tmp_path, table)
        cursor.fetch_arrow()
        with pytest.raises(ProgrammingError):
            cursor.fetch_arrow()

    def test_after_other_consumer_raises(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1]})
        cursor = _executed_cursor(tmp_path, table)
        cursor.fetch_record_batch()  # a consuming fetch
        with pytest.raises(ProgrammingError):
            cursor.fetch_arrow()

    def test_capsule_single_use_at_c_level(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1]})
        cursor = _executed_cursor(tmp_path, table)
        capsule = cursor.fetch_arrow()
        shim = _CapsuleShim(capsule)
        pa.RecordBatchReader.from_stream(shim).read_all()  # consumes the capsule
        with pytest.raises(pa.lib.ArrowInvalid):
            pa.RecordBatchReader.from_stream(shim).read_all()

    def test_fresh_execute_resets_consumption(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1]})
        cassette = tmp_path / "test"
        _populate_cassette(cassette, "SELECT 1", table)
        # Record a second identical interaction so the queue has two entries.
        sql_path, arrow_path, params_path = interaction_file_paths(cassette, 1)
        canonical = normalise_sql("SELECT 1")
        write_sql_file(canonical, sql_path)
        write_arrow_table(table, arrow_path)
        write_params_json(None, params_path)

        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        cursor.execute("SELECT 1")
        cursor.fetch_arrow()  # consumes first result
        cursor.execute("SELECT 1")  # fresh execute resets consumption state
        cursor.fetch_arrow()  # must not raise


# ---------------------------------------------------------------------------
# FETCH-03 / D3: fetchallarrow (silent alias)
# ---------------------------------------------------------------------------


class TestFetchallArrow:
    def test_returns_table_equal_to_fetch_arrow_table(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1, 2], "name": ["x", "y"]})
        cursor = _executed_cursor(tmp_path, table)
        result = cursor.fetchallarrow()
        assert isinstance(result, pa.Table)
        assert result.equals(cursor.fetch_arrow_table())

    def test_emits_no_warning(self, tmp_path: Path, recwarn: pytest.WarningsRecorder) -> None:
        table = pa.table({"id": [1]})
        cursor = _executed_cursor(tmp_path, table)
        cursor.fetchallarrow()
        assert len(recwarn.list) == 0

    def test_before_execute_does_not_raise(self, tmp_path: Path) -> None:
        # Inherits the lenient fetch_arrow_table behavior (D3) — no ProgrammingError.
        table = pa.table({"id": [1]})
        cursor = _unexecuted_cursor(tmp_path, table)
        result = cursor.fetchallarrow()
        assert isinstance(result, pa.Table)


# ---------------------------------------------------------------------------
# execute() consumption-state reset across modes
# ---------------------------------------------------------------------------


class TestExecuteResetsConsumptionState:
    def test_before_execute_guard_in_none_mode(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1]})
        cursor = _unexecuted_cursor(tmp_path, table)
        with pytest.raises(ProgrammingError):
            cursor.fetch_record_batch()
