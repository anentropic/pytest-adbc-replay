"""
End-to-end integration test: record-then-replay cycle using adbc-driver-sqlite.

Uses the pytester fixture to run two real pytest subprocess invocations:
  1. Record pass: --adbc-record=once with a live in-memory SQLite connection
  2. Replay pass: default mode=none with no DB connection

This validates the full plugin lifecycle end-to-end against a real ADBC driver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


class TestRecordThenReplayCycle:
    """Full E2E record-then-replay cycle against adbc-driver-sqlite."""

    def test_record_then_replay_sqlite(self, pytester: pytest.Pytester) -> None:
        """Record with adbc-driver-sqlite then replay without a DB connection."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.fixture
            def db_conn(adbc_replay, request):
                return adbc_replay.wrap(
                    "adbc_driver_sqlite.dbapi",
                    request=request,
                )

            def test_sqlite_query(db_conn):
                cursor = db_conn.cursor()
                cursor.execute("SELECT 1 AS answer")
                result = cursor.fetch_arrow_table()
                assert result.column("answer").to_pylist() == [1]
        """
        )

        # Run 1: record the cassette using a real in-memory SQLite connection
        record_result = pytester.runpytest("--adbc-record=once", "-v")
        record_result.assert_outcomes(passed=1)

        # Confirm the cassette was written to disk before attempting replay
        cassette_base = pytester.path / "tests" / "cassettes"
        assert cassette_base.exists(), (
            f"Cassette directory not created after record run. Expected: {cassette_base}"
        )

        # Run 2: replay from cassette -- no DB connection opened
        replay_result = pytester.runpytest("-v")
        replay_result.assert_outcomes(passed=1)
