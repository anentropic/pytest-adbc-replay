# Milestones

## v1.0.0a2 Foundry & Pool Support (Shipped: 2026-03-08)

**Phases completed:** 3 phases, 6 plans, 13 tasks

**Key accomplishments:**
- `cassette_differentiator_keys` ini key for Foundry driver shared-module path disambiguation
- Test reorganization into `tests/unit/` + `tests/integration/` split
- Integration tests with real Foundry MySQL driver via testcontainers + CI workflow
- `adbc_clone()` on `ReplayConnection` for connection pool support (shared cassette, shared wipe state)
- Shared `_wipe_state` dict refactor preventing double-wipe across pool clones in `all` mode
- Full Diataxis documentation for connection pooling (how-to guide, reference page, explanation article, fixtures.md update)

**Git range:** 2026-03-02 → 2026-03-08 (43 commits, 148 files, +6062/-305 lines)
**Source:** 1,861 Python LOC (src/)

---

## v1.0.0a1 Initial Release (Shipped: 2026-03-02)

**Phases completed:** 10 phases, 28 plans, 6 tasks

**Key accomplishments:**
- Installable pytest plugin with cursor proxy implementing the full ADBC protocol — replay works without any driver installed
- Record/replay engine: Arrow IPC cassette storage, sqlglot SQL normalisation, all four record modes (none/once/new_episodes/all), ordered-queue replay
- pyproject.toml/pytest.ini configuration, pytest header output, pytester E2E integration tests against adbc-driver-sqlite
- Complete PyPI metadata, py.typed PEP 561 marker, explicit `__all__`, GitHub Actions CI + publish-on-tag + GitHub Pages deployment
- Full diataxis-structured MkDocs documentation site (Tutorial, How-To, Reference, Explanation) with humanizer-polished prose
- Automatic ADBC wrapping via `adbc_auto_patch` ini key — no conftest boilerplate needed; per-driver cassette subdirectories
- Sensitive-data scrubbing: `adbc_scrub_keys` ini config + `adbc_scrubber` fixture with per-driver conditional logic
- Per-driver SQL dialect config via `adbc_dialect` linelist (`adbc_driver_snowflake: snowflake` pattern)

**Git range:** 2026-02-28 → 2026-03-02 (130 commits, 150 files, +26870/-81 lines)
**Source:** 1,719 Python LOC (src/)

---

