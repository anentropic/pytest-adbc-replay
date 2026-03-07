# Pool / adbc_clone() support for ReplayConnection

## Problem

adbc-poolhouse uses the ADBC `adbc_clone()` pattern: one source connection is created via `adbc_driver_manager.dbapi.connect()`, then `source.adbc_clone()` is called by the SQLAlchemy QueuePool to create each pooled connection. All pool checkouts go through `adbc_clone()`, not `connect()`.

`ReplayConnection` doesn't implement `adbc_clone()`. When `adbc_auto_patch` intercepts the initial `connect()` call (inside `create_adbc_connection()`), the pool receives a `ReplayConnection` as its source. It then tries to call `source.adbc_clone()` as the pool creator, which fails with `AttributeError`.

This means pool-based integration tests cannot use cassette replay at all.

## What adbc_clone() does

From the ADBC spec: `adbc_clone()` creates a new connection that shares the same underlying `AdbcDatabase` via reference counting. It returns a new DBAPI `Connection` object. The cloned connection has its own cursor state but shares the database handle (authentication, catalog, etc.).

In real usage:
```python
source = adbc_driver_manager.dbapi.connect(driver=path, db_kwargs=kwargs)
clone = source.adbc_clone()  # new Connection, same AdbcDatabase
```

## Requirements for ReplayConnection

### R1: Implement adbc_clone()

`ReplayConnection.adbc_clone()` should return a new `ReplayConnection` that:

- Shares the same cassette path, mode, dialect, and serialiser config as the source
- Has its own cursor state (independent replay queue)
- In record mode: delegates to `self._real_conn.adbc_clone()` to get a real cloned connection
- In replay mode: returns a new `ReplayConnection` with no real connection (same as current replay-mode constructor behaviour)

### R2: Clone identity for cassette paths

Cloned connections should use the same cassette directory as their source. The cassette path is per-test (from `@pytest.mark.adbc_cassette`), and clones operate within the same test scope. The replay queue should be shared or derived from the same cassette files.

### R3: Auto-patch compatibility

The auto-patch mechanism intercepts `driver.connect()`. When a pool calls `source.adbc_clone()`, that's a method on the (already-intercepted) `ReplayConnection` — no additional interception needed. The clone just needs to work.

### R4: Pool lifecycle support

Pool tests will call:
1. `create_pool(config)` — calls `connect()` (intercepted) then stores source, uses `source.adbc_clone` as pool creator
2. `pool.connect()` — calls `source.adbc_clone()` internally
3. `conn.cursor()` / `cursor.execute()` — standard cursor operations (already supported)
4. `close_pool(pool)` — calls `pool.dispose()` then `source.close()`

The clone needs to behave well through this lifecycle. In particular, `pool.dispose()` will call `close()` on each checked-out clone.

## Suggested implementation

```python
# In ReplayConnection:


def adbc_clone(self) -> ReplayConnection:
    """Create a cloned connection sharing the same cassette and config."""
    real_clone = self._real_conn.adbc_clone() if self._real_conn is not None else None
    clone = ReplayConnection.__new__(ReplayConnection)
    clone._driver_module_name = self._driver_module_name
    clone._db_kwargs = self._db_kwargs
    clone._mode = self._mode
    clone._cassette_path = self._cassette_path
    clone._dialect = self._dialect
    clone._param_serialisers = self._param_serialisers
    clone._scrub_keys_global = self._scrub_keys_global
    clone._scrub_keys_per_driver = self._scrub_keys_per_driver
    clone._scrubber = self._scrubber
    clone._real_conn = real_clone
    return clone
```

## Consumer

adbc-poolhouse integration tests. Once this is implemented, the Snowflake and Databricks integration tests can go through `create_pool()` / `pool.connect()` instead of raw `driver.dbapi.connect()`, and cassette replay will work in CI.
