---
phase: 02-record-replay-engine
plan: 02
subsystem: testing
tags: [pyarrow, ipc, cassette, file-io, arrow]

requires:
  - phase: 01-plugin-skeleton
    provides: ReplayCursor + cassette_path resolution

provides:
  - write_arrow_table/read_arrow_table (Arrow IPC File format, schema metadata preserved)
  - write_sql_file/read_sql_file (UTF-8 with trailing newline; strip on read)
  - write_params_json/read_params_json (JSON null/list/dict round-trip)
  - make_interaction_prefix(n) zero-padded 3-digit prefix
  - interaction_file_paths(cassette_path, index) -> (sql_path, arrow_path, params_path)
  - count_interactions/cassette_has_interactions for once-mode logic
  - load_all_interactions() ordered list of (sql, table, params_raw)

affects: 02-03 (cursor imports all of these), 02-04 (tests use write helpers to populate cassettes)

tech-stack:
  added: []
  patterns:
    - Arrow IPC File format (pa.ipc.new_file/open_file) for seekable cassette files
    - noqa: TC003 for Path import used at runtime but flagged by ruff TCH rules

key-files:
  created:
    - src/pytest_adbc_replay/_cassette_io.py
  modified: []

key-decisions:
  - "Arrow IPC File format (not Stream) — seekable, recommended for static files per Phase 2 research"
  - "Added noqa: TC003 to Path import — ruff incorrectly suggested moving to TYPE_CHECKING block; Path is used at runtime in all function bodies"

patterns-established:
  - "Cassette file naming: {N:03d}_query.sql, {N:03d}_result.arrow, {N:03d}_params.json"
  - "count_interactions() scans for *_query.sql — SQL file as canonical presence indicator"

requirements-completed:
  - CASS-01
  - CASS-02
  - CASS-03
  - CASS-04

duration: 8min
completed: 2026-02-28
---

# Phase 2 Plan 02: Cassette File I/O Summary

**Arrow IPC File format cassette I/O layer with schema metadata preservation, SQL text storage, and JSON parameter serialisation**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-28T00:12:00Z
- **Completed:** 2026-02-28T00:20:00Z
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments
- Single `_cassette_io.py` module covering all three cassette file types
- Arrow IPC round-trip preserves schema-level metadata (critical for ADBC extension type metadata)
- SQL file stores with trailing newline; reads back with `.strip()` — clean interface
- File naming convention locked in: `{N:03d}_{type}.{ext}`
- `cassette_has_interactions()` is the canonical "cassette exists" check for once mode

## Task Commits

1. **Task 1: Create _cassette_io.py** - `a067271` (feat)

## Files Created/Modified
- `src/pytest_adbc_replay/_cassette_io.py` - All file I/O functions, file naming utilities, interaction loading

## Decisions Made
- Arrow IPC File format over Stream format: File format is seekable and produces a complete file with a footer; better for static cassette files
- `noqa: TC003` on Path import: ruff's TCH rule incorrectly flagged Path as "only used in type annotations" but all functions use Path methods at runtime

## Deviations from Plan

None — plan executed exactly as written (aside from `noqa: TC003` suppression comment).

## Issues Encountered

None.

## Next Phase Readiness
- `_cassette_io.py` fully ready for import in Plan 02-03 (cursor wiring)
- Both Wave 1 plans (02-01, 02-02) complete — Wave 2 can proceed

---
*Phase: 02-record-replay-engine*
*Completed: 2026-02-28*
