---
phase: 02-record-replay-engine
plan: 04
subsystem: testing
tags: [tests, normaliser, cassette-io, record-modes, ordered-queue]

requires:
  - phase: 02-01
    provides: normalise_sql, NormalisationWarning
  - phase: 02-02
    provides: all cassette I/O functions
  - phase: 02-03
    provides: ReplayCursor with full record/replay state machine

provides:
  - test_normaliser.py: 16 tests for NORM-01 through NORM-04
  - test_cassette_io.py: 20 tests for CASS-02 through CASS-05
  - test_record_modes.py: 21 tests for MODE-01 through MODE-04 and CASS-06
  - 5 Phase 2 roadmap success criteria all covered by test assertions
  - Total test suite: 110 tests (66 added across Phase 2)

affects: phase 03 (comprehensive regression baseline established)

tech-stack:
  added: []
  patterns:
    - unittest.mock.MagicMock for real ADBC cursor simulation in record mode tests
    - _populate_cassette() helper for pre-populating cassette directories in tests
    - _make_mock_cursor() helper for creating mock cursors with configurable return values
    - noqa: TC003 for Path in test files (used at runtime in tmp_path parameters)

key-files:
  created:
    - tests/test_normaliser.py
    - tests/test_cassette_io.py
    - tests/test_record_modes.py
  modified: []

key-decisions:
  - "Used noqa: TC003 for Path import in test files — Path used at runtime in function signatures via tmp_path"
  - "Added _make_mock_cursor() helper — avoids repeating MagicMock setup in every test"
  - "Replaced %s placeholder test with named :param test — sqlglot may transform %s"
  - "F841 unused variable suppressed by using _c prefix for intentionally unused cursor"

patterns-established:
  - "Mock cursor pattern: MagicMock() with fetch_arrow_table.return_value = table"
  - "Cassette pre-population: write normalised SQL, then arrow table, then params JSON"
  - "All record-mode tests use fresh tmp_path directories — no shared state between tests"

requirements-completed:
  - CASS-01
  - CASS-02
  - CASS-03
  - CASS-04
  - CASS-05
  - CASS-06
  - NORM-01
  - NORM-02
  - NORM-03
  - NORM-04
  - MODE-01
  - MODE-02
  - MODE-03
  - MODE-04

duration: 10min
completed: 2026-02-28
---

# Phase 2 Plan 04: Phase 2 Test Suite Summary

**57 new tests covering SQL normalisation, cassette file I/O, and all four record modes — all green. Phase 2 complete.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-28T00:48:00Z
- **Completed:** 2026-02-28T00:58:00Z
- **Tasks:** 2
- **Files modified:** 3 (created)

## Accomplishments
- `test_normaliser.py`: 16 tests — keyword/identifier normalisation, fallback via mock.patch on sqlglot.parse_one, dialect parameter, placeholder preservation
- `test_cassette_io.py`: 20 tests — file naming scheme (prefix generation, path structure), Arrow IPC round-trip with schema metadata, SQL file read/write, JSON params round-trip, count_interactions and load_all_interactions including ordering
- `test_record_modes.py`: 21 tests — none/once/new_episodes/all modes with MagicMock cursors, ordered-queue FIFO replay for duplicate queries (CASS-06), mixed replay+record in new_episodes mode
- All Phase 2 roadmap success criteria demonstrably covered by test assertions
- Phase 2 ROADMAP.md updated to mark both Phase 1 and Phase 2 complete

## Task Commits

1. **Tasks 1+2: All three test files** - `a2ae24d` (feat)

## Files Created/Modified
- `tests/test_normaliser.py` - normalise_sql unit tests (16 tests)
- `tests/test_cassette_io.py` - cassette file I/O unit tests (20 tests)
- `tests/test_record_modes.py` - record mode integration tests (21 tests)
- `.planning/ROADMAP.md` - Phase 1 and Phase 2 marked complete

## Decisions Made

- `%s` placeholder test replaced with named `:param` test: sqlglot may transform `%s` depending on dialect. `:id` named parameter is more reliably preserved.
- `_c` prefix for intentionally unused cursor in `test_no_execute_no_side_effects` variants: avoids F841 ruff error for variables that exist only to trigger object creation side effects.
- `noqa: TC003` on `from pathlib import Path`: consistent with pattern established in source files — Path is used at runtime in test function signatures.
- `_populate_cassette()` helper accepts `list[tuple[str, list[int]]]` — simpler than the equivalent in test_cursor.py which takes arbitrary `pa.Table`. Keeps record-mode tests focused.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Lint] ruff TC003, D403, F401, F841 in new test files**
- **Found during:** First ruff check after creating files
- **Issue:** TC003 flagged Path import; D403 flagged lowercase first words in docstrings ("once mode", "all mode"); F401 flagged unused pytest import; F841 flagged unused cursor variable
- **Fix:** Added `# noqa: TC003` to Path imports; ruff `--fix` auto-fixed D403 and F401; renamed unused variable to `_c`
- **Files modified:** tests/test_cassette_io.py, tests/test_record_modes.py
- **Verification:** `ruff check`: 0 errors ✓

---

**Total deviations:** 1 auto-fixed (lint only, no logic changes)
**Impact on plan:** None. All tests ran green on first execution after lint fixes.

## Phase 2 Success Criteria Coverage

| Criterion | Covered By |
|-----------|------------|
| SC1: once mode produces cassette files | `TestModeOnce::test_records_when_no_cassette` |
| SC2: none mode passes without database | `TestModeNone::test_replay_success`, `test_never_calls_real_cursor` |
| SC3: SQL normalisation handles casing | `TestModeNone::test_normalisation_allows_casing_difference` |
| SC4: Duplicate queries ordered-queue | `TestOrderedQueueReplay::test_same_sql_twice_returns_in_order` |
| SC5: All four modes correct | `TestModeNone`, `TestModeOnce`, `TestModeNewEpisodes`, `TestModeAll` |

## Issues Encountered

None — all 57 new tests passed green on first run after lint fixes.

## Next Phase Readiness
- Phase 2 is **complete**: all 14 requirements delivered and tested
- ROADMAP.md updated: Phase 2 marked complete
- Phase 3 (Configuration, DX, Integration Testing) is the next phase

---
*Phase: 02-record-replay-engine*
*Completed: 2026-02-28*
