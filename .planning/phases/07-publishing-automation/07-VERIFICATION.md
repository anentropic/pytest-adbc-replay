---
phase: 07-publishing-automation
verified: 2026-03-01T18:00:00Z
status: human_needed
score: 10/10 must-haves verified
re_verification: false
gaps:
  - truth: "REQUIREMENTS.md PUB-02 description lists the correct Python version matrix (3.11, 3.12, 3.13, 3.14)"
    status: partial
    reason: "The version matrix text was updated correctly but the checkbox and traceability table were not updated — PUB-02 still reads '- [ ]' (pending) and the traceability table still shows 'Pending'. The implementation is complete; only the tracking markers are wrong."
    artifacts:
      - path: ".planning/REQUIREMENTS.md"
        issue: "Line 82: '- [ ] **PUB-02**' should be '- [x] **PUB-02**'. Line 175: 'Pending' should be 'Complete'."
    missing:
      - "Mark PUB-02 checkbox as complete: change '- [ ] **PUB-02**' to '- [x] **PUB-02**'"
      - "Update traceability table: change 'PUB-02 | Phase 7 | Pending' to 'PUB-02 | Phase 7 | Complete'"
human_verification:
  - test: "Live CI run on push"
    expected: "Push to any branch triggers the _test.yml matrix across Python 3.11, 3.12, 3.13, 3.14 and all four legs must pass"
    why_human: "Cannot run GitHub Actions locally; requires an actual git push to a remote branch"
  - test: "Live release workflow on version tag"
    expected: "Pushing a v*.*.* tag triggers: quality -> build -> (validate + changelog parallel) -> publish -> github-release. PyPI package appears at pypi.org/p/pytest-adbc-replay. GitHub Release is created as published (not draft) with git-cliff notes and dist/* attached."
    why_human: "Cannot trigger tag-push workflows locally; requires a real tag push and PyPI environment with OIDC trusted publisher configured"
---

# Phase 7: Publishing Automation Verification Report

**Phase Goal:** Automate the full publishing pipeline — CI matrix coverage (Python 3.11-3.14), docs deployment on tag push, PyPI publishing on release, and GitHub Release creation with changelog notes.
**Verified:** 2026-03-01T18:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A reusable `_test.yml` workflow exists callable via `workflow_call` | VERIFIED | `.github/workflows/_test.yml` line 4: `workflow_call:`. Commit `8e8ea3e` created the file. |
| 2 | The `_test.yml` matrix covers Python 3.11, 3.12, 3.13, 3.14, all legs required-to-pass | VERIFIED | Line 13: `python-version: ["3.11", "3.12", "3.13", "3.14"]`. `fail-fast: false`. No `continue-on-error`. |
| 3 | `_test.yml` contains the full quality gate (uv sync, prek, pytest, cache prune) | VERIFIED | Lines 25-34: `uv sync --locked --dev`, `prek run --all-files`, `uv run pytest`, `uv cache prune --ci`. |
| 4 | The docs workflow deploys on tag pushes matching `v*.*.*` in addition to main-branch pushes | VERIFIED | `.github/workflows/docs.yml` lines 10-12: `tags: - 'v[0-9]+.[0-9]+.[0-9]+'` and pre-release pattern. `--strict` flag preserved (line 45). |
| 5 | `pyproject.toml` classifiers include Python 3.14 | VERIFIED | Line 19: `"Programming Language :: Python :: 3.14"`. |
| 6 | REQUIREMENTS.md PUB-02 version matrix text reads (3.11, 3.12, 3.13, 3.14) | VERIFIED | Line 82 reads `(3.11, 3.12, 3.13, 3.14)`. Old `(3.10, 3.11, 3.12)` text is gone. |
| 7 | REQUIREMENTS.md PUB-02 tracking markers reflect completion | FAILED | Line 82: `- [ ]` still shows pending. Line 175 traceability table: shows "Pending". Implementation exists; only tracking markers were not updated. |
| 8 | `ci.yml` and `pr.yml` delegate to `_test.yml` with no quality gate duplication | VERIFIED | `ci.yml` line 16 and `pr.yml` line 17 both call `./.github/workflows/_test.yml`. Neither file contains `prek run`. `pr.yml` `uv run pytest --cov` is a coverage-specific call, not a duplicate quality gate. |
| 9 | `release.yml` calls `_test.yml` as quality gate, gating all downstream jobs | VERIFIED | Line 15: `uses: ./.github/workflows/_test.yml`. Line 19: `build` needs `[quality]`. Chain: quality -> build -> (validate, changelog) -> publish -> github-release. |
| 10 | `release.yml` cookiecutter bug is fixed; validate imports `pytest_adbc_replay` | VERIFIED | Lines 71, 77: `import pytest_adbc_replay`. No `cookiecutter` string in file. |
| 11 | `release.yml` creates a published GitHub Release with git-cliff notes | VERIFIED | Lines 150-155: `softprops/action-gh-release@v2`, `body_path: changelog/CHANGELOG.md`, `draft: false`, `prerelease: false`. |
| 12 | `release.yml` publishes to PyPI via OIDC trusted publisher | VERIFIED | Line 127: `pypa/gh-action-pypi-publish@release/v1`. Lines 113-118: `environment: pypi`, `id-token: write`. |

**Score:** 9/10 must-have truths verified (1 partial — documentation tracking markers only)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.github/workflows/_test.yml` | Reusable quality gate (lint + tests across Python 3.11-3.14 matrix) | VERIFIED | 35 lines. `on: workflow_call`. Matrix `["3.11","3.12","3.13","3.14"]`. Full step sequence present. Commit `8e8ea3e`. |
| `.github/workflows/docs.yml` | Docs build and deploy triggered on main push and version tag push | VERIFIED | Tags block with `v[0-9]+.[0-9]+.[0-9]+` and pre-release variant. `--strict` preserved. Commit `063b40a`. |
| `.github/workflows/ci.yml` | Push CI calling reusable workflow for all pushes | VERIFIED | 17 lines. Single `test` job. `uses: ./.github/workflows/_test.yml`. `on: push`. Commit `c8b371d`. |
| `.github/workflows/pr.yml` | PR CI calling reusable workflow plus coverage comment | VERIFIED | Two jobs: `test` (calls `_test.yml`) and `coverage` (inline steps preserved). `on: pull_request`. Commit `669ca83`. |
| `.github/workflows/release.yml` | Tag-triggered release: quality gate, build, validate, GitHub Release, PyPI publish | VERIFIED | Complete 156-line workflow. All six jobs present. Job chain verified. Commit `d9bbe0b`. |
| `pyproject.toml` | PyPI classifiers listing Python 3.14 | VERIFIED | Line 19: `"Programming Language :: Python :: 3.14"`. Commit `40f7629`. |
| `.planning/REQUIREMENTS.md` | Accurate PUB-02 description with correct Python version matrix | PARTIAL | Version text updated to `(3.11, 3.12, 3.13, 3.14)` (commit `e289ddc`). But `- [ ]` checkbox and "Pending" traceability status were NOT updated to reflect completion. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `.github/workflows/ci.yml` | `.github/workflows/_test.yml` | `uses: ./.github/workflows/_test.yml` | WIRED | Line 16 of ci.yml confirmed. |
| `.github/workflows/pr.yml` | `.github/workflows/_test.yml` | `uses: ./.github/workflows/_test.yml` | WIRED | Line 17 of pr.yml confirmed. |
| `.github/workflows/release.yml` | `.github/workflows/_test.yml` | quality gate job uses reusable workflow | WIRED | Line 15 of release.yml confirmed. `build` depends on `quality` (line 19). |
| `release.yml publish job` | PyPI | `pypa/gh-action-pypi-publish@release/v1` with OIDC | WIRED | Line 127. `id-token: write` permission set. `pypi` environment configured. |
| `release.yml github-release job` | GitHub Releases | `softprops/action-gh-release@v2` with git-cliff notes | WIRED | Line 150. `body_path: changelog/CHANGELOG.md`. `draft: false`. `contents: write` scoped to that job. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PUB-02 | 07-01, 07-02 | CI runs test suite on push and PRs across Python 3.11-3.14 | SATISFIED (implementation) / TRACKING GAP | `ci.yml` triggers on push, `pr.yml` triggers on `pull_request`, both call `_test.yml` with full 3.11-3.14 matrix. However, REQUIREMENTS.md still shows `- [ ]` and "Pending" — tracking not updated. |
| PUB-03 | 07-03 | Publish workflow builds and uploads to PyPI on `v*.*.*` tag | SATISFIED | `release.yml` triggers on `v[0-9]+.[0-9]+.[0-9]+` tags; `pypa/gh-action-pypi-publish@release/v1` present; gated on quality gate. REQUIREMENTS.md shows `[x]`. |
| PUB-04 | 07-01, 07-03 | Docs deploy on version tag push | SATISFIED | `docs.yml` triggers on `v[0-9]+.[0-9]+.[0-9]+` tags. REQUIREMENTS.md shows `[x]`. |

**Orphaned requirements check:** No additional Phase 7 requirements appear in REQUIREMENTS.md beyond PUB-02, PUB-03, PUB-04. All accounted for.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.planning/REQUIREMENTS.md` | 82, 175 | PUB-02 marked `[ ]` (pending) and "Pending" in traceability despite implementation being complete | Warning | Misleading project state; suggests work is unfinished when it is done |

No anti-patterns found in workflow YAML files. No TODO/FIXME/placeholder comments. No empty implementations. No stub handlers.

### Human Verification Required

#### 1. Live CI matrix run

**Test:** Push any branch to the remote repository.
**Expected:** GitHub Actions triggers `CI` workflow; a single `test` job fans out to four parallel matrix legs (`Quality (3.11)`, `Quality (3.12)`, `Quality (3.13)`, `Quality (3.14)`); all four legs must pass.
**Why human:** Cannot trigger GitHub Actions workflows locally; requires an actual remote push.

#### 2. Live PR matrix run with coverage comment

**Test:** Open a pull request against `main`.
**Expected:** GitHub Actions triggers `PR` workflow; two parallel jobs appear — `Test matrix` (four matrix legs via `_test.yml`) and `Report test coverage` (single leg with coverage comment posted to the PR). Both must complete.
**Why human:** Pull request event cannot be simulated locally.

#### 3. Live release pipeline on version tag

**Test:** Push a `v*.*.*` tag (e.g., `git tag v0.1.0 && git push origin v0.1.0`).
**Expected:** GitHub Actions triggers `Release` workflow following the chain: `Quality gates` (4-leg matrix) passes -> `Build distributions` runs -> `Validate distributions` and `Generate changelog` run in parallel -> `Publish to PyPI` runs -> `Create GitHub Release` runs. Result: package appears at `pypi.org/p/pytest-adbc-replay`, GitHub Release created as published (non-draft) with git-cliff notes and `dist/*` files attached.
**Why human:** Requires real tag push, configured PyPI environment with OIDC trusted publisher, and GitHub repository with proper permissions. Cannot be verified offline.

### Gaps Summary

The entire publishing automation infrastructure is implemented and correctly wired:

- `_test.yml` exists as a real, substantive reusable workflow with the full 3.11-3.14 matrix and complete quality gate steps (no stub)
- All three callers (`ci.yml`, `pr.yml`, `release.yml`) correctly reference it via `uses: ./.github/workflows/_test.yml`
- `docs.yml` has the tag trigger added with the `--strict` flag preserved
- `pyproject.toml` has the 3.14 classifier
- `release.yml` has the complete job chain, fixed cookiecutter bug, OIDC PyPI publish, and GitHub Release creation
- All 9 commits are verified in git history

The single gap is a **documentation tracking issue only**: REQUIREMENTS.md line 82 still shows `- [ ] **PUB-02**` (unchecked) and the traceability table at line 175 still shows `PUB-02 | Phase 7 | Pending`. The version matrix text was updated correctly (plan 07-01 task 4, commit `e289ddc`) but the plan did not include marking the requirement as complete — that is a separate action. The implementation fully satisfies PUB-02; only the tracking markers need updating.

This is a low-impact gap (documentation only, no code change required) but must be resolved to keep REQUIREMENTS.md accurate as the project source of truth.

---

_Verified: 2026-03-01T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
