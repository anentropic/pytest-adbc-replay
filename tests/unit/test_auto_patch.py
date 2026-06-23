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


class TestDifferentiatorKeysAutoPatch:
    """Auto-patch with cassette_differentiator_keys produces disambiguated paths."""

    def test_differentiator_segments_in_cassette_path(self, pytester: pytest.Pytester) -> None:
        """Verify driver='mysql' in db_kwargs produces /mysql/ segment in cassette path."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.adbc_cassette("diff_path_test")
            def test_differentiator_path(adbc_connect):
                # Pass driver='mysql' as a db_kwarg -- simulates Foundry usage.
                # The differentiator feature extracts it for cassette path.
                conn = adbc_connect("adbc_driver_sqlite.dbapi", driver="mysql")
                path_str = str(conn._cassette_path)
                # The path should contain /mysql after driver module name
                assert "/mysql" in path_str, (
                    f"Expected '/mysql' in cassette path, got: {path_str}"
                )
                # Verify driver module name appears in path before mysql
                idx_driver = path_str.index("adbc_driver_sqlite.dbapi")
                idx_mysql = path_str.index("mysql")
                assert idx_driver < idx_mysql, (
                    f"Expected driver module before mysql: {path_str}"
                )
            """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_no_differentiator_for_pypi_driver(self, pytester: pytest.Pytester) -> None:
        """PyPI drivers without 'driver' kwarg produce unchanged cassette paths."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.adbc_cassette("no_diff_test")
            def test_no_differentiator(adbc_connect):
                # Normal PyPI driver usage -- no driver= kwarg
                conn = adbc_connect("adbc_driver_sqlite.dbapi")
                path_str = str(conn._cassette_path)
                # The cassette path should end with the driver module name, no extra segments
                assert path_str.endswith("adbc_driver_sqlite.dbapi"), (
                    f"Expected path ending with driver module name, got: {path_str}"
                )
            """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_auto_patch_record_replay_with_differentiator(self, pytester: pytest.Pytester) -> None:
        """Record-then-replay cycle with auto-patch and differentiator key."""
        pytester.makeini("[pytest]\nadbc_auto_patch = adbc_driver_sqlite.dbapi\n")
        pytester.makepyfile(
            """
            import pytest
            import adbc_driver_sqlite.dbapi as driver

            @pytest.mark.adbc_cassette("auto_diff_test")
            def test_with_auto_patch():
                # Normal PyPI driver usage -- no driver= kwarg, no differentiator
                conn = driver.connect()
                cursor = conn.cursor()
                cursor.execute("SELECT 42 AS answer")
                result = cursor.fetch_arrow_table()
                assert result.column("answer").to_pylist() == [42]
            """
        )
        # Record
        record_result = pytester.runpytest("--adbc-record=once", "-v")
        record_result.assert_outcomes(passed=1)

        # Verify cassette created under driver subdir (no differentiator for PyPI driver)
        cassette_base = (
            pytester.path / "tests" / "cassettes" / "auto_diff_test" / "adbc_driver_sqlite.dbapi"
        )
        assert cassette_base.exists(), f"Expected cassette subdir at {cassette_base}"

        # Replay
        replay_result = pytester.runpytest("-v")
        replay_result.assert_outcomes(passed=1)


class TestPatchedConnectSignaturePreservation:
    """
    The patched connect() preserves the real driver's signature (functools.wraps).

    Regression for the downstream report where adbc-poolhouse introspects
    ``inspect.signature(driver.connect).parameters`` to choose its call
    convention: drivers exposing a ``db_kwargs=`` parameter ("Family A":
    Snowflake/Postgres/BigQuery/FlightSQL) are called ``connect(db_kwargs={...})``;
    others ("Family B": DuckDB/SQLite) get ``connect(**kwargs)``. Without
    ``functools.wraps`` the patched ``(**kwargs)`` signature hid ``db_kwargs``,
    so a Family-A driver was mis-detected as Family B and its options were
    flat-unpacked -- the real driver received ``db_kwargs=None`` ("account is
    empty"). Replay never opens a real connection so the mis-detection was
    invisible there; only record mode against a Family-A driver was hit.
    """

    # A fake "Family A" driver whose connect() mirrors the ADBC dbapi shape
    # (uri, db_kwargs, conn_kwargs, **kwargs) and records what it received so the
    # outer test can assert db_kwargs actually arrived populated.
    _FAKE_DRIVER_CONFTEST = """
        import sys
        import types
        from pathlib import Path

        _REC = Path(__file__).parent / "received_db_kwargs.txt"

        def connect(uri=None, db_kwargs=None, conn_kwargs=None, **kwargs):
            _REC.write_text(repr({"db_kwargs": db_kwargs, "kwargs": kwargs}))
            import pyarrow as pa

            cur = types.SimpleNamespace()
            cur.execute = lambda *a, **k: None
            cur.fetch_arrow_table = lambda: pa.table({"answer": [1]})
            cur.close = lambda: None
            cur.__enter__ = lambda s=cur: s
            cur.__exit__ = lambda *a: None
            rc = types.SimpleNamespace()
            rc.cursor = lambda *a, **k: cur
            rc.close = lambda: None
            return rc

        _mod = types.ModuleType("fake_family_a_driver.dbapi")
        _mod.connect = connect
        _parent = types.ModuleType("fake_family_a_driver")
        _parent.dbapi = _mod
        sys.modules["fake_family_a_driver"] = _parent
        sys.modules["fake_family_a_driver.dbapi"] = _mod
    """

    def test_signature_introspecting_caller_gets_db_kwargs_in_record_mode(
        self, pytester: pytest.Pytester
    ) -> None:
        """A poolhouse-style caller forwards db_kwargs to a Family-A driver in record mode."""
        pytester.makeconftest(self._FAKE_DRIVER_CONFTEST)
        pytester.makeini("[pytest]\nadbc_auto_patch = fake_family_a_driver.dbapi\n")
        pytester.makepyfile(
            """
            import inspect
            import pytest
            import fake_family_a_driver.dbapi as driver

            def _poolhouse_connect(mod, options):
                # Mirrors adbc-poolhouse: pick the call convention from the live signature.
                sig = inspect.signature(mod.connect)
                if "db_kwargs" in sig.parameters:
                    return mod.connect(db_kwargs=options)   # Family A
                return mod.connect(**options)               # Family B

            @pytest.mark.adbc_cassette("sig_preservation")
            def test_family_a_record():
                # Patched connect must still advertise db_kwargs so we stay on the Family-A path.
                assert "db_kwargs" in inspect.signature(driver.connect).parameters
                conn = _poolhouse_connect(
                    driver, {"adbc.snowflake.sql.account": "myorg-acct", "username": "u"}
                )
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    assert cur.fetch_arrow_table().column("answer").to_pylist() == [1]
            """
        )
        result = pytester.runpytest("--adbc-record=once", "-v")
        result.assert_outcomes(passed=1)

        received = (pytester.path / "received_db_kwargs.txt").read_text()
        assert "myorg-acct" in received, (
            f"Real driver should receive the account via db_kwargs, got: {received}"
        )
        # The options must arrive under db_kwargs=, not flat-unpacked into **kwargs.
        assert "'db_kwargs': None" not in received, (
            f"db_kwargs was dropped (flat-unpacked into **kwargs): {received}"
        )

    # A fake "manager"-style driver whose connect() takes the driver name as a
    # positional parameter (uri/driver first), mirroring
    # adbc_driver_manager.dbapi.connect(driver, ...). Records what it received.
    _FAKE_POSITIONAL_CONFTEST = """
        import sys
        import types
        from pathlib import Path

        _REC = Path(__file__).parent / "received_positional.txt"

        def connect(driver, db_kwargs=None, **kwargs):
            _REC.write_text(repr({"driver": driver, "db_kwargs": db_kwargs, "kwargs": kwargs}))
            import pyarrow as pa

            cur = types.SimpleNamespace()
            cur.execute = lambda *a, **k: None
            cur.fetch_arrow_table = lambda: pa.table({"answer": [1]})
            cur.close = lambda: None
            cur.__enter__ = lambda s=cur: s
            cur.__exit__ = lambda *a: None
            rc = types.SimpleNamespace()
            rc.cursor = lambda *a, **k: cur
            rc.close = lambda: None
            return rc

        _mod = types.ModuleType("fake_manager_driver.dbapi")
        _mod.connect = connect
        _parent = types.ModuleType("fake_manager_driver")
        _parent.dbapi = _mod
        sys.modules["fake_manager_driver"] = _parent
        sys.modules["fake_manager_driver.dbapi"] = _mod
    """

    def test_positional_connect_arg_forwarded_in_record_mode(
        self, pytester: pytest.Pytester
    ) -> None:
        """
        Positional connect() args (e.g. the driver path) reach the real driver.

        Because functools.wraps advertises the real signature, callers may pass
        the leading parameter positionally (as is idiomatic for
        ``adbc_driver_manager.dbapi.connect(driver, ...)``); the patched wrapper
        must accept and forward it rather than raising TypeError.
        """
        pytester.makeconftest(self._FAKE_POSITIONAL_CONFTEST)
        pytester.makeini("[pytest]\nadbc_auto_patch = fake_manager_driver.dbapi\n")
        pytester.makepyfile(
            """
            import pytest
            import fake_manager_driver.dbapi as driver

            @pytest.mark.adbc_cassette("positional_forward")
            def test_positional_record():
                # 'driver' passed positionally, options as db_kwargs.
                conn = driver.connect(
                    "/path/to/driver.so", db_kwargs={"adbc.x.account": "acct"}
                )
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    assert cur.fetch_arrow_table().column("answer").to_pylist() == [1]
            """
        )
        result = pytester.runpytest("--adbc-record=once", "-v")
        result.assert_outcomes(passed=1)

        received = (pytester.path / "received_positional.txt").read_text()
        assert "/path/to/driver.so" in received, (
            f"Positional driver arg should reach the real connect(), got: {received}"
        )
        assert "acct" in received, f"db_kwargs should also be forwarded, got: {received}"

    def test_positional_driver_resolves_cassette_differentiator(
        self, pytester: pytest.Pytester
    ) -> None:
        """
        A positionally-passed `driver` still drives the cassette differentiator subdir.

        The default differentiator key is ``driver``. When ``driver`` is passed
        positionally (``connect("mysql", ...)``) it lands in conn_args, not the
        keyword dict, so the patched wrapper resolves positional args back to their
        parameter names for differentiator lookup -- otherwise Foundry drivers
        sharing ``adbc_driver_manager.dbapi`` would collide on the same cassette path.
        """
        pytester.makeconftest(self._FAKE_POSITIONAL_CONFTEST)
        pytester.makeini("[pytest]\nadbc_auto_patch = fake_manager_driver.dbapi\n")
        pytester.makepyfile(
            """
            import pytest
            import fake_manager_driver.dbapi as driver

            @pytest.mark.adbc_cassette
            def test_positional_driver_differentiator():
                # 'mysql' passed positionally as the leading `driver` parameter.
                conn = driver.connect("mysql", db_kwargs={"adbc.x.account": "acct"})
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    assert cur.fetch_arrow_table().column("answer").to_pylist() == [1]
            """
        )
        result = pytester.runpytest("--adbc-record=once", "-v")
        result.assert_outcomes(passed=1)

        # A "mysql" differentiator subdir must appear under the driver-module dir.
        cassette_base = pytester.path / "tests" / "cassettes"
        mysql_dir = next(
            (
                p
                for p in cassette_base.rglob("*")
                if p.is_dir() and p.name == "mysql" and p.parent.name == "fake_manager_driver.dbapi"
            ),
            None,
        )
        assert mysql_dir is not None, (
            "Expected a 'mysql' differentiator subdir under the driver module dir; "
            f"tree: {sorted(str(p) for p in cassette_base.rglob('*'))}"
        )
