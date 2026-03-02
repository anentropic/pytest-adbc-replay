# pytest-adbc-replay

Record ADBC database queries to cassette files and replay them in CI without warehouse credentials.

## What / Why

Works like VCR: the first run records live queries to cassette files on disk, subsequent runs
replay from those cassettes. CI tests pass with no live warehouse connection, and query changes
are visible as plain diffs in pull requests (`.sql` files are human-readable and committed to
version control).

## Installation

```bash
pip install pytest-adbc-replay
```

## Quick Start

Install a DuckDB ADBC driver (no credentials needed):

```bash
pip install adbc-driver-duckdb
```

**`pyproject.toml`** — tell the plugin which drivers to intercept:

```toml
[tool.pytest.ini_options]
adbc_auto_patch = "adbc_driver_duckdb.dbapi"
```

**`test_example.py`** — mark each test and call `connect()` normally:

```python
import adbc_driver_duckdb.dbapi as duckdb
import pytest


@pytest.mark.adbc_cassette("my_query")
def test_my_query():
    conn = duckdb.connect()
    with conn.cursor() as cur:
        cur.execute("SELECT 42 AS answer")
        assert cur.fetchone() == (42,)
```

No `conftest.py` needed. The plugin intercepts `duckdb.connect()` automatically for tests decorated with `@pytest.mark.adbc_cassette`.

Record cassettes on the first run:

```bash
pytest --adbc-record=once
```

Replay from cassettes (default — no flag needed):

```bash
pytest
```

### Explicit conftest approach

For session-scoped connections or when you prefer explicit control, use `adbc_replay.wrap()` from a fixture:

```python
import adbc_driver_duckdb.dbapi as duckdb
import pytest


@pytest.fixture(scope="session")
def db_conn(adbc_replay, request):
    return adbc_replay.wrap(
        "adbc_driver_duckdb.dbapi",
        request=request,
    )
```

Both approaches produce cassettes in the same format.

## Cassette Layout

**With `adbc_auto_patch`** (automatic interception):

```
tests/cassettes/
└── my_query/
    └── adbc_driver_duckdb.dbapi/
        ├── 000.sql      # human-readable normalised SQL
        ├── 000.arrow    # Arrow IPC result with schema metadata
        └── 000.json     # parameters and driver options (null when absent)
```

**With `adbc_replay.wrap()`** (explicit fixture):

```
tests/cassettes/
└── my_query/
    ├── 000.sql
    ├── 000.arrow
    └── 000.json
```

Commit both formats to version control — query changes appear as diffs in pull requests.

## Configuration Reference

| Setting | Type | Default | Description |
|---|---|---|---|
| `--adbc-record` | CLI flag | `none` | Record mode for this run |
| `adbc_cassette_dir` | ini key | `tests/cassettes` | Directory to read/write cassettes |
| `adbc_record_mode` | ini key | `none` | Persistent record mode (overridden by CLI flag) |
| `adbc_dialect` | ini key | `""` | SQL dialect for normalisation (auto-detect when empty) |
| `adbc_auto_patch` | ini key | `""` | Space-separated list of ADBC driver module names to auto-intercept |

Minimal `pyproject.toml` snippet:

```toml
[tool.pytest.ini_options]
adbc_cassette_dir = "tests/cassettes"
adbc_record_mode = "none"
adbc_dialect = ""
adbc_auto_patch = ""  # e.g. "adbc_driver_duckdb.dbapi adbc_driver_snowflake.dbapi"
```

## Record Modes

| Mode | Behaviour |
|---|---|
| `none` | Replay only. Raises `CassetteMissError` if cassette is absent (default). |
| `once` | Record if cassette absent, replay if cassette present. |
| `new_episodes` | Replay existing interactions, record new ones. |
| `all` | Re-record everything on every run. |

## Advanced

`adbc_scrubber` is a session-scoped fixture that accepts a callable for scrubbing sensitive values
(tokens, passwords) from cassettes before they are written to disk. `adbc_param_serialisers` is a
session-scoped fixture for registering custom parameter serialisers for types not handled by default.

Full reference documentation: [https://TODO.github.io/pytest-adbc-replay](https://TODO.github.io/pytest-adbc-replay)

## License

[BSD-3-Clause](LICENSE)
