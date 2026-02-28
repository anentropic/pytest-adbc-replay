"""pytest-adbc-replay plugin: hooks, CLI option, fixture registration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pytest_adbc_replay._session import ReplaySession

_RECORD_MODES = ("none", "once", "new_episodes", "all")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register --adbc-record CLI option."""
    group = parser.getgroup("adbc-replay", "ADBC cassette record/replay")
    group.addoption(
        "--adbc-record",
        action="store",
        default="none",
        choices=list(_RECORD_MODES),
        help=(
            "ADBC cassette record mode. "
            "none (default): replay only, fail on miss. "
            "once: record if cassette absent, replay if present. "
            "new_episodes: replay existing, record new. "
            "all: re-record everything."
        ),
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register adbc_cassette marker to suppress PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        (
            "adbc_cassette(name, *, dialect=None): "
            "Set cassette name and SQL dialect for this test. "
            "name: cassette directory name (default: derived from node ID). "
            "dialect: sqlglot dialect string for SQL normalisation (e.g. 'snowflake')."
        ),
    )


@pytest.fixture(scope="session")
def adbc_param_serialisers() -> dict[Any, dict[str, Any]] | None:
    """
    Session-scoped fixture providing custom parameter serialisers for ADBC replay.

    Override this fixture in your conftest.py to register custom serialisers
    for non-JSON-native parameter types (e.g. numpy arrays, custom date wrappers).

    Returns:
        A dict mapping Python types to serialiser dicts, or None to use defaults.
        Each serialiser dict must have "serialise" and "type_tag" keys, and
        optionally a "deserialise" key.

    Example::

        import pytest
        import numpy as np
        from pytest_adbc_replay import NO_DEFAULT_SERIALISERS

        @pytest.fixture(scope="session")
        def adbc_param_serialisers():
            return {
                np.int64: {
                    "type_tag": "numpy.int64",
                    "serialise": lambda v: {"value": int(v)},
                },
            }
    """
    return None


@pytest.fixture(scope="session")
def adbc_replay(
    request: pytest.FixtureRequest,
    adbc_param_serialisers: dict[Any, dict[str, Any]] | None,
) -> ReplaySession:
    """
    Session-scoped fixture providing ADBC record/replay state.

    Returns a ReplaySession whose .wrap() method creates per-test
    ReplayConnection instances. Call .wrap() from your function-scoped
    fixture — it reads the adbc_cassette marker from request.node.

    Example::

        @pytest.fixture
        def my_connection(adbc_replay, request):
            return adbc_replay.wrap(
                "adbc_driver_snowflake",
                db_kwargs={"uri": os.environ["SNOWFLAKE_URI"]},
                request=request,
            )
    """
    mode: str = request.config.getoption("--adbc-record", default="none")
    # cassette_dir: could be read from ini config in Phase 3
    cassette_dir = Path("tests/cassettes")
    return ReplaySession(
        mode=mode,
        cassette_dir=cassette_dir,
        param_serialisers=adbc_param_serialisers,
    )
