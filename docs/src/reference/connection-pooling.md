# Connection Pooling

This page documents connection pooling support via `ReplayConnection.adbc_clone()`.

---

## `ReplayConnection.adbc_clone()`

**Returns:** `ReplayConnection`

Creates a cloned connection sharing the same cassette path and configuration. Follows the ADBC spec where clones share the underlying database handle.

In record mode, the clone delegates to the real connection's `adbc_clone()` method. In replay mode, the clone has no real connection (`_real_conn = None`) and replays entirely from the shared cassette.

**Interface:**

```text
connection.adbc_clone() -> ReplayConnection
```

**Usage:**

```python
clone = conn.adbc_clone()
with clone.cursor() as cur:
    cur.execute("SELECT 1")
```

Pool libraries such as [adbc-poolhouse](https://github.com/s-layer/adbc-poolhouse) call `adbc_clone()` internally when checking out connections.

---

## Shared cassette semantics

All clones share the cassette and configuration of the source connection. So do any other connections the same test opens on the same cassette.

| Property | Behaviour |
|---|---|
| Cassette path | Shared -- all clones record to and replay from the same cassette directory |
| Cassette state | Shared per test -- the `once` record/replay decision and the `all` wipe happen once, at the test's first query |
| Interaction numbering | Shared -- each recording takes the next free number, so cursors never overwrite each other |
| Replay queue | Shared per test -- each query's recordings replay in recorded order, whichever connection runs it |
| Real connection | Record mode: cloned via `real_conn.adbc_clone()`. Replay mode: `None` |
| Cursor state | Per cursor -- results, fetch position and consumption state are not shared |
| Close isolation | Closing a clone does not affect the source connection or other clones |

---

## Clone-of-clone

Cloning a clone is supported. The resulting connection shares the same cassette path and cassette state as the original source. This matches the ADBC spec, where `adbc_clone()` can be called on any connection, not just the original.

---

## Limitations

**Concurrent repeats of one query:** results are matched to queries by SQL and parameters, under a lock. If several threads run the same query at the same time and its recordings differ, which thread receives which recording depends on thread scheduling. Single-threaded pytest runs are not affected.

See the [explanation article](../explanation/connection-pooling.md) for how the shared cassette state works.

## Related

- [Use with connection pools](../how-to/connection-pools.md) -- how-to guide with pool fixture patterns
- [Connection pooling and replay](../explanation/connection-pooling.md) -- design rationale and lifecycle walkthrough
