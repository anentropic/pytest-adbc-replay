# Stack Research

**Domain:** pytest plugin -- record/replay testing of ADBC database connections
**Researched:** 2026-02-28
**Confidence:** HIGH (all versions verified from PyPI; entry_point pattern verified from pytest-recording source)

## Python Version

| Constraint | Value | Rationale |
|------------|-------|-----------|
| `requires-python` | `>=3.11` | pyarrow, adbc-driver-manager, and pytest 9 all require `>=3.10`. Setting floor at 3.11 is safe: it gives us `tomllib` in stdlib (useful for config parsing without extras), `StrEnum`, `ExceptionGroup`, and `TaskGroup` for free. 3.10 reaches EOL Oct 2026, so supporting it adds maintenance cost for a shrinking user base. The existing `pyproject.toml` already declares `>=3.11`. |
| Type-checking target | `3.14` | Already configured in `pyproject.toml` for basedpyright. Use latest syntax features in type stubs. |

**Confidence:** HIGH -- verified requires-python for all core deps on PyPI.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| **pytest** | `>=8.0,<10` | Plugin host framework | Pin floor at 8.0 for stable `pytester` fixture and modern hook signatures. Pytest 9.0.2 is current (Feb 2026). Floor of 8.0 keeps compat with projects not yet on 9. Upper bound `<10` avoids silent breakage on next major. | HIGH |
| **pyarrow** | `>=17.0` | Arrow IPC serialisation for cassette result files | Core to the project -- cassette results are stored as Arrow IPC files. `pyarrow.ipc.RecordBatchFileWriter` / `RecordBatchFileReader` are the stable API. v17+ is a reasonable floor (matches dbt-core 1.9+ ecosystem). Current is 23.0.1. No upper pin -- pyarrow maintains backward compat on IPC APIs. | HIGH |
| **sqlglot** | `>=26.0` | SQL normalisation for cassette key matching | `sqlglot.transpile()` with `read`/`write` dialect params is the core API used for normalisation. v26+ stabilised the dialect enum naming and the `pretty` flag behaviour. Current is 29.0.1. sqlglot moves fast (weekly releases) but the `transpile()` surface we use is stable. Floor at 26 avoids pre-stabilisation dialect name changes. | HIGH |
| **adbc-driver-manager** | `>=1.0` | Type references for cursor/connection interface; DBAPI2 module | Provides `adbc_driver_manager.dbapi.Connection` and `adbc_driver_manager.dbapi.Cursor` -- the types our proxy wraps. v1.0 was the first stable release; current is 1.10.0. Pin at `>=1.0` for maximum driver compatibility. This is a runtime dependency because we import its types, but specific backend drivers (snowflake, databricks, etc.) are NOT our dependency. | HIGH |

### Plugin Registration

| Mechanism | Configuration | Why |
|-----------|--------------|-----|
| `[project.entry-points.pytest11]` | `adbc_replay = "pytest_adbc_replay.plugin"` | Standard pytest plugin entry point. The `pytest11` group is how pytest discovers plugins at install time. Verified from pytest docs and pytest-recording source. No `conftest.py`-based registration -- entry_points is the correct approach for distributed plugins. | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| **pytest** (pytester) | built-in | Testing the plugin itself | Always. `pytester` is pytest's built-in fixture for testing pytest plugins. It runs pytest in a subprocess, creates temporary test directories, and captures results. Requires `pytest_plugins = ["pytester"]` in the test `conftest.py`. No separate package needed -- it ships with pytest. | HIGH |
| **pytest-cov** | `>=6.0` | Coverage measurement | Dev dependency only. Current is 7.0.0. Used during plugin development, not shipped to users. | HIGH |
| **ruff** | `>=0.15` | Linting + formatting | Dev dependency. Current is 0.15.4. Replaces flake8+isort+black. Already configured in `pyproject.toml`. | HIGH |
| **basedpyright** | `>=1.38` | Type checking | Dev dependency. Current is 1.38.2. Strict mode already configured. Preferred over mypy for speed and stricter defaults. | HIGH |

### Build & Packaging

| Tool | Version | Purpose | Why | Confidence |
|------|---------|---------|-----|------------|
| **uv** | `>=0.9` | Package manager, venv, lockfile | Already in use (uv.lock present). uv is the standard fast Python package manager in 2026. Handles dependency resolution, venv creation, and lockfiles. Current installed: 0.9.18. | HIGH |
| **uv_build** | `>=0.9.18,<1` | PEP 517 build backend | Already configured in `pyproject.toml`. uv's native build backend -- simpler than hatchling for pure-Python packages, integrates tightly with uv workflows. Current is 0.10.7. Keep the `<1` upper bound already in pyproject.toml until uv_build reaches 1.0. | HIGH |
| **pyproject.toml** | (standard) | Project metadata, build config, tool config | Single source of truth for project metadata, dependencies, entry_points, ruff config, basedpyright config, and pytest ini_options. No `setup.py`, no `setup.cfg`, no `requirements.txt`. | HIGH |

## Installation

```bash
# Project setup (already done)
uv init

# Add runtime dependencies
uv add pyarrow ">=17.0"
uv add sqlglot ">=26.0"
uv add adbc-driver-manager ">=1.0"
uv add pytest ">=8.0,<10"

# Dev dependencies (already partially configured)
uv add --group dev pytest-cov ">=6.0"
uv add --group dev ruff ">=0.15"
uv add --group dev basedpyright ">=1.38"

# For integration testing with a real ADBC driver (optional, dev only)
uv add --group dev adbc-driver-sqlite ">=1.0"
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| SQL normalisation | **sqlglot** | `sqlparse` | sqlparse only tokenises -- it cannot normalise across dialects. sqlglot parses into an AST and re-emits canonically, handling keyword casing, whitespace, quote styles, and dialect-specific syntax. sqlglot is also likely already in dbt-adjacent dependency trees. |
| SQL normalisation | **sqlglot** | Manual regex/whitespace normalisation | Fragile. Misses quote normalisation, keyword casing, and comment stripping. Falls over on complex SQL. sqlglot handles edge cases we would spend weeks debugging. |
| Cassette format | **Arrow IPC** (.arrow files via pyarrow) | Parquet | Parquet loses schema-level metadata fidelity and adds a dependency (`pyarrow[parquet]` or `fastparquet`). Arrow IPC preserves schema metadata exactly and needs only `pyarrow` core. IPC files are also streamable (supports `RecordBatchStreamWriter` for large results). |
| Cassette format | **Arrow IPC** | JSON | JSON cannot represent Arrow type information (decimal precision, timestamp timezone, nested types). Round-tripping through JSON loses type fidelity. JSON is fine for the `.sql` and `.json` param/options sidecar files but not for result data. |
| Cassette format | **Arrow IPC** | CSV | Same problems as JSON, worse. No schema, no types. Not a serious option for structured data with schema metadata. |
| Build backend | **uv_build** | hatchling | hatchling is mature and widely used (pytest-recording uses it). uv_build is the native choice for uv-based projects. Both work; uv_build avoids an extra dependency and integrates better with `uv build` / `uv publish`. Either is fine -- project already uses uv_build, no reason to switch. |
| Build backend | **uv_build** | setuptools | setuptools is legacy for new projects. pyproject.toml-native backends (uv_build, hatchling, flit) are simpler and faster. |
| Type checker | **basedpyright** | mypy | basedpyright is faster, has stricter defaults, and catches more issues. Already configured in the project. mypy is fine but slower and less strict by default. |
| Type checker | **basedpyright** | pyright (non-based) | basedpyright adds stricter defaults and better error messages on top of pyright. Already chosen. |
| Plugin testing | **pytester** (built-in) | `pytest-pytester` (separate package) | `pytest-pytester` does not exist as a separate package. `pytester` is built into pytest and has been since pytest 6.2. Just declare `pytest_plugins = ["pytester"]` in your test conftest. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **VCR.py / pytest-recording** for ADBC traffic | VCR.py intercepts HTTP. Warehouse connectors vendor urllib3, making HTTP interception fragile. ADBC cursor is the correct interception seam. | This plugin (pytest-adbc-replay) |
| **snowflake-vcrpy** | Vendors VCR.py internally (conflicts if VCR.py is already a dep). Snowflake-only. HTTP-layer interception inherits vendoring fragility. | This plugin |
| **Keploy** | eBPF-based, requires Linux 5.10+, designed for full-app HTTP service recording. Wrong abstraction for library-level cursor testing. | This plugin |
| **DuckDB as test double** | Cannot validate warehouse-specific SQL (FLATTEN, LATERAL, Databricks functions, Snowflake semi-structured operators). Tests pass against DuckDB but fail against real warehouse. | Record/replay with real warehouse SQL and results |
| **sqlparse** for normalisation | Tokeniser only, no AST, no cross-dialect normalisation. | sqlglot |
| **setup.py / setup.cfg** | Legacy packaging. No reason to use for a new project in 2026. | pyproject.toml with uv_build |
| **tox** | Adds complexity for multi-env testing. uv handles this natively with `uv run --python 3.x`. | `uv run` with matrix in CI (GitHub Actions) |
| **hatch** (as project manager) | Project already uses uv. No benefit to adding a second project manager. Hatchling as build backend is fine (pytest-recording uses it), but the build backend choice is already made (uv_build). | uv |
| **Parquet** for cassettes | Loses schema metadata fidelity. Adds dependency. Arrow IPC is simpler, lossless, and streamable. | Arrow IPC via pyarrow |

## Stack Patterns by Variant

**If the consuming project also uses pytest-recording (HTTP + ADBC):**
- Both plugins coexist independently. No shared code, no conflicts.
- CLI flags are parallel: `--record-mode=all` (HTTP) + `--adbc-record=all` (ADBC)
- Cassette directories are separate: `tests/cassettes/` (HTTP, VCR.py default) vs `tests/cassettes/` (ADBC, configurable via `adbc_cassette_dir`)
- Recommend: configure `adbc_cassette_dir = "tests/adbc_cassettes"` to avoid directory collision with VCR.py cassettes

**If the consuming project needs to test against multiple ADBC backends (Snowflake + Databricks):**
- Use the `dialect` parameter on `@pytest.mark.adbc_cassette` to set the sqlglot dialect per test
- Configure a global default dialect in `pyproject.toml` for the primary backend
- Each backend's tests get separate cassette directories (via cassette naming from test node IDs)

**If DBAPI2 support is needed later (v2):**
- The cursor proxy pattern extends naturally -- `execute()` and `fetchall()` exist on both ADBC and DBAPI2 cursors
- Results would be converted to Arrow tables for storage and back to tuples on replay
- Architecture should NOT preclude this -- keep the proxy interface generic

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| pyarrow >=17 | adbc-driver-manager >=1.0 | Both are Apache Arrow projects and are co-released. pyarrow 17+ works with adbc-driver-manager 1.0+. |
| pyarrow >=17 | Python >=3.10 | pyarrow 17+ supports Python 3.10+. Our floor of 3.11 is within range. |
| sqlglot >=26 | Python >=3.9 | No Python version constraint issues. sqlglot is pure Python. |
| adbc-driver-manager >=1.0 | Python >=3.10 | Within our 3.11+ floor. |
| pytest >=8,<10 | pluggy >=1.5,<2 | pytest 9 requires pluggy >=1.5. Our pytest floor of 8.0 requires pluggy >=1.3. Both work with pluggy 1.x. |
| uv_build >=0.9.18 | uv >=0.9 | uv_build is the build backend; uv is the package manager. They are co-developed by Astral. |

## Entry Points Configuration (pyproject.toml)

The following must be added to `pyproject.toml` for pytest to discover the plugin:

```toml
[project.entry-points.pytest11]
adbc_replay = "pytest_adbc_replay.plugin"
```

This registers the plugin module `pytest_adbc_replay.plugin` under the `pytest11` entry point group. Pytest discovers all installed packages with `pytest11` entry points at startup. The key (`adbc_replay`) becomes the plugin name visible in `pytest --co` output.

## Testing the Plugin Itself

### pytester fixture

The standard approach for testing pytest plugins is the `pytester` fixture (built into pytest). It:
- Creates a temporary directory for each test
- Writes test files and conftest.py into the temp dir
- Runs pytest as a subprocess against those files
- Returns a `RunResult` with stdout, stderr, and exit code for assertions

Setup in the plugin's own test suite:

```python
# tests/conftest.py
pytest_plugins = ["pytester"]
```

Usage:

```python
def test_replay_mode(pytester):
    pytester.makepyfile("""
        def test_query(adbc_replay):
            conn = adbc_replay.wrap("adbc_driver_sqlite")
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetch_arrow_table()
            assert len(result) == 1
    """)
    result = pytester.runpytest("--adbc-record=once")
    result.assert_outcomes(passed=1)
```

### adbc-driver-sqlite for integration tests

For integration tests that exercise real record/replay cycles, use `adbc-driver-sqlite` as a dev dependency. SQLite is zero-config, runs in-process, and supports ADBC. This avoids needing cloud warehouse access to test the plugin itself.

```bash
uv add --group dev adbc-driver-sqlite ">=1.0"
```

## Dependency Summary

### Runtime (shipped to users)

```toml
dependencies = [
    "pytest>=8.0,<10",
    "pyarrow>=17.0",
    "sqlglot>=26.0",
    "adbc-driver-manager>=1.0",
]
```

### Dev (plugin development only)

```toml
[dependency-groups]
dev = [
    "adbc-driver-sqlite>=1.0",
    "basedpyright>=1.38.0",
    "pytest-cov>=6.0",
    "ruff>=0.15",
]
```

## Sources

- PyPI JSON API (`https://pypi.org/pypi/<package>/json`) -- verified all version numbers (Feb 2026)
  - pyarrow: 23.0.1 (latest), requires-python >=3.10
  - sqlglot: 29.0.1 (latest), requires-python >=3.9
  - adbc-driver-manager: 1.10.0 (latest), requires-python >=3.10
  - pytest: 9.0.2 (latest), requires-python >=3.10
  - uv-build: 0.10.7 (latest), requires-python >=3.8
  - pytest-cov: 7.0.0 (latest)
  - ruff: 0.15.4 (latest)
  - basedpyright: 1.38.2 (latest)
  - pytest-recording: 0.13.4 (latest)
- pytest-recording pyproject.toml (GitHub raw) -- verified `[project.entry-points.pytest11]` pattern for plugin registration
- Existing project pyproject.toml and uv.lock -- confirmed current tooling choices

---
*Stack research for: pytest-adbc-replay (pytest plugin for ADBC record/replay testing)*
*Researched: 2026-02-28*
