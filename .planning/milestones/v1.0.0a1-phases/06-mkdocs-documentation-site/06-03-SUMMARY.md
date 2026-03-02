---
phase: 06-mkdocs-documentation-site
plan: 03
subsystem: docs
tags: [mkdocs, how-to, diataxis, github-actions, ci]

requires:
  - phase: 06-mkdocs-documentation-site
    provides: Nav structure with how-to/ registered

provides:
  - how-to/index.md: section overview listing all six guides
  - Six How-To guides: CI, ini config, cassette names, multiple drivers, scrubber, custom serialisers

affects: []

tech-stack:
  added: []
  patterns:
    - "Each How-To guide solves exactly one task — no cross-cutting concerns"
    - "GitHub Actions YAML uses actions/setup-python@v5 and actions/checkout@v4"

key-files:
  created:
    - docs/src/how-to/index.md
    - docs/src/how-to/ci-without-credentials.md
    - docs/src/how-to/configure-via-ini.md
    - docs/src/how-to/cassette-names.md
    - docs/src/how-to/multiple-drivers.md
    - docs/src/how-to/scrub-sensitive-values.md
    - docs/src/how-to/custom-param-serialisers.md
  modified: []

key-decisions:
  - "GitHub Actions job uses pip install (not uv) for simplicity in CI guide"
  - "scrub-sensitive-values.md includes warning admonition about consistent placeholder values"

patterns-established:
  - "Each guide ends with a 'Related' section linking to the Reference for exact specs"

requirements-completed:
  - DOC-07
  - DOC-10

duration: 1min
completed: 2026-03-01
---

# Phase 06 Plan 03: How-To Guides Summary

**Six task-oriented How-To guides covering CI, ini configuration, cassette naming, multiple drivers, value scrubbing, and custom serialisers**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-01T02:51:21Z
- **Completed:** 2026-03-01T02:52:07Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Wrote how-to/index.md listing all six guides with one-line descriptions
- Task 1: CI guide (GitHub Actions YAML), ini config guide (pyproject.toml + pytest.ini examples), cassette names guide (marker usage, shared cassettes, dialect override)
- Task 2: multiple drivers guide (DuckDB/Snowflake/BigQuery notes), scrubber guide (with consistency warning admonition), custom serialisers guide (NO_DEFAULT_SERIALISERS sentinel)
- Humanizer review applied to all seven files: second-person voice, no AI vocabulary

## Task Commits

1. **Task 1: index.md + guides 1-3** - `31a1c59` (docs)
2. **Task 2: guides 4-6** - `64b1a59` (docs)

## Files Created/Modified

- `docs/src/how-to/index.md` - Section overview with six guide links
- `docs/src/how-to/ci-without-credentials.md` - GitHub Actions job, CassetteMissError warning
- `docs/src/how-to/configure-via-ini.md` - All four settings, both ini formats
- `docs/src/how-to/cassette-names.md` - Auto-derived vs marker, sharing, dialect override
- `docs/src/how-to/multiple-drivers.md` - Two-connection conftest, driver-specific notes
- `docs/src/how-to/scrub-sensitive-values.md` - adbc_scrubber fixture, consistency warning
- `docs/src/how-to/custom-param-serialisers.md` - adbc_param_serialisers, NO_DEFAULT_SERIALISERS

## Decisions Made

None — followed plan as specified.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

blacken-docs reformatted code blocks in multiple files (collapsed single-statement function bodies). Accepted the reformatting and re-staged before final commit.

## User Setup Required

None.

## Next Phase Readiness

All six guides complete with cross-links to Reference pages (written in 06-04).

---
*Phase: 06-mkdocs-documentation-site*
*Completed: 2026-03-01*

## Self-Check: PASSED

- [x] `docs/src/how-to/index.md` exists and has >20 lines
- [x] `docs/src/how-to/ci-without-credentials.md` exists and has >50 lines
- [x] `git log --oneline --all --grep="06-03"` returns ≥1 commit
- [x] No `## Self-Check: FAILED` marker
