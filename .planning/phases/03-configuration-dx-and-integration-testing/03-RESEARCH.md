# Phase 3: Configuration, DX, and Integration Testing - Research

**Researched:** 2026-02-28
**Domain:** pytest plugin configuration (`addini`/`getini`), `pytest_report_header` hook, pytester integration testing, `adbc-driver-sqlite` DBAPI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Ini configuration (CONF-01, CONF-02, CONF-03)
- Register three ini keys via `parser.addini()` in `pytest_addoption`:
  - `adbc_cassette_dir` (string, default `"tests/cassettes"`) — replaces hardcoded default in `plugin.py:101`
  - `adbc_record_mode` (string, default `"none"`) — fallback when `--adbc-record` CLI flag is not given
  - `adbc_dialect` (string, default `""`) — global SQL dialect; empty string = sqlglot auto-detect
- CLI flag `--adbc-record` takes precedence over `adbc_record_mode` ini value (standard pytest convention: explicit CLI wins)
- Config is consumed in the `adbc_replay` session fixture; the fixture reads ini values then applies CLI overrides
- Both `[tool.pytest.ini_options]` (pyproject.toml) and `[pytest]` (pytest.ini) sections work automatically via `addini()` — no extra handling needed

#### Pytest header line (DX-01)
- Implement `pytest_report_header` hook in `plugin.py`
- Output exactly: `adbc-replay: record mode = {mode}` (matches success criteria wording)
- Do not include cassette dir or dialect in the header line — keep it minimal; those are discoverable from config files

#### Scrubbing hook stub (DX-02)
- Follow the `adbc_param_serialisers` fixture pattern — expose as a session-scoped fixture that users override in conftest.py
- Fixture name: `adbc_scrubber` (returns `None` by default)
- `ReplaySession` accepts an optional `scrubber` argument (stores it, never calls it in Phase 3)
- This makes the interface: "override `adbc_scrubber` in your conftest to register a callback" — identical pattern to `adbc_param_serialisers`
- No pluggy hook needed at this stage; a simple fixture override is sufficient for the v2 implementation slot

#### Integration test (Phase 3 success criterion 4)
- Add `adbc-driver-sqlite` to `[dependency-groups] dev` in pyproject.toml
- Write one pytester integration test in `tests/test_integration.py` (or `test_e2e.py`) that:
  1. Runs a real pytest subprocess via `pytester.runpytest` with `--adbc-record=once`
  2. The subprocess test connects to an in-memory SQLite DB via adbc-driver-sqlite, executes a real query, and records the cassette
  3. Runs the subprocess again with `--adbc-record=none` (replay-only) — the test must pass without any DB connection
- Test uses `pytester.makepyfile` to generate the test file, matching the pattern already in `test_plugin.py`
- Keep the integration test to a single scenario (record-then-replay); mode-specific edge cases are already covered by unit tests in `test_record_modes.py`

### Claude's Discretion
- Exact `pytest_report_header` signature and return type
- Whether to use `config.getoption` with a fallback or `config.getini` for reading values (standard pattern)
- SQLite query used in the integration test (any simple query is fine, e.g. `SELECT 1` or `CREATE TABLE / INSERT / SELECT`)
- File placement of integration test (`test_integration.py` vs `test_e2e.py`)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONF-01 | User can configure cassette directory via `adbc_cassette_dir` in `pyproject.toml`/`pytest.ini` | `parser.addini("adbc_cassette_dir", ..., type="string", default="tests/cassettes")` + `config.getini("adbc_cassette_dir")` in fixture; both config formats handled automatically |
| CONF-02 | User can configure default record mode via `adbc_record_mode` in `pyproject.toml`/`pytest.ini` | `parser.addini("adbc_record_mode", ..., type="string", default="none")` + CLI `--adbc-record` overrides via `config.getoption` with ini fallback pattern |
| CONF-03 | User can configure default SQL dialect via `adbc_dialect` in `pyproject.toml`/`pytest.ini` | `parser.addini("adbc_dialect", ..., type="string", default="")` + pass `None` to normaliser when empty string |
| DX-01 | Record mode printed in pytest header output | `pytest_report_header(config)` hook in `plugin.py` returning `f"adbc-replay: record mode = {mode}"` — verified pattern from Context7 |
| DX-02 | Plugin provides empty scrubbing hook slot | `adbc_scrubber` session-scoped fixture (returns `None`); `ReplaySession.__init__` adds `scrubber` param; stored but never called in Phase 3 |
</phase_requirements>

---

## Summary

Phase 3 is primarily a wiring phase: no new algorithms or data structures are required. All three technical domains — ini configuration, the report header hook, and the integration test — use well-established pytest patterns that are verified in current official documentation.

The `parser.addini()` / `config.getini()` API is stable, and the interaction between ini defaults and CLI overrides follows the standard pytest pattern: read ini with `config.getini()`, then override with `config.getoption()` if the CLI value is not the default. The `pytest_report_header` hook is trivially simple — it returns a string (or list of strings), and the return value is rendered directly in the test session header.

The integration test is the most non-trivial piece: it uses `adbc-driver-sqlite` (a real ADBC driver) in a `pytester.runpytest()` subprocess to exercise the full record-then-replay cycle. The `adbc_driver_sqlite.dbapi.connect()` call (no URI = in-memory SQLite) is confirmed by official ADBC documentation. The `pytester` fixture pattern is already established across ~10 test methods in `tests/test_plugin.py` — the integration test is an extension of that existing pattern.

**Primary recommendation:** Implement all three areas in `plugin.py` (the only file that needs changes beyond `_session.py` + new test file). The changes are: add three `addini()` calls, read them in the `adbc_replay` fixture with the CLI-override pattern, add `pytest_report_header`, add `adbc_scrubber` fixture, and update `ReplaySession.__init__` to accept `scrubber`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=8.0 (project dep; current: 9.x) | `parser.addini()`, `config.getini()`, `pytest_report_header`, `pytester` fixture | All plugin configuration APIs are in pytest itself; no additional libraries needed |
| adbc-driver-sqlite | latest (to be added as dev dep) | Real ADBC driver for integration test record-then-replay | SQLite is the only bundled-in-Python-tree ADBC driver; enables E2E test without a cloud warehouse |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | stdlib | Convert `config.getini("adbc_cassette_dir")` string to `Path` | Already used everywhere in project |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `adbc-driver-sqlite` for integration test | `adbc-driver-postgresql` or mock | SQLite needs no external server; PostgreSQL would require Docker or a test instance. SQLite is the obvious choice for CI-safe integration tests |
| `parser.addini()` for config | `pytest_configure` + `config.option` namespace | `addini()` is the official mechanism for file-based config; `pytest.ini` and `pyproject.toml [tool.pytest.ini_options]` both work automatically |

**Installation (new dev dependency):**
```bash
uv add --dev adbc-driver-sqlite
```

---

## Architecture Patterns

### Recommended Change Set (Phase 3)

```
src/pytest_adbc_replay/
├── plugin.py              # MODIFY: addini() calls, getini() in adbc_replay,
│                          #          pytest_report_header, adbc_scrubber fixture
└── _session.py            # MODIFY: ReplaySession.__init__ adds scrubber param

tests/
└── test_integration.py    # NEW: pytester E2E record-then-replay test
```

No new modules required. All changes are localised to `plugin.py`, `_session.py`, and one new test file.

### Pattern 1: `parser.addini()` — Registering Ini Keys

**What:** Register configuration file keys (readable from `pyproject.toml [tool.pytest.ini_options]` or `pytest.ini [pytest]`).

**When to use:** In `pytest_addoption`, alongside existing `addoption()` calls.

**Example (verified via Context7, pytest stable docs):**

```python
# src/pytest_adbc_replay/plugin.py — inside pytest_addoption()
def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("adbc-replay", "ADBC cassette record/replay")
    group.addoption(
        "--adbc-record",
        action="store",
        default="none",
        choices=list(_RECORD_MODES),
        help="...",
    )
    # Phase 3 additions:
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
        help="Default SQL dialect for sqlglot normalisation (default: '' = auto-detect).",
        type="string",
        default="",
    )
```

**Key points:**
- `type="string"` is the correct type for all three values (not `"path"` — we do the `Path()` conversion ourselves)
- `addini()` is called directly on `parser`, not on a group (groups are for CLI options only)
- Both `pyproject.toml [tool.pytest.ini_options]` and `pytest.ini [pytest]` are resolved automatically — no extra handling needed

### Pattern 2: CLI-Override-over-Ini — Reading Config in Fixture

**What:** Read the ini value as the base, then override with the CLI value if the user supplied it explicitly.

**When to use:** In the `adbc_replay` session fixture, to give CLI `--adbc-record` precedence over `adbc_record_mode` ini.

**The pytest standard pattern (verified via pytest docs):**

```python
# The "getoption with default" pattern disambiguates "user passed --adbc-record"
# from "defaulted to none because user didn't pass anything".
#
# Challenge: getoption("--adbc-record") always returns SOMETHING (the argparse default).
# There is no built-in "was this option explicitly passed?" sentinel.
#
# The correct pattern: set the CLI default to None (sentinel), read ini as fallback.

# In pytest_addoption:
group.addoption(
    "--adbc-record",
    action="store",
    default=None,           # <-- sentinel: None means "not supplied"
    choices=list(_RECORD_MODES) + [None],   # allow None internally
    # NOTE: choices validation in pytest/argparse; see pitfall below
    ...
)

# In adbc_replay fixture:
cli_mode = request.config.getoption("--adbc-record")       # None if not passed
ini_mode = request.config.getini("adbc_record_mode")       # e.g. "none" from ini
mode = cli_mode if cli_mode is not None else ini_mode      # CLI wins
```

**IMPORTANT CAVEAT:** Making `default=None` for `--adbc-record` breaks the `choices` validation because `None` is not in the choices list. There are two safe approaches:

**Approach A (recommended — simpler):** Keep `default="none"` on the CLI option (existing code), always read ini too, and use CLI value unless it equals the default AND the ini differs — but this is ambiguous (was `none` passed explicitly or defaulted?).

**Approach B (recommended by pytest-recording and many plugins):** Change the CLI `default` to `None` and add a sentinel value. But `choices=list(_RECORD_MODES)` would need to allow `None`. Argparse's `choices` check fails for `None` if `None` is not in choices. The fix: set `choices=None` (removes choices validation on the CLI argument itself) and validate manually in the fixture. This is fragile.

**Approach C (simplest, what existing tests already use):** Always use `config.getoption("--adbc-record")` — the CLI value. If the user wants a different default, they set it via `adbc_record_mode` in their ini file AND always pass `--adbc-record` in CI. The ini value becomes a "static default" for the case where CLI is not passed.

**Recommended final approach — Approach D:** Change `--adbc-record` default from `"none"` to `None`, do NOT include `None` in `choices`, handle the fallback in the fixture. Argparse processes choices validation AFTER applying the default only if the option is actually supplied on the command line. If the option is absent, the default is used without choices validation. This is safe:

```python
# In pytest_addoption:
group.addoption(
    "--adbc-record",
    action="store",
    default=None,           # None = "not supplied by user"
    choices=list(_RECORD_MODES),   # only applies when user actually passes the flag
    help="...",
)

# In adbc_replay fixture:
cli_mode: str | None = request.config.getoption("--adbc-record")
ini_mode: str = request.config.getini("adbc_record_mode") or "none"
mode: str = cli_mode if cli_mode is not None else ini_mode
```

**Verification:** argparse applies choices validation only when the argument is present on the command line, not when the default is used. This is standard argparse behaviour — the `default` value bypasses choices checking.

### Pattern 3: `pytest_report_header` Hook

**What:** Add a line to the pytest session header. Hook is called once per session at the start.

**When to use:** In `plugin.py` at module level (as a regular function, not a fixture).

**Example (verified via Context7, pytest stable docs):**

```python
# src/pytest_adbc_replay/plugin.py

def pytest_report_header(config: pytest.Config) -> str:
    """Add record mode to the pytest session header (DX-01)."""
    cli_mode: str | None = config.getoption("--adbc-record")
    ini_mode: str = config.getini("adbc_record_mode") or "none"
    mode: str = cli_mode if cli_mode is not None else ini_mode
    return f"adbc-replay: record mode = {mode}"
```

**Signature:** `pytest_report_header(config: pytest.Config) -> str | list[str]`

- Returning a `str` adds one line; returning a `list[str]` adds multiple lines
- The hook is called on all registered plugins — no `@hookimpl` decorator required for simple return
- Return value is displayed in the session header between the platform line and `rootdir:`

### Pattern 4: `adbc_scrubber` Session-Scoped Fixture

**What:** Expose a callable stub fixture that users can override in their `conftest.py`. Returns `None` by default.

**When to use:** Same fixture pattern as `adbc_param_serialisers` (already in `plugin.py:46`).

**Example:**

```python
# src/pytest_adbc_replay/plugin.py

from typing import Callable

@pytest.fixture(scope="session")
def adbc_scrubber() -> Callable[..., object] | None:
    """
    Session-scoped fixture providing a scrubbing callback for recorded data.

    Override this fixture in your conftest.py to register a callback that
    scrubs sensitive values before they are written to cassette files.
    The callback is stored but NOT called in v1 — this is the interface
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
```

**Wire into `adbc_replay` fixture** by adding `adbc_scrubber` as a parameter:

```python
@pytest.fixture(scope="session")
def adbc_replay(
    request: pytest.FixtureRequest,
    adbc_param_serialisers: dict[Any, dict[str, Any]] | None,
    adbc_scrubber: Callable[..., object] | None,
) -> ReplaySession:
    ...
    return ReplaySession(
        mode=mode,
        cassette_dir=cassette_dir,
        param_serialisers=adbc_param_serialisers,
        scrubber=adbc_scrubber,
    )
```

### Pattern 5: `ReplaySession` — Add `scrubber` Parameter

**What:** Add `scrubber` to `ReplaySession.__init__`, stored as `self.scrubber`. Never called in Phase 3.

**Example:**

```python
# src/pytest_adbc_replay/_session.py

class ReplaySession:
    def __init__(
        self,
        mode: str,
        cassette_dir: Path = _DEFAULT_CASSETTE_DIR,
        param_serialisers: dict[Any, dict[str, Any]] | None = None,
        scrubber: Callable[..., object] | None = None,
    ) -> None:
        self.mode = mode
        self.cassette_dir = cassette_dir
        self.param_serialisers = param_serialisers
        self.scrubber = scrubber  # stored; never called in v1
```

### Pattern 6: pytester Integration Test — Record-then-Replay

**What:** Full E2E test using `pytester.makepyfile()` and `pytester.runpytest()` to exercise the record-then-replay cycle with a real ADBC driver.

**When to use:** `tests/test_integration.py` — one test class, one test method (per CONTEXT.md).

**Example (verified against existing `test_plugin.py` patterns + ADBC SQLite docs):**

```python
# tests/test_integration.py

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


class TestRecordThenReplayCycle:
    """Full E2E record-then-replay cycle against adbc-driver-sqlite."""

    def test_record_then_replay_sqlite(self, pytester: pytest.Pytester) -> None:
        """Record with adbc-driver-sqlite, then replay without DB connection."""
        pytester.makepyfile(
            """
            import pytest
            import adbc_driver_sqlite.dbapi

            @pytest.fixture
            def db_conn(adbc_replay, request):
                return adbc_replay.wrap(
                    "adbc_driver_sqlite.dbapi",
                    request=request,
                )

            def test_sqlite_query(db_conn):
                cursor = db_conn.cursor()
                cursor.execute("SELECT 1 AS answer")
                result = cursor.fetch_arrow_table()
                assert result.column("answer").to_pylist() == [1]
        """
        )
        # First run: record the cassette
        result = pytester.runpytest("--adbc-record=once", "-v")
        result.assert_outcomes(passed=1)

        # Second run: replay without any DB connection (mode=none default)
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)
```

**Key insight:** The `pytester` fixture creates a temporary directory. The `adbc_replay` fixture will write cassettes to `{pytester.path}/tests/cassettes/`. The second `runpytest()` call runs in the same directory, so the cassette persists between runs.

**`adbc_driver_sqlite.dbapi` connection:** `connect()` with no URI creates an in-memory database. The plugin passes `driver_module_name="adbc_driver_sqlite.dbapi"` and calls `importlib.import_module("adbc_driver_sqlite.dbapi").connect()`. This works because `adbc_driver_sqlite.dbapi` exports a `connect()` function at the module level.

**Important:** The `db_kwargs` argument to `adbc_replay.wrap()` can be omitted or passed as `{}` for an in-memory SQLite connection. No URI is needed.

### Anti-Patterns to Avoid

- **Setting `addini()` on a group instead of directly on `parser`:** `group.addini()` does not exist. `addini()` is a method on `pytest.Parser`, not on `pytest.OptionGroup`. Always call `parser.addini()` directly.
- **Reading ini before options are registered:** `config.getini()` raises `ValueError` if called before `addini()` registers the key. The `adbc_replay` fixture is called after `pytest_addoption` — ordering is always correct.
- **Using `config.inicfg[name]` directly:** This is deprecated per pytest docs. Always use `config.getini(name)`.
- **Returning `None` from `pytest_report_header`:** Returning `None` produces no header line (silently skipped). Always return a string.
- **Forgetting `pytest_plugins = ["pytester"]` in conftest:** The `tests/conftest.py` already has this — the integration test file does not need to add it separately.
- **Using `adbc_replay.wrap(driver_module_name=..., db_kwargs=...)` with non-module driver names:** The driver module must be importable by `importlib.import_module()`. `"adbc_driver_sqlite.dbapi"` works correctly. `"adbc_driver_sqlite"` alone does not expose `connect()` at the top level.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reading config from pyproject.toml/pytest.ini | Custom config file parser | `parser.addini()` + `config.getini()` | pytest handles all config file formats, search path, and inheritance automatically |
| Report header output | Custom output hook or `print()` | `pytest_report_header` hook | Only correct hook for session header; `print()` goes to stdout not the header |
| Distinguishing CLI-supplied vs defaulted options | Custom argparse tracking | `default=None` sentinel on `addoption` + `getini` fallback | Standard pattern used by pytest-recording and pytest-cov; no custom tracking needed |

---

## Common Pitfalls

### Pitfall 1: `--adbc-record` CLI `choices` Validation with `None` Default

**What goes wrong:** Changing `--adbc-record` default from `"none"` to `None` causes pytest to output a confusing error if the user runs `--adbc-record` without specifying a mode (edge case). More practically, existing tests use `result.assert_outcomes(passed=1)` after `runpytest("--adbc-record=none")` — those still work because `"none"` is in choices.

**Why it happens:** argparse choices validation runs on CLI-supplied values only, not on the default. So `default=None` with `choices=["none", "once", "new_episodes", "all"]` is valid: None bypasses choices check.

**How to avoid:** Set `default=None` on the option. In the fixture and `pytest_report_header`, always do `cli_mode = config.getoption("--adbc-record")` and check `if cli_mode is not None`. The existing test for `test_invalid_mode_rejected` (`runpytest("--adbc-record=invalid")`) still works — `"invalid"` hits choices validation correctly.

**Warning signs:** If `test_adbc_record_option_accepted` (existing test) now fails because `getoption` returns `None` when the test passes `"--adbc-record=none"` — it shouldn't, because `"none"` is supplied explicitly on the command line.

### Pitfall 2: `pytest_report_header` Called Before Ini Keys Are Registered

**What goes wrong:** `pytest_report_header` is called after `pytest_addoption` in the pytest lifecycle, so `config.getini("adbc_record_mode")` is safe to call inside it. But if a test calls `config.getini()` in a context where `addini()` was not called (e.g. wrong plugin registration), a `ValueError` is raised.

**Why it happens:** `addini()` must be called in `pytest_addoption`. The `pytest_report_header` hook is called later, after all options are registered.

**How to avoid:** Both hooks are in the same `plugin.py` module, which is loaded as a plugin via `pytest11` entry point. Ordering is guaranteed. No defensive try/except needed.

**Warning signs:** `ValueError: unknown configuration value: 'adbc_record_mode'` — means `addini()` was not called, or the plugin is not being loaded.

### Pitfall 3: Integration Test Cassette Path Mismatch

**What goes wrong:** The second `pytester.runpytest()` call (replay mode) fails because the cassette path expected by the plugin does not match where the first run wrote the cassette.

**Why it happens:** The cassette path is derived from the test node ID: `{cassette_dir}/{module_name}/{test_name}`. The `pytester.makepyfile(content)` call creates a file named `test_<modulename>.py` (pytest derives the name from the call, defaulting to the test function name). The cassette directory defaults to `tests/cassettes` relative to the pytester temp directory.

**How to avoid:** Verify the cassette exists after the record run by adding an assertion:
```python
result = pytester.runpytest("--adbc-record=once", "-v")
result.assert_outcomes(passed=1)
cassette_base = pytester.path / "tests" / "cassettes"
assert cassette_base.exists(), "cassette directory was not created"
```
The test name must be stable — use a fixed function name in `makepyfile` (e.g. `def test_sqlite_query`), not a dynamically generated name.

**Warning signs:** Second run fails with `CassetteMissError`; cassette directory is empty or not found.

### Pitfall 4: `adbc_driver_sqlite.dbapi.connect()` vs `adbc_driver_sqlite.connect()`

**What goes wrong:** Passing `driver_module_name="adbc_driver_sqlite"` to `adbc_replay.wrap()` fails because `importlib.import_module("adbc_driver_sqlite")` does not expose `connect()` at the top level.

**Why it happens:** The DBAPI-compatible API is in `adbc_driver_sqlite.dbapi`, not in the top-level package.

**How to avoid:** Always use `driver_module_name="adbc_driver_sqlite.dbapi"` for the SQLite driver. The `ReplayConnection.__init__` calls `importlib.import_module(driver_module_name).connect(**db_kwargs)` — this maps to `adbc_driver_sqlite.dbapi.connect()`.

**Warning signs:** `AttributeError: module 'adbc_driver_sqlite' has no attribute 'connect'`.

### Pitfall 5: `adbc_dialect` Empty String vs `None` for sqlglot

**What goes wrong:** `config.getini("adbc_dialect")` returns `""` (empty string) when not set. Passing `""` to `normalise_sql(sql, dialect="")` instead of `None` may cause sqlglot to look for a dialect named `""`, which does not exist.

**Why it happens:** `addini(default="")` is correct — empty string is the user-visible representation of "no dialect". But the normaliser expects `dialect: str | None`, where `None` means auto-detect.

**How to avoid:** In the fixture, convert empty string to `None`:
```python
raw_dialect: str = request.config.getini("adbc_dialect")
dialect: str | None = raw_dialect if raw_dialect else None
```
Pass `dialect` to `ReplaySession` (and propagate to `ReplayConnection` and `ReplayCursor`).

**Warning signs:** sqlglot raises `UnsupportedError` or `ParseError` for valid SQL when `dialect=""` is passed instead of `None`.

### Pitfall 6: basedpyright Strict Mode Type Errors

**What goes wrong:** Pre-commit hook fails with type errors in new code.

**Why it happens:** `basedpyright` configured with `typeCheckingMode = "strict"`. Common issues in Phase 3:
- `adbc_scrubber` fixture return type must be fully annotated
- `scrubber` parameter in `ReplaySession.__init__` needs a proper type annotation
- `config.getoption("--adbc-record")` return type is `object` in basedpyright strict — needs `cast` or explicit annotation

**How to avoid:**
- Use `from typing import Callable` for the scrubber type
- For `config.getoption`, cast: `cli_mode = cast("str | None", config.getoption("--adbc-record"))`
- All new functions need full return type annotations

**Warning signs:** `prek run --all-files` fails with `error: Type "object" is not assignable to type "str | None"`.

---

## Code Examples

Verified patterns from official sources:

### `parser.addini()` — Three Ini Keys

```python
# Source: https://docs.pytest.org/en/stable/reference/reference.html#pytest.Parser.addini
# In pytest_addoption(), after the existing addoption() call:

parser.addini(
    "adbc_cassette_dir",
    help="Directory for ADBC cassette files.",
    type="string",
    default="tests/cassettes",
)
parser.addini(
    "adbc_record_mode",
    help="Default ADBC record mode (none/once/new_episodes/all).",
    type="string",
    default="none",
)
parser.addini(
    "adbc_dialect",
    help="Default SQL dialect for sqlglot normalisation (empty = auto-detect).",
    type="string",
    default="",
)
```

### `adbc_replay` Fixture — Reading Ini with CLI Override

```python
# Source: Context7 /pytest-dev/pytest, pytest stable docs

@pytest.fixture(scope="session")
def adbc_replay(
    request: pytest.FixtureRequest,
    adbc_param_serialisers: dict[Any, dict[str, Any]] | None,
    adbc_scrubber: Callable[..., object] | None,
) -> ReplaySession:
    cli_mode = cast("str | None", request.config.getoption("--adbc-record"))
    ini_mode: str = request.config.getini("adbc_record_mode") or "none"
    mode: str = cli_mode if cli_mode is not None else ini_mode

    raw_cassette_dir: str = request.config.getini("adbc_cassette_dir") or "tests/cassettes"
    cassette_dir = Path(raw_cassette_dir)

    raw_dialect: str = request.config.getini("adbc_dialect")
    dialect: str | None = raw_dialect if raw_dialect else None

    return ReplaySession(
        mode=mode,
        cassette_dir=cassette_dir,
        param_serialisers=adbc_param_serialisers,
        scrubber=adbc_scrubber,
        dialect=dialect,
    )
```

Note: `ReplaySession` may need a `dialect` parameter too (for the global default). Check whether `ReplaySession.wrap()` already passes `dialect` down — it does via `resolved_dialect`. The global dialect needs to flow: `ReplaySession.dialect` → `ReplaySession.wrap()` → `ReplayConnection.dialect` → `ReplayCursor.dialect`. Currently, `wrap()` accepts `dialect=None` as a parameter. The global ini dialect should be the fallback when `wrap(dialect=None)` and no marker is set.

### `pytest_report_header` Hook

```python
# Source: Context7 /pytest-dev/pytest (doc/en/example/simple.md)
# Returns a string; displayed in the session header.

def pytest_report_header(config: pytest.Config) -> str:
    """Display active record mode in pytest header (DX-01)."""
    cli_mode = cast("str | None", config.getoption("--adbc-record"))
    ini_mode: str = config.getini("adbc_record_mode") or "none"
    mode: str = cli_mode if cli_mode is not None else ini_mode
    return f"adbc-replay: record mode = {mode}"
```

### `adbc_driver_sqlite.dbapi` — ADBC SQLite DBAPI Pattern

```python
# Source: https://arrow.apache.org/adbc/current/driver/sqlite.html
# Source: https://arrow.apache.org/adbc/current/python/quickstart.html

import adbc_driver_sqlite.dbapi

# Connect to in-memory database (no URI = in-memory)
with adbc_driver_sqlite.dbapi.connect() as conn:
    with conn.cursor() as cursor:
        cursor.execute("SELECT 1 AS answer")
        result = cursor.fetch_arrow_table()
        # result is a pyarrow.Table
        assert result.column("answer").to_pylist() == [1]
```

### Integration Test Pattern (pytester)

```python
# Source: Existing tests/test_plugin.py patterns + CONTEXT.md

class TestRecordThenReplayCycle:
    def test_record_then_replay_sqlite(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            """
            import pytest
            import adbc_driver_sqlite.dbapi

            @pytest.fixture
            def db_conn(adbc_replay, request):
                return adbc_replay.wrap(
                    "adbc_driver_sqlite.dbapi",
                    request=request,
                )

            def test_sqlite_query(db_conn):
                cursor = db_conn.cursor()
                cursor.execute("SELECT 1 AS answer")
                result = cursor.fetch_arrow_table()
                assert result.column("answer").to_pylist() == [1]
        """
        )
        # Run 1: record
        result = pytester.runpytest("--adbc-record=once", "-v")
        result.assert_outcomes(passed=1)

        # Run 2: replay (default mode=none)
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `config.inicfg["name"]` to read ini values | `config.getini("name")` | Deprecated in recent pytest | `inicfg` was never public API; `getini()` caches, transforms, and aliases correctly |
| `[tool.pytest.ini_options]` only (pytest <9) | `[tool.pytest]` with native TOML types (pytest >=9.0) | pytest 9.0 | Project has `pytest>=8.0` in deps — `[tool.pytest.ini_options]` is the right section to document |
| `addini()` without `type=` | `addini(..., type="string", default=...)` | Explicit type is cleaner | Without `type=`, defaults to string but is less self-documenting; always specify both |

**Note on `[tool.pytest]` vs `[tool.pytest.ini_options]`:** pytest 9.0 added native TOML type support via `[tool.pytest]`. The project has `pytest>=8.0`, so the documentation example should use `[tool.pytest.ini_options]` for the widest compatibility. The plugin itself does not need to care which section the user puts values in — `addini()` handles both.

---

## Open Questions

1. **Does `ReplaySession` need a `dialect` attribute for the global ini default?**
   - What we know: `ReplaySession.wrap()` accepts `dialect=None` and applies the marker override. Currently there is no "session-level global dialect" attribute on `ReplaySession`.
   - What's unclear: When `adbc_dialect` is set in `pyproject.toml` and `wrap()` is called without `dialect=`, should the ini dialect be used?
   - Recommendation: Yes — add `self.dialect: str | None = dialect` to `ReplaySession.__init__` and update `wrap()` to use `self.dialect` as the fallback (before `None`). The priority chain becomes: marker > explicit `wrap(dialect=...)` > session global > `None`.

2. **Should `--adbc-record` default change from `"none"` to `None`?**
   - What we know: Currently defaults to `"none"`. Changing to `None` is required for the CLI-override-over-ini pattern. Argparse skips choices validation for defaults — `None` with `choices=["none",...]` is valid.
   - What's unclear: Existing tests call `getoption("--adbc-record", default="none")`. With `default=None`, calling `getoption` returns `None` (not `"none"`) when flag is absent.
   - Recommendation: Change to `default=None`. Update all getoption call sites. Existing tests that pass `--adbc-record=none` explicitly still work.

3. **Should the integration test use `SELECT 1` or a more complex query?**
   - Recommendation (Claude's discretion per CONTEXT.md): `SELECT 1 AS answer` is sufficient. It exercises the full record/replay cycle without requiring DDL. Use `fetch_arrow_table()` to verify the result column, not just `fetchall()` (Arrow path is the primary value of the plugin).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (already installed) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` (inferred; no explicit testpaths configured) |
| Quick run command | `python -m pytest tests/test_integration.py -x -v` |
| Full suite command | `python -m pytest -x -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-01 | `adbc_cassette_dir` ini key is read and used as cassette directory | pytester integration | `pytest tests/test_plugin.py::TestIniConfig::test_cassette_dir_from_ini -x` | Wave 0 |
| CONF-02 | `adbc_record_mode` ini key used as default when `--adbc-record` not passed | pytester integration | `pytest tests/test_plugin.py::TestIniConfig::test_record_mode_from_ini -x` | Wave 0 |
| CONF-03 | `adbc_dialect` ini key sets global SQL dialect | pytester integration | `pytest tests/test_plugin.py::TestIniConfig::test_dialect_from_ini -x` | Wave 0 |
| DX-01 | `adbc-replay: record mode = {mode}` appears in pytest header output | pytester integration | `pytest tests/test_plugin.py::TestReportHeader::test_header_contains_mode -x` | Wave 0 |
| DX-02 | `adbc_scrubber` fixture returns `None` by default; `ReplaySession` stores it | unit + pytester | `pytest tests/test_plugin.py::TestScrubberFixture -x` | Wave 0 |
| E2E | Full record-then-replay cycle with adbc-driver-sqlite | pytester integration | `pytest tests/test_integration.py -x -v` | Wave 0 (new file) |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_plugin.py tests/test_integration.py -x -v`
- **Per wave merge:** `python -m pytest -x -v` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_integration.py` — new file; covers E2E record-then-replay (success criterion 4)
- [ ] `tests/test_plugin.py::TestIniConfig` — new test class; covers CONF-01, CONF-02, CONF-03
- [ ] `tests/test_plugin.py::TestReportHeader` — new test class; covers DX-01
- [ ] `tests/test_plugin.py::TestScrubberFixture` — new test class; covers DX-02

---

## Sources

### Primary (HIGH confidence)

- `/pytest-dev/pytest` (Context7) — `addini()` API, `getini()` semantics, `pytest_report_header` hook signature and return value, `pytester` fixture pattern
- https://docs.pytest.org/en/stable/reference/reference.html — `Parser.addini()` signature (`name`, `help`, `type`, `default`); `Config.getini()` behaviour and `ValueError` on unregistered keys
- https://arrow.apache.org/adbc/current/driver/sqlite.html — `adbc_driver_sqlite.dbapi.connect()` with no URI = in-memory SQLite
- https://arrow.apache.org/adbc/current/python/quickstart.html — `cursor.execute()`, `cursor.fetch_arrow_table()` ADBC patterns
- `/Users/paul/Documents/Dev/Personal/pytest-adbc-replay/.planning/phases/03-configuration-dx-and-integration-testing/03-CONTEXT.md` — authoritative user decisions

### Secondary (MEDIUM confidence)

- https://pypi.org/project/adbc-driver-sqlite/ — confirmed package exists and is installable; latest version as of Feb 2026
- Existing `tests/test_plugin.py` — pytester patterns verified by reading project source directly; confidence HIGH (first-party)

### Tertiary (LOW confidence)

- argparse behaviour re: `default=None` bypassing `choices` validation — based on argparse documentation behaviour (standard library) but not directly verified against pytest's argparse wrapper

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all APIs verified via Context7 (pytest) and official ADBC docs
- Architecture: HIGH — CONTEXT.md provides locked decisions for all implementation choices; existing code patterns directly observed
- Pitfalls: HIGH — derived from CONTEXT.md, basedpyright strict mode (already known from Phases 1-2), and direct code inspection

**Research date:** 2026-02-28
**Valid until:** 2026-05-28 (pytest ini/config API is stable; adbc-driver-sqlite API is stable; record-then-replay semantics are product decisions locked in CONTEXT.md)
