# pytest-adbc-replay

Record ADBC database queries to cassette files and replay them in CI without warehouse credentials.

## Installation

```bash
pip install pytest-adbc-replay
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add pytest-adbc-replay
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

`adbc_driver_duckdb.dbapi` is the module path where `connect()` lives. See [Finding the right module path](how-to/configure-via-ini.md#finding-the-right-module-path) for other drivers.

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

No `conftest.py` needed. Record cassettes on the first run:

```bash
pytest --adbc-record=once
```

Replay from cassettes (default, no flag needed):

```bash
pytest
```

Cassette files land in `tests/cassettes/my_query/adbc_driver_duckdb.dbapi/` — commit them to version control so CI can replay without a live database connection.

## Where to go next

New to pytest-adbc-replay? Start with the [Tutorial](tutorial/index.md) — it walks through a full record-then-replay cycle from scratch using DuckDB.

Looking for a specific task? The [How-To Guides](how-to/index.md) cover CI setup, cassette naming, multiple drivers, and scrubbing sensitive values.

Need exact config values or fixture signatures? Check the [Reference](reference/pytest_adbc_replay/plugin.md).

Want to understand why the plugin works the way it does? The [Explanation](explanation/index.md) covers the cassette format, SQL normalisation, and record-mode semantics.
