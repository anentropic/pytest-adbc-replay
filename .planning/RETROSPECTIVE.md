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

## Milestone: v1.0.0a2 — Foundry & Pool Support

**Shipped:** 2026-03-08
**Phases:** 3 | **Plans:** 6 | **Timeline:** 6 days (2026-03-02 → 2026-03-08)

### What Was Built

- `cassette_differentiator_keys` ini key for Foundry driver shared-module path disambiguation
- Test directory reorganization: `tests/` split into `tests/unit/` + `tests/integration/`
- Integration tests with real Foundry MySQL driver via testcontainers (Docker-managed lifecycle)
- `ReplayConnection.adbc_clone()` for connection pool support -- shared cassette path, shared wipe state across clones
- Shared `_wipe_state` dict refactor preventing double-wipe across pool clones in `all` mode
- Connection pooling documentation: how-to guide, reference page, explanation article with mermaid lifecycle diagram

### What Worked

- **TDD for adbc_clone()**: Writing tests before the implementation made the shared-wipe-state behavior trivially correct on first attempt. The `__new__` bypass pattern was discovered during implementation rather than design.
- **Informal milestone**: Skipping `/gsd:new-milestone` and just adding phases manually worked fine for a small, focused milestone. The formal requirements ceremony would have been overhead for 3 phases.
- **Auto-advance pipeline**: Using `--auto` to chain plan → execute → verify in one pass reduced manual intervention. All three phases completed without needing manual checkpoints.
- **Humanizer on docs**: Caught a redundant section and a few word choices ("mirrors" → "follows") that would have looked AI-generated.

### What Was Inefficient

- **No formal REQUIREMENTS.md**: Without requirements, the milestone had no traceability. The CLONE-* and DOC-* requirement IDs were defined ad-hoc in plans rather than tracked centrally. This worked because the scope was small, but would not scale.
- **Phase 1 integration tests took ~20min**: The testcontainers + Foundry driver setup involved a human-verify checkpoint for Docker availability. This was the only phase that needed manual intervention.

### Patterns Established

- **`__new__` bypass for clone creation**: When creating objects that share state with a source but must not trigger `__init__` side effects (like driver imports), use `cls.__new__(cls)` and copy attributes manually.
- **Shared mutable dict for cross-object coordination**: A shared `{"wiped": False}` dict referenced by multiple objects provides simple coordination without coupling. Each object checks and updates the same dict reference.
- **testcontainers for integration testing**: Docker container lifecycle managed by the test framework, not CI services. Tests are self-contained and run locally the same as in CI.

### Key Lessons

1. **Informal milestones work for small focused work** -- 3 phases with clear goals don't need the full requirements ceremony. But traceability suffers.
2. **Auto-advance is worth the setup** -- chaining plan → execute → verify for a docs-only phase saved several `/clear` and manual invocation cycles.
3. **Integration tests with real databases are worth the Docker overhead** -- the Foundry MySQL tests caught a real cassette path issue that unit tests would have missed.

### Cost Observations

- Model mix: quality profile (opus for execution, sonnet for verification)
- Sessions: ~3-4 sessions across 6 days (intermittent work)
- Notable: Phase 3 (docs) completed in ~10min total execution time despite 2 plans and 5 tasks -- established patterns made content generation fast

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Timeline | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0.0a1 | 3 days | 10 | Initial project — established all core patterns |
| v1.0.0a2 | 6 days | 3 | Foundry compat + connection pooling — informal milestone, auto-advance pipeline |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0.0a1 | 188+ | unknown | 0 (pyarrow/sqlglot already required) |
| v1.0.0a2 | 200+ | unknown | 0 (testcontainers is dev-only) |

### Top Lessons (Verified Across Milestones)

1. Linelist ini keys provide a consistent per-driver configuration model
2. Set the release version once at packaging phase, don't drift
3. TDD works well for shared-state features (scrubbing pipeline in a1, wipe state in a2)
4. Humanizer on docs catches patterns that erode trust in documentation quality

