---
phase: 02-record-replay-engine
plan: 03
subsystem: core
tags: [cursor, record-replay, state-machine, param-serialisers, plugin]

requires:
  - phase: 02-01
    provides: normalise_sql, build_registry, params_to_cache_key, serialise_params
  - phase: 02-02
    provides: load_all_interactions, write_arrow_table, cassette_has_interactions, interaction_file_paths

provides:
  - ReplayCursor with full four-mode record/replay state machine (none/once/new_episodes/all)
  - Ordered-queue FIFO replay via defaultdict(deque) for duplicate queries (CASS-06)
  - Lazy _ensure_initialised() — cassette scanned only on first execute() call
  - CassetteMissError with distinct messages for missing dir, empty dir, missing interaction
  - ReplayConnection.param_serialisers threading to ReplayCursor
  - ReplaySession.param_serialisers threading to ReplayConnection.wrap()
  - adbc_param_serialisers session-scoped fixture in plugin.py (defaults to None)

affects: 02-04 (tests now exercise real cassette record/replay)

tech-stack:
  added: []
  patterns:
    - defaultdict(deque) for ordered-queue FIFO replay (same SQL = results served in order)
    - Lazy _ensure_initialised() called on first execute() — avoids cassette side effects for unused cursors
    - _ensure_initialised() wipes cassette dir for 'all' mode on first call
    - module-level json import (moved from inline) — avoids ruff PLC0415

key-files:
  created: []
  modified:
    - src/pytest_adbc_replay/_cursor.py
    - src/pytest_adbc_replay/_connection.py
    - src/pytest_adbc_replay/_session.py
    - src/pytest_adbc_replay/plugin.py
    - tests/test_cursor.py
    - tests/test_plugin.py

key-decisions:
  - "Lazy _ensure_initialised() — cassette scanned on first execute(), not at cursor creation"
  - "json imported at module level (not inline in _make_key_from_canonical) — required by ruff PLC0415"
  - "Per-call param_serialisers in wrap() overrides session-level default (per-call wins)"
  - "test_plugin.py cassette path includes module filename segment — pytester node IDs include file basename without .py"

patterns-established:
  - "param_serialisers flow: adbc_param_serialisers fixture -> ReplaySession -> ReplayConnection -> ReplayCursor -> build_registry()"
  - "CassetteMissError hierarchy: directory_missing | cassette empty (inline) | interaction_missing"

requirements-completed:
  - MODE-01
  - MODE-02
  - MODE-03
  - MODE-04
  - CASS-06
  - CASS-01

duration: 18min
completed: 2026-02-28
---

# Phase 2 Plan 03: Cursor Wiring Summary

**Full record/replay state machine wired into ReplayCursor.execute() with param_serialisers threaded through the entire connection stack**

## Performance

- **Duration:** 18 min
- **Started:** 2026-02-28T00:30:00Z
- **Completed:** 2026-02-28T00:48:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- `_cursor.py`: complete rewrite — four mode handlers, defaultdict(deque) replay queue, lazy init, CassetteMissError on miss, DBAPI2 fetch methods all preserved
- `_connection.py`: `param_serialisers` parameter added, passed through to `ReplayCursor`
- `_session.py`: `param_serialisers` added to `__init__` and `wrap()`; per-call override wins over session default
- `plugin.py`: `adbc_param_serialisers` session fixture added (returns None, overridable in conftest.py); `adbc_replay` fixture now receives and passes it to `ReplaySession`
- `tests/test_cursor.py`: updated for Phase 2 — `_populate_cassette()` helper, all `execute()` tests pre-populate cassettes
- `tests/test_plugin.py`: cassette path fixed to include module filename segment in path hierarchy

## Task Commits

1. **Tasks 1+2: Cursor rewrite + connection stack** - `b883490` (feat)

## Files Created/Modified
- `src/pytest_adbc_replay/_cursor.py` - full record/replay state machine
- `src/pytest_adbc_replay/_connection.py` - param_serialisers parameter added
- `src/pytest_adbc_replay/_session.py` - param_serialisers through __init__ and wrap()
- `src/pytest_adbc_replay/plugin.py` - adbc_param_serialisers fixture, adbc_replay updated
- `tests/test_cursor.py` - Phase 2 compatible tests with cassette pre-population
- `tests/test_plugin.py` - cassette path hierarchy fix for pytester node IDs

## Decisions Made

- `json` import moved to module level: originally `_make_key_from_canonical` had inline `import json`; ruff PLC0415 requires module-level imports.
- Lazy `_ensure_initialised()`: cassette scanned only on first `execute()` call. This ensures tests that never call `execute()` have zero side effects in any mode, and `all` mode only wipes the cassette when the test actually starts executing queries.
- Per-call `param_serialisers` wins in `wrap()`: if the caller passes `param_serialisers` to `wrap()`, it takes precedence over the session-level default. This allows fine-grained per-test overrides.
- `test_plugin.py` cassette path: the pytester subprocess's node ID for a top-level test function in `test_replay_mode_passes_without_adbc_driver.py` resolves to `tests/cassettes/test_replay_mode_passes_without_adbc_driver/test_replay_without_driver` — the module filename (without `.py`) is the first segment.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Regression] Phase 1 tests written for placeholder behavior**
- **Found during:** Running test suite after _cursor.py rewrite (11 failures)
- **Issue:** Phase 1 tests called `execute()` on cursors with no cassette; old placeholder set `_pending = pa.table({})` without checking cassette. New implementation raises `CassetteMissError`.
- **Fix:** Updated `test_cursor.py` with `_populate_cassette()` helper; all tests using `execute()` now use `tmp_path` and pre-populate cassette. Added `test_raised_on_missing_cassette` for PROXY-06 coverage. Updated `test_plugin.py` pytester test to pre-populate cassette.
- **Files modified:** tests/test_cursor.py, tests/test_plugin.py
- **Verification:** 44 tests pass ✓

**2. [Rule 2 - Regression] Cassette path mismatch in pytester test**
- **Found during:** Post-fix test run (1 remaining failure)
- **Issue:** Cassette was written to `tests/cassettes/test_replay_without_driver` but the plugin resolved it to `tests/cassettes/test_replay_mode_passes_without_adbc_driver/test_replay_without_driver` (module filename included as parent segment in `node_id_to_cassette_path`)
- **Fix:** Updated cassette path construction to include the module filename segment
- **Files modified:** tests/test_plugin.py
- **Verification:** All 44 tests pass ✓

---

**Total deviations:** 2 auto-fixed (both regressions from placeholder→real implementation transition)
**Impact on plan:** Both regressions expected and fully contained. Tests now verify real cassette I/O.

## Issues Encountered

None beyond the expected Phase 1 placeholder regression.

## Next Phase Readiness
- All four record modes fully implemented and tested
- param_serialisers flow complete: fixture → session → connection → cursor → registry
- Wave 3 (Plan 02-04: dedicated test suite) can proceed

---
*Phase: 02-record-replay-engine*
*Completed: 2026-02-28*
