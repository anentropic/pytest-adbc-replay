# pytest-adbc-replay — Design Document

## Overview

`pytest-adbc-replay` is a pytest plugin for record/replay testing of ADBC database connections. It intercepts queries at the ADBC cursor level, records results to cassette files, and replays them in subsequent test runs without requiring access to live warehouse backends (Snowflake, Databricks, BigQuery, etc.).

It is intended to pair with `pytest-recording` (VCR.py wrapper) in projects that use both HTTP APIs and ADBC database connections — providing a common record/replay interface across both transport types.

## Motivation

Testing against cloud data warehouses (Snowflake, Databricks, etc.) in CI is expensive. Free tiers are limited or time-bounded. Running tests on every push against real backends is not feasible for an open-source project developed without a budget.

Existing solutions do not fit:

- **VCR.py / pytest-recording** intercept HTTP at the `urllib3`/`requests` layer. Warehouse connectors vendor their own HTTP libraries (Snowflake vendors `urllib3`; Databricks has similar patterns), making VCR interception fragile or impossible without patching vendored internals.
- **Keploy** operates at the kernel network layer via eBPF, requires Linux 5.10+, and is designed for full-application HTTP service recording — the wrong abstraction for library-level database cursor testing.
- **DuckDB as test double** avoids warehouse costs but cannot validate warehouse-specific SQL syntax (`FLATTEN`, `LATERAL`, Databricks-specific functions, Snowflake semi-structured operators, etc.).
- **snowflake-vcrpy** exists but vendors VCR.py itself (causing conflicts if VCR.py is already a dependency), is Snowflake-specific, and intercepts at the HTTP layer — inheriting the vendoring fragility problem.

Intercepting at the **ADBC cursor interface** avoids all of these problems. The cursor API is uniform across all ADBC drivers, stable, and narrow — making it a clean and driver-agnostic seam for recording and replay.

## Design Goals

- Driver-agnostic: works for any ADBC-compatible backend (Snowflake, Databricks, BigQuery, Flight SQL, etc.)
- Pytest-native interface modelled on `pytest-recording` / VCR.py conventions
- Cassette files are human-readable and reviewable in pull requests
- SQL query changes are visible as cassette diffs in PRs
- No vendoring of dependencies
- Compatible with projects that also use `pytest-recording` for HTTP backends

## Non-Goals

- Not an HTTP recording tool (use `pytest-recording` for that)
- Not a query correctness validator (cassettes record whatever the live backend returned)
- DBAPI2 support is out of scope for v1 but the architecture should not preclude it later

## Architecture

### Interception Layer

Recording and replay happen by wrapping the ADBC cursor, not the connection or the driver. The proxy implements the same interface as `adbc_driver_manager.dbapi.Cursor`:

```python
class ReplayCursor:
    def __init__(self, real_cursor, cassette: Cassette):
        self._cursor = real_cursor
        self._cassette = cassette

    def execute(self, sql: str, parameters=None, **kwargs):
        key = CassetteKey(sql=sql, parameters=parameters, options=kwargs)
        if self._cassette.mode == "replay":
            self._pending = self._cassette.load(key)
        else:
            self._cursor.execute(sql, parameters, **kwargs)
            result = self._cursor.fetch_arrow_table()
            self._cassette.record(key, result)
            self._pending = result

    def fetch_arrow_table(self):
        return self._pending

    def fetch_record_batch(self, size=None):
        # yield batches from self._pending
        ...

    # DBAPI2-compatible fetch methods delegate to Arrow table conversion
    def fetchone(self): ...
    def fetchmany(self, size=None): ...
    def fetchall(self): ...
```

The `ReplayConnection` wraps the real connection and returns `ReplayCursor` instances from `.cursor()`. In replay-only mode it does not open a real connection at all — the `ReplayCursor` is constructed without a backing cursor and raises on any cassette miss.

### Cassette Format

Each cassette is a directory. Each recorded interaction is a pair of files:

```
cassettes/
  test_my_query/
    000_query.sql          # the SQL as executed
    000_params.json        # parameters (null if none)
    000_options.json       # driver-specific kwargs (null if none)
    000_result.arrow       # Arrow IPC file (schema + data)
    001_query.sql
    001_result.arrow
    ...
```

Interactions are numbered in execution order. The `.sql` files make query changes reviewable as plain diffs in PRs. Arrow IPC is used for results rather than Parquet because it preserves schema metadata more precisely and does not require an additional dependency beyond `pyarrow`.

### SQL Normalisation

SQL text is normalised before use as a cassette key to avoid spurious misses from irrelevant formatting differences — keyword casing, whitespace, quote style, etc.

Normalisation is done via `sqlglot`, which is likely already in the dependency tree for dbt-adjacent projects:

```python
import sqlglot


def normalise_sql(sql: str, dialect: str | None = None) -> str:
    try:
        # parse and re-emit canonically; pretty=False for single-line key
        return sqlglot.transpile(sql, read=dialect, write=dialect, pretty=False)[0]
    except sqlglot.errors.SqlglotError:
        # fallback: whitespace-only normalisation if parse fails
        return " ".join(sql.split()).strip()
```

This handles keyword casing (`SELECT` vs `select`), redundant whitespace, and quote normalisation in one pass. The stored `.sql` cassette file uses `pretty=True` for readability in PR diffs.

**Dialect configuration** controls how sqlglot parses the SQL. Without a dialect, sqlglot uses best-effort auto-detection which works for standard SQL but may misparse vendor-specific extensions. The dialect is used for normalisation only — it has no effect during replay, where no SQL is executed.

Dialect is configured at three levels, in increasing precedence:

1. **Global default** in `pyproject.toml` / `pytest.ini` — applies to all tests
2. **Per-test marker** — overrides the global default for a specific test
3. **No dialect (`None`)** — sqlglot best-effort, used if neither is set

**Normalisation failures** are caught and fall back to whitespace-only normalisation rather than raising, so unusual or heavily vendor-specific SQL that sqlglot cannot parse does not break cassette matching.

**Parameter placeholders** (`?`, `%s`, `$1`) are not normalised — they are left as-is in the SQL key, since placeholder style is determined by the driver and should be consistent within a project.

### Cassette Matching

A cassette key is `(normalised_sql, parameters, driver_options)`. All three must match for a cassette hit. There is no SQL-only matching mode — parameters are always part of the key.

Normalisation is applied at both record and replay time, so the key is always derived from the same canonical form regardless of minor formatting variations in the calling code.

### Record Modes

Matching `pytest-recording` conventions:

| Mode | Behaviour |
|------|-----------|
| `none` (default) | Replay only. Fail on any cassette miss. No network/warehouse access. |
| `new_episodes` | Replay existing interactions; record any that are not in the cassette. |
| `all` | Re-record everything, overwriting existing cassettes. |
| `once` | Record if the cassette does not exist; replay if it does. |

### Pytest Interface

**CLI flag:**

```
pytest --adbc-record=all       # re-record everything
pytest --adbc-record=new_episodes
pytest                         # default: none (replay only)
```

**Marker:**

```python
@pytest.mark.adbc_cassette("my_cassette_name")
def test_something(adbc_connection): ...


@pytest.mark.adbc_cassette("my_cassette_name", dialect="snowflake")
def test_something_snowflake(adbc_connection): ...
```

The `dialect` argument controls sqlglot SQL normalisation for this test, overriding any global default. If no marker is provided, the cassette name defaults to the test node ID (module + test name), matching pytest-recording behaviour.

**Fixture:**

```python
@pytest.fixture
def adbc_connection(adbc_replay):
    # adbc_replay is injected by the plugin; returns a wrapped connection
    # in replay mode it returns a connectionless ReplayConnection
    # in record mode it opens the real connection and wraps it
    driver = os.environ.get("ADBC_DRIVER", "adbc_driver_snowflake")
    return adbc_replay.wrap(driver, db_kwargs={...})
```

The plugin provides an `adbc_replay` session-scoped fixture that manages cassette state and exposes `.wrap()`.

### Configuration

In `pyproject.toml` or `pytest.ini`:

```toml
[tool.pytest.ini_options]
adbc_cassette_dir = "tests/cassettes"   # default: tests/cassettes
adbc_record_mode = "none"               # default: none
adbc_dialect = "snowflake"             # default dialect for SQL normalisation (optional)
```

## Cassette File Management

Cassettes are committed to the repository. The workflow is:

1. **Developing locally with warehouse access:** run with `--adbc-record=once` to record cassettes for new tests. Existing cassettes are not overwritten.
2. **CI:** run with default (`none`). No warehouse credentials needed. Tests fail fast on cassette misses (indicating a new test was added without recording).
3. **Updating cassettes after query changes:** run with `--adbc-record=all` against live backends, review the `.sql` diffs in the PR.

## Relationship to pytest-recording

Projects using both HTTP and ADBC backends configure both plugins independently. They share no code but follow the same conventions so the mental model is consistent:

```
pytest --record-mode=all --adbc-record=all
```

This re-records both HTTP cassettes (via VCR.py) and ADBC cassettes in one pass.

## Dependency Scope

| Dependency | Reason |
|---|---|
| `pyarrow` | Arrow IPC serialisation for cassette results |
| `sqlglot` | SQL normalisation for cassette key generation |
| `adbc-driver-manager` | Type references for the cursor interface |
| `pytest` | Plugin infrastructure |

Specific ADBC drivers (snowflake, databricks, etc.) are not dependencies — they are provided by the consuming project.

## Future Considerations

**DBAPI2 support:** The cursor proxy pattern extends naturally to DBAPI2 — `execute()` and `fetchall()` are present on both. Results would be converted to Arrow tables for storage and back to tuples on replay. This is left for a later version once the ADBC core is stable.

**Cassette format versioning:** The cassette directory should include a `manifest.json` with a format version field so future format changes can be detected and migration tooling provided.

**Sensitive data scrubbing:** A hook point for scrubbing sensitive values from recorded parameters and results before writing to disk — similar to VCR.py's `filter_headers` / `filter_query_parameters`. Not in v1 but the cassette write path should be designed with a filter callback in mind.
