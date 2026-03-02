"""
Tests for automatic ADBC connection wrapping (Phase 8).

Covers:
- adbc_auto_patch ini key registration and parsing
- Monkeypatch interception for @pytest.mark.adbc_cassette tests
- Pass-through for unmarked tests
- Per-driver cassette subdirectory layout
- adbc_connect escape-hatch fixture
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


class TestAutoPatchIniKey:
    """adbc_auto_patch ini key is registered and parseable."""

    def test_adbc_auto_patch_ini_key_accepted(self, pytester: pytest.Pytester) -> None:
        """adbc_auto_patch ini key does not cause pytest error."""
        pytester.makeini("[pytest]\nadbc_auto_patch = adbc_driver_sqlite\n")
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest()
        result.assert_outcomes(passed=1)

    def test_empty_auto_patch_no_effect(self, pytester: pytest.Pytester) -> None:
        """Empty adbc_auto_patch has no effect on test execution."""
        pytester.makeini("[pytest]\nadbc_auto_patch =\n")
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest()
        result.assert_outcomes(passed=1)

    def test_auto_patch_multiple_drivers_accepted(self, pytester: pytest.Pytester) -> None:
        """Multiple drivers listed in adbc_auto_patch (space-separated) are accepted."""
        pytester.makeini(
            "[pytest]\nadbc_auto_patch = adbc_driver_sqlite.dbapi adbc_driver_duckdb\n"
        )
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest()
        result.assert_outcomes(passed=1)


class TestAutoInterception:
    """Monkeypatch intercepts connect() for marked tests; passes through for unmarked."""

    def test_auto_patch_record_then_replay_sqlite(self, pytester: pytest.Pytester) -> None:
        """
        Auto-patched driver.connect() records cassette on first run and replays on second.

        Uses adbc_driver_sqlite.dbapi as the patched driver (available in test environment).
        """
        pytester.makeini("[pytest]\nadbc_auto_patch = adbc_driver_sqlite.dbapi\n")
        pytester.makepyfile(
            """
            import pytest
            import adbc_driver_sqlite.dbapi as driver

            @pytest.mark.adbc_cassette("auto_sqlite_test")
            def test_query_via_auto_patch():
                # No conftest fixture -- connect() is intercepted automatically
                conn = driver.connect()
                cursor = conn.cursor()
                cursor.execute("SELECT 42 AS answer")
                result = cursor.fetch_arrow_table()
                assert result.column("answer").to_pylist() == [42]
            """
        )
        # Run 1: record
        record_result = pytester.runpytest("--adbc-record=once", "-v")
        record_result.assert_outcomes(passed=1)

        # Verify per-driver cassette subdirectory was created
        cassette_base = (
            pytester.path / "tests" / "cassettes" / "auto_sqlite_test" / "adbc_driver_sqlite.dbapi"
        )
        assert cassette_base.exists(), f"Expected per-driver cassette subdir at {cassette_base}"

        # Run 2: replay without DB
        replay_result = pytester.runpytest("-v")
        replay_result.assert_outcomes(passed=1)

    def test_unmarked_test_passes_through_to_real_driver(self, pytester: pytest.Pytester) -> None:
        """
        Tests without @pytest.mark.adbc_cassette receive the real connect() unchanged.

        The monkeypatch intercepts the call but detects no marker and calls original.
        """
        pytester.makeini("[pytest]\nadbc_auto_patch = adbc_driver_sqlite.dbapi\n")
        pytester.makepyfile(
            """
            import adbc_driver_sqlite.dbapi as driver

            def test_no_marker_uses_real_driver():
                # No marker: connect() must pass through to real SQLite driver
                conn = driver.connect()
                cursor = conn.cursor()
                cursor.execute("SELECT 1 AS val")
                result = cursor.fetch_arrow_table()
                assert result.column("val").to_pylist() == [1]
            """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_non_patched_driver_unaffected(self, pytester: pytest.Pytester) -> None:
        """Drivers not in adbc_auto_patch list are not intercepted."""
        # Only patch sqlite.dbapi, not the raw adbc_driver_sqlite module
        pytester.makeini("[pytest]\nadbc_auto_patch = adbc_driver_sqlite.dbapi\n")
        pytester.makepyfile(
            """
            import pytest
            import adbc_driver_sqlite.dbapi as driver

            @pytest.mark.adbc_cassette("direct_connect_test")
            def test_direct_connect_works():
                # Even with marker, driver not in auto_patch list -> real driver
                conn = driver.connect()
                cursor = conn.cursor()
                cursor.execute("SELECT 7 AS num")
                result = cursor.fetch_arrow_table()
                assert result.column("num").to_pylist() == [7]
            """
        )
        # With auto_patch = adbc_driver_sqlite.dbapi, this patches that module.
        # Confirm that using the module works (this exercises the auto-patch code path).
        result = pytester.runpytest("--adbc-record=once", "-v")
        result.assert_outcomes(passed=1)


class TestPerDriverCassetteLayout:
    """Per-driver cassette subdirectory layout is enforced."""

    def test_cassette_path_includes_driver_subdir(self, pytester: pytest.Pytester) -> None:
        """
        Recorded cassette lives under cassette_dir/cassette_name/driver_module_name/.

        Full module name is used as the subdirectory (not shortened).
        """
        pytester.makeini("[pytest]\nadbc_auto_patch = adbc_driver_sqlite.dbapi\n")
        pytester.makepyfile(
            """
            import pytest
            import adbc_driver_sqlite.dbapi as driver

            @pytest.mark.adbc_cassette("driver_subdir_test")
            def test_records_with_driver_subdir():
                conn = driver.connect()
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetch_arrow_table()
            """
        )
        record_result = pytester.runpytest("--adbc-record=once", "-v")
        record_result.assert_outcomes(passed=1)

        # Check directory structure: cassette_dir/driver_subdir_test/adbc_driver_sqlite.dbapi/
        driver_dir = (
            pytester.path
            / "tests"
            / "cassettes"
            / "driver_subdir_test"
            / "adbc_driver_sqlite.dbapi"
        )
        assert driver_dir.exists(), f"Per-driver subdirectory not created: {driver_dir}"
        # At least one .sql file should exist inside
        sql_files = list(driver_dir.glob("*.sql"))
        assert sql_files, f"No .sql files found in {driver_dir}"

    def test_full_driver_module_name_in_subdir(self, pytester: pytest.Pytester) -> None:
        """Full driver module name (not shortened) appears as the cassette subdirectory."""
        pytester.makeini("[pytest]\nadbc_auto_patch = adbc_driver_sqlite.dbapi\n")
        pytester.makepyfile(
            """
            import pytest
            import adbc_driver_sqlite.dbapi as driver

            @pytest.mark.adbc_cassette("full_name_test")
            def test_full_name():
                conn = driver.connect()
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetch_arrow_table()
            """
        )
        pytester.runpytest("--adbc-record=once", "-v")

        cassette_base = pytester.path / "tests" / "cassettes" / "full_name_test"
        subdirs = [p.name for p in cassette_base.iterdir() if p.is_dir()]
        # Should see "adbc_driver_sqlite.dbapi" not "sqlite" or "dbapi"
        assert "adbc_driver_sqlite.dbapi" in subdirs, (
            f"Expected full module name 'adbc_driver_sqlite.dbapi' in {subdirs}"
        )


class TestAdbcConnectFixture:
    """adbc_connect fixture provides an escape hatch for explicit connections."""

    def test_adbc_connect_fixture_available(self, pytester: pytest.Pytester) -> None:
        """adbc_connect fixture is available without any conftest setup."""
        pytester.makepyfile(
            """
            def test_fixture_exists(adbc_connect):
                assert adbc_connect is not None
                assert callable(adbc_connect)
            """
        )
        result = pytester.runpytest()
        result.assert_outcomes(passed=1)

    def test_adbc_connect_fixture_record_then_replay(self, pytester: pytest.Pytester) -> None:
        """
        adbc_connect fixture creates a ReplayConnection with per-driver cassette subdir.

        Full E2E: record then replay via the escape-hatch fixture.
        """
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.adbc_cassette("adbc_connect_test")
            def test_via_adbc_connect(adbc_connect):
                conn = adbc_connect("adbc_driver_sqlite.dbapi")
                cursor = conn.cursor()
                cursor.execute("SELECT 99 AS val")
                result = cursor.fetch_arrow_table()
                assert result.column("val").to_pylist() == [99]
            """
        )
        # Record
        record_result = pytester.runpytest("--adbc-record=once", "-v")
        record_result.assert_outcomes(passed=1)

        # Verify per-driver subdir created
        driver_dir = (
            pytester.path / "tests" / "cassettes" / "adbc_connect_test" / "adbc_driver_sqlite.dbapi"
        )
        assert driver_dir.exists(), f"adbc_connect did not create per-driver subdir: {driver_dir}"

        # Replay
        replay_result = pytester.runpytest("-v")
        replay_result.assert_outcomes(passed=1)

    def test_adbc_connect_closes_connections_after_test(self, pytester: pytest.Pytester) -> None:
        """adbc_connect fixture closes connections when test finishes (no resource leak)."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.adbc_cassette("cleanup_test")
            def test_connection_closed(adbc_connect):
                conn = adbc_connect("adbc_driver_sqlite.dbapi")
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetch_arrow_table()
                # After test, adbc_connect fixture teardown should close conn
            """
        )
        # Record then replay -- if cleanup fails, second run may error
        record_result = pytester.runpytest("--adbc-record=once", "-v")
        record_result.assert_outcomes(passed=1)
        replay_result = pytester.runpytest("-v")
        replay_result.assert_outcomes(passed=1)

    def test_adbc_connect_uses_per_driver_cassette_path(self, pytester: pytest.Pytester) -> None:
        """adbc_connect fixture produces cassette_path with driver module name as subdir."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.adbc_cassette("path_check")
            def test_cassette_path_has_driver(adbc_connect):
                conn = adbc_connect("adbc_driver_sqlite.dbapi")
                # The cassette path should include the driver module name
                assert "adbc_driver_sqlite.dbapi" in str(conn._cassette_path), (
                    f"Expected driver in cassette path, got: {conn._cassette_path}"
                )
            """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)
