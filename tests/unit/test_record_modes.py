"""Tests for all four record modes and ordered-queue replay (MODE-01 to MODE-04, CASS-06)."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from unittest.mock import MagicMock

import pyarrow as pa
import pytest

from pytest_adbc_replay._cassette_io import (
    cassette_has_interactions,
    interaction_file_paths,
    load_all_interactions,
    write_arrow_table,
    write_params_json,
    write_sql_file,
)
from pytest_adbc_replay._connection import ReplayConnection
from pytest_adbc_replay._cursor import ReplayCursor
from pytest_adbc_replay._exceptions import CassetteMissError
from pytest_adbc_replay._normaliser import normalise_sql
from pytest_adbc_replay._session import ReplaySession


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


def _make_recording_connection(cassette: Path, mode: str) -> ReplayConnection:
    """
    Create a record-mode ReplayConnection whose real cursors echo the SQL they ran.

    Each real cursor returns a one-row table holding the SQL it executed, so a test
    can tell from the recorded result which query produced it.
    """
    conn = ReplayConnection(
        driver_module_name="adbc_driver_test",
        db_kwargs={},
        mode="none",  # avoid a real driver import
        cassette_path=cassette,
    )
    conn._mode = mode

    def _make_real_cursor() -> MagicMock:
        real = MagicMock()

        def _execute(sql: str, *_args: object, **_kwargs: object) -> None:
            real.fetch_arrow_table.return_value = pa.table({"sql": [sql]})

        real.execute.side_effect = _execute
        return real

    real_conn = MagicMock()
    real_conn.cursor.side_effect = _make_real_cursor
    conn._real_conn = real_conn
    return conn


def _recorded_sql(cassette: Path) -> list[str]:
    """Return the result 'sql' value of every recorded interaction, in index order."""
    return [table.column("sql")[0].as_py() for _, table, _ in load_all_interactions(cassette)]


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

    def test_records_every_query_on_one_cursor(self, tmp_path: Path) -> None:
        """
        Once mode keeps recording after the first query of a fresh recording.

        Regression: the record/replay decision was re-made on every execute() from
        whether the cassette had interactions, so the first recorded query flipped
        the rest of the test to replay and the second query raised CassetteMissError.
        """
        cassette = tmp_path / "new"
        conn = _make_recording_connection(cassette, "once")
        c = conn.cursor()

        c.execute("SELECT a FROM t")
        assert c.fetch_arrow_table().column("sql").to_pylist() == ["SELECT a FROM t"]
        c.execute("SELECT b FROM t")
        assert c.fetch_arrow_table().column("sql").to_pylist() == ["SELECT b FROM t"]
        c.execute("SELECT a FROM t")  # repeated SQL is recorded again, not replayed
        assert c.fetch_arrow_table().column("sql").to_pylist() == ["SELECT a FROM t"]

        assert _recorded_sql(cassette) == ["SELECT a FROM t", "SELECT b FROM t", "SELECT a FROM t"]

        # The recording replays in full.
        replay = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        for sql in ("SELECT a FROM t", "SELECT b FROM t", "SELECT a FROM t"):
            replay.execute(sql)
            assert replay.fetch_arrow_table().column("sql").to_pylist() == [sql]

    def test_records_queries_from_interleaved_cursors(self, tmp_path: Path) -> None:
        """
        Once mode records every query from several cursors without overwriting any.

        Covers a later cursor starting after the first query was recorded (it must
        still record) and an earlier cursor writing again after a later one wrote
        (it must not reuse an interaction index the other cursor already took).
        """
        cassette = tmp_path / "new"
        conn = _make_recording_connection(cassette, "once")
        first = conn.cursor()
        second = conn.cursor()

        first.execute("SELECT 1")
        second.execute("SELECT 2")
        assert second.fetch_arrow_table().column("sql").to_pylist() == ["SELECT 2"]
        first.execute("SELECT 3")

        assert _recorded_sql(cassette) == ["SELECT 1", "SELECT 2", "SELECT 3"]

    def test_records_queries_from_a_clone(self, tmp_path: Path) -> None:
        """Once mode keeps recording when a cloned connection queries after the source."""
        cassette = tmp_path / "new"
        conn = _make_recording_connection(cassette, "once")
        clone = conn.adbc_clone()
        clone._real_conn = conn._real_conn

        conn.cursor().execute("SELECT 1")
        clone.cursor().execute("SELECT 2")

        assert _recorded_sql(cassette) == ["SELECT 1", "SELECT 2"]

    def test_recording_cursor_does_not_load_cassette(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A cursor that will only record never reads the cassette back.

        In a pool each query opens a new cursor; loading the cassette in each
        would re-read every interaction recorded so far, and could read one
        another thread is half-way through writing.
        """
        loads: list[Path] = []
        real_load = load_all_interactions

        def _counting_load(path: Path) -> list[tuple[str, pa.Table, object]]:
            loads.append(path)
            return real_load(path)

        monkeypatch.setattr("pytest_adbc_replay._cursor.load_all_interactions", _counting_load)
        for mode in ("once", "all"):
            conn = _make_recording_connection(tmp_path / mode, mode)
            for sql in ("SELECT 1", "SELECT 2", "SELECT 3"):
                conn.cursor().execute(sql)
            assert _recorded_sql(tmp_path / mode) == ["SELECT 1", "SELECT 2", "SELECT 3"]
        assert loads == []

    def test_replays_every_query_from_existing_cassette(self, tmp_path: Path) -> None:
        """Once mode with a recorded cassette replays all queries, from any cursor."""
        cassette = tmp_path / "existing"
        _populate_cassette(
            cassette,
            [(normalise_sql("SELECT a FROM t"), [1]), (normalise_sql("SELECT b FROM t"), [2])],
        )
        conn = _make_recording_connection(cassette, "once")
        first = conn.cursor()
        second = conn.cursor()

        first.execute("SELECT a FROM t")
        assert first.fetch_arrow_table().column("value").to_pylist() == [1]
        second.execute("SELECT b FROM t")
        assert second.fetch_arrow_table().column("value").to_pylist() == [2]

        for real in (first._real_cursor, second._real_cursor):
            real.execute.assert_not_called()
        # A query missing from a recorded cassette is still a miss, never a recording.
        with pytest.raises(CassetteMissError):
            first.execute("SELECT c FROM t")
        first._real_cursor.execute.assert_not_called()
        assert len(load_all_interactions(cassette)) == 2


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

    def test_interleaved_cursors_do_not_overwrite(self, tmp_path: Path) -> None:
        """
        All mode records every query from several cursors without overwriting any.

        Regression: each cursor kept its own interaction index, so a second cursor
        started at index 0 and overwrote the first cursor's recording.
        """
        cassette = tmp_path / "existing"
        _populate_cassette(cassette, [(normalise_sql("SELECT old"), [0])])
        conn = _make_recording_connection(cassette, "all")
        first = conn.cursor()
        second = conn.cursor()

        first.execute("SELECT 1")
        second.execute("SELECT 2")
        first.execute("SELECT 3")

        assert _recorded_sql(cassette) == ["SELECT 1", "SELECT 2", "SELECT 3"]


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


class TestSessionCassetteState:
    """ReplaySession shares one CassetteState per test and cassette, until the test ends."""

    def test_same_test_and_cassette_share_state(self, tmp_path: Path) -> None:
        """Every connection a test opens on one cassette gets the same state."""
        session = ReplaySession(mode="once", cassette_dir=tmp_path)
        state = session.cassette_state("t.py::test_a", tmp_path / "c")
        assert session.cassette_state("t.py::test_a", tmp_path / "c") is state
        assert session.cassette_state("t.py::test_a", tmp_path / "other") is not state
        assert session.cassette_state("t.py::test_b", tmp_path / "c") is not state

    def test_release_test_drops_only_that_tests_state(self, tmp_path: Path) -> None:
        """release_test() makes the next run of that test start from fresh state."""
        session = ReplaySession(mode="once", cassette_dir=tmp_path)
        state_a = session.cassette_state("t.py::test_a", tmp_path / "c")
        state_a.once_replay = False
        state_b = session.cassette_state("t.py::test_b", tmp_path / "c")

        session.release_test("t.py::test_a")

        fresh = session.cassette_state("t.py::test_a", tmp_path / "c")
        assert fresh is not state_a
        assert fresh.once_replay is None
        assert session.cassette_state("t.py::test_b", tmp_path / "c") is state_b

    def test_no_test_gets_fresh_state_per_connection(self, tmp_path: Path) -> None:
        """
        A connection not tied to a test (wrap() without request) gets its own state.

        Keyed state with no test to release it would last the whole session, so a
        fixture calling wrap() without request would carry one test's 'once'
        decision and 'all' wipe into every later test.
        """
        session = ReplaySession(mode="once", cassette_dir=tmp_path)
        assert session.cassette_state(None, tmp_path / "c") is not session.cassette_state(
            None, tmp_path / "c"
        )
