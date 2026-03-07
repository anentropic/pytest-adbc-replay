---
phase: 01-test-compatibility-with-adbc-foundry-drivers
plan: 03
subsystem: testing
tags: [adbc, foundry, mysql, testcontainers, integration-tests, ci, docker, dbc]

# Dependency graph
requires:
  - phase: 01-01
    provides: cassette_differentiator_keys for Foundry driver path disambiguation
  - phase: 01-02
    provides: tests/integration/ directory structure
provides:
  - Foundry MySQL integration tests with testcontainers (record-then-replay cycle)
  - CI workflow with dbc CLI install and Docker-based integration test job
  - Proof that auto-patch intercepts adbc_driver_manager.dbapi.connect() for Foundry drivers
  - Proof that cassette paths include driver='mysql' differentiator segment
affects: [ci, documentation]

# Tech tracking
tech-stack:
  added: [testcontainers, testcontainers-mysql, pymysql]
  patterns: [pytester subprocess integration tests, testcontainers for ephemeral databases, session-scoped container fixtures]

key-files:
  created:
    - tests/integration/test_foundry_mysql.py
    - tests/integration/conftest.py
  modified:
    - .github/workflows/_test.yml
    - pyproject.toml
    - uv.lock

key-decisions:
  - "Used pytester with f-string DSN injection for subprocess test isolation"
  - "testcontainers manages Docker lifecycle (no CI services block needed)"
  - "dbc CLI installed via curl from columnar.tech with continue-on-error for CI resilience"
  - "ADBC driver path resolved and passed to pytester subprocesses via env var"

patterns-established:
  - "Integration tests use pytester for subprocess isolation with real database containers"
  - "Session-scoped testcontainers fixtures for container reuse across tests"
  - "MySqlContainer init wrapped in try/except for Docker daemon unavailability"

requirements-completed: []

# Metrics
duration: ~20min (across two sessions with checkpoint)
completed: 2026-03-07
---

# Phase 01 Plan 03: Foundry MySQL Integration Tests Summary

**Foundry MySQL integration tests with testcontainers proving record-then-replay cycle, auto-patch interception, and cassette path differentiation via adbc_driver_manager.dbapi**

## Performance

- **Duration:** ~20 min (across two sessions with human-verify checkpoint)
- **Started:** 2026-03-07T14:27:31Z
- **Completed:** 2026-03-07T14:48:08Z
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint)
- **Files modified:** 5

## Accomplishments

- 3 integration tests proving end-to-end Foundry driver compatibility: record-then-replay via wrap(), auto-patch interception, and cassette path differentiation
- testcontainers MySQL fixture with Docker availability skip logic and daemon error handling
- CI workflow updated with dbc CLI install step and separate integration test job
- All 217 unit tests + 3 integration tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Foundry MySQL integration tests and fixtures** - `129245d` (feat)
2. **Task 2: Update CI workflow for dbc CLI and Docker-based integration tests** - `7d89765` (chore)
3. **Task 3: Verify integration test setup and CI workflow** - checkpoint approved, no commit needed

Post-checkpoint fix commits:
- `02b6188` - fix(01-03): wrap MySqlContainer init in try/except for Docker daemon errors
- `1f4a8dd` - fix(01-03): resolve ADBC driver path for pytester subprocesses

## Files Created/Modified

- `tests/integration/conftest.py` - testcontainers MySQL fixture (session-scoped), dbc CLI availability check, Docker skip logic
- `tests/integration/test_foundry_mysql.py` - 3 pytester-based integration tests: wrap record-replay, auto-patch record-replay, cassette path differentiation
- `.github/workflows/_test.yml` - Added integration test job with dbc CLI install, Docker, and continue-on-error
- `pyproject.toml` - Added testcontainers[mysql] and pymysql dev dependencies
- `uv.lock` - Lockfile updated with new dependencies

## Decisions Made

- **pytester with f-string DSN injection:** The MySQL DSN from testcontainers is injected directly into pytester test code via f-string, providing full subprocess isolation while accessing the real database.
- **testcontainers manages Docker lifecycle:** No need for CI `services:` block -- testcontainers starts/stops containers automatically. This simplifies CI config and works the same locally and in CI.
- **dbc CLI install with continue-on-error:** The dbc CLI install step uses `continue-on-error: true` since the binary availability may vary. Integration tests skip gracefully via pytest markers when dbc is unavailable.
- **ADBC driver path forwarded to pytester:** The Foundry driver binary path is resolved in the parent process and passed to pytester subprocesses via environment variable, ensuring the subprocess can find the driver.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] MySqlContainer init fails without Docker daemon**
- **Found during:** Task 3 (human-verify checkpoint testing)
- **Issue:** `MySqlContainer()` constructor raised an unhandled error when Docker daemon was not running, causing test collection failure instead of a clean skip
- **Fix:** Wrapped MySqlContainer initialization in try/except, yielding skip if Docker daemon is unavailable
- **Files modified:** `tests/integration/conftest.py`
- **Verification:** Tests skip cleanly when Docker is unavailable
- **Committed in:** `02b6188`

**2. [Rule 3 - Blocking] pytester subprocess cannot find ADBC Foundry driver binary**
- **Found during:** Task 3 (human-verify checkpoint testing)
- **Issue:** pytester runs tests in a subprocess with a clean environment. The Foundry driver binary path wasn't propagated, causing `adbc_driver_manager.dbapi.connect(driver="mysql")` to fail in the subprocess.
- **Fix:** Resolved driver path in the parent process and set it as an environment variable accessible to the pytester subprocess
- **Files modified:** `tests/integration/test_foundry_mysql.py`
- **Verification:** All 3 integration tests pass in pytester subprocesses
- **Committed in:** `1f4a8dd`

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes were necessary for integration tests to work correctly in the pytester subprocess model. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

**External services require manual configuration** for local integration test runs:
- Install `dbc` CLI from https://columnar.tech
- Run `dbc install mysql` to install the MySQL Foundry driver
- Docker must be running for testcontainers to start MySQL container
- Without these prerequisites, integration tests skip gracefully

## Next Phase Readiness

- Phase 1 complete: all 3 plans executed successfully
- Foundry driver compatibility proven end-to-end with MySQL via testcontainers
- CI workflow ready for integration tests (dbc CLI + Docker)
- Pattern established for adding more Foundry driver integration tests (PostgreSQL, etc.)

## Self-Check: PASSED

All 5 modified files verified on disk. All 4 commits (129245d, 7d89765, 02b6188, 1f4a8dd) verified in git log.

---
*Phase: 01-test-compatibility-with-adbc-foundry-drivers*
*Completed: 2026-03-07*
