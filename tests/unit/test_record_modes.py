"""Tests for all four record modes and ordered-queue replay (MODE-01 to MODE-04, CASS-06)."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from unittest.mock import MagicMock

import pyarrow as pa
import pytest

from pytest_adbc_replay._cassette_io import (
    cassette_has_interactions,
    interaction_file_paths,
    write_arrow_table,
    write_params_json,
    write_sql_file,
)
from pytest_adbc_replay._cursor import ReplayCursor
from pytest_adbc_replay._exceptions import CassetteMissError
from pytest_adbc_replay._normaliser import normalise_sql


def _make_table(values: list[int]) -> pa.Table:
    """Create a simple pa.Table with one 'value' column."""
    return pa.table({"value": values})


def _populate_cassette(cassette: Path, interactions: list[tuple[str, list[int]]]) -> None:
    """Pre-populate a cassette directory with given SQL+result interactions."""
    cassette.mkdir(parents=True, exist_ok=True)
    for i, (sql, values) in enumerate(interactions):
        sql_path, arrow_path, params_path = interaction_file_paths(cassette, i)
        write_sql_file(sql, sql_path)
        write_arrow_table(_make_table(values), arrow_path)
        write_params_json(None, params_path)


def _make_mock_cursor(result_table: pa.Table) -> MagicMock:
    """Create a mock real ADBC cursor that returns result_table from fetch_arrow_table()."""
    mock = MagicMock()
    mock.fetch_arrow_table.return_value = result_table
    return mock


class TestModeNone:
    """MODE-01: none mode replays from cassette, never contacts warehouse."""

    def test_replay_success(self, tmp_path: Path) -> None:
        """Replay mode loads result from cassette file (CASS-04)."""
        cassette = tmp_path / "test"
        canonical = normalise_sql("SELECT * FROM users")
        _populate_cassette(cassette, [(canonical, [1, 2, 3])])

        c = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        c.execute("SELECT * FROM users")
        result = c.fetch_arrow_table()
        assert result.column("value").to_pylist() == [1, 2, 3]

    def test_normalisation_allows_casing_difference(self, tmp_path: Path) -> None:
        """SQL normalisation: 'select * from users' matches cassette for 'SELECT * FROM users'."""
        cassette = tmp_path / "test"
        canonical = normalise_sql("SELECT * FROM users")
        _populate_cassette(cassette, [(canonical, [42])])

        c = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        # Execute with different casing — should match cassette via normalisation
        c.execute("select  *  from  USERS")
        result = c.fetch_arrow_table()
        assert result.column("value").to_pylist() == [42]

    def test_missing_cassette_raises_error(self, tmp_path: Path) -> None:
        """CassetteMissError raised when cassette directory does not exist (PROXY-06)."""
        cassette = tmp_path / "nonexistent"
        c = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        with pytest.raises(CassetteMissError):
            c.execute("SELECT 1")

    def test_missing_cassette_error_message(self, tmp_path: Path) -> None:
        """CassetteMissError message mentions 'record' or 'does not exist'."""
        cassette = tmp_path / "nonexistent"
        c = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        with pytest.raises(CassetteMissError) as exc_info:
            c.execute("SELECT 1")
        msg = str(exc_info.value).lower()
        assert "record" in msg or "does not exist" in msg

    def test_empty_cassette_dir_raises_error(self, tmp_path: Path) -> None:
        """CassetteMissError with 'empty' message when cassette dir exists but is empty."""
        cassette = tmp_path / "empty"
        cassette.mkdir()
        c = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        with pytest.raises(CassetteMissError) as exc_info:
            c.execute("SELECT 1")
        assert "empty" in str(exc_info.value).lower()

    def test_never_calls_real_cursor(self, tmp_path: Path) -> None:
        """In none mode, real_cursor.execute() is never called (MODE-01)."""
        cassette = tmp_path / "test"
        canonical = normalise_sql("SELECT 1")
        _populate_cassette(cassette, [(canonical, [99])])

        mock_real = _make_mock_cursor(_make_table([999]))
        c = ReplayCursor(real_cursor=mock_real, mode="none", cassette_path=cassette)
        c.execute("SELECT 1")
        mock_real.execute.assert_not_called()

    def test_no_execute_no_side_effects(self, tmp_path: Path) -> None:
        """Test never calling execute() passes silently — no cassette touched."""
        cassette = tmp_path / "untouched"
        _c = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        # Never call execute() — cassette_path should not be created
        assert not cassette.exists()


class TestModeOnce:
    """MODE-02: once mode records new cassette; replays existing cassette."""

    def test_records_when_no_cassette(self, tmp_path: Path) -> None:
        """Once mode records to new cassette when cassette_has_interactions is False."""
        cassette = tmp_path / "new"
        result_table = _make_table([10, 20])
        mock_real = _make_mock_cursor(result_table)

        c = ReplayCursor(real_cursor=mock_real, mode="once", cassette_path=cassette)
        c.execute("SELECT id FROM t")

        # Cassette should now exist
        assert cassette.exists()
        assert cassette_has_interactions(cassette)
        mock_real.execute.assert_called_once()

    def test_replays_when_cassette_exists(self, tmp_path: Path) -> None:
        """Once mode replays from existing cassette without calling real cursor."""
        cassette = tmp_path / "existing"
        canonical = normalise_sql("SELECT id FROM t")
        _populate_cassette(cassette, [(canonical, [55])])

        mock_real = _make_mock_cursor(_make_table([999]))
        c = ReplayCursor(real_cursor=mock_real, mode="once", cassette_path=cassette)
        c.execute("SELECT id FROM t")

        result = c.fetch_arrow_table()
        assert result.column("value").to_pylist() == [55]  # From cassette, not mock
        mock_real.execute.assert_not_called()

    def test_empty_dir_treated_as_no_cassette(self, tmp_path: Path) -> None:
        """Once mode with empty dir re-records (empty dir != cassette exists)."""
        cassette = tmp_path / "empty"
        cassette.mkdir()
        result_table = _make_table([7])
        mock_real = _make_mock_cursor(result_table)

        c = ReplayCursor(real_cursor=mock_real, mode="once", cassette_path=cassette)
        c.execute("SELECT 1")
        mock_real.execute.assert_called_once()

    def test_once_result_accessible_after_record(self, tmp_path: Path) -> None:
        """Recorded result is immediately available for fetching in once mode."""
        cassette = tmp_path / "new"
        result_table = _make_table([10, 20])
        mock_real = _make_mock_cursor(result_table)

        c = ReplayCursor(real_cursor=mock_real, mode="once", cassette_path=cassette)
        c.execute("SELECT id FROM t")
        result = c.fetch_arrow_table()
        assert result.column("value").to_pylist() == [10, 20]


class TestModeNewEpisodes:
    """MODE-03: new_episodes replays existing; records new interactions."""

    def test_replays_existing_interaction(self, tmp_path: Path) -> None:
        """new_episodes replays interactions already in the cassette."""
        cassette = tmp_path / "partial"
        canonical = normalise_sql("SELECT id FROM t")
        _populate_cassette(cassette, [(canonical, [100])])

        mock_real = _make_mock_cursor(_make_table([999]))
        c = ReplayCursor(real_cursor=mock_real, mode="new_episodes", cassette_path=cassette)
        c.execute("SELECT id FROM t")

        result = c.fetch_arrow_table()
        assert result.column("value").to_pylist() == [100]  # From cassette
        mock_real.execute.assert_not_called()

    def test_records_new_interaction(self, tmp_path: Path) -> None:
        """new_episodes records a new interaction not in the cassette."""
        cassette = tmp_path / "partial"
        cassette.mkdir()  # Empty cassette — no interactions
        result_table = _make_table([200])
        mock_real = _make_mock_cursor(result_table)

        c = ReplayCursor(real_cursor=mock_real, mode="new_episodes", cassette_path=cassette)
        c.execute("SELECT id FROM t")
        mock_real.execute.assert_called_once()

        result = c.fetch_arrow_table()
        assert result.column("value").to_pylist() == [200]

    def test_mixed_replay_and_record(self, tmp_path: Path) -> None:
        """new_episodes replays existing SQL, records new SQL in same test."""
        cassette = tmp_path / "mixed"
        canonical_a = normalise_sql("SELECT a FROM t")
        _populate_cassette(cassette, [(canonical_a, [1, 2])])

        new_result = _make_table([99])
        mock_real = _make_mock_cursor(new_result)

        c = ReplayCursor(real_cursor=mock_real, mode="new_episodes", cassette_path=cassette)
        # Existing interaction — replayed
        c.execute("SELECT a FROM t")
        r1 = c.fetch_arrow_table()
        assert r1.column("value").to_pylist() == [1, 2]
        mock_real.execute.assert_not_called()

        # New interaction — recorded
        c.execute("SELECT b FROM t")
        r2 = c.fetch_arrow_table()
        assert r2.column("value").to_pylist() == [99]
        mock_real.execute.assert_called_once()


class TestModeAll:
    """MODE-04: all mode wipes cassette and re-records everything."""

    def test_wipes_existing_cassette(self, tmp_path: Path) -> None:
        """All mode deletes the existing cassette directory on first execute()."""
        cassette = tmp_path / "existing"
        canonical = normalise_sql("SELECT 1")
        _populate_cassette(cassette, [(canonical, [1, 2, 3])])

        result_table = _make_table([99])
        mock_real = _make_mock_cursor(result_table)

        c = ReplayCursor(real_cursor=mock_real, mode="all", cassette_path=cassette)
        c.execute("SELECT 1")

        # The original cassette was wiped; new cassette was recorded
        result = c.fetch_arrow_table()
        assert result.column("value").to_pylist() == [99]  # New recording, not old cassette

    def test_always_records_using_real_cursor(self, tmp_path: Path) -> None:
        """All mode always calls real cursor.execute()."""
        cassette = tmp_path / "new"
        result_table = _make_table([77])
        mock_real = _make_mock_cursor(result_table)

        c = ReplayCursor(real_cursor=mock_real, mode="all", cassette_path=cassette)
        c.execute("SELECT 1")
        mock_real.execute.assert_called_once()

    def test_no_execute_no_wipe(self, tmp_path: Path) -> None:
        """All mode does not wipe cassette if execute() is never called."""
        cassette = tmp_path / "keep"
        canonical = normalise_sql("SELECT 1")
        _populate_cassette(cassette, [(canonical, [42])])

        mock_real = _make_mock_cursor(_make_table([0]))
        _c = ReplayCursor(real_cursor=mock_real, mode="all", cassette_path=cassette)
        # Never call execute() — cassette should still exist
        assert cassette.exists()
        assert cassette_has_interactions(cassette)

    def test_records_new_cassette_when_none_existed(self, tmp_path: Path) -> None:
        """All mode creates new cassette when none existed before."""
        cassette = tmp_path / "fresh"
        result_table = _make_table([5, 6, 7])
        mock_real = _make_mock_cursor(result_table)

        c = ReplayCursor(real_cursor=mock_real, mode="all", cassette_path=cassette)
        c.execute("SELECT id FROM t")

        assert cassette.exists()
        assert cassette_has_interactions(cassette)


class TestOrderedQueueReplay:
    """CASS-06: Duplicate queries use ordered-queue replay (FIFO per key)."""

    def test_same_sql_twice_returns_in_order(self, tmp_path: Path) -> None:
        """Two execute() calls with same SQL return results in recorded order."""
        cassette = tmp_path / "duplicate"
        canonical = normalise_sql("SELECT * FROM t")
        # Two interactions with same SQL, different results
        _populate_cassette(
            cassette,
            [
                (canonical, [1, 2]),
                (canonical, [3, 4]),
            ],
        )

        c = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        c.execute("SELECT * FROM t")
        result1 = c.fetch_arrow_table()

        c.execute("SELECT * FROM t")
        result2 = c.fetch_arrow_table()

        assert result1.column("value").to_pylist() == [1, 2]
        assert result2.column("value").to_pylist() == [3, 4]

    def test_third_call_raises_cassette_miss(self, tmp_path: Path) -> None:
        """Third execute() with same SQL raises CassetteMissError when only 2 recorded."""
        cassette = tmp_path / "exhausted"
        canonical = normalise_sql("SELECT * FROM t")
        _populate_cassette(cassette, [(canonical, [1]), (canonical, [2])])

        c = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        c.execute("SELECT * FROM t")  # 1st — OK
        c.execute("SELECT * FROM t")  # 2nd — OK
        with pytest.raises(CassetteMissError):
            c.execute("SELECT * FROM t")  # 3rd — queue exhausted

    def test_different_sql_independent_queues(self, tmp_path: Path) -> None:
        """Different SQL keys have independent replay queues."""
        cassette = tmp_path / "multi"
        canonical_a = normalise_sql("SELECT a FROM t")
        canonical_b = normalise_sql("SELECT b FROM t")
        _populate_cassette(
            cassette,
            [
                (canonical_a, [10]),
                (canonical_b, [20]),
            ],
        )

        c = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        c.execute("SELECT a FROM t")
        ra = c.fetch_arrow_table()

        c.execute("SELECT b FROM t")
        rb = c.fetch_arrow_table()

        assert ra.column("value").to_pylist() == [10]
        assert rb.column("value").to_pylist() == [20]
