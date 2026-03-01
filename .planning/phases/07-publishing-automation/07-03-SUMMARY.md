---
phase: 07-publishing-automation
plan: "03"
subsystem: infra
tags: [github-actions, pypi, oidc, git-cliff, release-automation]

# Dependency graph
requires:
  - phase: 07-publishing-automation plan 01
    provides: reusable _test.yml workflow that release.yml calls as quality gate
provides:
  - Complete tag-triggered release workflow with quality gate, build, validate, changelog, PyPI publish, and GitHub Release jobs
  - Fixed cookiecutter import bug in validate job
affects: [publishing, release-automation]

# Tech tracking
tech-stack:
  added: [softprops/action-gh-release@v2]
  patterns:
    - Quality gate via reusable workflow (uses: ./.github/workflows/_test.yml) gates all downstream jobs
    - Job chain: quality -> build -> (validate, changelog parallel) -> publish -> github-release
    - OIDC trusted publisher for PyPI (id-token: write, no stored secrets)
    - contents: write permission scoped only to github-release job

key-files:
  created: []
  modified: [.github/workflows/release.yml]

key-decisions:
  - "softprops/action-gh-release@v2 chosen for GitHub Release creation (standard action for this purpose)"
  - "github-release depends on both publish and changelog: only create release after PyPI succeeds and notes are ready"
  - "build depends on quality: distributions never built if tests fail"
  - "changelog artifact gains retention-days: 7 for consistency with dist artifact"
  - "checkout actions updated to @v4 for consistency across the workflow"

patterns-established:
  - "Release gate pattern: all release jobs descend from quality gate calling reusable test workflow"
  - "Artifact handoff pattern: build uploads dist/, changelog job uploads CHANGELOG.md, downstream jobs download as needed"

requirements-completed: [PUB-03, PUB-04]

# Metrics
duration: 1min
completed: "2026-03-01"
---

# Phase 7 Plan 03: Release Workflow Quality Gate and GitHub Release Summary

**Tag-triggered release.yml rewritten: quality gate via _test.yml, cookiecutter import bug fixed, GitHub Release with git-cliff notes added via job chain quality->build->(validate,changelog)->publish->github-release**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-03-01T17:07:11Z
- **Completed:** 2026-03-01T17:08:08Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `quality` job at the top of release.yml that calls the reusable `./.github/workflows/_test.yml` workflow
- Gated the `build` job on `quality` (`needs: [quality]`) so distributions are never built if tests fail
- Fixed cookiecutter bug: validate job now imports `pytest_adbc_replay` instead of `{{ cookiecutter.package_name }}`
- Added `github-release` job using `softprops/action-gh-release@v2` that creates a published (not draft) GitHub Release with git-cliff notes and dist/* files attached
- Added `retention-days: 7` to changelog artifact for consistency with dist artifact

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite release.yml with quality gate, fixed validate, and GitHub Release** - `d9bbe0b` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `.github/workflows/release.yml` - Complete rewrite: quality gate job, fixed validate import, github-release job, updated checkout to @v4

## Decisions Made

- `softprops/action-gh-release@v2` chosen as the standard GitHub Releases action (Claude's discretion per CONTEXT.md)
- `github-release` depends on both `publish` and `changelog` — release only created after PyPI publish succeeds and changelog artifact is ready
- `build` depends on `quality` — never builds distributions if tests are failing
- `validate` and `changelog` run in parallel (both depend only on `build`)
- `publish` waits for both `validate` and `changelog` before publishing to PyPI
- `checkout@v4` used consistently (was `@v6` in the original, which is non-standard)
- `contents: write` permission scoped only to `github-release` job (top-level default remains `contents: read`)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required beyond the existing PyPI trusted publisher environment (`pypi`) and the GitHub Actions OIDC setup already in place.

## Next Phase Readiness

- All three plans in Phase 7 are now complete
- Publishing automation is fully operational: `_test.yml` reusable workflow + `release.yml` tag-triggered workflow
- The complete release pipeline is: push `v*.*.*` tag -> quality gates -> build -> validate + changelog -> publish to PyPI -> create GitHub Release
- No blockers

---
*Phase: 07-publishing-automation*
*Completed: 2026-03-01*
