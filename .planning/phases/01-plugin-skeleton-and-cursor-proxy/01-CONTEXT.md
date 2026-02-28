# Phase 1: Plugin Skeleton and Cursor Proxy - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver an installable pytest plugin auto-discovered via `pytest11` entry point. The plugin provides: `adbc_replay` fixture exposing `.wrap()`, `@pytest.mark.adbc_cassette` marker, `--adbc-record` CLI flag, and `ReplayCursor`/`ReplayConnection` implementing the full ADBC cursor protocol. Replay-only mode must work with no ADBC driver installed. Cassette storage, SQL normalisation, and record modes are Phase 2.

</domain>

<decisions>
## Implementation Decisions

### Cassette Miss Error UX

- `CassetteMissError` displays: the **raw SQL** (as written in the test) AND the **normalised SQL** (as stored in the cassette key) — helps debug normalisation-produced mismatches
- `CassetteMissError` also shows the **cassette directory path** — enough to diagnose without noise; does NOT list all recorded interactions (that would be verbose)
- **Two distinct messages**: "cassette directory does not exist — record first" vs "interaction N not found in cassette" — different failure modes get different guidance
- Raises as a **Python exception** (`CassetteMissError(Exception)`) from within `execute()` — surfaces as a test ERROR with full traceback pointing to the test line; matches pytest-recording / VCR.py convention

### Cassette Path Naming

- Node ID `tests/foo/test_bar.py::TestClass::test_method` → cassette directory `cassettes/foo/test_bar/TestClass/test_method/`
  - Strip `tests/` prefix (cassettes already live inside `tests/cassettes/`)
  - Strip `.py` extension from module name
  - Class and method become separate path segments
  - **Preserves original casing** — no lowercasing
- Special characters (brackets from parametrize, spaces) are **slugified**: replaced with `_` — safe on all filesystems, no collisions from invalid chars
- This mirrors the test directory structure inside `cassettes/` — no flat collisions across modules

### wrap() Fixture Interface

- `adbc_replay.wrap(driver_module_name: str, db_kwargs: dict = {}, **kwargs)` — accepts a **driver module name string** as first argument; plugin lazy-imports the driver
- In replay mode (`none`): **driver string is required but ignored** — same call signature always; user fixture code works unchanged between record and replay modes; no ADBC driver is imported
- `adbc_replay` is **session-scoped** but holds config only; `wrap()` creates per-test cassette state — avoids fixture scope mismatch
- `wrap()` returns the `ReplayConnection` **directly** (not a context manager) — user's fixture controls the lifecycle

### Marker and Fixture Scoping

- `@pytest.mark.adbc_cassette` on a **class applies to all methods** — standard pytest marker inheritance; each method gets its own cassette subdirectory
- When both a class and a method have the marker, **method marker wins** (most-specific-wins, standard pytest convention)
- Plugin **registers `adbc_cassette` in pytest's marker registry** during `pytest_configure` — suppresses `PytestUnknownMarkWarning`, standard practice
- `dialect=` in the marker accepts any string; if sqlglot doesn't recognise it, normalisation **falls back to whitespace-only with a warning** — lenient, doesn't break on new sqlglot dialect additions

### Claude's Discretion

- Exact `ReplayCursor.__getattr__` delegation pattern for unimplemented cursor methods in record mode
- Error message wording and formatting for `CassetteMissError`
- Internal session-to-function fixture bridging implementation

</decisions>

<specifics>
## Specific Ideas

- Behaviour should mirror `pytest-recording` (VCR.py wrapper) conventions wherever possible — same `CassetteMissError` raise-from-execute pattern, same marker inheritance model
- The design document (`_notes/pytest-adbc-replay-design.md`) has the `adbc_replay` fixture usage sketch — use that as the reference implementation shape

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-plugin-skeleton-and-cursor-proxy*
*Context gathered: 2026-02-28*
