# pytest-adbc-replay

[ [Docs](https://anentropic.github.io/pytest-adbc-replay) ]

Record/replay testing for ADBC database queries, as a pytest plugin.

## What / Why

Works like [VCR.py](https://vcrpy.readthedocs.io/) and [pytest-recording](https://github.com/kiwicom/pytest-recording): the first run records live queries to cassette
files on disk, subsequent runs replay from those cassettes. CI tests pass with no live warehouse
connection, and query changes are visible as plain diffs in pull requests (`.sql` files are
human-readable and committed to version control).

## Installation

```bash
pip install pytest-adbc-replay
```

## Quick Start

For this example we'll use the DuckDB ADBC driver (no credentials needed):

```bash
pip install adbc-driver-duckdb
```

Mocking is flexible enough to use with any ADBC driver.

**`pyproject.toml`** — tell the plugin which drivers to intercept:

```toml
[tool.pytest.ini_options]
adbc_auto_patch = ["adbc_driver_duckdb.dbapi"]
```

The value is the Python module path where `connect()` lives — for all standard ADBC drivers this is `adbc_driver_<name>.dbapi`.

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

## Cassette Layout

```
tests/cassettes/
└── my_query/
    └── adbc_driver_duckdb.dbapi/
        ├── 000.sql      # human-readable normalised SQL
        ├── 000.arrow    # Arrow IPC result with schema metadata
        └── 000.json     # parameters and driver options (null when absent)
```

Commit the cassettes to version control — any changes appear as diffs in pull requests.

## Configuration Reference

| Setting | Type | Default | Description |
|---|---|---|---|
| `--adbc-record` | CLI flag | `none` | Record mode for this run |
| `adbc_cassette_dir` | ini key | `tests/cassettes` | Directory to read/write cassettes |
| `adbc_record_mode` | ini key | `none` | Persistent record mode (overridden by CLI flag) |
| `adbc_dialect` | ini key (linelist) | `[]` | SQL dialect for normalisation. Bare value = global fallback, `driver: dialect` = per-driver. Empty = auto-detect. |
| `adbc_auto_patch` | ini key (linelist) | `[]` | ADBC driver module names to auto-intercept |
| `adbc_scrub_keys` | ini key (linelist) | `[]` | Parameter key names to redact from cassette `.json` files |

Minimal `pyproject.toml` snippet:

```toml
[tool.pytest.ini_options]
adbc_cassette_dir = "tests/cassettes"
adbc_record_mode = "none"
adbc_dialect = []  # e.g. ["adbc_driver_snowflake.dbapi: snowflake", "adbc_driver_duckdb.dbapi: duckdb"]
adbc_auto_patch = []  # e.g. ["adbc_driver_duckdb.dbapi", "adbc_driver_snowflake.dbapi"]
adbc_scrub_keys = []  # e.g. ["token password", "adbc_driver_snowflake: account_id"]
```

## Record Modes

| Mode | Behaviour |
|---|---|
| `none` | Replay only. Raises `CassetteMissError` if cassette is absent (default). |
| `once` | Record if cassette absent, replay if cassette present. |
| `new_episodes` | Replay existing interactions, record new ones. |
| `all` | Re-record everything on every run. |

## Scrubbing Sensitive Values

To keep credentials out of cassette files, list parameter key names in `adbc_scrub_keys`:

```toml
[tool.pytest.ini_options]
adbc_scrub_keys = ["token password api_key"]
```

Matched values become `REDACTED` in the `.json` cassette file. Per-driver form:

```toml
adbc_scrub_keys = [
    "token",
    "adbc_driver_snowflake: account_id warehouse",
]
```

For custom scrubbing logic, override the `adbc_scrubber` fixture in your `conftest.py`:

```python
import pytest


@pytest.fixture(scope="session")
def adbc_scrubber():
    def scrub(params: dict | None, driver_name: str) -> dict | None:
        if not isinstance(params, dict):
            return params
        return {k: "REDACTED" if k.endswith("_key") else v for k, v in params.items()}

    return scrub
```

Config scrubbing runs first; the fixture callable receives the already-config-scrubbed params.

## Advanced

`adbc_param_serialisers` is a session-scoped fixture for registering custom parameter serialisers
for types not handled by default.

Full reference documentation: [https://anentropic.github.io/pytest-adbc-replay](https://anentropic.github.io/pytest-adbc-replay)

## License

[BSD-3-Clause](LICENSE)
