# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0.0a1 — Initial Release

**Shipped:** 2026-03-02
**Phases:** 10 | **Plans:** 28 | **Timeline:** 3 days (2026-02-28 → 2026-03-02)

### What Was Built

- Full pytest plugin skeleton: cursor proxy implementing the complete ADBC protocol, all four record modes, cassette I/O with Arrow IPC and pretty-printed SQL
- pyproject.toml/pytest.ini configuration, pytest header output, pytester E2E integration tests against adbc-driver-sqlite
- Complete PyPI packaging: py.typed, `__all__`, classifiers, OIDC publish workflow, GitHub Release automation, GitHub Pages deployment
- Full diataxis-structured MkDocs documentation site (Tutorial, How-To, Reference, Explanation) with humanizer-polished prose
- Automatic ADBC wrapping via `adbc_auto_patch` — zero conftest boilerplate as the primary path
- Sensitive-data scrubbing via `adbc_scrub_keys` (config-driven) and `adbc_scrubber` (fixture-driven) with per-driver conditional logic
- Per-driver SQL dialect resolution via `adbc_dialect` linelist

### What Worked

- **Linelist pattern**: Using a consistent `key: value` linelist format for per-driver ini config (`adbc_auto_patch`, `adbc_scrub_keys`, `adbc_dialect`) created a coherent mental model that users can apply uniformly
- **TDD for scrubbing**: Writing failing tests first for the scrubbing pipeline made the implementation straightforward with no regression issues
- **basedpyright strict mode discipline**: Catching type issues at implementation time (e.g., `cast()` for pytest config accessors, `_auto_patch_state` dict instead of module globals) prevented subtle bugs
- **diataxis documentation structure**: Organizing docs into Tutorial/How-To/Reference/Explanation from the start made content decisions clear — no debate about where things go
- **humanizer for docs**: Applying the humanizer skill before finishing doc phases caught AI vocabulary patterns that would undermine credibility

### What Was Inefficient

- **Audit done mid-milestone**: The audit identified real issues (version mismatch, TODO URLs) but was run before phases 8-10 were planned. Running the audit late meant some gaps were already partially resolved by the time it was acted on.
- **Version number drift**: The pyproject.toml version drifted (0.1.0 → 1.0.0a1) across multiple phases without a single clear moment of alignment. A decision at Phase 4 to set the final version would have avoided confusion.
- **CHANGELOG format mismatch**: CHANGELOG.md was hand-written for v1.0.0 but the actual package version became 1.0.0a1. git-cliff will need to regenerate it on first tag push.
- **Phase 8 scope grew**: Automatic ADBC wrapping was significantly larger (~80 min) than the initial phases (~2 min each). Better scope estimation would have split it into smaller units.

### Patterns Established

- **linelist ini keys for per-driver config**: `driver_module_name: value` syntax for any ini key that needs to be customized per ADBC driver. Consistent across auto_patch, scrub_keys, dialect.
- **zero-conftest primary path**: New features that eliminate boilerplate are shown first in quick-start and tutorial; the explicit approach is a secondary "advanced" section
- **scrubbing pipeline order**: Config-based scrubbing runs first, fixture scrubbing runs second and receives already-scrubbed params. This makes each layer independent and composable.
- **`cast('Type', config.getoption())`**: Standard pattern for basedpyright strict compliance when accessing pytest config options (which return `Any`)
- **Two-arg scrubber signature**: `(params, driver_name) -> dict | None` allows per-driver logic in a single fixture without requiring separate fixtures per driver

### Key Lessons

1. **Set the release version at Phase 4 (packaging) and don't touch it again** — the version should be decided once and all subsequent phases reference it. Version drift between phases creates audit noise.
2. **Linelist ini keys compose well** — the `key: value` per-driver pattern is worth standardizing across all per-driver config. Users learn the pattern once and apply it everywhere.
3. **Run milestone audit after all phases are complete, not mid-milestone** — an audit mid-milestone generates noise for issues that planned phases will address anyway.
4. **Keep phase plans tight** — Phase 8 grew to ~80 min vs ~2 min for earlier phases. When a phase scope grows during planning, split it rather than letting one plan carry the entire weight.

### Cost Observations

- Model mix: quality profile throughout (sonnet for all execution)
- Sessions: ~8-10 sessions across 3 days
- Notable: Documentation phases (6, 8-03, 9-03, 10-03) were disproportionately fast relative to scope — humanizer + diataxis provided clear structure that reduced iteration

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Timeline | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0.0a1 | 3 days | 10 | Initial project — established all core patterns |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0.0a1 | 188+ | unknown | 0 (pyarrow/sqlglot already required) |

### Top Lessons (Verified Across Milestones)

1. Linelist ini keys provide a consistent per-driver configuration model
2. Set the release version once at packaging phase, don't drift

