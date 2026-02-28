---
phase: 03-configuration-dx-and-integration-testing
plan: 02
subsystem: testing
tags: [pytest, pytester, integration-test, adbc-driver-sqlite, ini-config]

# Dependency graph
requires:
  - phase: 03-01
    provides: ini config wiring, pytest_report_header, adbc_scrubber fixture, ReplaySession.scrubber/dialect

provides:
  - TestIniConfig (5 tests): cassette_dir, record_mode, CLI override, dialect, empty-dialect=None
  - TestReportHeader (3 tests): default header, ini mode header, CLI mode header
  - TestScrubberFixture (2 tests): None by default, stored when conftest overrides
  - TestRecordThenReplayCycle (1 E2E test): full record-then-replay with adbc-driver-sqlite

affects: []  # final phase

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pytester.makeini pattern: '[pytest]\nkey = value\n' for testing ini config reads"
    - "pytester.makeconftest pattern: overriding session fixtures to test override behaviour"
    - "E2E pattern: two sequential pytester.runpytest calls (record then replay)"

key-files:
  created:
    - tests/test_integration.py
  modified:
    - tests/test_plugin.py

key-decisions:
  - "E2E test uses adbc_driver_sqlite.dbapi (not adbc_driver_sqlite) as driver_module_name"
  - "Two separate runpytest calls (not one) for record-then-replay: ensures cassette persists between runs"

patterns-established:
  - "pytester E2E pattern: makepyfile -> runpytest(--adbc-record=once) -> assert cassette exists -> runpytest() -> assert passed"

requirements-completed:
  - CONF-01
  - CONF-02
  - CONF-03
  - DX-01
  - DX-02

# Metrics
duration: 2min
completed: 2026-02-28
---

# Phase 3 Plan 02: TestIniConfig, TestReportHeader, TestScrubberFixture, E2E integration test

**11 new tests validating all Phase 3 features: 10 pytester unit tests for ini config/header/scrubber and 1 E2E record-then-replay test against adbc-driver-sqlite**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-28T22:45:41Z
- **Completed:** 2026-02-28T22:47:58Z
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- `TestIniConfig` (5 tests): verifies all three ini keys (`adbc_cassette_dir`, `adbc_record_mode`, `adbc_dialect`) are read correctly from pytest.ini, and that CLI `--adbc-record` overrides the ini mode, and that empty `adbc_dialect` produces `dialect=None`
- `TestReportHeader` (3 tests): confirms "adbc-replay: record mode = {mode}" appears in pytest stdout for default, ini-configured, and CLI-supplied modes
- `TestScrubberFixture` (2 tests): confirms `adbc_replay.scrubber` is None by default and stored (not None, callable) when conftest overrides the fixture
- `TestRecordThenReplayCycle` (1 E2E test): runs two real pytest subprocess invocations — first records via a live in-memory SQLite connection, second replays without any DB connection — proving the full lifecycle works end-to-end
- Full test suite: 121 tests pass, 0 failures

## Task Commits

1. **Task 1: TestIniConfig + TestReportHeader + TestScrubberFixture** - `2b40eb7` (test)
2. **Task 2: TestRecordThenReplayCycle E2E test** - `87a6624` (test)

## Files Created/Modified

- `tests/test_integration.py` (created) - E2E record-then-replay integration test with adbc-driver-sqlite
- `tests/test_plugin.py` (modified) - Appended TestIniConfig, TestReportHeader, TestScrubberFixture classes

## Decisions Made

- `driver_module_name="adbc_driver_sqlite.dbapi"` is the correct module path for the SQLite ADBC driver's dbapi interface
- The E2E test uses two sequential `runpytest` calls to ensure cassette files truly persist to disk between independent pytest sessions

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 3 complete. All requirements satisfied:
1. CONF-01/02/03: adbc_cassette_dir, adbc_record_mode, adbc_dialect all read from pytest.ini/pyproject.toml
2. DX-01: "adbc-replay: record mode = {mode}" in pytest header output
3. DX-02: adbc_scrubber fixture exists and is overrideable; ReplaySession stores it
4. E2E: record-then-replay with adbc-driver-sqlite passes end-to-end
5. All 121 tests pass with 0 failures

---
*Phase: 03-configuration-dx-and-integration-testing*
*Completed: 2026-02-28*
