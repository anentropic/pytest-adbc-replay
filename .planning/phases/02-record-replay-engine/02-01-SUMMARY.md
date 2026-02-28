---
phase: 02-record-replay-engine
plan: 01
subsystem: testing
tags: [sqlglot, pyarrow, normalisation, serialisation, type-registry]

requires:
  - phase: 01-plugin-skeleton
    provides: _cursor.py stub and ReplayCursor constructor that dialect flows through

provides:
  - normalise_sql() with sqlglot pretty=True + normalize=True for keyword+identifier normalisation
  - NormalisationWarning subclass of UserWarning with fallback to whitespace collapse
  - type-tagged JSON parameter serialisation registry for datetime/date/time/Decimal/bytes/UUID
  - params_to_cache_key() for stable cassette key computation
  - NO_DEFAULT_SERIALISERS sentinel for clearing built-in defaults
  - Public API exports: NormalisationWarning, NO_DEFAULT_SERIALISERS

affects: 02-03 (cursor wiring uses normalise_sql and build_registry), 02-04 (tests import all of these)

tech-stack:
  added: [sqlglot 28.10.1 for SQL normalisation]
  patterns:
    - functools.lru_cache(maxsize=256) on (sql, dialect) pair for cached normalisation
    - type-tagged JSON encoding {"__type__": "TypeName", "value": "..."} for non-native types
    - typed named helper functions (not lambdas) to satisfy basedpyright strict mode
    - datetime before date in registry dict (datetime is subclass of date, order matters)

key-files:
  created:
    - src/pytest_adbc_replay/_normaliser.py
    - src/pytest_adbc_replay/_params.py
  modified:
    - src/pytest_adbc_replay/__init__.py

key-decisions:
  - "Used normalize=True in sqlglot .sql() call to normalize identifiers to lowercase — satisfies ROADMAP SC-3 (FOO vs foo match same cassette)"
  - "Replaced lambda-based registry with typed named functions to satisfy basedpyright strict reportUnknownLambdaType"
  - "datetime entry appears before date in _BUILTIN_SERIALISERS — critical since datetime is a date subclass"

patterns-established:
  - "Cassette key = (normalise_sql(sql, dialect), params_to_cache_key(params, registry)) — both components needed"
  - "All basedpyright lambdas → named functions with explicit parameter types"

requirements-completed:
  - NORM-01
  - NORM-02
  - NORM-03
  - NORM-04
  - CASS-05
  - CASS-06

duration: 12min
completed: 2026-02-28
---

# Phase 2 Plan 01: SQL Normaliser + Parameter Serialisation Summary

**sqlglot-powered SQL normalisation (keyword uppercase + identifier lowercase) with type-tagged JSON registry for datetime/Decimal/UUID round-trips through cassette files**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-28T00:00:00Z
- **Completed:** 2026-02-28T00:12:00Z
- **Tasks:** 3
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments
- `_normaliser.py`: `normalise_sql()` with LRU cache, `NormalisationWarning` subclass, ParseError fallback to whitespace collapse
- `_params.py`: type-tagged JSON registry covering 6 built-in types; `params_to_cache_key()` for stable cassette keys; `NO_DEFAULT_SERIALISERS` sentinel
- `__init__.py`: exports `NormalisationWarning` and `NO_DEFAULT_SERIALISERS` at package level

## Task Commits

1. **Task 1: Create _normaliser.py** - `78b3bc8` (feat)
2. **Tasks 2+3: Create _params.py + update __init__.py** - `970ab09` (feat)

## Files Created/Modified
- `src/pytest_adbc_replay/_normaliser.py` - normalise_sql() with sqlglot, NormalisationWarning, lru_cache
- `src/pytest_adbc_replay/_params.py` - type-tagged JSON serialisation registry with build_registry/serialise_params/deserialise_params
- `src/pytest_adbc_replay/__init__.py` - added NormalisationWarning, NO_DEFAULT_SERIALISERS to public exports

## Decisions Made
- Added `normalize=True` to `.sql()` call (not in plan) to satisfy ROADMAP SC-3 requirement that `SELECT * FROM foo` and `SELECT * FROM FOO` match the same cassette. Without this, identifier case was preserved by sqlglot.
- Rewrote lambdas as named typed functions: basedpyright strict mode (`reportUnknownLambdaType`) requires explicit parameter types even in dict values. Named functions satisfy this cleanly.
- `datetime` must precede `date` in `_BUILTIN_SERIALISERS` dict because `isinstance(datetime_obj, date)` is True — wrong ordering would serialise datetimes with the date handler.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added normalize=True to sqlglot .sql() call**
- **Found during:** Task 1 verification
- **Issue:** Without `normalize=True`, `normalise_sql('select * from FOO')` returned `'SELECT\n  *\nFROM FOO'` while `normalise_sql('SELECT * FROM foo')` returned `'SELECT\n  *\nFROM foo'` — different strings for semantically identical queries, breaking ROADMAP SC-3
- **Fix:** Changed `.sql(pretty=True)` to `.sql(pretty=True, normalize=True)` — sqlglot normalises identifiers to lowercase
- **Files modified:** src/pytest_adbc_replay/_normaliser.py
- **Verification:** normalise_sql('select * from FOO') == normalise_sql('SELECT * FROM foo') ✓
- **Committed in:** 78b3bc8

**2. [Rule 1 - Bug] Replaced lambdas with named typed functions**
- **Found during:** Task 2 quality gates (basedpyright)
- **Issue:** `_BUILTIN_SERIALISERS` dict used lambdas; basedpyright strict `reportUnknownLambdaType` flagged 16 errors
- **Fix:** Extracted each lambda to a named function (`_ser_datetime`, `_des_datetime`, etc.) with explicit parameter types
- **Files modified:** src/pytest_adbc_replay/_params.py
- **Verification:** basedpyright: 0 errors, 0 warnings ✓
- **Committed in:** 970ab09

---

**Total deviations:** 2 auto-fixed (2 bugs caught during verification)
**Impact on plan:** Both fixes essential for correctness. No scope creep.

## Issues Encountered

None — both deviations were caught by verification steps and fixed cleanly.

## Next Phase Readiness
- `_normaliser.py` and `_params.py` ready for import in Plan 02-03 (_cursor.py wiring)
- `_cassette_io.py` (Plan 02-02) also needed before 02-03 can proceed

---
*Phase: 02-record-replay-engine*
*Completed: 2026-02-28*
