---
phase: 06-mkdocs-documentation-site
plan: 04
subsystem: docs
tags: [mkdocs, reference, diataxis, configuration, api]

requires:
  - phase: 06-mkdocs-documentation-site
    provides: Nav structure with reference/ in nav

provides:
  - Explicit Reference nav section in mkdocs.yml
  - Seven hand-crafted reference pages: index, configuration, record-modes, fixtures, markers, exceptions, cassette-format

affects: []

tech-stack:
  added: []
  patterns:
    - "Reference nav uses explicit enumeration instead of literate-nav wildcard"
    - "Pseudo-code signatures use text code blocks to avoid blacken-docs errors"

key-files:
  created:
    - docs/src/reference/index.md
    - docs/src/reference/configuration.md
    - docs/src/reference/record-modes.md
    - docs/src/reference/fixtures.md
    - docs/src/reference/markers.md
    - docs/src/reference/exceptions.md
    - docs/src/reference/cassette-format.md
  modified:
    - mkdocs.yml

key-decisions:
  - "Reference nav changed from 'Reference: reference/' wildcard to explicit enumeration so hand-crafted pages are properly listed alongside auto-generated API reference"
  - "Pseudo-code interface signatures use text code blocks (not python) to avoid blacken-docs parse errors"

patterns-established:
  - "Reference pages use tables for information-dense content (configuration, modes, markers)"
  - "Neutral third-person voice throughout reference section"

requirements-completed:
  - DOC-08
  - DOC-10

duration: 1min
completed: 2026-03-01
---

# Phase 06 Plan 04: Reference Pages Summary

**Seven hand-crafted reference pages covering all user-facing surfaces; mkdocs.yml updated to explicit Reference nav**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-01T02:51:21Z
- **Completed:** 2026-03-01T02:52:07Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Updated mkdocs.yml Reference nav from wildcard `reference/` to explicit enumeration listing all hand-crafted pages plus the auto-generated API reference entry
- Task 1: reference/index.md (section overview), configuration.md (settings table + both ini formats), record-modes.md (modes table + CLI usage)
- Task 2: fixtures.md (three fixtures with full signatures), markers.md (adbc_cassette args table), exceptions.md (CassetteMissError + NormalisationWarning), cassette-format.md (directory layout + file descriptions)
- All pages checked for accuracy against README.md as source of truth

## Task Commits

1. **Task 1: reference index + configuration + record-modes** - `db9945f` (docs)
2. **Task 2: fixtures, markers, exceptions, cassette-format** - `cda82ee` (docs)

## Files Created/Modified

- `mkdocs.yml` - Reference nav from wildcard to explicit enumeration
- `docs/src/reference/index.md` - Section overview with links to all seven pages + API reference
- `docs/src/reference/configuration.md` - Four settings in table; pyproject.toml and pytest.ini examples
- `docs/src/reference/record-modes.md` - Four modes in table; CLI override note
- `docs/src/reference/fixtures.md` - adbc_replay, adbc_scrubber, adbc_param_serialisers; NO_DEFAULT_SERIALISERS
- `docs/src/reference/markers.md` - adbc_cassette arguments table; auto-derived naming example
- `docs/src/reference/exceptions.md` - CassetteMissError and NormalisationWarning with resolution guidance
- `docs/src/reference/cassette-format.md` - Directory layout, .sql/.arrow/.json descriptions, versioning note

## Decisions Made

- Reference nav updated to explicit enumeration because literate-nav wildcard `reference/` only discovers auto-generated pages; hand-crafted pages would be absent from the nav without explicit listing.
- Interface signatures (pseudo-code) moved to `text` code blocks to prevent blacken-docs parse errors.

## Deviations from Plan

None — the plan explicitly described the nav approach. Followed as written.

## Issues Encountered

blacken-docs raised parse errors on pseudo-code signatures in Python code blocks. Fixed by changing to `text` fence for non-executable signature display snippets.

## User Setup Required

None.

## Next Phase Readiness

All reference pages complete with cross-links to How-To and Explanation pages.

---
*Phase: 06-mkdocs-documentation-site*
*Completed: 2026-03-01*

## Self-Check: PASSED

- [x] `docs/src/reference/index.md` exists and has >20 lines
- [x] `docs/src/reference/configuration.md` exists and has >50 lines
- [x] `git log --oneline --all --grep="06-04"` returns ≥1 commit
- [x] No `## Self-Check: FAILED` marker
