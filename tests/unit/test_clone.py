"""Tests for ReplayConnection.adbc_clone() and shared wipe state."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pyarrow as pa

if TYPE_CHECKING:
    from pathlib import Path

from pytest_adbc_replay._cassette_io import (
    interaction_file_paths,
    write_arrow_table,
    write_params_json,
    write_sql_file,
)
from pytest_adbc_replay._connection import ReplayConnection
from pytest_adbc_replay._normaliser import normalise_sql


def _populate_cassette(cassette: Path, sql: str, table: pa.Table) -> None:
    """Pre-populate a cassette directory with one interaction."""
    cassette.mkdir(parents=True, exist_ok=True)
    canonical = normalise_sql(sql)
    sql_path, arrow_path, params_path = interaction_file_paths(cassette, 0)
    write_sql_file(canonical, sql_path)
    write_arrow_table(table, arrow_path)
    write_params_json(None, params_path)


class TestAdBCClone:
    """Tests for adbc_clone() behavior (CLONE-01 through CLONE-05, CLONE-07, CLONE-08)."""

    def _make_connection(self, tmp_path: Path, mode: str = "none") -> ReplayConnection:
        """Create a ReplayConnection with a pre-populated cassette."""
        cassette = tmp_path / "cassette"
        table = pa.table({"id": [1], "name": ["test"]})
        _populate_cassette(cassette, "SELECT 1", table)
        return ReplayConnection(
            driver_module_name="adbc_driver_test",
            db_kwargs={},
            mode=mode,
            cassette_path=cassette,
        )

    def test_clone_returns_replay_connection(self, tmp_path: Path) -> None:
        """CLONE-01: adbc_clone() returns a ReplayConnection instance."""
        source = self._make_connection(tmp_path)
        clone = source.adbc_clone()
        assert isinstance(clone, ReplayConnection)

    def test_clone_shares_cassette_path(self, tmp_path: Path) -> None:
        """CLONE-02: Clone's _cassette_path is the same object as source's."""
        source = self._make_connection(tmp_path)
        clone = source.adbc_clone()
        assert clone._cassette_path is source._cassette_path

    def test_clone_replay_mode_no_real_conn(self, tmp_path: Path) -> None:
        """CLONE-03: Clone in replay mode has _real_conn = None."""
        source = self._make_connection(tmp_path, mode="none")
        assert source._real_conn is None
        clone = source.adbc_clone()
        assert clone._real_conn is None

    def test_clone_record_mode_delegates(self, tmp_path: Path) -> None:
        """CLONE-04: Clone in record mode delegates to _real_conn.adbc_clone()."""
        source = self._make_connection(tmp_path, mode="none")
        # Simulate record mode by setting a mock real connection
        mock_real_conn = MagicMock()
        mock_clone_conn = MagicMock()
        mock_real_conn.adbc_clone.return_value = mock_clone_conn
        source._real_conn = mock_real_conn

        clone = source.adbc_clone()

        mock_real_conn.adbc_clone.assert_called_once()
        assert clone._real_conn is mock_clone_conn

    def test_clone_cursor_independent_queue(self, tmp_path: Path) -> None:
        """CLONE-05: Clone's cursor has independent replay queue."""
        source = self._make_connection(tmp_path, mode="none")
        clone = source.adbc_clone()

        # Both source and clone should be able to replay the same query independently
        source_cursor = source.cursor()
        clone_cursor = clone.cursor()

        source_cursor.execute("SELECT 1")
        clone_cursor.execute("SELECT 1")

        source_result = source_cursor.fetch_arrow_table()
        clone_result = clone_cursor.fetch_arrow_table()

        assert source_result.num_rows == 1
        assert clone_result.num_rows == 1

    def test_clone_of_clone(self, tmp_path: Path) -> None:
        """CLONE-07: Clone-of-clone works and shares cassette path and wipe state."""
        source = self._make_connection(tmp_path, mode="none")
        clone = source.adbc_clone()
        grandchild = clone.adbc_clone()

        assert isinstance(grandchild, ReplayConnection)
        assert grandchild._cassette_path is source._cassette_path
        assert grandchild._wipe_state is source._wipe_state

    def test_close_isolation(self, tmp_path: Path) -> None:
        """CLONE-08: Closing a clone does not affect source or cassette directory."""
        source = self._make_connection(tmp_path, mode="none")
        # Give source a mock real conn to verify it's not closed
        source_mock = MagicMock()
        source._real_conn = source_mock

        clone = source.adbc_clone()
        clone_mock = MagicMock()
        clone._real_conn = clone_mock

        clone.close()

        clone_mock.close.assert_called_once()
        source_mock.close.assert_not_called()
        assert source._cassette_path.exists()


class TestSharedWipeState:
    """Tests for shared wipe state across clones (CLONE-06)."""

    def test_first_cursor_wipes(self, tmp_path: Path) -> None:
        """CLONE-06: First cursor wipes cassette in 'all' mode; second clone cursor does not."""
        cassette = tmp_path / "cassette"
        # Pre-populate cassette with existing data that should be wiped
        table = pa.table({"old": [99]})
        _populate_cassette(cassette, "SELECT old", table)
        assert cassette.exists()

        # Create source in 'all' mode with a mock real connection
        source = ReplayConnection(
            driver_module_name="adbc_driver_test",
            db_kwargs={},
            mode="none",  # avoid real driver import
            cassette_path=cassette,
        )
        source._mode = "all"  # set mode after init to avoid driver import

        # Create mock real cursor for source
        mock_real_conn_source = MagicMock()
        mock_real_cursor_source = MagicMock()
        mock_real_cursor_source.fetch_arrow_table.return_value = pa.table({"x": [1]})
        mock_real_conn_source.cursor.return_value = mock_real_cursor_source
        source._real_conn = mock_real_conn_source

        # Create clone
        clone = source.adbc_clone()
        mock_real_conn_clone = MagicMock()
        mock_real_cursor_clone = MagicMock()
        mock_real_cursor_clone.fetch_arrow_table.return_value = pa.table({"x": [2]})
        mock_real_conn_clone.cursor.return_value = mock_real_cursor_clone
        clone._real_conn = mock_real_conn_clone

        # Source cursor executes first -- should wipe cassette dir
        source_cursor = source.cursor()
        source_cursor.execute("SELECT 1")

        # Cassette was wiped and new recording written
        assert source._wipe_state["wiped"] is True

        # Clone cursor executes second -- should NOT wipe again
        clone_cursor = clone.cursor()
        clone_cursor.execute("SELECT 1")

        # Verify wipe state is shared
        assert clone._wipe_state is source._wipe_state
        assert clone._wipe_state["wiped"] is True

        # The cassette should still have recordings from source's cursor
        # (if clone had wiped, source's recording would be gone)
        assert cassette.exists()
