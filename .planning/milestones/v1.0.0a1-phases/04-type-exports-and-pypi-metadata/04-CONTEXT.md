# Phase 4: Type Exports and PyPI Metadata - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the package typed and ready for a quality PyPI listing: ship a `py.typed` marker, declare an explicit `__all__` for the public API, and complete `pyproject.toml` with classifiers, project URLs, and keywords. No new runtime behaviour — this is purely packaging and metadata.

</domain>

<decisions>
## Implementation Decisions

### Public API (`__all__`)
- Current exports are correct: `CassetteMissError`, `NormalisationWarning`, `NO_DEFAULT_SERIALISERS`, `ReplaySession`
- `ReplayConnection` and `ReplayCursor` stay private — they are implementation details, not user-facing types
- Review all private modules to confirm no additional names warrant export (e.g. check if any public-facing type aliases are missing)

### py.typed marker
- Already present at `src/pytest_adbc_replay/py.typed` — TYPE-01 is done; just verify it's included in the wheel (no exclude rules in build config)

### Package version
- Do NOT bump version in this phase — versioning (`1.0.0`) is deferred to Phase 7 (publish automation) when the package is actually released
- Keep `version = "0.1.0"` for now

### PyPI classifiers
- Development Status: `4 - Beta` (not Production/Stable — full release is Phase 7)
- Python versions: `3.11`, `3.12`, `3.13` (matching `requires-python = ">=3.11"`)
- Include `Programming Language :: Python :: 3 :: Only`
- Framework: `Framework :: Pytest` (already present)
- License: `License :: OSI Approved :: BSD License` (BSD 3-Clause confirmed from LICENSE file)
- Audience: `Intended Audience :: Developers`
- Topics: `Topic :: Software Development :: Testing`, `Topic :: Database`

### Keywords
- `pytest`, `adbc`, `database`, `testing`, `cassette`, `record`, `replay`, `vcr`, `arrow`

### Project URLs
- No remote repository URL exists yet — add placeholder keys with `TODO` values so the planner knows to fill them in (or note they should be populated before Phase 7)
- Keys to add: `Homepage`, `Source`, `Issues`, `Documentation` (docs site will exist after Phase 6)

### Claude's Discretion
- Exact ordering of classifiers in pyproject.toml
- Whether to combine `Source` and `Homepage` into a single URL if they point to the same GitHub repo

</decisions>

<specifics>
## Specific Ideas

- No specific references — standard PyPI metadata conventions apply
- Follow the pattern of well-known pytest plugins (e.g. pytest-mock, pytest-httpx) for classifier completeness

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/pytest_adbc_replay/py.typed`: already present — just needs wheel inclusion verified
- `src/pytest_adbc_replay/__init__.py`: `__all__` already defined — needs review/validation, not creation

### Established Patterns
- `pyproject.toml` uses `uv_build` backend — no `MANIFEST.in` needed; `py.typed` should be included automatically
- `basedpyright` configured in strict mode — type exports need to satisfy downstream strict type checkers

### Integration Points
- `pyproject.toml` is the single source for all metadata — no `setup.cfg` or `setup.py` to reconcile
- License file is `LICENSE` (BSD 3-Clause) — classifier must match exactly

</code_context>

<deferred>
## Deferred Ideas

- Version bump to `1.0.0` — Phase 7 (publish automation)
- Filling in real GitHub URLs — depends on repo being pushed to GitHub (before Phase 7)

</deferred>

---

*Phase: 04-type-exports-and-pypi-metadata*
*Context gathered: 2026-03-01*
