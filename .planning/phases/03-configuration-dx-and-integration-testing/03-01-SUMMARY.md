---
phase: 03-configuration-dx-and-integration-testing
plan: 01
subsystem: plugin
tags: [pytest, ini-config, fixtures, adbc-driver-sqlite]

# Dependency graph
requires:
  - phase: 02-record-replay-engine
    provides: ReplaySession with mode/cassette_dir/param_serialisers; wrap() method

provides:
  - pytest ini config keys: adbc_cassette_dir, adbc_record_mode, adbc_dialect
  - pytest_report_header hook showing active record mode
  - adbc_scrubber session fixture (interface reservation for v1.x)
  - ReplaySession.scrubber attribute (stored, not called)
  - ReplaySession.dialect attribute (session-global dialect fallback)
  - adbc-driver-sqlite dev dependency for integration tests

affects:
  - 03-02 (test phase — relies on all features added here)

# Tech tracking
tech-stack:
  added: [adbc-driver-sqlite>=1.0.0]
  patterns:
    - "ini config pattern: parser.addini() in pytest_addoption, cast(str, config.getini()) in fixtures"
    - "fixture override slot pattern: adbc_scrubber returns None; users override in conftest.py"
    - "CLI sentinel pattern: --adbc-record default=None signals 'not supplied'; ini fallback used"

key-files:
  created: []
  modified:
    - src/pytest_adbc_replay/plugin.py
    - src/pytest_adbc_replay/_session.py
    - pyproject.toml
    - uv.lock

key-decisions:
  - "Tasks 1 and 2 committed atomically (pre-commit basedpyright checks full codebase; plugin.py passing scrubber/dialect needed _session.py changes to be staged together)"
  - "cli_mode=None sentinel detects whether --adbc-record was explicitly supplied vs defaulting"
  - "cast('str | None', config.getoption()) handles basedpyright strict object return type"
  - "dialect priority chain: marker > explicit wrap(dialect=...) > session self.dialect > None"

patterns-established:
  - "cast('str', config.getini('key')) pattern for basedpyright strict mode compliance"
  - "Fixture override slots: session fixture returns None; user overrides in conftest.py"

requirements-completed:
  - CONF-01
  - CONF-02
  - CONF-03
  - DX-01
  - DX-02

# Metrics
duration: 3min
completed: 2026-02-28
---

# Phase 3 Plan 01: ini config wiring, report header, scrubber fixture, ReplaySession params

**pytest.ini/pyproject.toml configuration wired into plugin with three ini keys, report header hook, adbc_scrubber fixture slot, and ReplaySession scrubber/dialect params with adbc-driver-sqlite added as dev dependency**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-28T22:41:25Z
- **Completed:** 2026-02-28T22:44:12Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Register three ini keys via `parser.addini()`: `adbc_cassette_dir` (default: tests/cassettes), `adbc_record_mode` (default: none), `adbc_dialect` (default: "")
- `pytest_report_header` hook prints "adbc-replay: record mode = {mode}" — CLI wins over ini, ini wins over hardcoded default
- `adbc_scrubber` session fixture returns None by default; users override in conftest to register a scrubbing callback (interface reservation for v1.x)
- `ReplaySession.__init__` gains `scrubber` and `dialect` params; `wrap()` uses `self.dialect` as fallback (priority: marker > explicit arg > session global > None)
- Added `adbc-driver-sqlite>=1.0.0` to dev dependencies; installed via `uv sync --dev`
- All 110 existing tests pass with no regressions

## Task Commits

Tasks committed together (pre-commit basedpyright validates full codebase):

1. **Tasks 1 + 2: Plugin ini wiring + _session.py params + pyproject.toml** - `070acb2` (feat)

## Files Created/Modified

- `src/pytest_adbc_replay/plugin.py` - Added `cast` import, three `addini()` calls, `pytest_report_header` hook, `adbc_scrubber` fixture, updated `adbc_replay` fixture to read ini config
- `src/pytest_adbc_replay/_session.py` - Added `scrubber` and `dialect` params to `__init__`; updated `wrap()` dialect priority chain
- `pyproject.toml` - Added `adbc-driver-sqlite>=1.0.0` to `[dependency-groups] dev`
- `uv.lock` - Updated lockfile with adbc-driver-sqlite 1.10.0

## Decisions Made

- **Atomic commit for both tasks**: The pre-commit hook runs basedpyright across the full codebase. plugin.py passes `scrubber=` and `dialect=` to `ReplaySession()`, which would fail type-checking until _session.py was updated. Both tasks had to be staged together.
- **cast() pattern for getini/getoption**: basedpyright strict mode types both as `object`. Using `cast("str | None", ...)` and `cast("str", ...)` satisfies the type checker without runtime overhead.
- **None sentinel for --adbc-record default**: Changed from `default="none"` to `default=None` so the fixture can distinguish "flag not provided" from "flag explicitly set to none". argparse only validates choices when the flag is actually supplied.

## Deviations from Plan

None — plan executed exactly as written, except that Tasks 1 and 2 were committed atomically rather than separately (pre-commit hook required both changes to be staged together to pass basedpyright).

## Issues Encountered

- **Broken venv shebangs**: The existing `.venv` had incorrect shebangs pointing to a non-existent path. Fixed by running `uv venv --clear && uv sync --dev`. This was a pre-existing environment issue unrelated to our changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All Phase 3 production code complete
- Plan 03-02 can now write tests against the new ini config, report header, and scrubber features
- `adbc-driver-sqlite` is installed and importable for the E2E integration test

---
*Phase: 03-configuration-dx-and-integration-testing*
*Completed: 2026-02-28*
