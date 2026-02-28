# Architecture Research

**Domain:** pytest record/replay plugin for ADBC database connections
**Researched:** 2026-02-28
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Pytest Plugin Layer                              │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │ Entry Point  │  │ Hook Impls   │  │ Config       │                   │
│  │ (pytest11)   │──│ addoption    │──│ INI values   │                   │
│  │              │  │ configure    │  │ CLI args     │                   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                   │
│         │                 │                 │                            │
├─────────┴─────────────────┴─────────────────┴────────────────────────────┤
│                        Fixture Layer                                     │
│                                                                          │
│  ┌──────────────────┐          ┌──────────────────────┐                  │
│  │ adbc_replay      │          │  Marker resolver      │                 │
│  │ (session-scoped) │──────────│  @adbc_cassette(...)  │                 │
│  │ .wrap() method   │          │  cassette name,       │                 │
│  └────────┬─────────┘          │  dialect override     │                 │
│           │                    └──────────────────────┘                  │
│           │                                                              │
├───────────┴──────────────────────────────────────────────────────────────┤
│                        Proxy Layer                                       │
│                                                                          │
│  ┌──────────────────┐   ┌──────────────────┐                             │
│  │ ReplayConnection │──→│ ReplayCursor     │                             │
│  │ wraps real conn  │   │ wraps real cursor │                            │
│  │ or standalone    │   │ or standalone     │                            │
│  └──────────────────┘   └────────┬─────────┘                             │
│                                  │                                       │
│                    ┌─────────────┼──────────────┐                        │
│                    │ execute()   │ fetch_*()    │                        │
│                    │             │              │                        │
├────────────────────┴─────────────┴──────────────┴────────────────────────┤
│                        Cassette Layer                                    │
│                                                                          │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐     │
│  │ SQL Normaliser   │   │ Cassette Store   │   │ Cassette Key     │     │
│  │ (sqlglot)        │──→│ (directory I/O)  │←──│ (sql+params+opts)│     │
│  └──────────────────┘   └────────┬─────────┘   └──────────────────┘     │
│                                  │                                       │
├──────────────────────────────────┴───────────────────────────────────────┤
│                        Storage Layer (filesystem)                        │
│                                                                          │
│  cassettes/                                                              │
│    test_my_query/                                                        │
│      000_query.sql          000_result.arrow                             │
│      000_params.json        001_query.sql                                │
│      000_options.json       001_result.arrow                             │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Plugin entrypoint** (`plugin.py`) | Registers hooks with pytest via `pytest11` entry point. Implements `pytest_addoption` (CLI flags), `pytest_configure` (marker registration, INI values), and fixture definitions. Single module that wires everything together. | Pytest framework, Fixture layer |
| **`adbc_replay` fixture** (session-scoped) | Holds session-wide config (record mode, cassette dir, default dialect). Exposes `.wrap(connection)` to produce `ReplayConnection` instances. Reads marker config per-test. | ReplayConnection, Cassette Store, Marker resolver |
| **Marker resolver** | Reads `@pytest.mark.adbc_cassette(name, dialect=...)` from test items. Provides cassette name and dialect override to the fixture layer. Falls back to test node ID if no marker. | Plugin hooks (`pytest_runtest_setup`), Fixture layer |
| **ReplayConnection** | Wraps a real ADBC connection (record mode) or operates standalone (replay mode). Returns `ReplayCursor` from `.cursor()`. In replay-only mode, never opens a real connection. | ReplayCursor, real ADBC connection (optional) |
| **ReplayCursor** | Intercepts `execute()` and `fetch_*()` calls. In record mode: delegates to real cursor, captures result, writes to cassette. In replay mode: looks up cassette by key, returns stored result. | Cassette Store, real ADBC cursor (optional), SQL Normaliser |
| **SQL Normaliser** | Canonicalises SQL text via `sqlglot.transpile()` for stable cassette keys. Handles dialect-aware parsing. Falls back to whitespace normalisation on parse failure. | sqlglot library |
| **Cassette Store** | Manages the cassette directory for a single test: reading, writing, and matching interactions. Tracks interaction sequence counter. Owns the mapping from `CassetteKey` to numbered file pairs. | Filesystem, SQL Normaliser |
| **CassetteKey** | Value object: `(normalised_sql, parameters, driver_options)`. Equality and hashing for cassette lookup. | SQL Normaliser, Cassette Store |

## Recommended Project Structure

```
src/
├── pytest_adbc_replay/
│   ├── __init__.py            # Public API re-exports
│   ├── plugin.py              # pytest hooks, fixtures, marker registration
│   ├── proxy.py               # ReplayConnection + ReplayCursor
│   ├── cassette.py            # Cassette store, CassetteKey, record modes
│   ├── normalise.py           # SQL normalisation via sqlglot
│   └── _types.py              # Shared type aliases, enums (RecordMode)
tests/
├── conftest.py                # Test fixtures (pytester-based)
├── test_plugin.py             # Integration tests via pytester
├── test_proxy.py              # Unit tests for ReplayCursor/ReplayConnection
├── test_cassette.py           # Unit tests for cassette store I/O
├── test_normalise.py          # Unit tests for SQL normalisation
└── cassettes/                 # Test cassette fixtures (golden files)
```

### Structure Rationale

- **`plugin.py`:** Single-module entrypoint is the standard pytest plugin pattern (matches pytest-cov, pytest-recording). Contains all hook implementations and fixture definitions. This is the module registered via `entry_points`.
- **`proxy.py`:** Isolates the cursor/connection proxy logic from pytest machinery. Can be unit-tested independently without pytest fixtures.
- **`cassette.py`:** Isolates file I/O and cassette matching from proxy logic. Can be tested against real filesystem without ADBC dependencies.
- **`normalise.py`:** Isolates sqlglot dependency. Single function with clear fallback behaviour. Easy to test exhaustively.
- **`_types.py`:** `RecordMode` enum and shared types prevent circular imports between modules.

## Architectural Patterns

### Pattern 1: Plugin Registration via entry_points

**What:** Pytest discovers third-party plugins through the `pytest11` entry point group. When a package is installed, pytest's plugin manager (pluggy) loads the module specified in the entry point and registers its hook implementations.

**When to use:** Always -- this is the standard mechanism for distributable pytest plugins. conftest.py is for project-local plugins only.

**Trade-offs:** The entry point must point to a module that contains top-level functions matching pytest hook names (e.g., `pytest_addoption`, `pytest_configure`). Fixtures defined at module level in this module are globally available to all tests. This is the correct pattern for a pip-installable plugin.

**Implementation in `pyproject.toml`:**
```toml
[project.entry-points.pytest11]
adbc_replay = "pytest_adbc_replay.plugin"
```

**Confidence:** HIGH -- verified against installed pytest-cov entry_points.txt (`[pytest11] / pytest_cov = pytest_cov.plugin`) and pytest's own hook specification source.

### Pattern 2: Three-Hook Plugin Bootstrap

**What:** A standard pytest plugin implements three hooks at module level for setup:

1. `pytest_addoption(parser)` -- registers CLI flags and INI config values
2. `pytest_configure(config)` -- registers custom markers, performs early validation
3. Fixture functions decorated with `@pytest.fixture` -- provide the user-facing API

**When to use:** Every pytest plugin that adds CLI options, config, and fixtures follows this pattern.

**Trade-offs:** Keep hook implementations thin. Heavy logic belongs in the domain classes (Cassette, ReplayCursor), not in the hook functions. The hooks are the wiring layer.

**Example (`plugin.py` skeleton):**
```python
import pytest

def pytest_addoption(parser):
    group = parser.getgroup("adbc_replay", "ADBC record/replay")
    group.addoption(
        "--adbc-record",
        default="none",
        choices=["none", "once", "new_episodes", "all"],
        help="ADBC cassette record mode",
    )
    parser.addini("adbc_cassette_dir", default="tests/cassettes", help="...")
    parser.addini("adbc_record_mode", default="none", help="...")
    parser.addini("adbc_dialect", default=None, help="...")

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "adbc_cassette(name, dialect=None): name the cassette and set SQL dialect",
    )

@pytest.fixture(scope="session")
def adbc_replay(request):
    # Build session-wide replay manager from config
    ...
```

**Confidence:** HIGH -- directly verified from pytest-cov source and pytest hookspec.py.

### Pattern 3: Session-Scoped Manager with Per-Test Cassette State

**What:** A session-scoped fixture holds immutable configuration (cassette dir, default record mode, default dialect). Each test gets its own cassette directory derived from the test node ID or marker. The per-test cassette lifecycle is managed through the `.wrap()` call which the user makes in their own fixture.

**When to use:** This is the `pytest-recording` pattern. The session fixture is a factory; the per-test state is created on each invocation.

**Trade-offs:** Session-scoped fixture cannot directly access per-test markers (it receives the session-level request, not the item-level request). Two approaches to resolve this:

- **Option A (recommended):** User writes a function-scoped fixture that depends on `adbc_replay` and calls `adbc_replay.wrap(...)`. The cassette name comes from the user fixture or is derived from `request.node.nodeid` by default.
- **Option B:** Use `pytest_runtest_setup` hook to push per-test cassette state into the session manager before the test runs, and pop it in `pytest_runtest_teardown`. This is more magic and harder to debug.

Option A matches the design document's approach and keeps the plugin simple.

**Example:**
```python
# In the consuming project's conftest.py:
@pytest.fixture
def adbc_connection(request, adbc_replay):
    marker = request.node.get_closest_marker("adbc_cassette")
    cassette_name = marker.args[0] if marker else None
    dialect = marker.kwargs.get("dialect") if marker else None
    return adbc_replay.wrap(
        driver="adbc_driver_snowflake",
        db_kwargs={...},
        cassette_name=cassette_name,
        dialect=dialect,
    )
```

**Confidence:** HIGH -- this is the standard pattern for pytest plugins that need per-test configuration with session-level shared state.

### Pattern 4: Transparent Proxy (Cursor Wrapping)

**What:** `ReplayCursor` implements the same interface as the real ADBC cursor. Tests never know they are talking to a proxy. In record mode, every `execute()` delegates to the real cursor and records the result. In replay mode, `execute()` looks up the cassette and stages the result for the next `fetch_*()` call.

**When to use:** When intercepting an existing API at a well-defined interface boundary. The ADBC cursor API surface is narrow (`execute`, `fetch_arrow_table`, `fetchone`, `fetchmany`, `fetchall`, `close`, `description`, `rowcount`) making it an ideal proxy target.

**Trade-offs:**
- Must keep the proxy interface in sync with the real cursor. If ADBC adds new methods, the proxy must be updated.
- In replay mode the proxy must handle `description` and `rowcount` attributes from the stored Arrow schema metadata.
- The proxy must handle `executemany()` if ADBC cursors support it (check driver manager API).

**Confidence:** HIGH -- the design document specifies this pattern, and proxy/wrapper is the standard approach in VCR.py, responses, and similar record/replay libraries.

### Pattern 5: Directory-per-Cassette with Numbered Interactions

**What:** Each test's cassette is a directory. Each `execute()` call within the test produces a numbered set of files: `NNN_query.sql`, `NNN_result.arrow`, optional `NNN_params.json` and `NNN_options.json`. Interactions are matched by sequence order during replay.

**When to use:** When tests execute multiple queries in a deterministic order. The numbered-sequence approach is simpler and more predictable than content-based matching.

**Trade-offs:**
- **Sequence-based matching** (replay interaction 0 on first execute, interaction 1 on second, etc.) is simpler to implement and debug. But it breaks if query order changes.
- **Content-based matching** (look up by normalised SQL key) tolerates reordering but is more complex and ambiguous if the same query is executed multiple times with different results.
- The design document uses content-based keying (`CassetteKey`), but the file format is numbered. This implies a **hybrid**: files are numbered for storage order, but lookup can use the key for matching. In practice, most test cassettes have deterministic ordering, so sequence-based matching with key validation is the pragmatic approach.

**Confidence:** MEDIUM -- the design document shows both numbered files and key-based lookup. The implementation needs to decide: pure sequence, pure key-lookup, or hybrid. Recommendation: use sequence-based replay (simpler, matches VCR.py's approach) with the key stored in files for diagnostics and `new_episodes` mode matching.

## Data Flow

### Record Flow

```
Test code calls: connection.cursor().execute(sql, params)
    |
    v
ReplayCursor.execute(sql, params, **opts)
    |
    +---> SQL Normaliser: normalise_sql(sql, dialect) -> normalised_key
    |
    +---> Real cursor: self._cursor.execute(sql, params, **opts)
    |
    +---> Real cursor: self._cursor.fetch_arrow_table() -> arrow_table
    |
    +---> Cassette Store: record(key, arrow_table)
    |         |
    |         +---> Write NNN_query.sql    (pretty-printed SQL for PR diffs)
    |         +---> Write NNN_params.json  (if params present)
    |         +---> Write NNN_options.json (if opts present)
    |         +---> Write NNN_result.arrow (Arrow IPC bytes)
    |         +---> Increment interaction counter
    |
    +---> Stage arrow_table for subsequent fetch_*() calls
    |
    v
Test code calls: cursor.fetch_arrow_table() -> returns staged arrow_table
```

### Replay Flow

```
Test code calls: connection.cursor().execute(sql, params)
    |
    v
ReplayCursor.execute(sql, params, **opts)
    |
    +---> SQL Normaliser: normalise_sql(sql, dialect) -> normalised_key
    |
    +---> Cassette Store: load(interaction_index)
    |         |
    |         +---> Read NNN_query.sql -> stored_key
    |         +---> Validate: normalised_key matches stored_key
    |         |        (if mismatch: raise CassetteMismatchError)
    |         +---> Read NNN_result.arrow -> arrow_table
    |         +---> Increment interaction counter
    |
    +---> Stage arrow_table for subsequent fetch_*() calls
    |
    v
Test code calls: cursor.fetch_arrow_table() -> returns staged arrow_table
```

### Key Data Flows

1. **Config resolution:** CLI args (`--adbc-record`) override INI values (`adbc_record_mode`), which override defaults (`none`). Per-test marker overrides cassette name and dialect. This flows: `pytest_addoption` -> `config.getoption()`/`config.getini()` -> `adbc_replay` fixture constructor -> per-test `.wrap()` call.

2. **Cassette name resolution:** Test node ID (`module::class::test_name`) is the default cassette directory name. The `@pytest.mark.adbc_cassette("custom_name")` marker overrides it. Path sanitisation replaces `::` and `/` with filesystem-safe separators.

3. **Dialect propagation:** Global default (`pyproject.toml: adbc_dialect`) -> marker override (`@pytest.mark.adbc_cassette(dialect="snowflake")`) -> passed to `normalise_sql()` for both record and replay. This ensures the same normalisation at record time and replay time.

4. **Mode-dependent connection creation:** In `none` mode, `ReplayConnection` is constructed without a real connection (no driver loaded, no credentials needed). In `once`/`new_episodes`/`all` modes, a real connection is opened and wrapped.

## Build Order (Suggested Implementation Sequence)

The components have clear dependency relationships that dictate build order:

```
Phase 1: Foundation (no pytest dependency needed for unit tests)
    _types.py          -- RecordMode enum, type aliases
    normalise.py       -- SQL normaliser (depends on: sqlglot)
    cassette.py        -- Cassette store I/O (depends on: pyarrow, _types, normalise)

Phase 2: Proxy Layer (depends on Phase 1)
    proxy.py           -- ReplayConnection + ReplayCursor (depends on: cassette, _types)

Phase 3: Plugin Wiring (depends on Phase 2)
    plugin.py          -- pytest hooks + fixtures (depends on: proxy, cassette, _types)
    pyproject.toml     -- entry_points registration

Phase 4: Integration Testing
    pytester-based tests exercising full record/replay cycle
```

**Rationale:**
- Phase 1 components are pure-Python with minimal dependencies, unit-testable in isolation.
- Phase 2 composes Phase 1 components into the cursor proxy. Testable with mock cursors.
- Phase 3 is thin glue connecting Phase 2 to pytest. Tested with `pytester` (pytest's own test-a-plugin fixture).
- Each phase produces working, tested code before the next phase depends on it.

## Anti-Patterns

### Anti-Pattern 1: Fat Plugin Module

**What people do:** Put all logic (normalisation, file I/O, proxy, hooks) in one `plugin.py`.
**Why it's wrong:** Violates single-responsibility. Makes unit testing painful because every test needs a pytest fixture context. Makes the module hard to navigate.
**Do this instead:** Keep `plugin.py` as a thin wiring layer. Domain logic lives in `normalise.py`, `cassette.py`, `proxy.py`.

### Anti-Pattern 2: Monkey-patching the Driver

**What people do:** Patch `adbc_driver_manager.dbapi.Cursor` globally at import time to intercept all cursor creation.
**Why it's wrong:** Affects all connections including those not under test. Breaks if multiple test sessions run in parallel. Fragile across driver-manager version upgrades.
**Do this instead:** Use explicit wrapping via `.wrap()`. The user controls which connections are wrapped. No global state mutation.

### Anti-Pattern 3: Fixture Scope Mismatch

**What people do:** Make the cassette fixture session-scoped while cassette state is per-test.
**Why it's wrong:** A session-scoped fixture that holds mutable per-test state is a concurrency bug waiting to happen (xdist) and makes reasoning about lifecycle hard.
**Do this instead:** Session-scoped fixture holds only immutable config. Per-test cassette state is created fresh in each `.wrap()` call (which happens in a function-scoped user fixture) or is managed via a function-scoped internal fixture.

### Anti-Pattern 4: Content-Based Matching Without Sequence Fallback

**What people do:** Match cassettes purely by SQL content hash, ignoring execution order.
**Why it's wrong:** If a test executes the same query twice with different expected results (e.g., before and after an update), content-based matching cannot distinguish them.
**Do this instead:** Use sequence-based replay as the primary mechanism. Store normalised SQL in the cassette for validation and diagnostics, but replay by interaction index.

## Integration Points

### External Dependencies

| Dependency | Integration Pattern | Notes |
|-----------|---------------------|-------|
| `pytest` | Hook implementations + fixture decorator in `plugin.py` | Minimum pytest 7.0+ for `@pytest.hookimpl(wrapper=True)` syntax. Plugin registered via `pytest11` entry point. |
| `pyarrow` | `pyarrow.ipc.RecordBatchFileWriter` / `RecordBatchFileReader` for cassette Arrow IPC files | Used only in `cassette.py`. No Arrow dependency in proxy or plugin layers. |
| `sqlglot` | `sqlglot.transpile(sql, read=dialect, write=dialect)` for normalisation | Used only in `normalise.py`. Failure is caught and falls back gracefully. |
| `adbc-driver-manager` | Type references for cursor interface (`adbc_driver_manager.dbapi.Cursor`) | Used in `proxy.py` for type hints and interface reference. Not a hard runtime dependency -- the proxy duck-types the interface. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `plugin.py` <-> `proxy.py` | `plugin.py` constructs `ReplayConnection` via factory in `.wrap()` | Plugin passes config (mode, cassette dir, dialect); proxy returns wrapped connection |
| `proxy.py` <-> `cassette.py` | `ReplayCursor` calls `cassette.record(key, table)` and `cassette.load(index)` | Proxy owns the execute/fetch lifecycle; cassette owns file I/O |
| `cassette.py` <-> `normalise.py` | Cassette builds `CassetteKey` using `normalise_sql()` | Normaliser is a pure function; cassette calls it during both record and replay |
| `plugin.py` <-> pytest markers | `request.node.get_closest_marker("adbc_cassette")` | Standard pytest marker API; plugin reads marker args for cassette name and dialect |

### Relationship to pytest-recording

Both plugins coexist independently. They share no code, no fixtures, and no state. They follow matching conventions:

| Aspect | pytest-recording | pytest-adbc-replay |
|--------|-----------------|-------------------|
| CLI flag | `--record-mode` | `--adbc-record` |
| Marker | `@pytest.mark.vcr` | `@pytest.mark.adbc_cassette` |
| Cassette dir | `tests/cassettes/` | `tests/cassettes/` (configurable, may want a separate default) |
| Record modes | `none`, `once`, `new_episodes`, `all` | Same four modes |
| Transport | HTTP (urllib3/requests) | ADBC cursor |

**Note on cassette directory:** If both plugins share `tests/cassettes/`, HTTP cassettes (YAML) and ADBC cassettes (directories with .arrow files) will coexist. This works because their file formats do not collide. However, a separate default like `tests/adbc_cassettes/` may be cleaner and avoids any confusion.

## Sources

- Installed pytest source: `/Users/paul/Documents/Dev/Personal/pytest-adbc-replay/.venv/lib/python3.14/site-packages/_pytest/hookspec.py` -- hook specifications (HIGH confidence)
- Installed pytest-cov source: `/Users/paul/Documents/Dev/Personal/pytest-adbc-replay/.venv/lib/python3.14/site-packages/pytest_cov/plugin.py` -- reference plugin structure (HIGH confidence)
- Installed pytest-cov entry_points: `/Users/paul/Documents/Dev/Personal/pytest-adbc-replay/.venv/lib/python3.14/site-packages/pytest_cov-7.0.0.dist-info/entry_points.txt` -- entry point format (HIGH confidence)
- Project design document: `/Users/paul/Documents/Dev/Personal/pytest-adbc-replay/_notes/pytest-adbc-replay-design.md` (HIGH confidence -- project-internal)
- pluggy documentation and hook system -- training data knowledge of pluggy 1.x API (MEDIUM confidence -- not independently verified against current docs, but confirmed consistent with installed pluggy 1.6.0 source)
- pytest-recording / VCR.py conventions -- training data knowledge (MEDIUM confidence -- not verified via current source, but well-established patterns)

---
*Architecture research for: pytest-adbc-replay*
*Researched: 2026-02-28*
