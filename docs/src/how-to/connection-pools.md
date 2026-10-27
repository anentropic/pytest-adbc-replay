# Use with connection pools

This guide shows how to test code that uses a connection pool with pytest-adbc-replay. The examples use [adbc-poolhouse](https://github.com/s-layer/adbc-poolhouse), but any pool library that calls `adbc_clone()` internally works the same way.

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

Create the pool in a function-scoped fixture, so each test's pool connects inside that test. The plugin fixes a connection's cassette, and its record/replay state, when the source connection is created:

```python
# conftest.py
import pytest
from adbc_poolhouse import DuckDBConfig, create_pool, close_pool


@pytest.fixture
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

!!! note
    A session- or module-scoped pool connects once, during the first test that uses it. Every later test then records into, and replays from, that first test's cassette, with one shared `once` decision and replay queue. Use a function-scoped pool unless your tests are meant to share one cassette.

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

If you prefer not to use auto-patching, open the source connection with the `adbc_connect` fixture and build the pool on its `adbc_clone()`. This example uses SQLAlchemy's `QueuePool` directly:

```python
# conftest.py
import pytest
from sqlalchemy.pool import QueuePool


@pytest.fixture
def pool(adbc_connect):
    source = adbc_connect("adbc_driver_duckdb.dbapi", path="/tmp/test.db")
    p = QueuePool(source.adbc_clone, pool_size=5)
    yield p
    p.dispose()
```

The pool calls `adbc_clone()` on the `ReplayConnection` for each new connection, and all checkouts share the test's cassette. The `adbc_connect` fixture closes the source connection when the test ends.

Record the cassette with `--adbc-record=once` as usual. Every query the test runs is recorded, whichever pool connection runs it, and replay hands each connection the results in the order they were recorded.

!!! warning
    If several threads run the *same* query at the same time and its recorded results differ, which thread receives which result depends on thread scheduling. Different queries are always matched correctly. See the [explanation article](../explanation/connection-pooling.md) for details.

## Related

- [Connection pooling reference](../reference/connection-pooling.md) -- `adbc_clone()` method spec and shared cassette semantics
- [Connection pooling and replay](../explanation/connection-pooling.md) -- design rationale and shared cassette state
- [Run in CI without credentials](ci-without-credentials.md) -- replay cassettes in CI
