# Phase 7: Publishing Automation - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

GitHub Actions workflows that make releasing the package safe and automatic: CI test matrix on every push and PR, PyPI publish on version tag, GitHub Release creation on version tag, and GitHub Pages docs deployment on version tag and main-branch push. No new product features — only automation infrastructure.

</domain>

<decisions>
## Implementation Decisions

### Python version matrix
- Test matrix: Python 3.11, 3.12, 3.13, 3.14
- All legs are required-to-pass (no allowed-to-fail)
- 3.10 is unsupported (requires-python = ">=3.11"); REQUIREMENTS.md item saying "3.10, 3.11, 3.12" needs updating
- CI runs on both `push` and `pull_request` events

### Docs deployment trigger
- Deploy to GitHub Pages on **both** main-branch push (current) and tag push (new, per PUB-04)
- `--strict` flag used in both triggers — warnings fail the build
- Current docs.yml already handles main-push; add tag trigger on top of it

### GitHub Release creation
- Pushing a `v*.*.*` tag creates a **published** (not draft) GitHub Release automatically
- Release notes sourced from git-cliff (cliff.toml already exists in repo)
- Release only proceeds after quality gates pass (see DRY gate below)

### Quality gate before release (DRY)
- Extract the quality gate steps (lint + tests) into a **reusable workflow** (`workflow_call`) so both `ci.yml` and `release.yml` call the same logic without duplication
- Release workflow jobs for build, validate, publish, GitHub Release creation all depend on the quality gate job completing successfully

### PR CI scope
- PRs run the full 3.11–3.14 test matrix (same reusable workflow as push CI)
- Coverage report still posted as a PR comment (separate job in pr.yml or combined)
- Branch protection rules should require the CI check to pass before merging (configured in GitHub Settings — not a workflow file task)

### Claude's Discretion
- Exact reusable workflow file name and structure (e.g., `_test.yml` or `test.yml`)
- Whether coverage is a separate workflow or merged into ci.yml
- Exact GitHub Release action to use (e.g., `softprops/action-gh-release`)
- Artifact retention days and naming

</decisions>

<specifics>
## Specific Ideas

- "DRY" is a hard requirement: quality gate steps (lint + tests) must not be duplicated between CI and release workflows — use `workflow_call` reusable workflow
- The release workflow should be clearly gated: nothing publishes until quality passes

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ci.yml`: Runs on all pushes, matrix 3.11+3.14, quality gates (prek) + tests — needs matrix update and PR trigger added
- `pr.yml`: Coverage report on PRs (single Python version) — needs matrix test added
- `release.yml`: Tag-triggered, build + validate + changelog + PyPI publish — has a leftover cookiecutter template bug (`import {{ cookiecutter.package_name }}`) in the validate job; does not create GitHub Release; does not have a quality gate
- `docs.yml`: Main-push triggered, GitHub Pages deployment — needs tag trigger added
- `weekly.yml`: Weekly latest-deps compatibility check — no changes needed
- `dependabot.yml`: Keeps GitHub Actions and pip deps updated — no changes needed
- `cliff.toml`: git-cliff configuration already in repo root — use for GitHub Release notes
- `pyproject.toml`: `requires-python = ">=3.11"`, classifiers list 3.11, 3.12, 3.13 — update classifiers to include 3.14

### Established Patterns
- All workflows use `astral-sh/setup-uv@v7` and `uv sync --locked` for dependency management
- `prek run --all-files` is the quality gate command
- `uv run pytest` is the test command
- Trusted publisher (OIDC) already configured for PyPI via `pypa/gh-action-pypi-publish@release/v1`

### Integration Points
- Reusable workflow needs `on: workflow_call` — called by `ci.yml`, `pr.yml`, and `release.yml`
- GitHub Release creation needs `contents: write` permission
- Docs deployment already has `pages: write` and `id-token: write` permissions in `docs.yml`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 07-publishing-automation*
*Context gathered: 2026-03-01*
