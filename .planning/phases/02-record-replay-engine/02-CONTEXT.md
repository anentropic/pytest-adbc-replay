# Phase 2: Record/Replay Engine - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the Phase 1 `ReplayCursor`/`ReplayConnection` stubs to real cassette storage and SQL normalisation. Deliver: cassette file I/O (`.sql`, `.arrow`, `.json`), SQL normalisation via sqlglot with fallback, four record mode state machines (`none`/`once`/`new_episodes`/`all`), and ordered-queue replay. No new user-facing API surface — this is the engine behind what Phase 1 already exposes.

</domain>

<decisions>
## Implementation Decisions

### SQL Normalisation Warnings

- When sqlglot cannot parse SQL and falls back to whitespace-only normalisation: emit a **`warnings.warn()`** with a named `NormalisationWarning` subclass
- Warning includes the **full SQL** (not truncated) — helps identify the query without ambiguity
- `NormalisationWarning` is suppressible via pytest's `-W` flag: `-W ignore::pytest_adbc_replay.NormalisationWarning`
- Warning fires on **both record and replay** — same behaviour regardless of mode

### Parameter Serialisation

- Non-JSON-native types use **type-tagged JSON**: `{"__type__": "datetime", "value": "2024-01-15T12:00:00"}` — round-trips cleanly, human-readable
- `None` parameters are stored as JSON `null`
- If a type cannot be serialised by the built-in registry and no custom handler is registered, **raise `TypeError`** with a clear message pointing the user to `adbc_param_serialisers` fixture
- **Parameters are part of the cassette key** — same SQL with different bind values = different interaction (matches CASS-06 design)

**Custom serialiser API — per-type registry fixture:**

```python
# conftest.py
@pytest.fixture(scope="session")
def adbc_param_serialisers():
    from myapp.models import Money
    return {
        Money: {
            "serialise": lambda m: {"currency": m.currency, "amount": str(m.amount)},
            "deserialise": lambda d: Money(d["currency"], Decimal(d["amount"])),
        },
    }
```

- Fixture returns `{type: {"serialise": fn, "deserialise": fn}}` — plugin **merges** with built-in defaults (user entries override)
- To clear all defaults and start from scratch: `return NO_DEFAULT_SERIALISERS | {MyType: {...}}` where `NO_DEFAULT_SERIALISERS` is exported from `pytest_adbc_replay`

**Built-in default serialisers** (no user config needed):
- `datetime`, `date`, `time` — ISO 8601 string round-trip
- `Decimal` — `str()` round-trip
- `bytes` — hex string round-trip
- `UUID` — `str()` round-trip

### Record Mode Edge Cases

**`once` mode — "cassette exists" definition:**
- Cassette is considered present if the **directory exists AND contains at least one interaction file** (e.g. `000_query.sql`)
- Empty directory → re-record (not treated as "cassette exists")

**`new_episodes` mode — new queries during an existing cassette run:**
- Queue-based: **replay interactions 0..N-1 from cassette, record interaction N as a new file** — matches VCR.py `new_episodes` semantics exactly

**`none` mode — empty cassette directory:**
- Distinct error message: **"cassette directory is empty — run with --adbc-record=once to record"** (not the same as "cassette missing")

**`none` mode — test never calls `execute()`:**
- **Passes silently** — plugin is transparent when unused; no warning emitted

### `all` Mode Cleanup

- **Delete-and-recreate** the cassette directory at the first `execute()` call during the test (not at fixture init — avoids wiping dirs for tests that never call execute)
- If recording is interrupted mid-test (crash), the **partial cassette is kept** — user can inspect and re-run; no silent data loss
- `all` mode **records all tests** including those with no existing cassette — uniform behaviour, no distinction from `once` for new tests

### Claude's Discretion

- Arrow IPC format choice: `RecordBatchFileWriter` vs `RecordBatchStreamWriter` — use File format for v1 (simpler, seekable, recommended by research)
- Internal cassette key hashing/serialisation implementation
- Ordered-queue data structure for duplicate-query replay
- LRU cache size for normalised SQL

</decisions>

<specifics>
## Specific Ideas

- `NO_DEFAULT_SERIALISERS` should be exported from the top-level `pytest_adbc_replay` package so users can import it cleanly
- Error messages for record mode edge cases should echo the applicable `--adbc-record=<mode>` flag so users know what to run next
- The `new_episodes` semantics should exactly mirror VCR.py — any user familiar with pytest-recording should have zero learning curve

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-record-replay-engine*
*Context gathered: 2026-02-28*
