# Use with connection pools

This guide shows how to test code that uses a connection pool (such as [adbc-poolhouse](https://github.com/anentropic/adbc-poolhouse)) with pytest-adbc-replay. Any pool library that calls `adbc_clone()` internally works the same way.

## Configure auto-patching

List the driver module in `adbc_auto_patch` so the plugin intercepts `connect()` calls automatically:

=== "pyproject.toml"

    ```toml
    [tool.pytest.ini_options]
    adbc_auto_patch = [
        "adbc_driver_duckdb.dbapi",
    ]
    ```

=== "pytest.ini"

    ```ini
    [pytest]
    adbc_auto_patch =
        adbc_driver_duckdb.dbapi
    ```

With auto-patching enabled, the connection returned by the driver's `connect()` is already a `ReplayConnection`. When the pool library calls `adbc_clone()` on it, each clone shares the same cassette path and configuration.

## Create a pool fixture

Set up the pool in a session-scoped fixture and expose individual connections as function-scoped fixtures:

```python
# conftest.py
import pytest
from adbc_poolhouse import DuckDBConfig, create_pool, close_pool


@pytest.fixture(scope="session")
def pool():
    p = create_pool(DuckDBConfig(database="/tmp/test.db"))
    yield p
    close_pool(p)


@pytest.fixture
def db_conn(pool):
    conn = pool.connect()
    yield conn
    conn.close()
```

`pool.connect()` calls `adbc_clone()` internally, so each checkout connection is a `ReplayConnection` sharing the same cassette.

## Write a test

Use the `db_conn` fixture with `@pytest.mark.adbc_cassette` as usual:

```python
import pytest


@pytest.mark.adbc_cassette("pool_query")
def test_pool_query(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("SELECT 42 AS answer")
        result = cur.fetchall()
    assert result
```

## Explicit wrap() approach

If you prefer not to use auto-patching, wrap the source connection manually before creating the pool:

```python
# conftest.py
import pytest
import adbc_driver_duckdb.dbapi as duckdb
from adbc_poolhouse import DuckDBConfig, create_pool, close_pool


@pytest.fixture(scope="session")
def pool(adbc_replay):
    source = duckdb.connect(database="/tmp/test.db")
    wrapped = adbc_replay.wrap(source)
    p = create_pool(DuckDBConfig(database="/tmp/test.db"), source=wrapped)
    yield p
    close_pool(p)
```

The pool then calls `adbc_clone()` on the wrapped `ReplayConnection`, and all checkouts share the same cassette.

!!! warning
    Cloned connections must be used sequentially. In typical single-threaded pytest runs, this is not a concern. Sequential access is only a limitation when testing multi-threaded server code with concurrent pool connections. See the [explanation article](../explanation/connection-pooling.md) for details on the failure mode.

## Other pool libraries

The examples above use [adbc-poolhouse](https://github.com/anentropic/adbc-poolhouse), but any pool library that creates connections via `adbc_clone()` works the same way. The plugin does not depend on adbc-poolhouse -- it only requires that the pool calls the standard ADBC `adbc_clone()` method.

## Related

- [Connection pooling reference](../reference/connection-pooling.md) -- `adbc_clone()` method spec and shared cassette semantics
- [Connection pooling and replay](../explanation/connection-pooling.md) -- design rationale and concurrent-access failure mode
- [Run in CI without credentials](ci-without-credentials.md) -- replay cassettes in CI
