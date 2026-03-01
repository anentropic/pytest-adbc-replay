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

Replay from cassettes (default, no flag needed):

```bash
pytest
```

Cassette files land in `tests/cassettes/my_query/` — commit them to version control so CI can replay without a live database connection.

## Where to go next

New to pytest-adbc-replay? Start with the [Tutorial](tutorial/index.md) — it walks through a full record-then-replay cycle from scratch using DuckDB.

Looking for a specific task? The [How-To Guides](how-to/index.md) cover CI setup, cassette naming, multiple drivers, and scrubbing sensitive values.

Need exact config values or fixture signatures? Check the [Reference](reference/pytest_adbc_replay/plugin.md).

Want to understand why the plugin works the way it does? The [Explanation](explanation/index.md) covers the cassette format, SQL normalisation, and record-mode semantics.
