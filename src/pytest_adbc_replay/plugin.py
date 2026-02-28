"""pytest-adbc-replay plugin: hooks, CLI option, fixture registration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from pytest_adbc_replay._session import ReplaySession

_RECORD_MODES = ("none", "once", "new_episodes", "all")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register --adbc-record CLI option and ini configuration keys."""
    group = parser.getgroup("adbc-replay", "ADBC cassette record/replay")
    group.addoption(
        "--adbc-record",
        action="store",
        default=None,
        choices=list(_RECORD_MODES),
        help=(
            "ADBC cassette record mode. "
            "none (default): replay only, fail on miss. "
            "once: record if cassette absent, replay if present. "
            "new_episodes: replay existing, record new. "
            "all: re-record everything."
        ),
    )
    parser.addini(
        "adbc_cassette_dir",
        help="Directory for ADBC cassette files (default: tests/cassettes).",
        type="string",
        default="tests/cassettes",
    )
    parser.addini(
        "adbc_record_mode",
        help="Default ADBC record mode when --adbc-record is not supplied (default: none).",
        type="string",
        default="none",
    )
    parser.addini(
        "adbc_dialect",
        help="Default SQL dialect for sqlglot normalisation ('' = auto-detect).",
        type="string",
        default="",
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


def pytest_report_header(config: pytest.Config) -> str:
    """Display active record mode in the pytest session header (DX-01)."""
    cli_mode = cast("str | None", config.getoption("--adbc-record"))
    ini_mode: str = cast("str", config.getini("adbc_record_mode")) or "none"
    mode: str = cli_mode if cli_mode is not None else ini_mode
    return f"adbc-replay: record mode = {mode}"


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
def adbc_scrubber() -> object:
    """
    Session-scoped fixture providing a scrubbing callback for recorded data (DX-02).

    Override this fixture in your conftest.py to register a callback that
    scrubs sensitive values before they are written to cassette files.
    The callback is stored but NOT called in v1 -- this is the interface
    reservation for v1.x implementation.

    Returns:
        A callable or None (default). Return None to use no scrubbing.

    Example::

        @pytest.fixture(scope="session")
        def adbc_scrubber():
            def scrub(data):
                return data  # no-op
            return scrub
    """
    return None


@pytest.fixture(scope="session")
def adbc_replay(
    request: pytest.FixtureRequest,
    adbc_param_serialisers: dict[Any, dict[str, Any]] | None,
    adbc_scrubber: object,
) -> ReplaySession:
    """
    Session-scoped fixture providing ADBC record/replay state.

    Returns a ReplaySession whose .wrap() method creates per-test
    ReplayConnection instances. Call .wrap() from your function-scoped
    fixture -- it reads the adbc_cassette marker from request.node.

    Example::

        @pytest.fixture
        def my_connection(adbc_replay, request):
            return adbc_replay.wrap(
                "adbc_driver_snowflake",
                db_kwargs={"uri": os.environ["SNOWFLAKE_URI"]},
                request=request,
            )
    """
    cli_mode = cast("str | None", request.config.getoption("--adbc-record"))
    ini_mode: str = cast("str", request.config.getini("adbc_record_mode")) or "none"
    mode: str = cli_mode if cli_mode is not None else ini_mode

    raw_cassette_dir: str = (
        cast("str", request.config.getini("adbc_cassette_dir")) or "tests/cassettes"
    )
    cassette_dir = Path(raw_cassette_dir)

    raw_dialect: str = cast("str", request.config.getini("adbc_dialect"))
    dialect: str | None = raw_dialect if raw_dialect else None

    return ReplaySession(
        mode=mode,
        cassette_dir=cassette_dir,
        param_serialisers=adbc_param_serialisers,
        scrubber=adbc_scrubber,
        dialect=dialect,
    )
