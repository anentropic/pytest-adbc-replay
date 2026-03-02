"""pytest-adbc-replay plugin: hooks, CLI option, fixture registration."""

from __future__ import annotations

import contextlib
import importlib
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from pytest_adbc_replay._session import ReplaySession

if TYPE_CHECKING:
    from collections.abc import Generator

_RECORD_MODES = ("none", "once", "new_episodes", "all")

# --- Auto-patch state -----------------------------------------------------------
# Use a mutable container to hold state that changes after module load,
# avoiding basedpyright's reportConstantRedefinition on uppercase module globals.

_auto_patch_state: dict[str, Any] = {
    # Currently-running test item; set in pytest_runtest_setup, cleared in teardown.
    "current_item": None,
    # Session-level ReplaySession instance, set by adbc_replay fixture.
    "session_state": None,
}

_ITEM_LOCK = threading.Lock()

# Open connections per test item (keyed by id(item)) for auto-close in teardown.
_OPEN_CONNECTIONS: dict[int, list[Any]] = {}

# Original connect() functions before monkeypatching, keyed by driver module name.
_ORIGINAL_CONNECTS: dict[str, Any] = {}


# --- Registration ---------------------------------------------------------------


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
    parser.addini(
        "adbc_auto_patch",
        help=(
            "Space-separated list of ADBC driver module names whose connect() is "
            "intercepted automatically for tests with @pytest.mark.adbc_cassette. "
            "Example: adbc_driver_snowflake adbc_driver_duckdb.dbapi"
        ),
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


# --- Auto-patch hooks -----------------------------------------------------------


def _build_session_from_config(config: pytest.Config) -> ReplaySession:
    """Build a ReplaySession from pytest config. Used by auto-patch initialization."""
    cli_mode = cast("str | None", config.getoption("--adbc-record"))
    ini_mode: str = cast("str", config.getini("adbc_record_mode")) or "none"
    mode: str = cli_mode if cli_mode is not None else ini_mode

    raw_cassette_dir: str = cast("str", config.getini("adbc_cassette_dir")) or "tests/cassettes"
    cassette_dir = Path(raw_cassette_dir)

    raw_dialect: str = cast("str", config.getini("adbc_dialect"))
    dialect: str | None = raw_dialect if raw_dialect else None

    return ReplaySession(
        mode=mode,
        cassette_dir=cassette_dir,
        param_serialisers=None,
        scrubber=None,
        dialect=dialect,
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    """Monkeypatch ADBC driver connect() for each driver in adbc_auto_patch."""
    raw: str = cast("str", session.config.getini("adbc_auto_patch")) or ""
    driver_names = [d.strip() for d in raw.split() if d.strip()]

    if not driver_names:
        return

    # Initialize the session state eagerly from config so it's available before
    # the adbc_replay fixture is first requested. The adbc_replay fixture will
    # overwrite this with an instance that includes param_serialisers/scrubber.
    _auto_patch_state["session_state"] = _build_session_from_config(session.config)

    for driver_name in driver_names:
        try:
            driver_mod = importlib.import_module(driver_name)
        except ImportError:
            # Driver not installed — skip silently (supports replay-only environments)
            continue

        original_connect = driver_mod.connect
        _ORIGINAL_CONNECTS[driver_name] = original_connect

        def _make_patched(dn: str, orig: Any) -> Any:
            def _patched_connect(**kwargs: Any) -> Any:
                with _ITEM_LOCK:
                    item = _auto_patch_state["current_item"]

                if item is None:
                    # Called outside a test — pass through to real driver
                    return orig(**kwargs)

                marker = item.get_closest_marker("adbc_cassette")
                if marker is None:
                    # No cassette marker — pass through to real driver
                    return orig(**kwargs)

                # Retrieve the session-scoped ReplaySession (always set above)
                session_obj: ReplaySession = _auto_patch_state["session_state"]

                conn = session_obj.wrap_from_item(dn, item, db_kwargs=dict(kwargs), connect_fn=orig)
                with _ITEM_LOCK:
                    _OPEN_CONNECTIONS.setdefault(id(item), []).append(conn)
                return conn

            return _patched_connect

        setattr(driver_mod, "connect", _make_patched(driver_name, original_connect))  # noqa: B010


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Track the currently-running test item for monkeypatched connect() resolution."""
    with _ITEM_LOCK:
        _auto_patch_state["current_item"] = item


def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:  # noqa: ARG001
    """Clear current item and close all connections opened during this test."""
    with _ITEM_LOCK:
        _auto_patch_state["current_item"] = None
    connections = _OPEN_CONNECTIONS.pop(id(item), [])
    for conn in connections:
        with contextlib.suppress(Exception):
            conn.close()


# --- Header and fixtures --------------------------------------------------------


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

    session = ReplaySession(
        mode=mode,
        cassette_dir=cassette_dir,
        param_serialisers=adbc_param_serialisers,
        scrubber=adbc_scrubber,
        dialect=dialect,
    )
    # Overwrite the eagerly-initialized session_state (set in pytest_sessionstart)
    # with this fully-configured instance that includes param_serialisers and scrubber.
    _auto_patch_state["session_state"] = session
    return session


@pytest.fixture
def adbc_connect(
    adbc_replay: ReplaySession,
    request: pytest.FixtureRequest,
) -> Generator[Any, None, None]:
    """
    Function-scoped factory fixture for creating ADBC replay connections explicitly.

    Use this as the escape hatch when ``adbc_auto_patch`` is not appropriate --
    for example, when you need a session-scoped or module-scoped connection, or
    when you prefer explicit control over connection creation.

    Returns a callable: ``(driver_module_name: str, **db_kwargs) -> ReplayConnection``

    The fixture closes all opened connections when the test finishes. Cassette
    paths follow the per-driver subdirectory layout used by auto-patch.

    Example::

        @pytest.mark.adbc_cassette("my_test")
        def test_my_query(adbc_connect):
            conn = adbc_connect("adbc_driver_snowflake.dbapi", uri=os.environ["SF_URI"])
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
    """
    opened: list[Any] = []

    def _factory(driver_module_name: str, **db_kwargs: Any) -> Any:
        conn = adbc_replay.wrap_from_item(
            driver_module_name,
            request.node,
            db_kwargs=db_kwargs,
        )
        opened.append(conn)
        return conn

    yield _factory

    for conn in opened:
        with contextlib.suppress(Exception):
            conn.close()
