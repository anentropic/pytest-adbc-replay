"""Tests for parameter serialisation and the NO_DEFAULT_SERIALISERS sentinel."""

from __future__ import annotations

from datetime import date, datetime

from pytest_adbc_replay import NO_DEFAULT_SERIALISERS
from pytest_adbc_replay._params import _NoDefaultSerialisers, build_registry


class TestNoDefaultSerialisers:
    """NO_DEFAULT_SERIALISERS sentinel identity and | behaviour."""

    def test_is_instance_of_sentinel_type(self) -> None:
        assert isinstance(NO_DEFAULT_SERIALISERS, _NoDefaultSerialisers)

    def test_bare_sentinel_is_empty(self) -> None:
        assert NO_DEFAULT_SERIALISERS == {}

    def test_or_returns_sentinel_type(self) -> None:
        result = NO_DEFAULT_SERIALISERS | {str: {"serialise": str}}
        assert isinstance(result, _NoDefaultSerialisers)

    def test_ror_returns_sentinel_type(self) -> None:
        result = {str: {"serialise": str}} | NO_DEFAULT_SERIALISERS
        assert isinstance(result, _NoDefaultSerialisers)

    def test_or_preserves_entries(self) -> None:
        handler = {"serialise": str}
        result = NO_DEFAULT_SERIALISERS | {str: handler}
        assert result == {str: handler}

    def test_or_with_multiple_types(self) -> None:
        h1 = {"serialise": str}
        h2 = {"serialise": repr}
        result = NO_DEFAULT_SERIALISERS | {str: h1, bytes: h2}
        assert result == {str: h1, bytes: h2}


class TestBuildRegistry:
    """build_registry() behaviour for all input cases."""

    def test_none_returns_builtins(self) -> None:
        result = build_registry(None)
        assert datetime in result
        assert date in result

    def test_bare_sentinel_returns_empty(self) -> None:
        result = build_registry(NO_DEFAULT_SERIALISERS)
        assert result == {}

    def test_sentinel_or_types_excludes_builtins(self) -> None:
        handler = {"serialise": str}
        result = build_registry(NO_DEFAULT_SERIALISERS | {float: handler})
        assert result == {float: handler}
        assert datetime not in result
        assert date not in result

    def test_sentinel_or_types_with_builtin_type_replaces_only_that_type(self) -> None:
        # User overrides date handler — only date is in the result, no other builtins
        def ser_date(d: date) -> int:
            return d.year

        custom_handler: dict[str, object] = {"serialise": ser_date}
        result = build_registry(NO_DEFAULT_SERIALISERS | {date: custom_handler})
        assert result == {date: custom_handler}
        assert datetime not in result

    def test_plain_dict_merges_with_builtins(self) -> None:
        handler = {"serialise": str}
        result = build_registry({float: handler})
        assert float in result
        assert datetime in result

    def test_plain_dict_user_wins_on_conflict(self) -> None:
        def ser_custom(d: date) -> str:
            return "custom"

        custom_handler: dict[str, object] = {"serialise": ser_custom}
        result = build_registry({date: custom_handler})
        assert result[date] is custom_handler
        assert datetime in result  # other builtins preserved

    def test_plain_empty_dict_returns_empty(self) -> None:
        result = build_registry({})
        assert result == {}
