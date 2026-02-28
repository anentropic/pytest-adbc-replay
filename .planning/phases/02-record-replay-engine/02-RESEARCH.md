# Phase 2: Record/Replay Engine - Research

**Researched:** 2026-02-28
**Domain:** Arrow IPC serialization + SQL normalisation (sqlglot) + record mode state machine
**Confidence:** HIGH

## Summary

Phase 2 wires the Phase 1 `ReplayCursor`/`ReplayConnection` stubs to real cassette storage and SQL normalisation. The Phase 1 implementation is complete: all files exist, the plugin is discoverable, and `ReplayCursor.execute()` in replay mode currently stores an empty `pa.table({})` as a placeholder. Phase 2 replaces those placeholders with real file I/O.

Three technical domains must be implemented:

1. **Cassette Storage** — Write `.sql` (pretty-printed), `.arrow` (Arrow IPC file format), and `.json` (params) files per interaction; read them back in replay mode. `pyarrow.ipc.RecordBatchFileWriter` / `open_file().read_all()` is the correct pair (File format, not Stream format, because it is seekable and simpler). Schema metadata round-trips cleanly at the schema level.

2. **SQL Normalisation** — `sqlglot.parse_one(sql, dialect=dialect).sql(pretty=True)` normalises keyword casing, whitespace, and quote style in one pass. On `sqlglot.errors.ParseError`, fall back to `" ".join(sql.split())` and emit `warnings.warn(msg, NormalisationWarning)`. Cache normalised SQL with `functools.lru_cache` (maxsize=256 is sufficient for typical test suites).

3. **Record Mode State Machine** — Four modes control `ReplayCursor.execute()` behaviour. The ordered-queue replay (duplicate queries get their own FIFO queue per interaction key) uses `collections.defaultdict(collections.deque)` — no external dependency needed.

**Primary recommendation:** Implement in three focused modules: `_normaliser.py` (SQL normalisation + warning), `_cassette_io.py` (Arrow IPC + JSON read/write), and `_record_mode.py` (mode dispatch logic). Wire into the existing `_cursor.py` which already has the correct interface.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### SQL Normalisation Warnings
- When sqlglot cannot parse SQL and falls back to whitespace-only normalisation: emit a **`warnings.warn()`** with a named `NormalisationWarning` subclass
- Warning includes the **full SQL** (not truncated) — helps identify the query without ambiguity
- `NormalisationWarning` is suppressible via pytest's `-W` flag: `-W ignore::pytest_adbc_replay.NormalisationWarning`
- Warning fires on **both record and replay** — same behaviour regardless of mode

#### Parameter Serialisation
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

#### Record Mode Edge Cases
- **`once` mode — "cassette exists" definition:** Directory exists AND contains at least one interaction file (e.g. `000_query.sql`). Empty directory → re-record.
- **`new_episodes` mode:** Replay interactions 0..N-1 from cassette, record interaction N as a new file — matches VCR.py `new_episodes` semantics exactly.
- **`none` mode — empty cassette directory:** Distinct error message: "cassette directory is empty — run with --adbc-record=once to record" (not the same as "cassette missing")
- **`none` mode — test never calls `execute()`:** Passes silently — plugin is transparent when unused

#### `all` Mode Cleanup
- **Delete-and-recreate** the cassette directory at the first `execute()` call during the test (not at fixture init)
- If recording is interrupted mid-test (crash), the **partial cassette is kept** — no silent data loss
- `all` mode **records all tests** including those with no existing cassette — uniform behaviour

### Claude's Discretion
- Arrow IPC format choice: `RecordBatchFileWriter` vs `RecordBatchStreamWriter` — use File format for v1 (simpler, seekable, recommended by research)
- Internal cassette key hashing/serialisation implementation
- Ordered-queue data structure for duplicate-query replay
- LRU cache size for normalised SQL

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CASS-01 | Cassettes stored in configurable directory (default: `tests/cassettes`) | `ReplaySession.cassette_dir` already wired from Phase 1; cassette_path passed to ReplayCursor |
| CASS-02 | Each cassette is a directory per test; interactions are numbered files (`000_query.sql`, `000_result.arrow`, `000_params.json`) | Directory-per-test via cassette_path already resolved; numbered files with `{n:03d}_{role}.{ext}` pattern |
| CASS-03 | SQL stored as human-readable pretty-printed `.sql` files | `sqlglot.parse_one(sql).sql(pretty=True)` produces readable SQL; write as UTF-8 text |
| CASS-04 | Results stored as Arrow IPC `.arrow` files preserving schema metadata | `pa.ipc.RecordBatchFileWriter` + `pa.ipc.open_file().read_all()` — schema metadata (including field metadata) preserved at schema level |
| CASS-05 | Parameters and driver options stored as `.json` files (null when absent) | `json.dumps(serialise_params(params), indent=2)` with type-tagged encoding; `null` when params is None |
| CASS-06 | Cassette key is `(normalised_sql, parameters, driver_options)`; duplicate queries use ordered-queue replay | Key = normalised SQL + serialised params tuple; `defaultdict(deque)` tracks per-key interaction index |
| NORM-01 | SQL normalised via sqlglot before use as cassette key | `parse_one(sql, dialect=dialect).sql(pretty=True)` — handles casing, whitespace, quote style |
| NORM-02 | Normalisation falls back to whitespace-only stripping when sqlglot cannot parse | `except sqlglot.errors.ParseError: " ".join(sql.split())` + `warnings.warn(NormalisationWarning)` |
| NORM-03 | Dialect configurable at three levels: global → marker → None (auto-detect) | `dialect` param already flows from `ReplaySession` → `ReplayConnection` → `ReplayCursor`; pass to `parse_one(dialect=...)` |
| NORM-04 | Parameter placeholders (`?`, `%s`, `$1`) preserved as-is | Placeholders are not SQL constants — sqlglot preserves them; verify with test |
| MODE-01 | `none` mode — replay only; fail with clear error on cassette miss; never contacts warehouse | Load from cassette files; `CassetteMissError` if missing; ReplayConnection already skips driver import |
| MODE-02 | `once` mode — record if cassette directory absent (or empty); replay if present with interactions | Check `cassette_path.exists()` AND any `.sql` file present; if absent/empty → record; else → replay |
| MODE-03 | `new_episodes` mode — replay existing interactions; record any not in cassette | Use ordered-queue position as interaction index; replay index < cassette size; record index >= cassette size |
| MODE-04 | `all` mode — re-record everything, overwriting existing cassettes | Delete + recreate directory on first `execute()` call; then record all subsequent calls |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyarrow | >=14.0 (installed; latest is 23.0.1) | Arrow IPC file write/read for cassette result storage | Already a project dependency (Phase 1); only format with full ADBC schema fidelity |
| sqlglot | >=23.0 (installed; latest is 28.10.1) | SQL normalisation — parse + re-emit in canonical form | Already a project dependency (Phase 1); pure Python, zero dependencies, 31 dialects |
| json | stdlib | Serialise parameters and driver options to `.json` cassette files | Stdlib; type-tagged encoding is sufficient for the requirement |
| warnings | stdlib | `NormalisationWarning` via `warnings.warn()` | Stdlib; suppressible with `-W ignore::pytest_adbc_replay.NormalisationWarning` |
| functools | stdlib | `lru_cache` for normalised SQL memoisation | Stdlib; O(1) cache lookup for warm test runs |
| collections | stdlib | `defaultdict(deque)` for ordered-queue replay of duplicate queries | Stdlib; exactly the right structure for FIFO per-interaction-key queues |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | stdlib | All cassette path operations | Already used in Phase 1 code |
| shutil | stdlib | `shutil.rmtree(cassette_path)` for `all` mode directory cleanup | Stdlib; `rmtree` is the right tool for "delete this directory tree" |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Arrow IPC File format | Arrow IPC Stream format | File format supports seeking and random access; Stream format does not. For cassettes, File format is simpler (no partial-read scenarios) |
| Arrow IPC File format | Parquet | Parquet has more complex chunking; Arrow IPC is a direct memory-mapped format with zero transformation — better for simple write-and-read-back patterns |
| `json.dumps` with type tags | pickle | pickle is unsafe (arbitrary code execution on load), not human-readable, not git-diff-friendly |
| `lru_cache` on normalise function | dict cache | `lru_cache` is simpler, already evicts stale entries by LRU policy, no manual cache management |

## Architecture Patterns

### Recommended Module Structure (Phase 2 additions)

```
src/pytest_adbc_replay/
├── __init__.py          # Add: NormalisationWarning, NO_DEFAULT_SERIALISERS
├── _normaliser.py       # NEW: normalise_sql(), NormalisationWarning
├── _cassette_io.py      # NEW: CassetteReader, CassetteWriter (Arrow IPC + JSON)
├── _params.py           # NEW: serialise_params(), deserialise_params(), built-in registry
├── _record_mode.py      # NEW: RecordModeHandler dispatch logic for execute()
├── _cursor.py           # MODIFY: wire _normaliser, _cassette_io, _record_mode into execute()
└── plugin.py            # MODIFY: register adbc_param_serialisers fixture

tests/
├── test_normaliser.py   # NEW: SQL normalisation, NormalisationWarning, fallback
├── test_cassette_io.py  # NEW: Arrow IPC round-trip, JSON params read/write
├── test_record_modes.py # NEW: all four record mode behaviours with real cassette files
└── conftest.py          # Add: adbc_param_serialisers fixture for tests
```

### Pattern 1: SQL Normalisation with Fallback

**What:** Parse SQL with sqlglot, re-emit in canonical dialect. On parse error, fall back to whitespace normalisation and emit a warning.

**When to use:** Every time a cassette key is computed (on `execute()` in both record and replay mode).

**Example (verified via Context7):**

```python
# src/pytest_adbc_replay/_normaliser.py
from __future__ import annotations

import functools
import warnings

import sqlglot
import sqlglot.errors


class NormalisationWarning(UserWarning):
    """Emitted when sqlglot cannot parse SQL and falls back to whitespace normalisation."""


@functools.lru_cache(maxsize=256)
def _cached_normalise(sql: str, dialect: str | None) -> str:
    """Cached SQL normalisation — cache is warm for repeated execute() calls."""
    try:
        return sqlglot.parse_one(sql, dialect=dialect).sql(pretty=True)
    except sqlglot.errors.ParseError:
        warnings.warn(
            f"sqlglot could not parse SQL; falling back to whitespace normalisation.\n"
            f"  SQL: {sql}\n"
            f"  Suppress: -W ignore::pytest_adbc_replay.NormalisationWarning",
            NormalisationWarning,
            stacklevel=4,
        )
        return " ".join(sql.split())


def normalise_sql(sql: str, dialect: str | None = None) -> str:
    """Return canonical SQL string for use as a cassette key."""
    return _cached_normalise(sql, dialect)
```

**Key point:** `lru_cache` requires hashable arguments. Both `str` and `str | None` are hashable — no issue.

### Pattern 2: Arrow IPC File Write/Read Round-Trip

**What:** Write a `pyarrow.Table` to a `.arrow` file using `RecordBatchFileWriter`; read it back with `open_file().read_all()`. Schema metadata (including field-level metadata) is preserved.

**When to use:** Recording `execute()` result; loading result in replay mode.

**Example (verified via official Apache Arrow docs v23.0.1):**

```python
# src/pytest_adbc_replay/_cassette_io.py — Arrow IPC patterns
import pyarrow as pa

def write_arrow_table(table: pa.Table, path: Path) -> None:
    """Write a pyarrow.Table to an Arrow IPC file."""
    with pa.ipc.new_file(str(path), table.schema) as writer:
        writer.write_table(table)


def read_arrow_table(path: Path) -> pa.Table:
    """Read a pyarrow.Table from an Arrow IPC file."""
    with pa.ipc.open_file(str(path)) as reader:
        return reader.read_all()
```

**Schema metadata preservation:** Arrow IPC File format preserves `schema.metadata` (key-value bytes dict) and per-field metadata. ADBC drivers may embed Arrow type extension metadata in field metadata; this round-trips cleanly via the File format.

**File vs Stream format:** Use `pa.ipc.new_file()` (File writer), not `pa.ipc.new_stream()` (Stream writer). File format includes a footer with schema + batch offsets — supports random access. Stream format is simpler for streaming but cannot be memory-mapped. For cassettes (written once, read once) File format is the better choice per the CONTEXT.md decision.

### Pattern 3: Type-Tagged JSON Parameter Serialisation

**What:** Serialise `execute(sql, parameters)` parameters to JSON with type tags for non-native types. Deserialise on replay.

**When to use:** Writing `.json` cassette interaction files; reading them back in replay.

**Example:**

```python
# src/pytest_adbc_replay/_params.py
from __future__ import annotations

import json
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID
from typing import Any


_BUILTIN_SERIALISERS: dict[type, dict[str, Any]] = {
    datetime: {
        "serialise": lambda v: {"__type__": "datetime", "value": v.isoformat()},
        "deserialise": lambda d: datetime.fromisoformat(d["value"]),
    },
    date: {
        "serialise": lambda v: {"__type__": "date", "value": v.isoformat()},
        "deserialise": lambda d: date.fromisoformat(d["value"]),
    },
    time: {
        "serialise": lambda v: {"__type__": "time", "value": v.isoformat()},
        "deserialise": lambda d: time.fromisoformat(d["value"]),
    },
    Decimal: {
        "serialise": lambda v: {"__type__": "Decimal", "value": str(v)},
        "deserialise": lambda d: Decimal(d["value"]),
    },
    bytes: {
        "serialise": lambda v: {"__type__": "bytes", "value": v.hex()},
        "deserialise": lambda d: bytes.fromhex(d["value"]),
    },
    UUID: {
        "serialise": lambda v: {"__type__": "UUID", "value": str(v)},
        "deserialise": lambda d: UUID(d["value"]),
    },
}

# Sentinel — users return NO_DEFAULT_SERIALISERS | {...} to start from scratch
NO_DEFAULT_SERIALISERS: dict[type, dict[str, Any]] = {}


def build_registry(user_serialisers: dict[type, dict[str, Any]] | None) -> dict[type, dict[str, Any]]:
    """Merge built-ins with user-provided serialisers. User entries override built-ins."""
    if user_serialisers is None:
        return _BUILTIN_SERIALISERS.copy()
    # If user returned NO_DEFAULT_SERIALISERS (empty dict) | {their types}, use as-is
    if not user_serialisers:
        return {}
    return {**_BUILTIN_SERIALISERS, **user_serialisers}


def serialise_params(params: Any, registry: dict[type, dict[str, Any]]) -> Any:
    """Serialise parameters to a JSON-safe structure with type tags."""
    if params is None:
        return None
    if isinstance(params, (list, tuple)):
        return [_serialise_value(v, registry) for v in params]
    if isinstance(params, dict):
        return {k: _serialise_value(v, registry) for k, v in params.items()}
    return _serialise_value(params, registry)


def _serialise_value(v: Any, registry: dict[type, dict[str, Any]]) -> Any:
    if v is None:
        return None
    if isinstance(v, (bool, int, float, str)):
        return v  # JSON-native
    for typ, handler in registry.items():
        if isinstance(v, typ):
            return handler["serialise"](v)
    raise TypeError(
        f"Cannot serialise parameter of type {type(v).__name__!r}.\n"
        f"Register a custom handler via the `adbc_param_serialisers` fixture:\n"
        f"  @pytest.fixture(scope='session')\n"
        f"  def adbc_param_serialisers():\n"
        f"      return {{{type(v).__name__}: {{'serialise': ..., 'deserialise': ...}}}}"
    )
```

### Pattern 4: Ordered-Queue Replay for Duplicate Queries

**What:** When the same (normalised_sql, params) key appears multiple times in a cassette, each `execute()` call pops the next result from a FIFO queue. This is the "ordered-queue" design from CASS-06.

**When to use:** `execute()` in replay mode whenever multiple interactions exist for the same key.

**Example:**

```python
# In ReplayCursor — initialised per-test
from collections import defaultdict, deque

class ReplayCursor:
    def __init__(self, ...):
        ...
        # key: (normalised_sql, frozen_params) -> deque of interaction indices
        self._replay_queue: dict[tuple[str, ...], deque[int]] = defaultdict(deque)
        self._record_index: int = 0  # Next interaction number to write

    def _make_key(self, normalised_sql: str, params: Any) -> tuple[str, str]:
        """Create a hashable cassette key from normalised SQL + serialised params."""
        import json
        params_json = json.dumps(serialise_params(params, self._registry), sort_keys=True)
        return (normalised_sql, params_json)
```

**Key insight:** Use a monotonic `_record_index` counter (0, 1, 2, ...) for file naming during record. Use separate per-key deques pre-populated from cassette file scan during replay initialisation.

### Pattern 5: Record Mode State Machine

**What:** Four modes dispatch `execute()` to different handlers. The decision tree is:

```
execute(sql, params) called:
  1. Normalise SQL → canonical_sql
  2. Compute key = (canonical_sql, serialised_params)
  3. Dispatch by mode:

  none:
    - Load next interaction from cassette queue for this key
    - If no interaction: CassetteMissError
    - Return: set self._pending = loaded_table

  once:
    - If cassette_path has no interaction files: record (same as `all` for new cassettes)
    - Else: replay (same as `none`)

  new_episodes:
    - If interaction exists in queue: replay
    - Else: record to disk (next file index = current record_index), increment record_index

  all:
    - On FIRST execute() call: delete + recreate cassette_path dir
    - Always: record to disk, increment record_index
```

**When to use:** Core dispatch in `ReplayCursor.execute()`.

**Example:**

```python
# In ReplayCursor._execute_dispatch():
def _execute_dispatch(self, sql: str, params: Any, kwargs: dict) -> None:
    canonical = normalise_sql(sql, self._dialect)
    key = self._make_key(canonical, params)

    if self._mode == "none":
        self._pending = self._load_from_queue(key, sql, canonical)
    elif self._mode == "once":
        if self._cassette_has_interactions():
            self._pending = self._load_from_queue(key, sql, canonical)
        else:
            self._pending = self._record_interaction(sql, canonical, params, kwargs)
    elif self._mode == "new_episodes":
        if key in self._replay_queue and self._replay_queue[key]:
            self._pending = self._replay_queue[key].popleft()
        else:
            self._pending = self._record_interaction(sql, canonical, params, kwargs)
    elif self._mode == "all":
        if self._record_index == 0:
            self._wipe_cassette_dir()
        self._pending = self._record_interaction(sql, canonical, params, kwargs)
```

### Pattern 6: Cassette Initialisation on execute()

**What:** When a `ReplayCursor` is about to be used, load the existing cassette directory (if present) to populate the replay queue. For `all` mode, wipe on first execute.

**When to use:** Lazy initialisation — only scan cassette directory when `execute()` is first called, not at cursor construction. This avoids scanning for tests that never call `execute()` (MODE-01 "passes silently" requirement).

**Example:**

```python
def _ensure_initialised(self) -> None:
    if self._initialised:
        return
    self._initialised = True
    if self._mode in ("none", "once", "new_episodes"):
        self._load_cassette_interactions()

def _load_cassette_interactions(self) -> None:
    """Pre-populate replay queue from existing cassette files."""
    if not self._cassette_path.exists():
        return
    # Find all *_query.sql files in order
    sql_files = sorted(self._cassette_path.glob("*_query.sql"))
    for sql_file in sql_files:
        prefix = sql_file.stem.replace("_query", "")  # e.g. "000"
        arrow_file = self._cassette_path / f"{prefix}_result.arrow"
        params_file = self._cassette_path / f"{prefix}_params.json"
        canonical_sql = sql_file.read_text(encoding="utf-8").strip()
        params_raw = json.loads(params_file.read_text(encoding="utf-8")) if params_file.exists() else None
        key = self._make_key_from_canonical(canonical_sql, params_raw)
        table = read_arrow_table(arrow_file)
        self._replay_queue[key].append(table)
```

### Anti-Patterns to Avoid

- **Using Stream format instead of File format for Arrow IPC:** `pa.ipc.new_stream()` does not support seeking; `pa.ipc.new_file()` produces a proper Arrow file with footer. Always use `new_file()`.
- **Initialising the replay queue in `__init__` instead of lazily on `execute()`:** Tests that never call `execute()` must pass silently (`none` mode). Scanning cassette dir at construction would cause failures for tests that don't use the cursor.
- **Using `all` mode to wipe at fixture init instead of at first execute():** CONTEXT.md specifies "wipe at first execute()" to avoid deleting cassette dirs for tests that never call execute.
- **Computing the cassette key from raw SQL:** Key must use normalised SQL — different whitespace/casing → same cassette entry.
- **Raising ParseError instead of falling back in normaliser:** NORM-02 requires fallback + warning, never an exception from the normaliser.
- **Treating `once` mode "cassette exists" as directory-exists only:** CONTEXT.md: directory must exist AND contain at least one `.sql` file. Empty dir → re-record.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Arrow serialisation | Custom binary format | `pa.ipc.new_file()` + `pa.ipc.open_file()` | Arrow IPC handles all type edge cases (extension types, dictionaries, nullability, nested types); hand-rolling loses metadata |
| SQL normalisation | Regex-based lowercasing | `sqlglot.parse_one().sql(pretty=True)` | sqlglot handles dialect-specific keyword sets, function casing, quote style, whitespace — regex cannot |
| FIFO duplicate-query queue | Custom linked list | `collections.defaultdict(collections.deque)` | Stdlib; thread-safe appends/pops; exactly FIFO semantics |
| Parameter serialisation | Python's pickle | Type-tagged JSON (`{"__type__": ..., "value": ...}`) | pickle is unsafe to deserialise from disk; JSON is human-readable and git-diff-friendly |
| Directory wipe | `os.remove` loop | `shutil.rmtree(path)` | stdlib; handles non-empty dirs, symlinks, permissions correctly |

**Key insight:** All three non-trivial problems (Arrow, SQL normalisation, FIFO queues) have stdlib or already-installed library solutions. The Phase 2 work is primarily wiring, not algorithm design.

## Common Pitfalls

### Pitfall 1: Arrow Schema Metadata Not Preserved

**What goes wrong:** Arrow table is written and read back, but ADBC extension types are lost (schema metadata stripped).

**Why it happens:** Using `write_batch()` with a default schema instead of `write_table()`. Or using Stream format instead of File format.

**How to avoid:** Always use `writer.write_table(table)` (not manual batch decomposition). Use `pa.ipc.new_file(path, table.schema)` — the schema is embedded in the file header and footer. Read back with `pa.ipc.open_file(path).read_all()`.

**Warning signs:** `test_arrow_round_trip_schema_metadata_preserved` fails; schema equality check returns False.

### Pitfall 2: sqlglot ParseError Not Caught on All Code Paths

**What goes wrong:** Some SQL strings (vendor-specific syntax, parameter placeholders like `$1`) cause sqlglot to raise `ParseError`. If the catch is missing, `normalise_sql()` raises instead of falling back.

**Why it happens:** `sqlglot.parse_one()` raises `sqlglot.errors.ParseError` on many inputs that are valid SQL for specific dialects but not sqlglot's superset parser.

**How to avoid:** Catch `sqlglot.errors.ParseError` (not the base `SqlglotError`) specifically. The fallback must produce a deterministic key: `" ".join(sql.split())` (collapse all whitespace, including tabs/newlines).

**Warning signs:** Tests with `$1` or `%s` placeholders cause `ParseError` in normaliser; `NormalisationWarning` not emitted when expected.

### Pitfall 3: `once` Mode Overwrites Existing Cassette

**What goes wrong:** `once` mode records over an existing cassette because the "has interactions" check only looks at directory existence.

**Why it happens:** CONTEXT.md definition: cassette exists = directory present + at least one `.sql` file. Empty directory → treat as missing → re-record.

**How to avoid:**
```python
def _cassette_has_interactions(self) -> bool:
    if not self._cassette_path.exists():
        return False
    return any(self._cassette_path.glob("*_query.sql"))
```

**Warning signs:** Second run in `once` mode overwrites first run's cassette; replay mode then fails.

### Pitfall 4: `all` Mode Wipes Directory Even for Tests That Don't Execute

**What goes wrong:** A test that uses `--adbc-record=all` but never calls `cursor.execute()` still has its cassette directory wiped.

**Why it happens:** Directory wipe in `__init__` or in fixture setup, not deferred to first `execute()`.

**How to avoid:** Set `self._wiped = False` in `__init__`. In `execute()` with mode `all`, check `if not self._wiped: shutil.rmtree(...); self._wiped = True` before recording.

**Warning signs:** Empty cassette directories appear after `--adbc-record=all` runs for tests that don't call execute.

### Pitfall 5: `none` Mode Silently Passes with Empty Cassette Dir

**What goes wrong:** `none` mode on an empty cassette directory (not missing, but empty) gives wrong error message — says "cassette missing" instead of "cassette is empty".

**Why it happens:** Both cases raise `CassetteMissError.directory_missing` when the correct message for empty dirs is "cassette directory is empty — run with --adbc-record=once to record".

**How to avoid:** Add a third `CassetteMissError` factory method (or extend the existing ones) for the empty-directory case. Check: `cassette_path.exists() and not any(cassette_path.glob("*_query.sql"))` → "empty cassette" message.

**Warning signs:** Users see "directory does not exist" message when the directory clearly exists but is empty.

### Pitfall 6: Parameter Placeholder Normalisation Breaks Cassette Key Stability

**What goes wrong:** `?` or `%s` placeholders in SQL get normalised differently between runs, causing cassette miss errors.

**Why it happens:** Some sqlglot versions normalise `%s` to `%(1)s` or similar vendor forms. The cassette key includes the normalised SQL, so the key changes between Python versions / sqlglot versions.

**How to avoid:** Write a unit test that verifies `normalise_sql("SELECT * FROM t WHERE id = ?")` → stable output across two calls. If the output contains `?`/`%s`/`$1` as-is, the round-trip is stable (NORM-04). If sqlglot mutates them, add a pre/post replacement step.

**Warning signs:** Cassette keys change between patch versions of sqlglot; replay fails after updating sqlglot.

### Pitfall 7: basedpyright Strict Mode Rejects Untyped Code

**What goes wrong:** Pre-commit hook (`prek run --all-files`) fails with type errors.

**Why it happens:** `basedpyright` configured with `typeCheckingMode = "strict"` in `pyproject.toml`. Any untyped variable, missing return annotation, or use of `Any` without import causes an error.

**How to avoid:** All new modules need `from __future__ import annotations`. All functions need full type annotations. Import `Any` from `typing` for parameters accepted as `Any`. Use `TYPE_CHECKING` blocks for forward references to avoid circular imports.

## Code Examples

### Writing and Reading Arrow IPC Files (Verified from Apache Arrow v23.0.1 docs)

```python
# Source: https://arrow.apache.org/docs/python/ipc.html + https://arrow.apache.org/docs/python/generated/pyarrow.ipc.RecordBatchFileWriter.html

import pyarrow as pa

def write_arrow_table(table: pa.Table, path: str | Path) -> None:
    """Write table to Arrow IPC file format."""
    with pa.ipc.new_file(str(path), table.schema) as writer:
        writer.write_table(table)


def read_arrow_table(path: str | Path) -> pa.Table:
    """Read table from Arrow IPC file format."""
    with pa.ipc.open_file(str(path)) as reader:
        return reader.read_all()
```

### sqlglot Normalisation with Error Handling (Verified from Context7)

```python
# Source: https://context7.com/tobymao/sqlglot/llms.txt
import sqlglot
import sqlglot.errors

try:
    normalised = sqlglot.parse_one("select * from FOO", dialect=None).sql(pretty=True)
    # → "SELECT\n  *\nFROM foo"
except sqlglot.errors.ParseError as e:
    normalised = " ".join("select * from FOO".split())
    warnings.warn(f"sqlglot fallback: {e}", NormalisationWarning)
```

### NormalisationWarning Suppressible in pytest

```python
# conftest.py — add to suppress warnings in all tests
import warnings
from pytest_adbc_replay import NormalisationWarning

# Or via pytest CLI: -W ignore::pytest_adbc_replay.NormalisationWarning
# Or via pytest.ini:
# [pytest]
# filterwarnings = ignore::pytest_adbc_replay.NormalisationWarning
```

### Ordered-Queue Replay Population

```python
# Verified design — stdlib only
from collections import defaultdict, deque
from pathlib import Path
import pyarrow as pa

replay_queue: dict[tuple[str, str], deque[pa.Table]] = defaultdict(deque)

cassette_path = Path("tests/cassettes/my_test")
for sql_file in sorted(cassette_path.glob("*_query.sql")):
    prefix = sql_file.name.split("_")[0]  # "000", "001", etc.
    arrow_file = cassette_path / f"{prefix}_result.arrow"
    # Read normalised SQL and table
    normalised_sql = sql_file.read_text("utf-8").strip()
    table = pa.ipc.open_file(str(arrow_file)).read_all()
    key = (normalised_sql, "null")  # simplified; real key includes params
    replay_queue[key].append(table)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Parquet for tabular storage | Arrow IPC file format | Always for ADBC (cassettes) | IPC format is zero-transformation — same in-memory layout as Arrow; no Parquet overhead |
| `sqlglot.transpile()` for normalisation | `parse_one().sql(pretty=True)` | Current best practice | `transpile` is for dialect conversion; `parse_one().sql()` is for normalisation within same dialect |
| `vcr.py` (HTTP-only) | Custom ADBC-level cassette | N/A | VCR.py patches the HTTP layer; ADBC drivers use native C transports — socket patching doesn't reach them |

**Deprecated/outdated:**
- `pyarrow.ipc.RecordBatchStreamWriter` for files: Use `new_file()` not `new_stream()` when writing to a file (stream format has no footer, cannot be seeked or memory-mapped)

## Open Questions

1. **Should `_cursor.py` be split into a slimmer cursor + a separate `_execute_handler.py`?**
   - What we know: `_cursor.py` currently has ~150 lines; Phase 2 will add record/replay dispatch, cassette init, replay queue management
   - What's unclear: Will the file grow past 300 lines and become hard to follow?
   - Recommendation: Yes — extract `RecordModeHandler` or similar into `_record_mode.py`. Keep `ReplayCursor` as a thin coordinator that delegates to `_record_mode.py` for all mode-specific logic. This makes unit testing easier (test mode logic without a full cursor object).

2. **How should `adbc_param_serialisers` fixture integrate with `ReplayCursor`?**
   - What we know: The fixture is session-scoped; `ReplayCursor` is created per test via `ReplaySession.wrap()`; the fixture registry needs to be available at cursor construction
   - What's unclear: Does `ReplaySession` need to receive the registry from `plugin.py`, or should `ReplayCursor` accept it directly?
   - Recommendation: Add `param_serialisers` as a parameter to `ReplaySession.wrap()` (and thus `ReplayConnection.__init__` → `ReplayCursor.__init__`). In `plugin.py`, add an `adbc_param_serialisers` fixture that defaults to `None` (meaning use built-ins). Pass `request.getfixturevalue("adbc_param_serialisers")` inside the `adbc_replay` session fixture is NOT possible (session scope can't access function-scoped fixtures). Instead, register a `_adbc_param_serialisers` session fixture that attempts to pull the user's fixture via `request.config` hook — OR accept that the user must pass `adbc_param_serialisers=...` explicitly to `.wrap()`.
   - **Simplest path:** Add an optional session-scoped `adbc_param_serialisers` fixture in `plugin.py` that returns `None` (use built-ins). The user overrides this in their `conftest.py`. Plugin reads it in the `adbc_replay` session fixture and passes to `ReplaySession`.

3. **File naming: `000_query.sql` or `000_result.sql`?**
   - CONTEXT.md and REQUIREMENTS.md specify `000_query.sql`, `000_result.arrow`, `000_params.json` — confirmed by CASS-02. Use this naming exactly.
   - The "query" vs "result" distinction in the file suffix is intentional: SQL is the query; Arrow is the result; JSON is the params.

## Sources

### Primary (HIGH confidence)

- `/tobymao/sqlglot` (Context7) — `parse_one()` API, `ParseError` exception class, `ErrorLevel`, `.sql(pretty=True)` pattern
- https://arrow.apache.org/docs/python/ipc.html (Apache Arrow v23.0.1 docs) — `new_file()`, `open_file()`, `read_all()`, `write_table()` — current documentation
- https://arrow.apache.org/docs/python/generated/pyarrow.ipc.RecordBatchFileWriter.html — constructor parameters, `write_table()`, `write_batch()`
- https://vcrpy.readthedocs.io/en/latest/usage.html — VCR.py record mode semantics (none/once/new_episodes/all) — verified against CONTEXT.md
- `/Users/paul/Documents/Dev/Personal/pytest-adbc-replay/.planning/phases/02-record-replay-engine/02-CONTEXT.md` — authoritative user decisions

### Secondary (MEDIUM confidence)

- https://pypi.org/project/sqlglot/ — confirmed latest version 28.10.1 (Feb 2026); project has >=23.0 in deps
- https://pypi.org/project/pyarrow/ — latest is 23.0.1 (Feb 2026); project has >=14.0 in deps
- https://sqlglot.com/sqlglot/errors.html — `SqlglotError` hierarchy, `ParseError`, `ErrorLevel` enum

### Tertiary (LOW confidence)

- GitHub issue apache/arrow#31539 — batch-specific metadata not fully exposed in PyArrow Python API (schema-level metadata is preserved; batch-level metadata has gaps). This is LOW confidence as it references a GitHub issue, not official docs. Impact: use schema metadata only (not batch metadata) for any custom metadata needs.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — sqlglot and pyarrow are already installed project dependencies; APIs verified via Context7 and official docs
- Architecture: HIGH — CONTEXT.md provides locked decisions for all ambiguous choices; record mode semantics verified against VCR.py docs
- Pitfalls: HIGH — derived from CONTEXT.md edge cases and basedpyright strict mode requirements already known from Phase 1

**Research date:** 2026-02-28
**Valid until:** 2026-05-28 (pyarrow and sqlglot APIs are stable; record mode semantics are product decisions locked in CONTEXT.md)

---

## RESEARCH COMPLETE

**Phase:** 02 - Record/Replay Engine
**Confidence:** HIGH

### Key Findings

- Phase 1 is fully implemented — `_cursor.py`, `_connection.py`, `_session.py`, `_exceptions.py`, `plugin.py` all exist and are wired. Phase 2 replaces placeholder `execute()` logic with real cassette I/O.
- Arrow IPC **File format** (`pa.ipc.new_file()`) is the correct choice — schema metadata is preserved, seekable, simpler than Stream format. `writer.write_table(table)` handles the full table in one call.
- sqlglot `parse_one(sql, dialect=dialect).sql(pretty=True)` normalises SQL; `except sqlglot.errors.ParseError` triggers fallback to `" ".join(sql.split())` + `NormalisationWarning`.
- Ordered-queue replay uses `collections.defaultdict(collections.deque)` — pre-populated by scanning `*_query.sql` files in cassette directory when first `execute()` is called.
- `all` mode: wipe cassette directory on first `execute()` (not at fixture init) — avoids wiping dirs for tests that never call execute.
- `once` mode: "cassette exists" = directory present AND at least one `*_query.sql` file present.
- `adbc_param_serialisers` fixture should be session-scoped in `plugin.py` (returning `None` = use built-ins); user overrides in their `conftest.py`; passed to `ReplaySession` at init.

### File Created

`.planning/phases/02-record-replay-engine/02-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | sqlglot + pyarrow already installed; APIs verified via Context7 and official docs |
| Architecture | HIGH | CONTEXT.md provides locked decisions; VCR.py semantics verified |
| Pitfalls | HIGH | Known from Phase 1 (basedpyright strict), CONTEXT.md edge cases, Arrow IPC docs |

### Open Questions

1. `adbc_param_serialisers` fixture wiring — recommend session-scoped fixture in `plugin.py`, passed to `ReplaySession` init
2. Whether `_cursor.py` should be split — recommend extracting `_record_mode.py` for testability

### Ready for Planning

Research complete. Planner can now create PLAN.md files.
