# Milestones

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

