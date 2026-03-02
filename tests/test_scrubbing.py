"""Tests for the adbc_scrubber pipeline and adbc_scrub_keys config."""

from __future__ import annotations

from typing import Any

from pytest_adbc_replay._cursor import _apply_config_scrubbing, apply_scrubbing

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
