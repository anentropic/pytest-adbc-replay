---
phase: 06-mkdocs-documentation-site
plan: 01
subsystem: docs
tags: [mkdocs, material, diataxis, nav, gen-files]

requires:
  - phase: 05-readme-and-changelog
    provides: CHANGELOG.md and README content used as reference for Quick Start

provides:
  - MkDocs nav with Tutorial, How-To Guides, Reference, Explanation, Changelog sections
  - Complete docs/src/index.md with Quick Start and section navigation links
  - gen_ref_pages.py fix (main() invocation)
  - gen_changelog.py script to include CHANGELOG.md in the build

affects: [06-02, 06-03, 06-04, 06-05]

tech-stack:
  added: []
  patterns:
    - "gen-files scripts at docs/scripts/ handle virtual filesystem population"
    - "CHANGELOG.md included via gen_changelog.py script, not symlink"

key-files:
  created:
    - docs/scripts/gen_changelog.py
    - docs/src/tutorial/index.md
    - docs/src/how-to/index.md
    - docs/src/explanation/index.md
  modified:
    - mkdocs.yml
    - docs/src/index.md
    - docs/scripts/gen_ref_pages.py

key-decisions:
  - "gen_ref_pages.py had if __name__ == '__main__' guard preventing gen-files from calling main(); fixed by replacing with direct call"
  - "CHANGELOG.md brought into docs via gen_changelog.py gen-files script rather than symlink or copy"
  - "Reference link in index.md points to reference/pytest_adbc_replay/plugin.md (the auto-generated page) since reference/ directory has no index.md"

patterns-established:
  - "Placeholder section index files use '(Coming soon — replaced by XX-PLAN)' to make in-progress state clear"

requirements-completed:
  - DOC-05

duration: 2min
completed: 2026-03-01
---

# Phase 06 Plan 01: MkDocs Nav Wiring and Quick Start Summary

**MkDocs nav wired with all four Diataxis sections; index.md Quick Start complete with DuckDB example and section links; build pipeline fixed so `mkdocs build --strict` exits 0**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-01T02:42:03Z
- **Completed:** 2026-03-01T02:44:46Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Updated `mkdocs.yml` nav to include Tutorial, How-To Guides, Reference, Explanation, and Changelog alongside the existing Home entry
- Created placeholder `index.md` files for tutorial/, how-to/, and explanation/ sections
- Replaced the TODO placeholder in `docs/src/index.md` with a complete Quick Start (DuckDB example, install steps, section navigation links)
- Fixed pre-existing build failures: `gen_ref_pages.py` main() was never called; CHANGELOG.md was not accessible from the docs virtual filesystem

## Task Commits

1. **Task 1: Update mkdocs.yml nav and create placeholder section index files** - `8700dd2` (docs)
2. **Task 2: Complete docs/src/index.md with Quick Start and section links** - `60cd79a` (docs)

## Files Created/Modified

- `mkdocs.yml` - Added Tutorial, How-To Guides, Explanation to nav; added gen_changelog.py script
- `docs/scripts/gen_ref_pages.py` - Fixed: replaced `if __name__ == '__main__': main()` with `main()` so gen-files plugin invokes it
- `docs/scripts/gen_changelog.py` - New script: copies CHANGELOG.md into the virtual docs filesystem as changelog.md
- `docs/src/tutorial/index.md` - Placeholder for 06-02
- `docs/src/how-to/index.md` - Placeholder for 06-03
- `docs/src/explanation/index.md` - Placeholder for 06-05
- `docs/src/index.md` - Complete home page with installation, Quick Start, and section navigation

## Decisions Made

- `gen_ref_pages.py` used `if __name__ == "__main__": main()` which prevents the gen-files plugin from calling it (gen-files imports the script, it doesn't run it as a subprocess). Fixed to call `main()` directly at module level.
- `CHANGELOG.md` lives at the project root but MkDocs docs_dir is `docs/src/`. Added `gen_changelog.py` to read and copy it into the virtual filesystem as `changelog.md`.
- The `reference/` section in the nav works via literate-nav + the auto-generated `reference/SUMMARY.md`. The home page links to `reference/pytest_adbc_replay/plugin.md` since there is no reference index page.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] gen_ref_pages.py main() was never invoked by gen-files plugin**
- **Found during:** Task 1 verification (`mkdocs build --strict`)
- **Issue:** Script wrapped main() in `if __name__ == "__main__":` guard. The gen-files plugin imports scripts as modules, not subprocess calls, so the guard prevented execution. Result: no reference pages generated, `reference/` nav entry failed.
- **Fix:** Replaced `if __name__ == "__main__": main()` with `main()` at module level.
- **Files modified:** `docs/scripts/gen_ref_pages.py`
- **Verification:** `mkdocs build --strict` exits 0; reference/pytest_adbc_replay/plugin.md appears in built site
- **Committed in:** 8700dd2 (Task 1 commit)

**2. [Rule 3 - Blocking] changelog.md missing from docs virtual filesystem**
- **Found during:** Task 1 verification (`mkdocs build --strict`)
- **Issue:** The nav referenced `changelog.md` but the file didn't exist in `docs/src/`. The `CHANGELOG.md` lives at the project root.
- **Fix:** Added `docs/scripts/gen_changelog.py` script that copies CHANGELOG.md into the virtual filesystem. Registered it in `mkdocs.yml` gen-files scripts list.
- **Files modified:** `mkdocs.yml`, `docs/scripts/gen_changelog.py` (new)
- **Verification:** `mkdocs build --strict` exits 0; Changelog page appears in built site
- **Committed in:** 8700dd2 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes necessary for the build to pass. Pre-existing issues in the scaffold, not introduced by this plan.

## Issues Encountered

None — both deviations were caught during Task 1 verification and resolved before Task 2 began.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plans 06-02 through 06-05 can now execute in parallel. Each writes content into directories already registered in the nav (tutorial/, how-to/, explanation/) and the build pipeline is verified clean.

---
*Phase: 06-mkdocs-documentation-site*
*Completed: 2026-03-01*

## Self-Check: PASSED

- [x] `docs/src/tutorial/index.md` exists on disk
- [x] `docs/src/explanation/index.md` exists on disk
- [x] `git log --oneline --all --grep="06-01"` returns ≥1 commit (8700dd2, 60cd79a)
- [x] No `## Self-Check: FAILED` marker
