---
phase: 02-pool-clone-support-for-replayconnection
plan: 01
subsystem: testing
tags: [adbc, connection-pool, clone, pyarrow, tdd]

# Dependency graph
requires:
  - phase: 01-test-compatibility-with-adbc-foundry-drivers
    provides: "ReplayConnection and ReplayCursor proxy classes"
provides:
  - "adbc_clone() method on ReplayConnection for pool-based usage"
  - "Shared _wipe_state container for cross-clone wipe coordination"
  - "Clone-of-clone support (arbitrary depth)"
affects: [pool-integration, adbc-poolhouse-compat]

# Tech tracking
tech-stack:
  added: []
  patterns: ["__new__ bypass for clone construction", "shared mutable dict for cross-instance state"]

key-files:
  created:
    - tests/unit/test_clone.py
  modified:
    - src/pytest_adbc_replay/_connection.py
    - src/pytest_adbc_replay/_cursor.py

key-decisions:
  - "Used __new__ bypass to create clones without triggering __init__ driver import"
  - "Shared _wipe_state dict referenced by all clones prevents double-wipe in 'all' mode"
  - "wipe_state parameter defaults to None in ReplayCursor for backward compatibility"

patterns-established:
  - "CLONE-SYNC comment marker in __init__ to remind updating adbc_clone() when attributes change"

requirements-completed: [CLONE-01, CLONE-02, CLONE-03, CLONE-04, CLONE-05, CLONE-06, CLONE-07, CLONE-08, CLONE-09]

# Metrics
duration: 3min
completed: 2026-03-07
---

# Phase 2 Plan 1: Shared Wipe State and adbc_clone() Summary

**adbc_clone() on ReplayConnection with shared _wipe_state dict for pool-based cassette replay**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-07T20:41:39Z
- **Completed:** 2026-03-07T20:45:13Z
- **Tasks:** 2 (TDD RED+GREEN cycle)
- **Files modified:** 3

## Accomplishments
- Implemented `adbc_clone()` method on `ReplayConnection` enabling connection pool consumers to create cloned connections sharing cassette config
- Refactored per-cursor `_wiped` flag into shared `_wipe_state` dict threaded from connection to cursor, preventing double-wipe across clones in 'all' mode
- 8 new unit tests covering CLONE-01 through CLONE-08; all 225 tests pass (217 existing + 8 new)

## Task Commits

Each task was committed atomically:

1. **Task 1+2: Implement shared wipe state and adbc_clone()** - `9689053` (feat)
2. **Task 1+2: Add unit tests for clone behavior** - `b11b86d` (test)

_Note: Pre-commit type-checker requires implementation to exist before tests can commit, so implementation was committed first with tests second._

## Files Created/Modified
- `src/pytest_adbc_replay/_connection.py` - Added `_wipe_state` dict init, `adbc_clone()` method, `wipe_state` threading through `cursor()`
- `src/pytest_adbc_replay/_cursor.py` - Added `wipe_state` parameter, replaced `_wiped` flag with `_wipe_state` container
- `tests/unit/test_clone.py` - 8 tests: clone returns, shares cassette, replay mode, record delegation, independent queues, shared wipe state, clone-of-clone, close isolation

## Decisions Made
- Used `__new__` bypass to create clones without triggering `__init__` (which imports driver modules and opens real connections)
- Shared `_wipe_state` dict (mutable container) referenced by all clones ensures only the first cursor to `execute()` in 'all' mode triggers `rmtree`
- `wipe_state` parameter in `ReplayCursor.__init__` defaults to `None` (creates standalone dict) for backward compatibility with 217 existing tests

## Deviations from Plan

### Commit Order Adjustment

Pre-commit hooks include basedpyright type-checking which stashes unstaged changes before running. This means tests referencing `adbc_clone()` and `_wipe_state` cannot be committed before the implementation exists (type-checker fails). The TDD RED commit was merged with GREEN, with implementation committed first and tests second. Both tasks' work is fully represented in the two commits.

---

**Total deviations:** 1 (commit ordering due to type-checker constraints)
**Impact on plan:** No functional impact. All code is identical to plan spec.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `adbc_clone()` is ready for pool-based consumers (e.g., adbc-poolhouse)
- All 225 unit tests pass including backward compatibility
- No new dependencies added

## Self-Check: PASSED

- All 3 source/test files exist
- Both commit hashes verified (9689053, b11b86d)
- `adbc_clone()` method present in _connection.py
- `_wipe_state` present in _cursor.py
- Old `_wiped` flag fully removed from _cursor.py

---
*Phase: 02-pool-clone-support-for-replayconnection*
*Completed: 2026-03-07*
