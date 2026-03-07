"""Tests for the adbc_scrubber pipeline and adbc_scrub_keys config."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from typing import Any
from unittest.mock import MagicMock

import pyarrow as pa
import pytest  # noqa: TC002

from pytest_adbc_replay._cassette_io import interaction_file_paths
from pytest_adbc_replay._cursor import ReplayCursor, _apply_config_scrubbing, apply_scrubbing

# ---------------------------------------------------------------------------
# Unit tests for _apply_config_scrubbing
# ---------------------------------------------------------------------------


class TestApplyConfigScrubbing:
    def test_no_scrub_keys_passes_through(self) -> None:
        params: dict[str, Any] = {"token": "abc", "x": 1}
        result = _apply_config_scrubbing(params, [], {}, "drv")
        assert result == {"token": "abc", "x": 1}

    def test_global_key_redacted(self) -> None:
        params: dict[str, Any] = {"token": "abc", "x": 1}
        result = _apply_config_scrubbing(params, ["token"], {}, "drv")
        assert result == {"token": "REDACTED", "x": 1}

    def test_per_driver_key_redacted(self) -> None:
        params: dict[str, Any] = {"acct": "x", "y": 2}
        result = _apply_config_scrubbing(params, [], {"drv": ["acct"]}, "drv")
        assert result == {"acct": "REDACTED", "y": 2}

    def test_wrong_driver_not_redacted(self) -> None:
        params: dict[str, Any] = {"acct": "secret"}
        result = _apply_config_scrubbing(params, [], {"other_drv": ["acct"]}, "drv")
        assert result == {"acct": "secret"}

    def test_list_params_skipped(self) -> None:
        params: list[Any] = [1, 2, "sensitive"]
        result = _apply_config_scrubbing(params, ["sensitive"], {}, "drv")
        assert result == [1, 2, "sensitive"]

    def test_none_params_skipped(self) -> None:
        result = _apply_config_scrubbing(None, ["token"], {}, "drv")
        assert result is None

    def test_key_not_in_params_ignored(self) -> None:
        params: dict[str, Any] = {"x": 1}
        result = _apply_config_scrubbing(params, ["missing"], {}, "drv")
        assert result == {"x": 1}

    def test_global_and_per_driver_union(self) -> None:
        params: dict[str, Any] = {"token": "tok", "acct": "act", "visible": "v"}
        result = _apply_config_scrubbing(params, ["token"], {"drv": ["acct"]}, "drv")
        assert result == {"token": "REDACTED", "acct": "REDACTED", "visible": "v"}

    def test_multiple_global_keys(self) -> None:
        params: dict[str, Any] = {"password": "pwd", "token": "tok", "user": "alice"}
        result = _apply_config_scrubbing(params, ["password", "token"], {}, "drv")
        assert result == {"password": "REDACTED", "token": "REDACTED", "user": "alice"}

    def test_does_not_mutate_original(self) -> None:
        params: dict[str, Any] = {"token": "abc"}
        original = dict(params)
        _apply_config_scrubbing(params, ["token"], {}, "drv")
        assert params == original  # Original unchanged


# ---------------------------------------------------------------------------
# Unit tests for apply_scrubbing (includes fixture scrubber)
# ---------------------------------------------------------------------------


class TestApplyScrubbing:
    def test_no_scrubbing_configured(self) -> None:
        params: dict[str, Any] = {"x": 1}
        result = apply_scrubbing(params, [], {}, "drv", None)
        assert result == {"x": 1}

    def test_fixture_scrubber_called_after_config(self) -> None:
        """Config scrubbing runs first; fixture receives already-scrubbed params."""
        calls: list[tuple[Any, str]] = []

        def scrubber(p: Any, driver_name: str) -> Any:
            calls.append((p, driver_name))
            return p

        params: dict[str, Any] = {"token": "abc", "x": 1}
        apply_scrubbing(params, ["token"], {}, "drv", scrubber)

        assert len(calls) == 1
        received_params, received_driver = calls[0]
        # Config scrubbing already ran: token is REDACTED in the dict the fixture sees
        assert received_params == {"token": "REDACTED", "x": 1}
        assert received_driver == "drv"

    def test_fixture_returning_none_keeps_config_result(self) -> None:
        """Fixture returning None -> config-scrubbed params written unchanged."""

        def scrubber(p: Any, driver_name: str) -> None:
            return None

        params: dict[str, Any] = {"token": "abc", "x": 1}
        result = apply_scrubbing(params, ["token"], {}, "drv", scrubber)
        assert result == {"token": "REDACTED", "x": 1}

    def test_fixture_returning_dict_wins(self) -> None:
        """Fixture return value replaces config-scrubbed params."""

        def scrubber(p: Any, driver_name: str) -> dict[str, Any]:
            return {"custom": "CUSTOM_REDACTED"}

        params: dict[str, Any] = {"token": "abc", "x": 1}
        result = apply_scrubbing(params, [], {}, "drv", scrubber)
        assert result == {"custom": "CUSTOM_REDACTED"}

    def test_list_params_skipped_by_both(self) -> None:
        params: list[int] = [1, 2]
        result = apply_scrubbing(params, ["token"], {}, "drv", None)
        assert result == [1, 2]

    def test_none_params_skipped_by_both(self) -> None:
        result = apply_scrubbing(None, ["token"], {}, "drv", None)
        assert result is None

    def test_fixture_receives_driver_name(self) -> None:
        received: list[str] = []

        def scrubber(p: Any, driver_name: str) -> Any:
            received.append(driver_name)
            return p

        apply_scrubbing({"x": 1}, [], {}, "adbc_driver_snowflake", scrubber)
        assert received == ["adbc_driver_snowflake"]


# ---------------------------------------------------------------------------
# Integration tests: ReplayCursor writes scrubbed params to cassette JSON
# ---------------------------------------------------------------------------


def _make_mock_cursor(result_table: pa.Table) -> MagicMock:
    """Create a mock ADBC cursor that returns the given table from fetch_arrow_table()."""
    mock = MagicMock()
    mock.fetch_arrow_table.return_value = result_table
    return mock


class TestScrubKeysIntegration:
    """End-to-end scrubbing pipeline: params written to cassette JSON are scrubbed."""

    def test_global_scrub_key_redacted_in_cassette(self, tmp_path: Path) -> None:
        """Global adbc_scrub_keys key causes value to appear as REDACTED in cassette JSON."""
        cassette = tmp_path / "test_global_scrub"
        result_table = pa.table({"n": [1]})
        mock_cursor = _make_mock_cursor(result_table)

        cursor = ReplayCursor(
            real_cursor=mock_cursor,
            mode="once",
            cassette_path=cassette,
            scrub_keys_global=["password"],
            driver_name="adbc_driver_test",
        )
        cursor.execute("SELECT 1", {"password": "secret123", "user": "alice"})

        # Verify cassette params JSON was written with REDACTED
        _, _, params_path = interaction_file_paths(cassette, 0)
        assert params_path.exists(), f"Expected params JSON at {params_path}"
        data = json.loads(params_path.read_text(encoding="utf-8"))
        assert data.get("password") == "REDACTED", f"Expected REDACTED, got: {data}"
        assert data.get("user") == "alice", "Non-scrubbed key should be unchanged"

    def test_per_driver_scrub_key_targets_correct_driver(self, tmp_path: Path) -> None:
        """Per-driver scrub key only redacts params for the matching driver."""
        cassette = tmp_path / "test_per_driver"
        result_table = pa.table({"n": [1]})
        mock_cursor = _make_mock_cursor(result_table)

        cursor = ReplayCursor(
            real_cursor=mock_cursor,
            mode="once",
            cassette_path=cassette,
            scrub_keys_per_driver={"adbc_driver_test": ["secret_key"]},
            driver_name="adbc_driver_test",
        )
        cursor.execute("SELECT 1", {"secret_key": "topsecret", "other": "visible"})

        _, _, params_path = interaction_file_paths(cassette, 0)
        data = json.loads(params_path.read_text(encoding="utf-8"))
        assert data.get("secret_key") == "REDACTED"
        assert data.get("other") == "visible"

    def test_per_driver_scrub_key_does_not_redact_wrong_driver(self, tmp_path: Path) -> None:
        """Per-driver scrub key for driver A does not redact params for driver B."""
        cassette = tmp_path / "test_wrong_driver"
        result_table = pa.table({"n": [1]})
        mock_cursor = _make_mock_cursor(result_table)

        cursor = ReplayCursor(
            real_cursor=mock_cursor,
            mode="once",
            cassette_path=cassette,
            scrub_keys_per_driver={"adbc_driver_snowflake": ["secret_key"]},
            driver_name="adbc_driver_sqlite",
        )
        cursor.execute("SELECT 1", {"secret_key": "should_be_visible"})

        _, _, params_path = interaction_file_paths(cassette, 0)
        data = json.loads(params_path.read_text(encoding="utf-8"))
        assert data.get("secret_key") == "should_be_visible"

    def test_none_params_written_as_null(self, tmp_path: Path) -> None:
        """None params (no parameters) are written as JSON null — not touched by scrubbing."""
        cassette = tmp_path / "test_none_params"
        result_table = pa.table({"n": [1]})
        mock_cursor = _make_mock_cursor(result_table)

        cursor = ReplayCursor(
            real_cursor=mock_cursor,
            mode="once",
            cassette_path=cassette,
            scrub_keys_global=["token"],
            driver_name="adbc_driver_test",
        )
        cursor.execute("SELECT 1")  # No params

        _, _, params_path = interaction_file_paths(cassette, 0)
        data = json.loads(params_path.read_text(encoding="utf-8"))
        assert data is None, f"Expected null for no params, got: {data}"

    def test_fixture_scrubber_called_at_record_time(self, tmp_path: Path) -> None:
        """adbc_scrubber callable is invoked with (params, driver_name) during record."""
        cassette = tmp_path / "test_scrubber_called"
        result_table = pa.table({"n": [1]})
        mock_cursor = _make_mock_cursor(result_table)

        calls: list[tuple[Any, str | None]] = []

        def scrubber(params: Any, driver_name: str | None) -> Any:
            calls.append((params, driver_name))
            return params

        cursor = ReplayCursor(
            real_cursor=mock_cursor,
            mode="once",
            cassette_path=cassette,
            driver_name="adbc_driver_snowflake",
            scrubber=scrubber,
        )
        cursor.execute("SELECT 1", {"x": 1})

        assert len(calls) == 1, "scrubber should have been called exactly once"
        received_params, received_driver = calls[0]
        assert received_params == {"x": 1}
        assert received_driver == "adbc_driver_snowflake"

    def test_fixture_scrubber_return_wins_over_config(self, tmp_path: Path) -> None:
        """adbc_scrubber return value replaces the config-scrubbed params in cassette."""
        cassette = tmp_path / "test_scrubber_return_wins"
        result_table = pa.table({"n": [1]})
        mock_cursor = _make_mock_cursor(result_table)

        def scrubber(params: Any, driver_name: str | None) -> dict[str, Any]:
            # Return a completely custom dict, ignoring config-scrubbed result
            return {"custom_key": "CUSTOM_REDACTED"}

        cursor = ReplayCursor(
            real_cursor=mock_cursor,
            mode="once",
            cassette_path=cassette,
            scrub_keys_global=["token"],
            driver_name="adbc_driver_test",
            scrubber=scrubber,
        )
        cursor.execute("SELECT 1", {"token": "secret", "extra": "data"})

        _, _, params_path = interaction_file_paths(cassette, 0)
        data = json.loads(params_path.read_text(encoding="utf-8"))
        assert data == {"custom_key": "CUSTOM_REDACTED"}

    def test_global_and_per_driver_keys_combined(self, tmp_path: Path) -> None:
        """Global keys and per-driver keys are unioned for scrubbing."""
        cassette = tmp_path / "test_combined_keys"
        result_table = pa.table({"n": [1]})
        mock_cursor = _make_mock_cursor(result_table)

        cursor = ReplayCursor(
            real_cursor=mock_cursor,
            mode="once",
            cassette_path=cassette,
            scrub_keys_global=["token"],
            scrub_keys_per_driver={"adbc_driver_test": ["account_id"]},
            driver_name="adbc_driver_test",
        )
        cursor.execute("SELECT 1", {"token": "tok", "account_id": "acct", "visible": "v"})

        _, _, params_path = interaction_file_paths(cassette, 0)
        data = json.loads(params_path.read_text(encoding="utf-8"))
        assert data.get("token") == "REDACTED"
        assert data.get("account_id") == "REDACTED"
        assert data.get("visible") == "v"


# ---------------------------------------------------------------------------
# Pytester integration: adbc_scrubber fixture callable via plugin
# ---------------------------------------------------------------------------


class TestScrubberFixturePytester:
    """Pytester tests proving adbc_scrubber fixture is wired through the plugin."""

    def test_scrubber_two_arg_callable_stored(self, pytester: pytest.Pytester) -> None:
        """Overriding adbc_scrubber with a two-arg callable is stored on ReplaySession."""
        pytester.makeconftest(
            """
            import pytest

            @pytest.fixture(scope="session")
            def adbc_scrubber():
                def scrub(params, driver_name):
                    return params
                return scrub
            """
        )
        pytester.makepyfile(
            """
            def test_scrubber_stored(adbc_replay):
                assert adbc_replay.scrubber is not None
                assert callable(adbc_replay.scrubber)
            """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_scrub_keys_ini_sets_global_keys_on_session(self, pytester: pytest.Pytester) -> None:
        """adbc_scrub_keys ini key is parsed and stored as scrub_keys_global on ReplaySession."""
        pytester.makeini("[pytest]\nadbc_scrub_keys = token password\n")
        pytester.makepyfile(
            """
            def test_scrub_keys(adbc_replay):
                assert "token" in adbc_replay.scrub_keys_global
                assert "password" in adbc_replay.scrub_keys_global
            """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_per_driver_scrub_keys_ini_sets_per_driver_on_session(
        self, pytester: pytest.Pytester
    ) -> None:
        """Per-driver adbc_scrub_keys ini line parsed into scrub_keys_per_driver on session."""
        pytester.makeini(
            "[pytest]\nadbc_scrub_keys = adbc_driver_snowflake: account_id warehouse\n"
        )
        pytester.makepyfile(
            """
            def test_per_driver_keys(adbc_replay):
                drv_keys = adbc_replay.scrub_keys_per_driver
                assert "adbc_driver_snowflake" in drv_keys
                assert "account_id" in drv_keys["adbc_driver_snowflake"]
                assert "warehouse" in drv_keys["adbc_driver_snowflake"]
            """
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)
