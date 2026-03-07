"""
Integration tests: record-then-replay cycle with Foundry MySQL driver.

Uses testcontainers to spin up a real MySQL instance, and the dbc CLI's
MySQL Foundry driver (adbc_driver_manager.dbapi with driver="mysql") to
exercise the full record-then-replay lifecycle.

These tests validate:
- Record-then-replay via wrap() with Foundry MySQL
- Record-then-replay via auto-patch with Foundry MySQL
- Cassette path differentiation (driver="mysql" produces correct subdir)

Prerequisites:
- Docker (for testcontainers)
- dbc CLI installed (https://columnar.tech)
- MySQL Foundry driver installed (dbc install mysql)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from typing import Any

pytestmark = pytest.mark.integration


class TestFoundryMySQLRecordReplay:
    """Full E2E record-then-replay cycle with Foundry MySQL driver."""

    def test_record_then_replay_via_wrap(
        self,
        pytester: pytest.Pytester,
        mysql_dsn: str,
        dbc_mysql_available: Any,
        adbc_driver_path: str | None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Record with Foundry MySQL via wrap(), then replay without a DB connection."""
        if adbc_driver_path:
            monkeypatch.setenv("ADBC_DRIVER_PATH", adbc_driver_path)
        pytester.makepyfile(
            f"""
            import pytest

            @pytest.fixture
            def db_conn(adbc_replay, request):
                return adbc_replay.wrap(
                    "adbc_driver_manager.dbapi",
                    db_kwargs={{"driver": "mysql", "uri": "{mysql_dsn}"}},
                    request=request,
                )

            def test_mysql_query(db_conn):
                cursor = db_conn.cursor()
                cursor.execute("SELECT 1 AS answer")
                result = cursor.fetch_arrow_table()
                assert result.column("answer").to_pylist() == [1]
        """
        )

        # Record pass: use the real MySQL container via Foundry driver
        record_result = pytester.runpytest("--adbc-record=once", "-v")
        record_result.assert_outcomes(passed=1)

        # Verify cassette was written
        cassette_base = pytester.path / "tests" / "cassettes"
        assert cassette_base.exists(), (
            f"Cassette directory not created after record run. Expected: {cassette_base}"
        )

        # Replay pass: no DB connection needed
        replay_result = pytester.runpytest("-v")
        replay_result.assert_outcomes(passed=1)

    def test_record_then_replay_via_auto_patch(
        self,
        pytester: pytest.Pytester,
        mysql_dsn: str,
        dbc_mysql_available: Any,
        adbc_driver_path: str | None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Record with Foundry MySQL via auto-patch, then replay."""
        if adbc_driver_path:
            monkeypatch.setenv("ADBC_DRIVER_PATH", adbc_driver_path)
        pytester.makeini(
            """
            [pytest]
            adbc_auto_patch =
                adbc_driver_manager.dbapi
        """
        )
        pytester.makepyfile(
            f"""
            import pytest
            import adbc_driver_manager.dbapi

            @pytest.mark.adbc_cassette
            def test_mysql_auto_patch():
                conn = adbc_driver_manager.dbapi.connect(
                    driver="mysql",
                    uri="{mysql_dsn}",
                )
                cursor = conn.cursor()
                cursor.execute("SELECT 1 AS answer")
                result = cursor.fetch_arrow_table()
                assert result.column("answer").to_pylist() == [1]
                conn.close()
        """
        )

        # Record pass
        record_result = pytester.runpytest("--adbc-record=once", "-v")
        record_result.assert_outcomes(passed=1)

        # Replay pass
        replay_result = pytester.runpytest("-v")
        replay_result.assert_outcomes(passed=1)

    def test_cassette_path_includes_mysql_differentiator(
        self,
        pytester: pytest.Pytester,
        mysql_dsn: str,
        dbc_mysql_available: Any,
        adbc_driver_path: str | None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        After recording, cassette files contain 'mysql' differentiator segment.

        The cassette path for Foundry drivers using driver="mysql" should include
        a "mysql" subdirectory under "adbc_driver_manager.dbapi" to disambiguate
        from other Foundry drivers sharing the same Python module.
        """
        if adbc_driver_path:
            monkeypatch.setenv("ADBC_DRIVER_PATH", adbc_driver_path)
        pytester.makeini(
            """
            [pytest]
            adbc_auto_patch =
                adbc_driver_manager.dbapi
        """
        )
        pytester.makepyfile(
            f"""
            import pytest
            import adbc_driver_manager.dbapi

            @pytest.mark.adbc_cassette
            def test_mysql_differentiator():
                conn = adbc_driver_manager.dbapi.connect(
                    driver="mysql",
                    uri="{mysql_dsn}",
                )
                cursor = conn.cursor()
                cursor.execute("SELECT 1 AS answer")
                result = cursor.fetch_arrow_table()
                assert result.column("answer").to_pylist() == [1]
                conn.close()
        """
        )

        # Record to create cassette files
        record_result = pytester.runpytest("--adbc-record=once", "-v")
        record_result.assert_outcomes(passed=1)

        # Check that the cassette path contains the mysql differentiator segment
        cassette_base = pytester.path / "tests" / "cassettes"
        assert cassette_base.exists(), "Cassette directory not created"

        # Walk the cassette directory to find the mysql differentiator path segment
        # Expected: .../adbc_driver_manager.dbapi/mysql/
        found_mysql_dir = False
        for path in cassette_base.rglob("*"):
            if path.is_dir() and path.name == "mysql":
                parent = path.parent
                if parent.name == "adbc_driver_manager.dbapi":
                    found_mysql_dir = True
                    # Verify there are cassette files inside
                    cassette_files = list(path.rglob("*.json"))
                    assert len(cassette_files) > 0, f"No cassette JSON files found under {path}"
                    break

        assert found_mysql_dir, (
            f"Expected cassette path with .../adbc_driver_manager.dbapi/mysql/ "
            f"but no such directory found under {cassette_base}. "
            f"Contents: {list(cassette_base.rglob('*'))}"
        )
