# Phase 1: Plugin Skeleton and Cursor Proxy - Research

**Researched:** 2026-02-28
**Domain:** pytest plugin development + ADBC cursor protocol
**Confidence:** HIGH

## Summary

Phase 1 builds an installable pytest plugin skeleton with auto-discovery, and a `ReplayCursor`/`ReplayConnection` implementing the full ADBC cursor protocol for replay-only mode (no real ADBC driver required). The project already has a `src/pytest_adbc_replay/` package stub with an `__init__.py` but **no `pytest11` entry point, no plugin module, no fixtures, no markers, and no cursor proxy classes**. Everything in this phase is new code.

The ADBC cursor interface (from `adbc_driver_manager.dbapi.Cursor`) is well-documented and stable. The key challenge is: in replay-only mode (`none`), `ReplayConnection` must never import or invoke a real ADBC driver. `ReplayCursor` acts as a pure-Python stub that loads from cassette storage (Phase 2) or raises `CassetteMissError`. The fixture scoping design (session-scoped `adbc_replay` holding config, with per-test cassette state created via `.wrap()`) avoids pytest scope-mismatch issues.

**Primary recommendation:** Create a `plugin.py` module in `src/pytest_adbc_replay/`, register it via `pytest11` entry point in `pyproject.toml`, and implement `ReplayCursor`/`ReplayConnection` as standalone classes that do not touch any ADBC driver import in replay mode.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Cassette Miss Error UX
- `CassetteMissError` displays: the **raw SQL** (as written in the test) AND the **normalised SQL** (as stored in the cassette key) — helps debug normalisation-produced mismatches
- `CassetteMissError` also shows the **cassette directory path** — enough to diagnose without noise; does NOT list all recorded interactions (that would be verbose)
- **Two distinct messages**: "cassette directory does not exist — record first" vs "interaction N not found in cassette" — different failure modes get different guidance
- Raises as a **Python exception** (`CassetteMissError(Exception)`) from within `execute()` — surfaces as a test ERROR with full traceback pointing to the test line; matches pytest-recording / VCR.py convention

#### Cassette Path Naming
- Node ID `tests/foo/test_bar.py::TestClass::test_method` → cassette directory `cassettes/foo/test_bar/TestClass/test_method/`
  - Strip `tests/` prefix (cassettes already live inside `tests/cassettes/`)
  - Strip `.py` extension from module name
  - Class and method become separate path segments
  - **Preserves original casing** — no lowercasing
- Special characters (brackets from parametrize, spaces) are **slugified**: replaced with `_` — safe on all filesystems, no collisions from invalid chars
- This mirrors the test directory structure inside `cassettes/` — no flat collisions across modules

#### wrap() Fixture Interface
- `adbc_replay.wrap(driver_module_name: str, db_kwargs: dict = {}, **kwargs)` — accepts a **driver module name string** as first argument; plugin lazy-imports the driver
- In replay mode (`none`): **driver string is required but ignored** — same call signature always; user fixture code works unchanged between record and replay modes; no ADBC driver is imported
- `adbc_replay` is **session-scoped** but holds config only; `wrap()` creates per-test cassette state — avoids fixture scope mismatch
- `wrap()` returns the `ReplayConnection` **directly** (not a context manager) — user's fixture controls the lifecycle

#### Marker and Fixture Scoping
- `@pytest.mark.adbc_cassette` on a **class applies to all methods** — standard pytest marker inheritance; each method gets its own cassette subdirectory
- When both a class and a method have the marker, **method marker wins** (most-specific-wins, standard pytest convention)
- Plugin **registers `adbc_cassette` in pytest's marker registry** during `pytest_configure` — suppresses `PytestUnknownMarkWarning`, standard practice
- `dialect=` in the marker accepts any string; if sqlglot doesn't recognise it, normalisation **falls back to whitespace-only with a warning** — lenient, doesn't break on new sqlglot dialect additions

### Claude's Discretion
- Exact `ReplayCursor.__getattr__` delegation pattern for unimplemented cursor methods in record mode
- Error message wording and formatting for `CassetteMissError`
- Internal session-to-function fixture bridging implementation

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Plugin discoverable via `pytest11` entry point | Standard `[project.entry-points.pytest11]` in pyproject.toml; plugin module registers hooks |
| INFRA-02 | `--adbc-record=<mode>` CLI flag | `pytest_addoption` hook with `parser.addoption("--adbc-record", ...)` |
| INFRA-03 | `adbc_replay` session-scoped fixture exposing `.wrap()` | `@pytest.fixture(scope="session")` returning a `ReplaySession` object |
| INFRA-04 | `@pytest.mark.adbc_cassette("name")` marker | Register in `pytest_configure`; read via `request.node.get_closest_marker("adbc_cassette")` |
| INFRA-05 | `dialect=` argument on cassette marker | Marker registered with `name: dialect` kwarg; read alongside cassette name |
| INFRA-06 | Default cassette name from test node ID | Derive from `request.node.nodeid` with slug transformation when no marker present |
| PROXY-01 | `ReplayConnection.cursor()` returns `ReplayCursor` | Simple factory method; in record mode wraps real cursor; in replay returns stub cursor |
| PROXY-02 | In replay mode, `ReplayConnection` does not open/import ADBC driver | Guard: only import driver module when `mode != "none"`; replay path constructs cursor without driver |
| PROXY-03 | `ReplayCursor.execute()` records in record mode | Phase 2 — implement stub that raises NotImplementedError or no-ops for Phase 1 |
| PROXY-04 | `ReplayCursor.execute()` loads from cassette in replay mode | Phase 2 — implement stub that raises `CassetteMissError` always (cassette storage deferred) |
| PROXY-05 | `ReplayCursor` implements full cursor protocol | All methods listed: `execute`, `fetch_arrow_table`, `fetchall`, `fetchone`, `fetchmany`, `description`, `rowcount`, `close`, `__enter__`/`__exit__` |
| PROXY-06 | `CassetteMissError` raised on cassette miss | Custom exception class with raw SQL, normalised SQL, cassette path; two distinct messages |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 (installed) | Plugin host framework | Already installed; hooks, fixtures, markers all present |
| adbc-driver-manager | latest (not yet installed) | Type references for cursor interface; real driver in record mode | Apache Arrow project; the canonical ADBC Python binding |
| pyarrow | latest (not yet installed) | Arrow IPC for cassette result storage (Phase 2) | ADBC cursor returns `pyarrow.Table`; only option with full schema fidelity |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlglot | latest (not yet installed) | SQL normalisation for cassette keys (Phase 2) | Likely in consumer's dep tree; pure Python |

### Phase 1 Install Changes
```toml
# pyproject.toml — add to [project] dependencies
dependencies = [
    "adbc-driver-manager>=1.0.0",
    "pyarrow>=14.0",
    "sqlglot>=23.0",
    "pytest>=8.0",
]
```

Note: `adbc-driver-manager` is needed for type references even in replay mode. In replay mode the driver itself is never imported, only the manager types. The import guard in `ReplayConnection.__init__` ensures `importlib.import_module(driver_module_name)` is not called in `none` mode.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `adbc-driver-manager` for types | `typing.Protocol` stubs only | Protocol stubs lose real cursor delegation in record mode; manager gives us real proxy target |
| `pyarrow.Table` for replay data | `list[dict]` | Lists lose type information; pyarrow preserves column types for faithful replay |

## Architecture Patterns

### Recommended Project Structure (Phase 1)

```
src/pytest_adbc_replay/
├── __init__.py          # Public API: CassetteMissError, ReplayConnection, ReplayCursor
├── py.typed             # (already exists)
├── plugin.py            # pytest hooks: pytest_addoption, pytest_configure, adbc_replay fixture
├── _connection.py       # ReplayConnection: wraps/stubs ADBC connection
├── _cursor.py           # ReplayCursor: full ADBC cursor protocol stub
├── _cassette.py         # CassettePath (node ID → path); placeholder for Phase 2 storage
└── _exceptions.py       # CassetteMissError

tests/
├── __init__.py          # (already exists)
├── conftest.py          # (already exists — add shared fixtures as needed)
└── test_plugin.py       # Plugin discovery, CLI flag, fixture existence, marker registration
└── test_cursor.py       # ReplayCursor protocol compliance, CassetteMissError
└── test_cassette_path.py # Node ID → cassette path slug transformation
```

### Pattern 1: pytest11 Entry Point Registration
**What:** `pyproject.toml` entry point causes pytest to auto-load the plugin module.
**When to use:** Any installable pytest plugin.
**Example:**
```toml
# pyproject.toml
[project.entry-points.pytest11]
adbc-replay = "pytest_adbc_replay.plugin"
```
Source: https://docs.pytest.org/en/stable/how-to/writing_plugins.html

### Pattern 2: Hook Registration in plugin.py
**What:** Plugin module implements `pytest_addoption`, `pytest_configure`, and provides `adbc_replay` fixture.
**When to use:** Minimal plugin skeleton.
**Example:**
```python
# src/pytest_adbc_replay/plugin.py
import pytest

def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("adbc-replay")
    group.addoption(
        "--adbc-record",
        action="store",
        default="none",
        choices=["none", "once", "new_episodes", "all"],
        help="ADBC cassette record mode (default: none = replay only)",
    )

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "adbc_cassette(name, dialect=None): override cassette name and SQL dialect for this test",
    )

@pytest.fixture(scope="session")
def adbc_replay(request: pytest.FixtureRequest) -> "ReplaySession":
    mode = request.config.getoption("--adbc-record", default="none")
    return ReplaySession(mode=mode)
```
Source: pytest docs (verified via Context7)

### Pattern 3: Session-Scoped Fixture + wrap() for Per-Test State
**What:** `adbc_replay` is session-scoped (holds config/mode), `.wrap()` is called per test to create per-test cassette state. This avoids scope mismatch — session fixture never depends on function-scoped fixtures.
**When to use:** Plugin needs both global config and per-test state.
**Example:**
```python
class ReplaySession:
    def __init__(self, mode: str) -> None:
        self.mode = mode

    def wrap(
        self,
        driver_module_name: str,
        db_kwargs: dict[str, object] | None = None,
        **kwargs: object,
    ) -> "ReplayConnection":
        return ReplayConnection(
            driver_module_name=driver_module_name,
            db_kwargs=db_kwargs or {},
            mode=self.mode,
            cassette_path=...,  # resolved per test in Phase 2
            **kwargs,
        )
```

### Pattern 4: Cassette Path from Node ID
**What:** The cassette directory path is derived from the test node ID, stripping the `tests/` prefix and slugifying special characters.
**When to use:** Default when no `@pytest.mark.adbc_cassette` marker is present.
**Example:**
```python
import re
from pathlib import Path

def node_id_to_cassette_path(node_id: str, cassette_dir: Path) -> Path:
    # "tests/foo/test_bar.py::TestClass::test_method" → "cassettes/foo/test_bar/TestClass/test_method"
    # Strip leading "tests/" if present
    node_id = re.sub(r"^tests/", "", node_id)
    # Split on "::"
    parts = node_id.split("::")
    # First part is module path — strip .py and convert / to sub-paths
    module = parts[0].removesuffix(".py")
    rest = parts[1:]
    # Slugify each segment: replace non-alphanumeric (except _) with _
    def slugify(s: str) -> str:
        return re.sub(r"[^\w]", "_", s)
    segments = [slugify(p) for p in module.split("/")] + [slugify(p) for p in rest]
    return cassette_dir.joinpath(*segments)
```
Note: Design doc says "preserves original casing" and "slugifies special chars to `_`". The re.sub pattern `[^\w]` replaces non-word chars (preserves letters, digits, `_`).

### Pattern 5: ReplayConnection — Driver Import Guard
**What:** In replay mode, `ReplayConnection` never imports the driver.
**When to use:** Core to PROXY-02 requirement.
**Example:**
```python
import importlib

class ReplayConnection:
    def __init__(self, driver_module_name: str, db_kwargs: dict, mode: str, ...) -> None:
        self._mode = mode
        self._real_conn = None
        if mode != "none":
            driver = importlib.import_module(driver_module_name)
            # open real connection via driver
            self._real_conn = driver.connect(**db_kwargs)

    def cursor(self) -> "ReplayCursor":
        real_cursor = self._real_conn.cursor() if self._real_conn else None
        return ReplayCursor(real_cursor=real_cursor, mode=self._mode, ...)
```

### Pattern 6: Full ADBC Cursor Protocol on ReplayCursor
**What:** `ReplayCursor` must implement all methods without raising `AttributeError`.
**ADBC Cursor interface** (from official docs, version 21/current):
- `execute(operation, parameters=None)` — main entry point
- `executemany(operation, seq_of_parameters)` — multiple param sets
- `fetch_arrow_table()` → `pyarrow.Table`
- `fetchall()` → `list[tuple]`
- `fetchone()` → `tuple | None`
- `fetchmany(size=None)` → `list[tuple]`
- `description` property → schema info or None
- `rowcount` property → int or -1
- `close()` — free resources
- `__enter__` / `__exit__` — context manager
Source: https://arrow.apache.org/adbc/current/python/api/adbc_driver_manager.html

### Anti-Patterns to Avoid
- **Importing ADBC driver in ReplayConnection.__init__ unconditionally:** Breaks PROXY-02 (replay mode must have no driver dependency).
- **Making `adbc_replay` function-scoped:** Causes performance problems (session config re-created per test). The design spec is clear: session-scoped for config, per-test via `.wrap()`.
- **Raising `AttributeError` from unimplemented cursor methods:** PROXY-05 requires all methods exist without `AttributeError` even in stub form.
- **Using `get_closest_marker` at fixture time without accessing `request.node`:** Session fixtures can't call `request.node.get_closest_marker` — `request.node` at session scope is the session, not the test item. Cassette path resolution must happen inside `.wrap()` with the test item passed in, OR via a separate function-scoped fixture that receives the marker and passes info to `.wrap()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Entry point discovery | Custom import-path hack | `[project.entry-points.pytest11]` in pyproject.toml | Standard mechanism; works with all Python packaging tools |
| Marker registration | Warning suppression hacks | `config.addinivalue_line("markers", ...)` in `pytest_configure` | Official API; no monkey patching needed |
| Node ID slugification | Complex encoding | Simple `re.sub(r"[^\w]", "_", s)` | Covers parametrize brackets, spaces, all special chars in one pass |

## Common Pitfalls

### Pitfall 1: pytest11 Entry Point Not Picked Up
**What goes wrong:** Plugin installs but pytest never loads it; `adbc_replay` fixture not available.
**Why it happens:** `pyproject.toml` uses wrong key format or the package isn't installed in editable mode.
**How to avoid:** Use `[project.entry-points.pytest11]` (not `[tool.pytest.entry-points.pytest11]`). Verify with `pytest --co -q` showing the fixture. Package must be installed (editable install: `uv pip install -e .`).
**Warning signs:** `adbc_replay` fixture not in `pytest --fixtures` output; `PytestUnknownMarkWarning` for `adbc_cassette`.

### Pitfall 2: Scope Mismatch — Session Fixture Accessing Test Item
**What goes wrong:** Session-scoped `adbc_replay` tries to call `request.node.get_closest_marker("adbc_cassette")` but `request.node` is the session, not the test item.
**Why it happens:** Marker resolution must happen at function scope.
**How to avoid:** Do NOT resolve cassette path/marker inside `adbc_replay`. Design: cassette path resolution happens inside `.wrap()` which is called from a function-scoped user fixture. Or: provide a separate function-scoped `_adbc_cassette_path` internal fixture that reads the marker and is composed with `.wrap()`.
**Warning signs:** `ScopeMismatch` error; marker always returns None even when set.

### Pitfall 3: AttributeError from Missing Cursor Methods
**What goes wrong:** Test calls `cursor.fetchall()` in replay mode and gets `AttributeError` because `ReplayCursor` only implements `execute()`.
**Why it happens:** Incomplete protocol implementation.
**How to avoid:** Implement ALL methods from PROXY-05 list in `ReplayCursor`, even as stubs that return empty results or raise `CassetteMissError` where appropriate.
**Warning signs:** `AttributeError: 'ReplayCursor' object has no attribute 'fetchall'` in test output.

### Pitfall 4: Accidentally Importing ADBC Driver in Replay Mode
**What goes wrong:** `ReplayConnection` imports the driver at module level or unconditionally in `__init__`, causing test failures in environments without the driver.
**Why it happens:** `import adbc_driver_snowflake` at top of file fails if driver not installed.
**How to avoid:** Use `importlib.import_module(driver_module_name)` inside an `if mode != "none"` guard. Never import driver at module level.
**Warning signs:** `ModuleNotFoundError` for `adbc_driver_snowflake` even when running in replay mode.

### Pitfall 5: pyproject.toml Missing pytest Framework Classifier
**What goes wrong:** PyPI listing doesn't show plugin; discoverability issues.
**Why it happens:** Missing `Framework :: Pytest` classifier (cosmetic, not functional, but convention).
**How to avoid:** Add classifier to `pyproject.toml`.

### Pitfall 6: basedpyright Strict Mode Rejects Untyped Code
**What goes wrong:** Pre-commit hook fails on type errors in new plugin code.
**Why it happens:** `basedpyright` is configured with `typeCheckingMode = "strict"` in `pyproject.toml`.
**How to avoid:** Use explicit type annotations on all public functions, class attributes, and return types. The `adbc-driver-manager` package provides type stubs. Use `TYPE_CHECKING` blocks for forward references.
**Warning signs:** Pre-commit fails with `error` not `warning`; CI fails.

## Code Examples

Verified patterns from official sources:

### pytest11 Entry Point in pyproject.toml
```toml
# Source: https://docs.pytest.org/en/stable/how-to/writing_plugins.html
[project.entry-points.pytest11]
adbc-replay = "pytest_adbc_replay.plugin"
```

### pytest_addoption Hook
```python
# Source: pytest official docs (verified via Context7)
def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("adbc-replay")
    group.addoption(
        "--adbc-record",
        action="store",
        default="none",
        choices=["none", "once", "new_episodes", "all"],
        help="ADBC cassette record mode (default: none = replay only)",
    )
```

### Marker Registration in pytest_configure
```python
# Source: pytest official docs (verified via Context7)
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "adbc_cassette(name, dialect=None): set cassette name and SQL dialect for this test",
    )
```

### Session Fixture with .wrap()
```python
# Source: design doc + pytest fixtures docs
@pytest.fixture(scope="session")
def adbc_replay(request: pytest.FixtureRequest) -> ReplaySession:
    mode = request.config.getoption("--adbc-record", default="none")
    return ReplaySession(mode=mode)
```

### Reading Marker from Function-Scoped Fixture
```python
# Source: pytest fixtures docs (verified via Context7)
# In user's conftest.py or test file:
@pytest.fixture
def adbc_connection(adbc_replay, request):
    marker = request.node.get_closest_marker("adbc_cassette")
    name = marker.args[0] if marker and marker.args else None
    dialect = marker.kwargs.get("dialect") if marker else None
    return adbc_replay.wrap("adbc_driver_snowflake", db_kwargs={...}, cassette_name=name, dialect=dialect)
```

### ReplayCursor Context Manager
```python
# Source: design doc + ADBC docs
class ReplayCursor:
    def __enter__(self) -> "ReplayCursor":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `setup.py` entry_points | `pyproject.toml [project.entry-points.pytest11]` | PEP 517/518 (2018+) | Both work; pyproject.toml is now standard |
| ADBC 0.x series | ADBC 21 (current) stable API | 2024 | API stable; `fetch_arrow_table()` present since early versions |

**Deprecated/outdated:**
- `setup.cfg` for entry points: works but not idiomatic with uv/uv_build; use pyproject.toml

## Open Questions

1. **How should `.wrap()` receive the current test item for cassette path resolution?**
   - What we know: `adbc_replay` is session-scoped; markers live on the test item; `.wrap()` is called from user's function-scoped fixture
   - What's unclear: Should `.wrap()` accept `request` as a parameter? Or should the plugin provide a function-scoped helper fixture?
   - Recommendation: Accept `request: pytest.FixtureRequest` as an optional parameter on `.wrap()`, so the user's fixture can pass it: `adbc_replay.wrap(driver, db_kwargs={...}, request=request)`. The plugin reads the marker from `request.node` inside `.wrap()`. This is the cleanest interface — no hidden magic, no extra fixtures.

2. **Should `ReplayCursor` in Phase 1 raise `CassetteMissError` on ALL `execute()` calls?**
   - What we know: Cassette storage (Phase 2) is not implemented; the cursor stub cannot load from cassette
   - What's unclear: Should Phase 1 stub always raise, or silently no-op?
   - Recommendation: Raise `CassetteMissError` with a clear "cassette storage not yet implemented — this is Phase 1" message, OR implement `execute()` to set `self._pending = None` and have fetch methods return empty results. The latter lets integration tests run in replay mode without needing real cassettes in Phase 1 tests, making it easier to test the protocol itself. **Use the latter approach for Phase 1.**

## Validation Architecture

> Skipped (nyquist_validation_enabled is false per config.json)

## Sources

### Primary (HIGH confidence)
- `/pytest-dev/pytest` (Context7) — plugin entry points, addoption hook, fixture scoping, marker registration
- https://arrow.apache.org/adbc/current/python/api/adbc_driver_manager.html — full cursor API (ADBC v21, current)
- `/Users/paul/Documents/Dev/Personal/pytest-adbc-replay/_notes/pytest-adbc-replay-design.md` — authoritative design decisions for this project

### Secondary (MEDIUM confidence)
- https://docs.pytest.org/en/stable/how-to/writing_plugins.html — plugin authoring guide
- WebSearch: ADBC cursor interface verification against official docs

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pytest 9.0.2 already installed; ADBC API stable from official docs
- Architecture: HIGH — design doc is authoritative; pytest patterns verified via Context7
- Pitfalls: HIGH — based on project constraints (basedpyright strict, entry points standard)

**Research date:** 2026-02-28
**Valid until:** 2026-08-28 (ADBC API stable; pytest hooks stable)

---

## RESEARCH COMPLETE

**Phase:** 01 - Plugin Skeleton and Cursor Proxy
**Confidence:** HIGH

### Key Findings
- No `pytest11` entry point exists in `pyproject.toml` — must be added as first step
- `adbc-driver-manager`, `pyarrow`, `sqlglot` are NOT yet installed — must be added to `[project] dependencies`
- Python 3.14.2 + pytest 9.0.2 — modern Python, strict typing required by basedpyright
- The ADBC cursor interface is stable (v21): `execute`, `fetch_arrow_table`, `fetchall`, `fetchone`, `fetchmany`, `description`, `rowcount`, `close`, `__enter__`/`__exit__`
- Scope mismatch is the key architectural challenge: session fixture cannot access test item markers; resolve via `request` param on `.wrap()`

### File Created
`.planning/phases/01-plugin-skeleton-and-cursor-proxy/01-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | Official ADBC docs + installed pytest verified |
| Architecture | HIGH | Design doc is authoritative; pytest Context7 verified |
| Pitfalls | HIGH | Known from project tooling (strict typing, pre-commit hooks) |

### Open Questions
- Phase 1 stub behaviour: recommend `execute()` sets `_pending = None`, fetch methods return empty — enables protocol testing without cassettes

### Ready for Planning
Research complete. Planner can now create PLAN.md files.
