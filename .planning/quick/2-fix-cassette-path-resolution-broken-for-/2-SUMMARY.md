---
phase: quick-02
plan: 01
subsystem: testing
tags: [pathlib, cassette-path, sanitization, adbc-pool]

# Dependency graph
requires:
  - phase: 01-foundry-pool
    provides: "Differentiator keys and _extract_differentiator_segments method"
provides:
  - "Safe differentiator segment extraction that sanitizes absolute paths"
  - "Path.stem sanitization preventing joinpath corruption"
affects: [pool-integration, cassette-path-resolution]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Path.stem for sanitizing user-supplied path segments before joinpath"]

key-files:
  created: []
  modified:
    - src/pytest_adbc_replay/_session.py
    - tests/unit/test_cassette_path.py

key-decisions:
  - "Use Path.stem for sanitization: strips directory components and single file extension, handles all edge cases with zero new dependencies"

patterns-established:
  - "Sanitize user-supplied values before Path.joinpath to prevent absolute paths replacing the base"

requirements-completed: [QUICK-02]

# Metrics
duration: 2min
completed: 2026-03-08
---

# Quick Task 2: Fix Cassette Path Resolution for Pool Connections Summary

**Path.stem sanitization of differentiator values prevents absolute .so paths from corrupting cassette directory layout via Path.joinpath**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-08T09:19:30Z
- **Completed:** 2026-03-08T09:22:03Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Sanitized differentiator segment values using `Path(value).stem` in `_extract_differentiator_segments`
- Short driver names ("mysql", "databricks") pass through unchanged
- Absolute `.so` paths (e.g. `/usr/lib/libadbc_driver_snowflake.so`) are safely reduced to stem (`libadbc_driver_snowflake`)
- Relative paths with extensions (e.g. `drivers/libfoo.so`) are safely reduced to stem (`libfoo`)
- All 233 unit tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add sanitization tests (TDD RED)** - `3eb38a7` (test)
2. **Task 2: Implement Path.stem sanitization (TDD GREEN)** - `90dbc62` (feat)

## Files Created/Modified
- `src/pytest_adbc_replay/_session.py` - Changed `_extract_differentiator_segments` return to use `Path(value).stem` instead of `str(value)`, updated docstring
- `tests/unit/test_cassette_path.py` - Added `TestDifferentiatorSegmentSanitization` class with 8 test cases

## Decisions Made
- Used `Path.stem` for sanitization: it strips directory components and the final file extension in a single call, handles all edge cases (short names unchanged, absolute paths stripped, extensions removed), and requires zero new dependencies since `Path` is already imported

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Steps
- Pool-based integration tests in adbc-poolhouse should now be able to replay cassettes correctly
- Consider re-recording existing cassettes if pool routing changes the driver module name segment

## Self-Check: PASSED

- FOUND: src/pytest_adbc_replay/_session.py
- FOUND: tests/unit/test_cassette_path.py
- FOUND: 2-SUMMARY.md
- FOUND: commit 3eb38a7
- FOUND: commit 90dbc62

---
*Quick Task: 02-fix-cassette-path-resolution*
*Completed: 2026-03-08*
