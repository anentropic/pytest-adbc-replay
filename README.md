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

**`conftest.py`** — wrap your real connection with `adbc_replay.wrap()`:

```python
import adbc_driver_duckdb.dbapi as duckdb
import pytest


@pytest.fixture(scope="session")
def db_conn(adbc_replay):
    with duckdb.connect() as conn:
        yield adbc_replay.wrap(conn)
```

**`test_example.py`** — mark each test with a cassette name:

```python
import pytest


@pytest.mark.adbc_cassette("my_query")
def test_my_query(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("SELECT 42 AS answer")
        assert cur.fetchone() == (42,)
```

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
    ├── 000.sql      # human-readable normalised SQL
    ├── 000.arrow    # Arrow IPC result with schema metadata
    └── 000.json     # parameters and driver options (null when absent)
```

Commit the cassette directory to version control — query changes appear as diffs in pull requests.

## Configuration Reference

| Setting | Type | Default | Description |
|---|---|---|---|
| `--adbc-record` | CLI flag | `none` | Record mode for this run |
| `adbc_cassette_dir` | ini key | `tests/cassettes` | Directory to read/write cassettes |
| `adbc_record_mode` | ini key | `none` | Persistent record mode (overridden by CLI flag) |
| `adbc_dialect` | ini key | `""` | SQL dialect for normalisation (auto-detect when empty) |

Minimal `pyproject.toml` snippet:

```toml
[tool.pytest.ini_options]
adbc_cassette_dir = "tests/cassettes"
adbc_record_mode = "none"
adbc_dialect = ""
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
