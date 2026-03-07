# Phase 2: Pool clone support for ReplayConnection - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement `adbc_clone()` on `ReplayConnection` so that connection pooling consumers (like adbc-poolhouse) can use cassette replay. The pool pattern creates a source connection via `connect()`, then calls `source.adbc_clone()` to create each pooled connection. Currently `ReplayConnection` lacks this method, causing `AttributeError` when pools try to clone it.

</domain>

<decisions>
## Implementation Decisions

### Cassette sharing model
- Clones share the source's `_cassette_path` — all clones read/write the same cassette directory
- Sequential access only — no locking or concurrent-clone protection
- Each clone's cursor loads the full cassette independently via `_ensure_initialised()` (existing lazy-init pattern)
- Replay matching is by `(normalised_sql, params)` key — each cursor pops from its own independent replay queue
- Document the sequential-access limitation

### Clone constructor
- Use `__new__` bypass to skip `__init__` (which opens real connections)
- Manually copy all attributes from source to clone
- In record mode: `_real_conn` set to `self._real_conn.adbc_clone()`
- In replay mode: `_real_conn` set to `None`

### Clone depth
- Clone-of-clone is supported — `adbc_clone()` works on any `ReplayConnection`, not just the original source
- Matches real ADBC spec behavior (clones share the same `AdbcDatabase`)
- No need to track source/clone relationships

### Wipe state sharing ('all' mode)
- Source creates a shared mutable container (e.g. `{'wiped': False}` dict)
- All clones (and clones-of-clones) reference the same container
- Only the first cursor to `execute()` across all clones triggers `rmtree`
- Prevents later clones from wiping earlier clones' recordings

### Close behavior
- `close()` on a clone closes its real connection only (existing behavior)
- No cassette cleanup — cassette outlives individual connections
- Source can be closed independently of clones (pool lifecycle: `pool.dispose()` closes clones, then source is closed)

### Auto-patch compatibility
- No additional interception needed — `adbc_clone()` is called on an already-intercepted `ReplayConnection`
- The clone inherits all config from the source (mode, dialect, scrub keys, etc.)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ReplayConnection.__init__` (`_connection.py:26-59`): 10 instance attributes to copy in clone — `_driver_module_name`, `_db_kwargs`, `_mode`, `_cassette_path`, `_dialect`, `_param_serialisers`, `_scrub_keys_global`, `_scrub_keys_per_driver`, `_scrubber`, `_real_conn`
- `ReplayCursor._ensure_initialised()` (`_cursor.py:144-161`): lazy cassette loading — works naturally per-clone since each cursor has its own replay queue
- `ReplayCursor._wiped` flag (`_cursor.py:142`): currently per-cursor — needs to be replaced with shared container from connection for clone support

### Established Patterns
- `connect_fn` parameter bypasses monkeypatching recursion (used by auto-patch) — clones don't go through `connect()` so this isn't needed for clones
- Per-driver ini keys use linelist with colon syntax — no new ini keys needed for this phase

### Integration Points
- `ReplayConnection` (`_connection.py`): add `adbc_clone()` method + shared wipe state container
- `ReplayCursor.__init__` (`_cursor.py`): accept shared wipe state container instead of per-cursor `_wiped` flag
- Tests: new test file in `tests/unit/` for clone behavior

</code_context>

<specifics>
## Specific Ideas

- The requirements doc at `_notes/pool-clone-support.md` has a suggested `adbc_clone()` implementation using `__new__` — use as starting point, extend with shared wipe state
- Consumer is adbc-poolhouse: `create_pool(config)` → `source.adbc_clone()` as pool creator → `pool.connect()` returns clones → cursor operations → `pool.dispose()` closes clones

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-pool-clone-support-for-replayconnection*
*Context gathered: 2026-03-07*
