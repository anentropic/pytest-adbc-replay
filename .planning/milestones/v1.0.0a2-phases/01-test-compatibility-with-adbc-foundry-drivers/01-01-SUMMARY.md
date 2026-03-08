---
phase: 01-test-compatibility-with-adbc-foundry-drivers
plan: 01
subsystem: testing
tags: [adbc, foundry, cassette-path, differentiator, ini-config]

# Dependency graph
requires:
  - phase: v1.0.0a1 (Phase 8 - Automatic ADBC Wrapping)
    provides: auto-patch, wrap_from_item, per-driver cassette subdirs
provides:
  - cassette_differentiator_keys ini key for Foundry driver disambiguation
  - differentiator_segments parameter on node_id_to_cassette_path
  - differentiator_keys_default on ReplaySession (default ("driver",))
  - cassette_differentiator_keys kwarg on wrap()
  - _parse_differentiator_keys helper
  - _extract_differentiator_segments method on ReplaySession
affects: [01-02, 01-03, documentation]

# Tech tracking
tech-stack:
  added: []
  patterns: [differentiator-key extraction from db_kwargs, transparent default for PyPI drivers]

key-files:
  created: []
  modified:
    - src/pytest_adbc_replay/_cassette_path.py
    - src/pytest_adbc_replay/_session.py
    - src/pytest_adbc_replay/plugin.py
    - tests/test_cassette_path.py
    - tests/test_plugin.py
    - tests/test_auto_patch.py

key-decisions:
  - "Default differentiator_keys is ('driver',) -- transparent for PyPI drivers (no 'driver' in their db_kwargs), auto-works for Foundry drivers"
  - "differentiator_segments appended after driver_module_name in cassette path for clean nesting"
  - "ini key uses linelist type with space-separated keys, consistent with existing config patterns"

patterns-established:
  - "Differentiator key extraction: tuple of db_kwargs keys -> tuple of str values -> path segments"
  - "Transparent defaults: new features default to values that are no-ops for existing users"

requirements-completed: []

# Metrics
duration: 6min
completed: 2026-03-07
---

# Phase 01 Plan 01: Cassette Differentiator Keys Summary

**cassette_differentiator_keys ini key and path threading for Foundry driver disambiguation via db_kwargs value extraction**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-07T14:14:58Z
- **Completed:** 2026-03-07T14:21:22Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `node_id_to_cassette_path()` accepts `differentiator_segments` and appends them after driver_module_name
- `ReplaySession` stores `differentiator_keys_default` (default: `("driver",)`) and extracts segments from db_kwargs
- `wrap()` supports `cassette_differentiator_keys` per-call kwarg override
- `wrap_from_item()` automatically extracts differentiator segments from db_kwargs
- `adbc_cassette_differentiator_keys` ini key registered, parsed, and threaded through both `_build_session_from_config` and `adbc_replay` fixture
- All 217 tests pass (29 new tests added), basedpyright and ruff clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Add cassette_differentiator_keys to cassette path and session** - `e0d3e07` (feat)
2. **Task 2: Verify full test suite passes** - no commit needed (verification only, all 217 tests pass)

## Files Created/Modified

- `src/pytest_adbc_replay/_cassette_path.py` - Added `differentiator_segments` parameter to `node_id_to_cassette_path()`
- `src/pytest_adbc_replay/_session.py` - Added `differentiator_keys_default`, `_extract_differentiator_segments()`, updated `wrap()` and `wrap_from_item()`
- `src/pytest_adbc_replay/plugin.py` - Registered `adbc_cassette_differentiator_keys` ini key, added `_parse_differentiator_keys()` helper, updated `_build_session_from_config()` and `adbc_replay` fixture
- `tests/test_cassette_path.py` - 5 new unit tests for differentiator_segments path computation
- `tests/test_plugin.py` - 10 new tests: 6 unit tests for `_parse_differentiator_keys`, 4 pytester integration tests for ini key
- `tests/test_auto_patch.py` - 3 new pytester integration tests for differentiator path segments and PyPI driver transparency

## Decisions Made

- Default `differentiator_keys_default` is `("driver",)` so Foundry drivers work out of the box without configuration. PyPI drivers are unaffected because their db_kwargs don't contain a `driver` key.
- Differentiator segments are appended after `driver_module_name` in the cassette path, producing clean nesting: `.../adbc_driver_manager.dbapi/mysql/`
- The ini key uses `linelist` type with space-separated key names, following the established pattern of other ini keys.
- The `_extract_differentiator_segments` helper was added as a method on `ReplaySession` (not a standalone function) since it needs access to `differentiator_keys_default`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test approach for auto-patch differentiator**
- **Found during:** Task 1 (pytester integration tests)
- **Issue:** Plan suggested passing `driver='mysql'` to `adbc_driver_sqlite.dbapi.connect()` via auto-patch, but SQLite's `connect()` rejects unknown kwargs (`TypeError: Connection.__init__() got an unexpected keyword argument 'driver'`)
- **Fix:** Changed test to use `adbc_connect` fixture (which calls `wrap_from_item` and sets `_cassette_path` without calling the real driver), verifying the cassette path structure directly. Added a separate record-then-replay test without the problematic kwarg for the auto-patch path.
- **Files modified:** `tests/test_auto_patch.py`
- **Verification:** All 3 new auto-patch differentiator tests pass
- **Committed in:** e0d3e07

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Adjusted test strategy to avoid SQLite driver kwarg incompatibility. No scope creep. All plan objectives met.

## Issues Encountered

- Pre-commit hooks prevented separate TDD RED commit (basedpyright rejects calls to non-existent parameter). Combined RED and GREEN into a single commit, which is appropriate since the pre-commit type checker enforces internal consistency.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Differentiator keys feature complete and tested
- Ready for Plan 02 (test directory reorganization) and Plan 03 (Foundry MySQL integration tests)
- The `cassette_differentiator_keys` feature provides the foundation for Foundry driver cassette path disambiguation

## Self-Check: PASSED

All 6 modified files exist. Commit e0d3e07 verified in git log.

---
*Phase: 01-test-compatibility-with-adbc-foundry-drivers*
*Completed: 2026-03-07*
