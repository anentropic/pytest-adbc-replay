---
phase: 07-publishing-automation
plan: 02
subsystem: infra
tags: [github-actions, ci-cd, reusable-workflows, python-matrix]

requires:
  - phase: 07-publishing-automation
    provides: _test.yml reusable workflow with full 3.11-3.14 matrix (created in plan 07-01)

provides:
  - Lean ci.yml that delegates all quality gate steps to _test.yml on every push
  - Updated pr.yml with matrix test job (via _test.yml) plus preserved coverage comment job

affects: [07-03, publishing, release]

tech-stack:
  added: []
  patterns:
    - "Reusable workflow call pattern: `uses: ./.github/workflows/_test.yml` with no inputs"
    - "Parallel PR jobs: test matrix and coverage run independently (no needs: dependency)"

key-files:
  created: []
  modified:
    - .github/workflows/ci.yml
    - .github/workflows/pr.yml

key-decisions:
  - "ci.yml reduced to 16 lines: single test job calling _test.yml, no inline steps"
  - "pr.yml coverage job preserved as-is; uv run pytest --cov is coverage-specific, not a duplicate quality gate"
  - "Two PR jobs (test + coverage) run in parallel with no needs: dependency"

patterns-established:
  - "No quality gate step duplication: prek run and uv run pytest live exclusively in _test.yml"
  - "Workflow callers stay lean: only trigger, concurrency, permissions, and job(s) calling reusable workflow"

requirements-completed: [PUB-02]

duration: 3min
completed: 2026-03-01
---

# Phase 7 Plan 02: CI/PR Workflow Refactor Summary

**ci.yml and pr.yml both delegate the full 3.11-3.14 test matrix to the reusable _test.yml workflow, eliminating step duplication while preserving PR coverage comments**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-01T17:04:30Z
- **Completed:** 2026-03-01T17:07:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Replaced 35-line ci.yml (inline steps, 3.11+3.14 only) with a 16-line lean caller that gets full 3.11-3.14 matrix via _test.yml
- Added `test:` job to pr.yml so pull requests now run the same full matrix as pushes
- Preserved coverage comment job in pr.yml unchanged — it runs in parallel with the test job

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite ci.yml to call reusable workflow** - `c8b371d` (feat)
2. **Task 2: Update pr.yml to add matrix test job alongside coverage** - `669ca83` (feat)

## Files Created/Modified

- `.github/workflows/ci.yml` - Reduced from inline matrix steps to single `uses: ./.github/workflows/_test.yml` call
- `.github/workflows/pr.yml` - Added `test:` job calling `_test.yml`; coverage job preserved as-is

## Decisions Made

- The `uv run pytest --cov` command in `pr.yml`'s coverage job is not a duplicate quality gate — it is coverage-specific (different flags, different purpose). Only `prek run` and plain `uv run pytest` in _test.yml constitute the quality gate.
- Jobs in pr.yml run in parallel (no `needs:` dependency) for faster PR feedback.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

`python3 -c "import yaml"` failed in sandbox (no system PyYAML). Verified workflow content directly by reading files and grep-checking for absence of `prek run` in ci.yml and pr.yml.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ci.yml and pr.yml are now lean callers; _test.yml is the single source of quality gate truth
- Ready for plan 07-03 (release/publish workflow)

---
*Phase: 07-publishing-automation*
*Completed: 2026-03-01*
