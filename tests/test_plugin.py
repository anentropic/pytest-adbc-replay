"""
Integration tests for pytest-adbc-replay plugin auto-discovery and hooks.

Uses the pytester fixture (built-in to pytest 9.x) to run a pytest subprocess
and verify the plugin is loaded, the fixture is available, and the CLI option works.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_adbc_replay.plugin import _parse_scrub_keys

if TYPE_CHECKING:
    import pytest


class TestPluginDiscovery:
    """INFRA-01: Plugin is discoverable via pytest11 entry point."""

    def test_adbc_replay_fixture_available(self, pytester: pytest.Pytester) -> None:
        """adbc_replay fixture is available without manual imports."""
        pytester.makepyfile(
            """
            def test_fixture_available(adbc_replay):
                assert adbc_replay is not None
        """
        )
        result = pytester.runpytest()
        result.assert_outcomes(passed=1)

    def test_adbc_replay_is_session_scoped(self, pytester: pytest.Pytester) -> None:
        """adbc_replay fixture is session-scoped (same instance across tests)."""
        pytester.makepyfile(
            """
            _instances = []

            def test_first(adbc_replay):
                _instances.append(id(adbc_replay))

            def test_second(adbc_replay):
                _instances.append(id(adbc_replay))

            def test_same_instance():
                assert len(_instances) == 2
                assert _instances[0] == _instances[1], "adbc_replay must be session-scoped"
        """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=3)


class TestCLIOption:
    """INFRA-02: --adbc-record CLI flag."""

    def test_adbc_record_option_accepted(self, pytester: pytest.Pytester) -> None:
        """--adbc-record is a recognised pytest CLI option."""
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest("--adbc-record=none")
        result.assert_outcomes(passed=1)

    def test_adbc_record_all_mode(self, pytester: pytest.Pytester) -> None:
        """--adbc-record=all is accepted as a valid choice."""
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest("--adbc-record=all")
        result.assert_outcomes(passed=1)

    def test_adbc_record_once_mode(self, pytester: pytest.Pytester) -> None:
        """--adbc-record=once is accepted."""
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest("--adbc-record=once")
        result.assert_outcomes(passed=1)

    def test_adbc_record_new_episodes_mode(self, pytester: pytest.Pytester) -> None:
        """--adbc-record=new_episodes is accepted."""
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest("--adbc-record=new_episodes")
        result.assert_outcomes(passed=1)

    def test_invalid_mode_rejected(self, pytester: pytest.Pytester) -> None:
        """--adbc-record=invalid is rejected by pytest."""
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest("--adbc-record=invalid")
        assert result.ret != 0


class TestMarkerRegistration:
    """INFRA-04, INFRA-05: adbc_cassette marker is registered."""

    def test_marker_no_warning(self, pytester: pytest.Pytester) -> None:
        """@pytest.mark.adbc_cassette does not produce PytestUnknownMarkWarning."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.adbc_cassette("my_cassette")
            def test_with_marker():
                pass
        """
        )
        result = pytester.runpytest("-W", "error::pytest.PytestUnknownMarkWarning")
        result.assert_outcomes(passed=1)

    def test_marker_with_dialect_kwarg(self, pytester: pytest.Pytester) -> None:
        """@pytest.mark.adbc_cassette with dialect= kwarg is accepted."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.adbc_cassette("my_cassette", dialect="snowflake")
            def test_with_dialect():
                pass
        """
        )
        result = pytester.runpytest("-W", "error::pytest.PytestUnknownMarkWarning")
        result.assert_outcomes(passed=1)

    def test_marker_on_class_applies_to_methods(self, pytester: pytest.Pytester) -> None:
        """@pytest.mark.adbc_cassette on class applies to all its methods."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.adbc_cassette("class_cassette")
            class TestWithClassMarker:
                def test_method_one(self, adbc_replay, request):
                    marker = request.node.get_closest_marker("adbc_cassette")
                    assert marker is not None
                    assert marker.args[0] == "class_cassette"

                def test_method_two(self, adbc_replay, request):
                    marker = request.node.get_closest_marker("adbc_cassette")
                    assert marker is not None
        """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)


class TestCassettePathResolution:
    """INFRA-06: Cassette path derived from node ID when no marker."""

    def test_wrap_without_marker_uses_node_id(self, pytester: pytest.Pytester) -> None:
        """When no adbc_cassette marker, wrap() derives path from node ID."""
        pytester.makepyfile(
            """
            import pytest
            from pathlib import Path

            def test_cassette_path_from_node_id(adbc_replay, request):
                conn = adbc_replay.wrap(
                    "adbc_driver_nonexistent",
                    request=request,
                )
                # cassette_path should include the test name
                assert "test_cassette_path_from_node_id" in str(conn._cassette_path)
        """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_wrap_with_marker_uses_marker_name(self, pytester: pytest.Pytester) -> None:
        """When adbc_cassette marker present, wrap() uses marker name."""
        pytester.makepyfile(
            """
            import pytest

            @pytest.mark.adbc_cassette("custom_name")
            def test_uses_custom_name(adbc_replay, request):
                conn = adbc_replay.wrap(
                    "adbc_driver_nonexistent",
                    request=request,
                )
                assert "custom_name" in str(conn._cassette_path)
        """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestReplayModeNoDriver:
    """PROXY-02, PROXY-03, PROXY-04: replay mode works without ADBC driver."""

    def test_replay_mode_passes_without_adbc_driver(self, pytester: pytest.Pytester) -> None:
        """Tests using replay-only mode pass even with no ADBC driver installed."""
        # Pre-populate a cassette so execute() finds data to replay
        import pyarrow as pa

        from pytest_adbc_replay._cassette_io import (
            interaction_file_paths,
            write_arrow_table,
            write_params_json,
            write_sql_file,
        )
        from pytest_adbc_replay._normaliser import normalise_sql

        # The cassette path for pytester is derived from node ID:
        # test_replay_mode_passes_without_adbc_driver.py::test_replay_without_driver
        # -> tests/cassettes/test_replay_mode_passes_without_adbc_driver/test_replay_without_driver
        cassette_dir = pytester.path / "tests" / "cassettes"
        cassette_path = (
            cassette_dir
            / "test_replay_mode_passes_without_adbc_driver"
            / "test_replay_without_driver"
        )
        cassette_path.mkdir(parents=True, exist_ok=True)

        canonical = normalise_sql("SELECT 1")
        sql_path, arrow_path, params_path = interaction_file_paths(cassette_path, 0)
        write_sql_file(canonical, sql_path)
        write_arrow_table(pa.table({"result": [1]}), arrow_path)
        write_params_json(None, params_path)

        pytester.makepyfile(
            """
            import pytest

            def test_replay_without_driver(adbc_replay, request):
                # 'adbc_driver_completely_nonexistent' does not exist.
                # In replay mode (none), it must never be imported.
                conn = adbc_replay.wrap(
                    "adbc_driver_completely_nonexistent",
                    request=request,
                )
                cursor = conn.cursor()
                cursor.execute("SELECT 1")  # replays from cassette
                results = cursor.fetchall()
                assert isinstance(results, list)
                assert len(results) == 1
        """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestIniConfig:
    """CONF-01, CONF-02, CONF-03: pyproject.toml/pytest.ini configuration."""

    def test_cassette_dir_from_ini(self, pytester: pytest.Pytester) -> None:
        """CONF-01: adbc_cassette_dir ini key is used as cassette directory."""
        pytester.makeini("[pytest]\nadbc_cassette_dir = custom_cassettes\n")
        pytester.makepyfile(
            """
            from pathlib import Path

            def test_cassette_dir(adbc_replay):
                assert adbc_replay.cassette_dir == Path("custom_cassettes"), (
                    f"Expected custom_cassettes, got {adbc_replay.cassette_dir!r}"
                )
        """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_record_mode_from_ini(self, pytester: pytest.Pytester) -> None:
        """CONF-02: adbc_record_mode ini key is used when --adbc-record not passed."""
        pytester.makeini("[pytest]\nadbc_record_mode = once\n")
        pytester.makepyfile(
            """
            def test_mode(adbc_replay):
                assert adbc_replay.mode == "once", (
                    f"Expected once, got {adbc_replay.mode!r}"
                )
        """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_cli_overrides_ini(self, pytester: pytest.Pytester) -> None:
        """CONF-02: CLI --adbc-record takes precedence over adbc_record_mode ini."""
        pytester.makeini("[pytest]\nadbc_record_mode = once\n")
        pytester.makepyfile(
            """
            def test_mode(adbc_replay):
                assert adbc_replay.mode == "all", (
                    f"Expected all (CLI override), got {adbc_replay.mode!r}"
                )
        """
        )
        result = pytester.runpytest("--adbc-record=all", "-v")
        result.assert_outcomes(passed=1)

    def test_dialect_from_ini(self, pytester: pytest.Pytester) -> None:
        """CONF-03: adbc_dialect ini key sets global SQL dialect on ReplaySession."""
        pytester.makeini("[pytest]\nadbc_dialect = snowflake\n")
        pytester.makepyfile(
            """
            def test_dialect(adbc_replay):
                assert adbc_replay.dialect_global == "snowflake", (
                    f"Expected snowflake, got {adbc_replay.dialect_global!r}"
                )
        """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_empty_dialect_means_none(self, pytester: pytest.Pytester) -> None:
        """CONF-03: No adbc_dialect in ini means dialect_global=None on ReplaySession."""
        pytester.makepyfile(
            """
            def test_dialect(adbc_replay):
                assert adbc_replay.dialect_global is None, (
                    f"Expected None, got {adbc_replay.dialect_global!r}"
                )
        """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestReportHeader:
    """DX-01: Record mode printed in pytest header output."""

    def test_header_contains_mode_default(self, pytester: pytest.Pytester) -> None:
        """Header shows 'adbc-replay: record mode = none' with default settings."""
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)
        assert "adbc-replay: record mode = none" in result.stdout.str(), (
            f"Expected header line in stdout. Got:\n{result.stdout.str()}"
        )

    def test_header_reflects_ini_mode(self, pytester: pytest.Pytester) -> None:
        """Header shows ini-configured mode when --adbc-record not passed."""
        pytester.makeini("[pytest]\nadbc_record_mode = once\n")
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)
        assert "adbc-replay: record mode = once" in result.stdout.str(), (
            f"Expected 'once' in header. Got:\n{result.stdout.str()}"
        )

    def test_header_reflects_cli_mode(self, pytester: pytest.Pytester) -> None:
        """Header shows CLI-supplied mode (CLI wins over ini)."""
        pytester.makeini("[pytest]\nadbc_record_mode = once\n")
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest("--adbc-record=all", "-v")
        result.assert_outcomes(passed=1)
        assert "adbc-replay: record mode = all" in result.stdout.str(), (
            f"Expected 'all' in header. Got:\n{result.stdout.str()}"
        )


class TestScrubberFixture:
    """DX-02: adbc_scrubber fixture and ReplaySession.scrubber storage."""

    def test_scrubber_is_none_by_default(self, pytester: pytest.Pytester) -> None:
        """adbc_scrubber returns None by default; ReplaySession.scrubber is None."""
        pytester.makepyfile(
            """
            def test_scrubber(adbc_replay):
                assert adbc_replay.scrubber is None, (
                    f"Expected None, got {adbc_replay.scrubber!r}"
                )
        """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_scrubber_stored_when_overridden(self, pytester: pytest.Pytester) -> None:
        """Overriding adbc_scrubber in conftest causes ReplaySession.scrubber to be set."""
        pytester.makeconftest(
            """
            import pytest

            @pytest.fixture(scope="session")
            def adbc_scrubber():
                def my_scrubber(params, driver_name):
                    return params
                return my_scrubber
        """
        )
        pytester.makepyfile(
            """
            def test_scrubber(adbc_replay):
                assert adbc_replay.scrubber is not None, "scrubber should be set"
                assert callable(adbc_replay.scrubber), "scrubber should be callable"
        """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestParseScrupKeys:
    """Unit tests for _parse_scrub_keys helper."""

    def test_empty_list_returns_empty(self) -> None:
        """Empty input -> empty global keys and empty per-driver dict."""
        global_keys, per_driver = _parse_scrub_keys([])
        assert global_keys == []
        assert per_driver == {}

    def test_blank_lines_ignored(self) -> None:
        """Blank and whitespace-only lines are ignored."""
        global_keys, per_driver = _parse_scrub_keys(["", "   ", "\t"])
        assert global_keys == []
        assert per_driver == {}

    def test_global_keys_single_line(self) -> None:
        """Single line with no colon -> all tokens are global keys."""
        global_keys, per_driver = _parse_scrub_keys(["token password api_key"])
        assert global_keys == ["token", "password", "api_key"]
        assert per_driver == {}

    def test_global_keys_multiple_lines(self) -> None:
        """Multiple global lines accumulate into a single flat list."""
        global_keys, per_driver = _parse_scrub_keys(["token", "password secret"])
        assert global_keys == ["token", "password", "secret"]
        assert per_driver == {}

    def test_per_driver_single_line(self) -> None:
        """Colon-prefixed line -> per-driver keys for that driver."""
        global_keys, per_driver = _parse_scrub_keys(["adbc_driver_snowflake: account_id warehouse"])
        assert global_keys == []
        assert per_driver == {"adbc_driver_snowflake": ["account_id", "warehouse"]}

    def test_per_driver_multiple_drivers(self) -> None:
        """Multiple colon-prefixed lines build separate per-driver lists."""
        global_keys, per_driver = _parse_scrub_keys(
            [
                "adbc_driver_snowflake: account_id",
                "adbc_driver_duckdb: secret",
            ]
        )
        assert global_keys == []
        assert per_driver == {
            "adbc_driver_snowflake": ["account_id"],
            "adbc_driver_duckdb": ["secret"],
        }

    def test_global_and_per_driver_coexist(self) -> None:
        """Global and per-driver forms can coexist in the same linelist."""
        global_keys, per_driver = _parse_scrub_keys(["token", "adbc_driver_snowflake: account_id"])
        assert global_keys == ["token"]
        assert per_driver == {"adbc_driver_snowflake": ["account_id"]}

    def test_same_driver_multiple_lines_accumulated(self) -> None:
        """Multiple per-driver lines for the same driver accumulate keys."""
        global_keys, per_driver = _parse_scrub_keys(
            [
                "adbc_driver_snowflake: account_id",
                "adbc_driver_snowflake: warehouse",
            ]
        )
        assert global_keys == []
        assert per_driver == {"adbc_driver_snowflake": ["account_id", "warehouse"]}

    def test_colon_only_line_ignored(self) -> None:
        """A line with colon but empty driver or empty keys is ignored."""
        global_keys, per_driver = _parse_scrub_keys([": key1"])  # empty driver
        assert global_keys == []
        assert per_driver == {}

    def test_driver_with_no_keys_ignored(self) -> None:
        """A line with driver name but no keys after colon is ignored."""
        global_keys, per_driver = _parse_scrub_keys(["adbc_driver_snowflake: "])
        assert global_keys == []
        assert per_driver == {}
