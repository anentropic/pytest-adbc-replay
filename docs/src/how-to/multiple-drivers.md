# Use multiple drivers in one session

## Automatic patching (adbc_auto_patch)

List both drivers in `adbc_auto_patch`:

```toml
[tool.pytest.ini_options]
adbc_auto_patch = "adbc_driver_duckdb.dbapi adbc_driver_snowflake.dbapi"
```

Each value is the module path where `connect()` lives — see [Finding the right module path](configure-via-ini.md#finding-the-right-module-path).

Then call `connect()` in your tests directly — no fixture needed:

```python
import os

import adbc_driver_duckdb.dbapi as duckdb
import adbc_driver_snowflake.dbapi as snowflake
import pytest


@pytest.mark.adbc_cassette("cross_db_query")
def test_cross_db():
    duck = duckdb.connect()
    snow = snowflake.connect(uri=os.environ["SNOWFLAKE_URI"])
    # Both connections are intercepted automatically.
    # Cassettes are stored separately per driver:
    # tests/cassettes/cross_db_query/adbc_driver_duckdb.dbapi/000.*
    # tests/cassettes/cross_db_query/adbc_driver_snowflake.dbapi/000.*
```

## Explicit fixture approach

`adbc_replay` is session-scoped, and you can call `.wrap()` on it multiple times for different connection objects. Each wrapped connection records and replays independently.

## Two databases in one conftest

```python
import adbc_driver_duckdb.dbapi as duckdb
import adbc_driver_snowflake.dbapi as snowflake
import pytest


@pytest.fixture(scope="session")
def duck_conn(adbc_replay):
    with duckdb.connect() as conn:
        yield adbc_replay.wrap(conn)


@pytest.fixture(scope="session")
def snow_conn(adbc_replay):
    conn = snowflake.connect(uri=os.environ["SNOWFLAKE_URI"])
    try:
        yield adbc_replay.wrap(conn)
    finally:
        conn.close()
```

Each wrapped connection has its own cassette tracking — a query on `duck_conn` and the same query on `snow_conn` are stored separately.

## Driver notes

**DuckDB** (`adbc-driver-duckdb`): runs in-process, no credentials needed. Good for local development and CI. Cassettes recorded locally replay fine in CI.

**Snowflake** (`adbc-driver-snowflake`): requires credentials in `SNOWFLAKE_URI`. Record cassettes locally (`--adbc-record=once`), commit them, then CI runs in `none` mode with no credentials.

**BigQuery** (`adbc-driver-bigquery`): similar pattern to Snowflake. Connect via `adbc_driver_bigquery.dbapi.connect(...)`. Record locally, replay in CI.

## SQL dialect per connection

If your two databases use different SQL dialects, use the `dialect` argument on the marker to normalise SQL correctly per test:

```python
@pytest.mark.adbc_cassette("sf_query", dialect="snowflake")
def test_snowflake(snow_conn): ...


@pytest.mark.adbc_cassette("duck_query")
def test_duckdb(duck_conn): ...
```

You can also set a global default with `adbc_dialect` in ini and override per test.

## Related

- [Name cassettes per test](cassette-names.md) — dialect override on the marker
- [Configuration reference](../reference/configuration.md) — `adbc_dialect` ini key
