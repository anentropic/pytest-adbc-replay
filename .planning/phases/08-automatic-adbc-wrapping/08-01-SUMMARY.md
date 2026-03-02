---
phase: 08-automatic-adbc-wrapping
plan: 01
subsystem: testing
tags: [pytest, adbc, monkeypatch, fixtures, cassette, threading]

# Dependency graph
requires: []
provides:
  - node_id_to_cassette_path extended with optional driver_module_name kwarg for per-driver subdirectory
  - ReplaySession.wrap_from_item() accepting pytest.Item instead of FixtureRequest
  - adbc_auto_patch ini key registered and parsed at session start
  - pytest_sessionstart monkeypatches configured driver connect() functions
  - pytest_runtest_setup/teardown track current item and close connections
  - adbc_connect function-scoped factory fixture (escape hatch)
  - connect_fn parameter on ReplayConnection to prevent recursion when monkeypatched
affects: [08-02, 08-03, future-phases-using-auto-patch]

# Tech tracking
tech-stack:
  added: [threading.Lock for thread-safe item tracking]
  patterns: [monkeypatch-at-sessionstart, eager-session-init-for-hooks, connect_fn-recursion-guard, mutable-dict-for-module-state]

key-files:
  created: []
  modified:
    - src/pytest_adbc_replay/_cassette_path.py
    - src/pytest_adbc_replay/_session.py
    - src/pytest_adbc_replay/_connection.py
    - src/pytest_adbc_replay/plugin.py
    - tests/test_cassette_path.py

key-decisions:
  - "Used _auto_patch_state dict instead of uppercase module globals to avoid basedpyright reportConstantRedefinition errors"
  - "Eager ReplaySession initialization in pytest_sessionstart (from config) so auto-patch works even without any test requesting adbc_replay fixture"
  - "Added connect_fn parameter to ReplayConnection to prevent infinite recursion when auto-patch has replaced driver.connect"
  - "Stored original connect callables in _ORIGINAL_CONNECTS keyed by driver name for pass-through and recursion guard"
  - "Used threading.Lock around _auto_patch_state['current_item'] access for thread safety"
  - "Per-driver cassette subdir always applied in wrap_from_item — no opt-out needed"

patterns-established:
  - "monkeypatch-at-sessionstart: patching third-party module attributes in pytest_sessionstart for global interception"
  - "connect_fn-recursion-guard: pass original (un-patched) callable as connect_fn to ReplayConnection to prevent recursive patching"
  - "eager-session-init: build ReplaySession from config in pytest_sessionstart, overwrite with fixture instance later"
  - "mutable-dict-for-module-state: use dict container for module-level variables that need reassignment to avoid type checker constant complaints"

requirements-completed: [AUTO-01, AUTO-02, AUTO-03, AUTO-04, AUTO-05]

# Metrics
duration: 45min
completed: 2026-03-02
---

# Phase 8, Plan 01: Automatic ADBC Wrapping — Core Implementation Summary

**pytest_sessionstart monkeypatching of ADBC driver connect() with per-driver cassette subdirectories, wrap_from_item() on ReplaySession, and adbc_connect escape-hatch fixture**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-03-02
- **Completed:** 2026-03-02
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Extended `node_id_to_cassette_path` to accept an optional `driver_module_name` keyword argument, appended verbatim as the final cassette path segment
- Added `ReplaySession.wrap_from_item()` method that resolves cassette path from a `pytest.Item` (no FixtureRequest needed), applying per-driver subdirectory always
- Added full auto-patch mechanism to `plugin.py`: `adbc_auto_patch` ini key, eager session init, `pytest_sessionstart` hook monkeypatching drivers, `pytest_runtest_setup/teardown` tracking current item, and `adbc_connect` factory fixture

## Task Commits

1. **Task 1-3: Core auto-patch implementation** - `30276b1` (feat)
2. **Fix: connect_fn recursion guard + session eager init** - `af6235f` (fix, combined with 08-02)

## Files Created/Modified

- `src/pytest_adbc_replay/_cassette_path.py` - Added `driver_module_name: str | None = None` kwarg to `node_id_to_cassette_path()`
- `src/pytest_adbc_replay/_session.py` - Added `wrap_from_item(driver_module_name, item, db_kwargs, connect_fn)` method
- `src/pytest_adbc_replay/_connection.py` - Added `connect_fn: Any = None` parameter to `__init__`; when provided, used instead of `driver.connect()` in record mode
- `src/pytest_adbc_replay/plugin.py` - Added `_auto_patch_state` dict, `_ITEM_LOCK`, `_OPEN_CONNECTIONS`, `_ORIGINAL_CONNECTS`, `_build_session_from_config()`, `pytest_sessionstart`, `pytest_runtest_setup`, `pytest_runtest_teardown`, `adbc_connect` fixture
- `tests/test_cassette_path.py` - Added `TestDriverModuleNameSubdir` class (5 tests)

## Decisions Made

- Used `_auto_patch_state: dict[str, Any]` container instead of `_CURRENT_ITEM: ... = None` module variables because basedpyright treats uppercase module-level variables as immutable constants and raises `reportConstantRedefinition` when they are reassigned in hook functions.
- Initialized `ReplaySession` eagerly in `pytest_sessionstart` from config so the monkeypatched `connect()` has a session object even before any test requests the `adbc_replay` fixture (which is lazily instantiated).
- Added `connect_fn` parameter to `ReplayConnection.__init__`: when the auto-patch hook passes the original (un-patched) connect callable, `ReplayConnection` uses it directly, preventing recursive calls into the patched version.
- Used `setattr(driver_mod, "connect", ...)  # noqa: B010` instead of direct attribute assignment to satisfy ruff's B010 rule and basedpyright's `reportAttributeAccessIssue` on `ModuleType`.

## Deviations from Plan

### Auto-fixed Issues

**1. [basedpyright reportConstantRedefinition] Module-level state variables**
- **Found during:** Task 3 (plugin.py implementation)
- **Issue:** `_CURRENT_ITEM: pytest.Item | None = None` at module level is treated as a constant by basedpyright; reassigning in hooks raised type errors
- **Fix:** Replaced with `_auto_patch_state: dict[str, Any] = {"current_item": None, "session_state": None}` mutable container
- **Files modified:** `src/pytest_adbc_replay/plugin.py`
- **Verification:** basedpyright passes; all hook reads/writes go through dict keys

**2. [RecursionError] connect_fn missing from ReplayConnection**
- **Found during:** Plan 08-02 test execution (record mode test)
- **Issue:** `ReplayConnection.__init__` in record mode called `driver.connect()` but driver.connect was already the patched version → infinite recursion
- **Fix:** Added `connect_fn` parameter; auto-patch passes `orig` as `connect_fn`; `ReplayConnection` uses it instead of module attribute
- **Files modified:** `src/pytest_adbc_replay/_connection.py`, `src/pytest_adbc_replay/_session.py`, `src/pytest_adbc_replay/plugin.py`
- **Verification:** All 12 auto-patch tests pass; no recursion

**3. [None _SESSION_STATE] adbc_replay fixture lazily instantiated**
- **Found during:** Plan 08-02 test execution
- **Issue:** Auto-patch hook read `_auto_patch_state["session_state"]` which was None because `adbc_replay` fixture had not yet been requested
- **Fix:** Added `_build_session_from_config()` helper; called in `pytest_sessionstart` to eagerly create a `ReplaySession` from config; `adbc_replay` fixture overwrites it with the fully-configured instance
- **Files modified:** `src/pytest_adbc_replay/plugin.py`
- **Verification:** Tests without `adbc_replay` fixture in conftest work correctly

---

**Total deviations:** 3 auto-fixed (2 type-checker, 1 runtime)
**Impact on plan:** All fixes necessary for correctness. No scope creep.

## Issues Encountered

- ruff rules requiring: `contextlib.suppress` (SIM105), `Generator` in TYPE_CHECKING (TC003), `setattr()` instead of direct attribute assignment (B010), and `noqa: B010` for the setattr call.
- basedpyright treating uppercase module-level assignments as immutable constants.
- RecursionError in record mode discovered during test writing (Plan 08-02).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Auto-patch implementation complete; 138 tests pass
- Plan 08-02 test suite complete (12 tests, all passing)
- Ready for Wave 2: Plan 08-03 (documentation updates)

---
*Phase: 08-automatic-adbc-wrapping*
*Completed: 2026-03-02*
