# Phase 2: Pool Clone Support for ReplayConnection - Research

**Researched:** 2026-03-07
**Domain:** ADBC connection cloning, connection pooling proxy support
**Confidence:** HIGH

## Summary

This phase adds `adbc_clone()` to `ReplayConnection` so that connection pool consumers (like adbc-poolhouse) can use cassette replay. The pool pattern calls `source.adbc_clone()` to create each pooled connection; without this method, `ReplayConnection` raises `AttributeError`.

The implementation is well-scoped: one new method on `ReplayConnection`, a shared wipe-state container threaded from connection to cursor, and unit tests. No new dependencies, no new ini keys, no new fixtures. The real ADBC `adbc_clone()` creates a new `Connection` sharing the same `AdbcDatabase` -- our proxy version mirrors this by copying config from source to clone and (in record mode) delegating to the real connection's `adbc_clone()`.

**Primary recommendation:** Implement `adbc_clone()` using `__new__` bypass with attribute copy, add a shared `_wipe_state` dict threaded through to cursors, and write focused unit tests covering clone creation, cursor independence, shared wipe state, close isolation, and clone-of-clone.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Clones share the source's `_cassette_path` -- all clones read/write the same cassette directory
- Sequential access only -- no locking or concurrent-clone protection
- Each clone's cursor loads the full cassette independently via `_ensure_initialised()` (existing lazy-init pattern)
- Replay matching is by `(normalised_sql, params)` key -- each cursor pops from its own independent replay queue
- Document the sequential-access limitation
- Use `__new__` bypass to skip `__init__` (which opens real connections)
- Manually copy all attributes from source to clone
- In record mode: `_real_conn` set to `self._real_conn.adbc_clone()`
- In replay mode: `_real_conn` set to `None`
- Clone-of-clone is supported -- `adbc_clone()` works on any `ReplayConnection`, not just the original source
- Matches real ADBC spec behavior (clones share the same `AdbcDatabase`)
- No need to track source/clone relationships
- Source creates a shared mutable container (e.g. `{'wiped': False}` dict)
- All clones (and clones-of-clones) reference the same container
- Only the first cursor to `execute()` across all clones triggers `rmtree`
- Prevents later clones from wiping earlier clones' recordings
- `close()` on a clone closes its real connection only (existing behavior)
- No cassette cleanup -- cassette outlives individual connections
- Source can be closed independently of clones
- No additional interception needed for auto-patch -- `adbc_clone()` is called on an already-intercepted `ReplayConnection`
- The clone inherits all config from the source (mode, dialect, scrub keys, etc.)

### Claude's Discretion

None specified -- all decisions are locked.

### Deferred Ideas (OUT OF SCOPE)

None -- discussion stayed within phase scope.
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=8.0 | Test framework | Already in project deps |
| pyarrow | >=14.0 | Arrow table fixtures for cursor tests | Already in project deps |
| unittest.mock | stdlib | Mock real ADBC connections/cursors | Used throughout existing tests |

### Supporting

No new libraries needed. This phase modifies existing source files only.

### Alternatives Considered

None -- all decisions are locked. No new dependencies required.

## Architecture Patterns

### Files to Modify

```
src/pytest_adbc_replay/
├── _connection.py   # Add adbc_clone() method + _wipe_state init
├── _cursor.py       # Accept _wipe_state container, replace _wiped flag

tests/unit/
└── test_clone.py    # New file: clone behavior tests
```

### Pattern 1: `__new__` Bypass for Clone Construction

**What:** Use `ReplayConnection.__new__(ReplayConnection)` to create the clone instance, then manually copy all attributes. This avoids `__init__` which would try to `importlib.import_module()` and `driver.connect()` in record mode.

**When to use:** Always -- this is the locked decision for clone construction.

**Example:**
```python
# Source: _notes/pool-clone-support.md + CONTEXT.md decisions
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
    clone._wipe_state = self._wipe_state  # shared mutable container
    return clone
```

### Pattern 2: Shared Wipe State Container

**What:** Replace the per-cursor `_wiped: bool` flag with a shared mutable dict `{'wiped': False}` created by the connection. All cursors from a connection (and its clones) reference the same dict. The first cursor to call `_ensure_initialised()` in `'all'` mode sets `wiped = True` and performs `rmtree`.

**When to use:** Always -- this is the locked decision for wipe state.

**Implementation threading:**

1. `ReplayConnection.__init__` creates `self._wipe_state = {'wiped': False}`
2. `ReplayConnection.adbc_clone()` copies `self._wipe_state` reference (shared)
3. `ReplayConnection.cursor()` passes `self._wipe_state` to `ReplayCursor.__init__`
4. `ReplayCursor._ensure_initialised()` checks/sets `self._wipe_state['wiped']` instead of `self._wiped`

**Example (cursor side):**
```python
# In ReplayCursor.__init__:
def __init__(self, ..., wipe_state: dict[str, bool] | None = None) -> None:
    ...
    self._wipe_state = wipe_state if wipe_state is not None else {'wiped': False}

# In ReplayCursor._ensure_initialised:
def _ensure_initialised(self) -> None:
    if self._initialised:
        return
    self._initialised = True
    if self._mode == "all" and not self._wipe_state['wiped']:
        if self._cassette_path.exists():
            shutil.rmtree(self._cassette_path)
        self._wipe_state['wiped'] = True
        return
    ...
```

### Pattern 3: Real ADBC adbc_clone() Delegation

**What:** The real ADBC `Connection.adbc_clone()` creates a new `AdbcConnection` using the shared `AdbcDatabase`, then wraps it in a new `Connection`. Our proxy mirrors this: in record mode, call `self._real_conn.adbc_clone()` to get a real cloned connection. In replay mode, set `_real_conn = None`.

**Source:** [ADBC Driver Manager API docs](https://arrow.apache.org/adbc/current/python/api/adbc_driver_manager.html)

```python
# Real ADBC implementation (for reference):
def adbc_clone(self) -> "Connection":
    conn = _lib.AdbcConnection(self._db._db, **(self._conn_kwargs or {}))
    return Connection(self._db, conn)
```

### Anti-Patterns to Avoid

- **Calling `__init__` for clones:** Would trigger driver import and real `connect()` call, duplicating the source connection's database state. Use `__new__` bypass.
- **Per-cursor wipe state without sharing:** Each cursor would independently decide to wipe, causing later clones to destroy earlier clones' recordings. Use shared container.
- **Tracking source/clone relationships:** Adds complexity with no benefit. Clones are fully independent once created. The shared `_wipe_state` is the only connection.
- **Deep-copying mutable config:** `_scrub_keys_global`, `_scrub_keys_per_driver`, and `_param_serialisers` are set once and never mutated. Shallow copy (reference sharing) is correct and intentional.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Connection cloning | Custom factory pattern or copy.copy | `__new__` + manual attribute copy | `__new__` is the canonical Python pattern for bypassing `__init__`; `copy.copy` would invoke `__copy__` and miss the `_real_conn.adbc_clone()` delegation |
| Shared mutable state | Threading primitives (locks, events) | Plain `dict` | Decision: sequential access only, no concurrent protection needed |

## Common Pitfalls

### Pitfall 1: Forgetting to Initialize `_wipe_state` in `__init__`

**What goes wrong:** If `__init__` doesn't create `_wipe_state`, existing code paths that don't go through `adbc_clone()` (i.e., direct `ReplayConnection(...)` construction) will fail with `AttributeError` when `cursor()` tries to pass `self._wipe_state` to `ReplayCursor`.

**Why it happens:** Easy to focus on the clone path and forget the normal construction path.

**How to avoid:** Add `self._wipe_state = {'wiped': False}` in `__init__` alongside the other attribute assignments.

**Warning signs:** Existing tests break with `AttributeError: '_wipe_state'`.

### Pitfall 2: Breaking the `ReplayCursor` Constructor Signature

**What goes wrong:** Adding `wipe_state` as a required parameter to `ReplayCursor.__init__` breaks all existing tests that construct `ReplayCursor` directly without passing `wipe_state`.

**Why it happens:** Many unit tests call `ReplayCursor(real_cursor=None, mode="none", cassette_path=...)` directly.

**How to avoid:** Make `wipe_state` an optional parameter with a default value. If `None`, create a standalone `{'wiped': False}` dict (backward-compatible default).

**Warning signs:** 50+ test failures across `test_cursor.py`, `test_record_modes.py`, etc.

### Pitfall 3: Clone Attributes Going Stale

**What goes wrong:** If new attributes are added to `ReplayConnection.__init__` in the future but not to `adbc_clone()`, clones silently miss attributes.

**Why it happens:** `__new__` bypass means Python gives no warning about missing attributes.

**How to avoid:** Keep `adbc_clone()` immediately after `__init__` in the source file. Consider a comment "CLONE-SYNC: update adbc_clone() when adding attributes".

**Warning signs:** `AttributeError` on cloned connections during future development.

### Pitfall 4: `_real_conn.adbc_clone()` Called When `_real_conn` Is None

**What goes wrong:** In replay mode, `_real_conn` is `None`. Calling `None.adbc_clone()` raises `AttributeError`.

**Why it happens:** Forgetting the None guard.

**How to avoid:** Always guard: `real_clone = self._real_conn.adbc_clone() if self._real_conn is not None else None`. This is already in the suggested implementation.

## Code Examples

### Complete `adbc_clone()` Implementation

```python
# Source: CONTEXT.md decisions + _notes/pool-clone-support.md
def adbc_clone(self) -> ReplayConnection:
    """
    Create a cloned connection sharing the same cassette and config.

    Mirrors the ADBC spec: clones share the underlying database handle.
    In record mode, delegates to the real connection's adbc_clone().
    In replay mode, creates a new ReplayConnection with no real connection.

    All clones share the same cassette path and wipe state.
    Clone-of-clone is supported.
    """
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
    clone._wipe_state = self._wipe_state
    return clone
```

### Modified `ReplayConnection.__init__` (add `_wipe_state`)

```python
def __init__(self, ...) -> None:
    # ... existing attribute assignments ...
    self._wipe_state: dict[str, bool] = {'wiped': False}
    # ... rest of __init__ ...
```

### Modified `ReplayConnection.cursor()` (thread `_wipe_state`)

```python
def cursor(self) -> ReplayCursor:
    real_cursor = self._real_conn.cursor() if self._real_conn is not None else None
    return ReplayCursor(
        real_cursor=real_cursor,
        mode=self._mode,
        cassette_path=self._cassette_path,
        dialect=self._dialect,
        param_serialisers=self._param_serialisers,
        scrub_keys_global=self._scrub_keys_global,
        scrub_keys_per_driver=self._scrub_keys_per_driver,
        driver_name=self._driver_module_name,
        scrubber=self._scrubber,
        wipe_state=self._wipe_state,  # NEW
    )
```

### Modified `ReplayCursor.__init__` (accept `wipe_state`)

```python
def __init__(
    self,
    real_cursor: Any,
    mode: str,
    cassette_path: Path,
    ...,
    wipe_state: dict[str, bool] | None = None,
) -> None:
    # ... existing assignments ...
    # Replace: self._wiped: bool = False
    self._wipe_state: dict[str, bool] = wipe_state if wipe_state is not None else {'wiped': False}
```

### Modified `ReplayCursor._ensure_initialised()` (use `_wipe_state`)

```python
def _ensure_initialised(self) -> None:
    if self._initialised:
        return
    self._initialised = True
    if self._mode == "all" and not self._wipe_state['wiped']:
        if self._cassette_path.exists():
            shutil.rmtree(self._cassette_path)
        self._wipe_state['wiped'] = True
        return
    # ... rest unchanged ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-cursor `_wiped` bool | Shared `_wipe_state` dict from connection | This phase | Enables safe wipe-once-across-clones for 'all' mode |
| No `adbc_clone()` method | Full `adbc_clone()` support | This phase | Enables pool-based testing with cassette replay |

## Open Questions

None -- the CONTEXT.md decisions are comprehensive and cover all design considerations.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/unit/test_clone.py -x` |
| Full suite command | `uv run pytest tests/unit/ -x` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLONE-01 | `adbc_clone()` returns a `ReplayConnection` | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_clone_returns_replay_connection -x` | No -- Wave 0 |
| CLONE-02 | Clone shares same cassette path as source | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_clone_shares_cassette_path -x` | No -- Wave 0 |
| CLONE-03 | Clone in replay mode has `_real_conn = None` | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_clone_replay_mode_no_real_conn -x` | No -- Wave 0 |
| CLONE-04 | Clone in record mode delegates to `_real_conn.adbc_clone()` | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_clone_record_mode_delegates -x` | No -- Wave 0 |
| CLONE-05 | Clone's cursor has independent replay queue | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_clone_cursor_independent_queue -x` | No -- Wave 0 |
| CLONE-06 | Shared wipe state: first cursor wipes, second does not | unit | `uv run pytest tests/unit/test_clone.py::TestSharedWipeState::test_first_cursor_wipes -x` | No -- Wave 0 |
| CLONE-07 | Clone-of-clone works (depth > 1) | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_clone_of_clone -x` | No -- Wave 0 |
| CLONE-08 | Close on clone does not affect source or cassette | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_close_isolation -x` | No -- Wave 0 |
| CLONE-09 | All existing tests still pass (backward compat) | unit | `uv run pytest tests/unit/ -x` | Yes -- existing |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_clone.py -x`
- **Per wave merge:** `uv run pytest tests/unit/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_clone.py` -- covers CLONE-01 through CLONE-08
- No framework install needed -- pytest already configured
- No conftest changes needed -- existing unit conftest is minimal

## Sources

### Primary (HIGH confidence)
- [ADBC Driver Manager API docs](https://arrow.apache.org/adbc/current/python/api/adbc_driver_manager.html) -- `adbc_clone()` method signature and behavior
- [ADBC Driver Manager source (GitHub)](https://github.com/apache/arrow-adbc/blob/main/python/adbc_driver_manager/adbc_driver_manager/dbapi.py) -- actual implementation of `Connection.adbc_clone()` and `Connection.__init__`
- Project source: `_notes/pool-clone-support.md` -- requirements and suggested implementation
- Project source: `src/pytest_adbc_replay/_connection.py` -- current `ReplayConnection` (10 attributes to copy)
- Project source: `src/pytest_adbc_replay/_cursor.py` -- current `ReplayCursor._wiped` flag and `_ensure_initialised()` wipe logic

### Secondary (MEDIUM confidence)
- None needed -- implementation is fully specified by CONTEXT.md decisions and existing source code

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, modifying existing files only
- Architecture: HIGH -- decisions locked in CONTEXT.md, suggested implementation in `_notes/pool-clone-support.md`, real ADBC source verified
- Pitfalls: HIGH -- identified from direct code analysis of existing test patterns and constructor signatures

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable -- no external dependency changes expected)
