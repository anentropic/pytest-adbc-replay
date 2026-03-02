---
phase: 07-publishing-automation
plan: "01"
subsystem: infra
tags: [github-actions, workflow_call, pypi, classifiers, mkdocs, python-matrix]

requires:
  - phase: 04-type-exports-and-pypi-metadata
    provides: pyproject.toml with complete PyPI metadata (classifiers, URLs, keywords)
  - phase: 06-mkdocs-site
    provides: docs.yml workflow for MkDocs build and deploy

provides:
  - Reusable GitHub Actions quality gate workflow (_test.yml) callable via workflow_call
  - docs.yml triggers on version tag push in addition to main-branch push
  - pyproject.toml classifiers include Python 3.14
  - REQUIREMENTS.md PUB-02 description corrected to list actual supported Python version matrix

affects:
  - 07-02 (CI workflow will call _test.yml via workflow_call)
  - 07-03 (release workflow will call _test.yml via workflow_call)

tech-stack:
  added: []
  patterns:
    - "Reusable workflow pattern: _test.yml called via workflow_call from ci.yml and release.yml"
    - "Tag trigger pattern: docs deploy on both main push and v*.*.* semver tags"

key-files:
  created:
    - .github/workflows/_test.yml
  modified:
    - .github/workflows/docs.yml
    - pyproject.toml
    - .planning/REQUIREMENTS.md

key-decisions:
  - "_test.yml has no inputs — callers pass no parameters; all four Python versions (3.11-3.14) are required-to-pass legs"
  - "Tag trigger uses regex patterns v[0-9]+.[0-9]+.[0-9]+ and v[0-9]+.[0-9]+.[0-9]+-* to cover both stable and pre-release versions"
  - "checkout@v4 used in _test.yml (consistent with docs.yml pattern; ci.yml used v6 which is non-standard)"

patterns-established:
  - "Reusable workflow: _test.yml is the DRY quality gate; never duplicate lint+test steps across workflows"
  - "Version tag pattern: v[0-9]+.[0-9]+.[0-9]+ (stable) and v[0-9]+.[0-9]+.[0-9]+-* (pre-release) covers all semver variants"

requirements-completed:
  - PUB-04

duration: 2min
completed: "2026-03-01"
---

# Phase 7 Plan 01: Shared Workflow Infrastructure Summary

**Reusable GitHub Actions quality gate (_test.yml) with 4-version Python matrix, docs deploy on version tags, Python 3.14 PyPI classifier, and corrected PUB-02 requirement description**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-01T17:00:49Z
- **Completed:** 2026-03-01T17:02:00Z
- **Tasks:** 4
- **Files modified:** 4

## Accomplishments

- Created `.github/workflows/_test.yml` as reusable quality gate callable via `workflow_call`, matrix covers Python 3.11, 3.12, 3.13, 3.14 with all legs required-to-pass
- Updated `docs.yml` to trigger on version tag pushes (`v*.*.*` and pre-release patterns) alongside existing main-branch push and `workflow_dispatch`
- Added `"Programming Language :: Python :: 3.14"` classifier to `pyproject.toml`
- Corrected `REQUIREMENTS.md` PUB-02 description from `(3.10, 3.11, 3.12)` to `(3.11, 3.12, 3.13, 3.14)` to match actual `requires-python = ">=3.11"` constraint

## Task Commits

Each task was committed atomically:

1. **Task 1: Create reusable quality gate workflow** - `8e8ea3e` (feat)
2. **Task 2: Add tag-push trigger to docs.yml** - `063b40a` (feat)
3. **Task 3: Add Python 3.14 classifier to pyproject.toml** - `40f7629` (feat)
4. **Task 4: Correct PUB-02 Python version matrix in REQUIREMENTS.md** - `e289ddc` (fix)

## Files Created/Modified

- `.github/workflows/_test.yml` - Reusable workflow with `on: workflow_call`, Python 3.11-3.14 matrix, full quality gate steps (checkout, uv, prek, pytest, cache prune)
- `.github/workflows/docs.yml` - Added tags trigger for stable (`v[0-9]+.[0-9]+.[0-9]+`) and pre-release (`v[0-9]+.[0-9]+.[0-9]+-*`) versions
- `pyproject.toml` - Added `"Programming Language :: Python :: 3.14"` after the 3.13 classifier entry
- `.planning/REQUIREMENTS.md` - PUB-02 description now lists `(3.11, 3.12, 3.13, 3.14)`

## Decisions Made

- `_test.yml` uses `actions/checkout@v4` (consistent with `docs.yml`; `ci.yml` used `@v6` which is non-standard and was kept as-is since ci.yml is out of scope for this task)
- Tag trigger uses two regex patterns to cover both stable releases and pre-release versions (e.g., `v1.0.0-rc1`)
- No inputs on `_test.yml` — callers pass no parameters, keeping the interface minimal

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `_test.yml` is ready to be called by `ci.yml` (plan 07-02) and `release.yml` (plan 07-03) via `uses: ./.github/workflows/_test.yml`
- `docs.yml` is ready to deploy on version tag pushes (PUB-04 addressed)
- Plans 07-02 and 07-03 can now reference `_test.yml` for the shared quality gate

## Self-Check: PASSED

- FOUND: `.github/workflows/_test.yml`
- FOUND: `.github/workflows/docs.yml`
- FOUND: `pyproject.toml`
- FOUND: `.planning/REQUIREMENTS.md`
- FOUND: `.planning/phases/07-publishing-automation/07-01-SUMMARY.md`
- FOUND commit `8e8ea3e` (Task 1)
- FOUND commit `063b40a` (Task 2)
- FOUND commit `40f7629` (Task 3)
- FOUND commit `e289ddc` (Task 4)

---
*Phase: 07-publishing-automation*
*Completed: 2026-03-01*
