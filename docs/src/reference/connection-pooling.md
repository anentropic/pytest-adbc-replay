# Connection Pooling

This page documents connection pooling support via `ReplayConnection.adbc_clone()`.

---

## `ReplayConnection.adbc_clone()`

**Returns:** `ReplayConnection`

Creates a cloned connection sharing the same cassette path and configuration. Mirrors the ADBC spec where clones share the underlying database handle.

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

Pool libraries such as [adbc-poolhouse](https://github.com/anentropic/adbc-poolhouse) call `adbc_clone()` internally when checking out connections.

---

## Shared cassette semantics

All clones share the cassette and configuration of the source connection. Each clone has its own independent cursor state.

| Property | Behaviour |
|---|---|
| Cassette path | Shared -- all clones record to and replay from the same cassette directory |
| Wipe state | Shared mutable dict -- only the first cursor across all clones wipes the cassette in `all` mode |
| Real connection | Record mode: cloned via `real_conn.adbc_clone()`. Replay mode: `None` |
| Cursor state | Independent per clone -- each cursor maintains its own replay queue |
| Close isolation | Closing a clone does not affect the source connection or other clones |

---

## Clone-of-clone

Cloning a clone is supported. The resulting connection shares the same cassette path and wipe state as the original source. This matches the ADBC spec, where `adbc_clone()` can be called on any connection, not just the original.

---

## Limitations

**Sequential access:** Replay queues are per-cursor. If two cursors from different clones execute concurrently (e.g. in multi-threaded test code), each cursor pops results from its own independent queue. The pop order depends on thread scheduling, not query identity, which can lead to incorrect result matching.

In typical single-threaded pytest runs, cursors execute sequentially and this is never a problem. The sequential access constraint only applies when multiple threads hold pool connections and execute queries concurrently.

See the [explanation article](../explanation/connection-pooling.md) for a detailed walkthrough of the concurrent-access failure mode.

## Related

- [Use with connection pools](../how-to/connection-pools.md) -- how-to guide with pool fixture patterns
- [Connection pooling and replay](../explanation/connection-pooling.md) -- design rationale and lifecycle walkthrough
