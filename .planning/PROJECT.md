# pytest-adbc-replay

## What This Is

`pytest-adbc-replay` is a pytest plugin for record/replay testing of ADBC database connections. It intercepts queries at the ADBC cursor level, records results to cassette files, and replays them in subsequent test runs — eliminating the need for live cloud warehouse access (Snowflake, Databricks, BigQuery, etc.) in CI. It is designed to pair with `pytest-recording` (VCR.py wrapper) in projects that use both HTTP APIs and ADBC connections.

## Core Value

CI tests pass without warehouse credentials — record once locally, replay everywhere, with query changes visible as plain diffs in PRs.

## Current Milestone: v1.0.0 Docs and Publishing Polish

**Goal:** Make the plugin publicly releasable on PyPI with complete documentation, publishing automation, and proper type exports

**Target features:**
- README with installation, usage, record modes, configuration, and cassette format examples
- PyPI metadata + GitHub Actions CI and publish-on-tag workflows
- CHANGELOG.md documenting v1.0.0
- `py.typed` marker and explicit public API exports

## Requirements

### Validated

- ✓ Installable plugin discoverable via `pytest11` entry point — Phase 1
- ✓ `--adbc-record=<mode>` CLI flag, `adbc_replay` fixture, `@pytest.mark.adbc_cassette` marker — Phase 1
- ✓ Full cursor proxy protocol (`execute`, `fetch_arrow_table`, `fetchall`, `fetchone`, `fetchmany`, `description`, `rowcount`, context manager) — Phase 1
- ✓ Cassette storage: directory-per-test, numbered `.sql`/`.arrow`/`.json` interaction files — Phase 2
- ✓ SQL normalisation via sqlglot with fallback — Phase 2
- ✓ All four record modes (`none`, `once`, `new_episodes`, `all`) — Phase 2
- ✓ `pyproject.toml`/`pytest.ini` configuration (`adbc_cassette_dir`, `adbc_record_mode`, `adbc_dialect`) — Phase 3
- ✓ Pytest header shows active record mode — Phase 3
- ✓ Scrubber hook stub — Phase 3
- ✓ Pytester E2E integration test against adbc-driver-sqlite — Phase 3

### Active

- [ ] README with full user documentation ready for PyPI
- [ ] PyPI metadata complete (classifiers, URLs, license, keywords)
- [ ] GitHub Actions CI (multi-Python matrix) and publish-on-tag workflows
- [ ] CHANGELOG.md for v1.0.0
- [ ] `py.typed` marker and `__all__` on public API exports

### Out of Scope

- HTTP recording — use `pytest-recording` for that
- Query correctness validation — cassettes record whatever the live backend returned
- DBAPI2 support — v1 is ADBC only; architecture should not preclude it later
- Sensitive data scrubbing hooks — v2 consideration
- Cassette format versioning / migration tooling — v2 consideration

## Context

- **Domain**: pytest plugin ecosystem; mirrors `pytest-recording` / VCR.py conventions
- **Existing code**: Initial cookiecutter structure only — `src/pytest_adbc_replay/__init__.py` is empty; `tests/` has placeholder files
- **Why ADBC cursor interception**: VCR.py intercepts HTTP but warehouse connectors vendor their own HTTP libraries, making interception fragile. ADBC cursor interface is uniform, stable, and narrow — the right seam.
- **Key prior art**: `pytest-recording` (model for UX), `snowflake-vcrpy` (avoided due to vendoring conflicts and Snowflake-only scope)
- **Design document**: `_notes/pytest-adbc-replay-design.md`

## Constraints

- **Tech stack**: Python; `pyarrow` (Arrow IPC), `sqlglot` (SQL normalisation), `adbc-driver-manager` (type references), `pytest` — no other core dependencies
- **Driver independence**: Specific ADBC drivers (snowflake, databricks, etc.) are provided by consuming projects, not this plugin
- **No vendoring**: Cannot vendor dependencies (avoids the `snowflake-vcrpy` problem)
- **Cassette format**: Arrow IPC (not Parquet) — preserves schema metadata precisely, no extra dependency

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Intercept at ADBC cursor, not HTTP | HTTP layer is fragile due to vendored urllib3 in warehouse connectors | — Pending |
| Arrow IPC for cassette results | Precise schema metadata; no extra dependency beyond pyarrow | — Pending |
| sqlglot for SQL normalisation | Handles keyword casing/whitespace/quote normalisation; likely already in dbt-adjacent dependency trees | — Pending |
| Directory-per-cassette with numbered files | Human-readable `.sql` files make query changes visible as PR diffs | — Pending |
| Mirror pytest-recording conventions | Consistent mental model for projects using both plugins | — Pending |

---
*Last updated: 2026-03-01 after v1.0.0 milestone start*
