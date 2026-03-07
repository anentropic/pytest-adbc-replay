# Roadmap: pytest-adbc-replay

## Milestones

- ✅ **v1.0.0a1 Initial Release** — Phases 1-10 (shipped 2026-03-02)

## Phases

<details>
<summary>✅ v1.0.0a1 Initial Release (Phases 1-10) — SHIPPED 2026-03-02</summary>

- [x] Phase 1: Plugin Skeleton and Cursor Proxy (3/3 plans) — completed 2026-02-28
- [x] Phase 2: Record/Replay Engine (4/4 plans) — completed 2026-02-28
- [x] Phase 3: Configuration, DX, and Integration Testing (2/2 plans) — completed 2026-03-01
- [x] Phase 4: Type Exports and PyPI Metadata (1/1 plan) — completed 2026-03-01
- [x] Phase 5: README and CHANGELOG (1/1 plan) — completed 2026-03-01
- [x] Phase 6: MkDocs Documentation Site (5/5 plans) — completed 2026-03-01
- [x] Phase 7: Publishing Automation (3/3 plans) — completed 2026-03-01
- [x] Phase 8: Automatic ADBC Wrapping (3/3 plans) — completed 2026-03-02
- [x] Phase 9: Scrubber Interface (3/3 plans) — completed 2026-03-02
- [x] Phase 10: Per-driver Dialect Config (3/3 plans) — completed 2026-03-02

</details>

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Plugin Skeleton and Cursor Proxy | v1.0.0a1 | 3/3 | Complete | 2026-02-28 |
| 2. Record/Replay Engine | v1.0.0a1 | 4/4 | Complete | 2026-02-28 |
| 3. Configuration, DX, Integration Testing | v1.0.0a1 | 2/2 | Complete | 2026-03-01 |
| 4. Type Exports and PyPI Metadata | v1.0.0a1 | 1/1 | Complete | 2026-03-01 |
| 5. README and CHANGELOG | v1.0.0a1 | 1/1 | Complete | 2026-03-01 |
| 6. MkDocs Documentation Site | v1.0.0a1 | 5/5 | Complete | 2026-03-01 |
| 7. Publishing Automation | v1.0.0a1 | 3/3 | Complete | 2026-03-01 |
| 8. Automatic ADBC Wrapping | v1.0.0a1 | 3/3 | Complete | 2026-03-02 |
| 9. Scrubber Interface | v1.0.0a1 | 3/3 | Complete | 2026-03-02 |
| 10. Per-driver Dialect Config | v1.0.0a1 | 3/3 | Complete | 2026-03-02 |

_Full phase details archived to `.planning/milestones/v1.0.0a1-ROADMAP.md`_

### Phase 1: Test compatibility with ADBC Foundry drivers

**Goal:** Verify pytest-adbc-replay works with ADBC Foundry drivers (Go-based drivers via adbc_driver_manager.dbapi). Add cassette_differentiator_keys for shared-module path disambiguation, reorganize tests into unit/integration split, and create integration tests with real Foundry MySQL driver via testcontainers.
**Requirements**: TBD
**Depends on:** Phase 0
**Plans:** 3/3 plans complete

Plans:
- [x] 01-01-PLAN.md — Cassette differentiator keys feature (ini key, session/path threading, unit tests)
- [x] 01-02-PLAN.md — Test directory reorganization (tests/ to tests/unit/ + tests/integration/)
- [x] 01-03-PLAN.md — Foundry MySQL integration tests and CI workflow

### Phase 2: Pool clone support for ReplayConnection

**Goal:** Implement `adbc_clone()` on `ReplayConnection` so that connection pooling consumers (like adbc-poolhouse) can use cassette replay. Refactor per-cursor `_wiped` flag into a shared `_wipe_state` container threaded from connection to cursor, then add the `adbc_clone()` method that creates clones sharing config, cassette path, and wipe state.
**Requirements**: CLONE-01, CLONE-02, CLONE-03, CLONE-04, CLONE-05, CLONE-06, CLONE-07, CLONE-08, CLONE-09
**Depends on:** Phase 1
**Plans:** 1/1 plans complete

Plans:
- [x] 02-01-PLAN.md — TDD: shared wipe state refactor + adbc_clone() implementation with unit tests
