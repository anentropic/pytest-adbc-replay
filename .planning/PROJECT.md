# pytest-adbc-replay

## What This Is

`pytest-adbc-replay` is a pytest plugin for record/replay testing of ADBC database connections. It intercepts queries at the ADBC cursor level, records results to cassette files (Arrow IPC + pretty-printed SQL + JSON parameters), and replays them in subsequent test runs — eliminating the need for live cloud warehouse access (Snowflake, Databricks, BigQuery, etc.) in CI. It supports automatic driver patching via `adbc_auto_patch`, sensitive-data scrubbing via `adbc_scrub_keys` and `adbc_scrubber`, and per-driver SQL dialect configuration. It is designed to pair with `pytest-recording` (VCR.py wrapper) in projects that use both HTTP APIs and ADBC connections.

## Core Value

CI tests pass without warehouse credentials — record once locally, replay everywhere, with query changes visible as plain diffs in PRs.

## Requirements

### Validated

- ✓ Installable plugin discoverable via `pytest11` entry point — v1.0.0a1 (Phase 1)
- ✓ `--adbc-record=<mode>` CLI flag, `adbc_replay` fixture, `@pytest.mark.adbc_cassette` marker — v1.0.0a1 (Phase 1)
- ✓ Full cursor proxy protocol (`execute`, `fetch_arrow_table`, `fetchall`, `fetchone`, `fetchmany`, `description`, `rowcount`, context manager) — v1.0.0a1 (Phase 1)
- ✓ Cassette storage: directory-per-test, numbered `.sql`/`.arrow`/`.json` interaction files — v1.0.0a1 (Phase 2)
- ✓ SQL normalisation via sqlglot with fallback — v1.0.0a1 (Phase 2)
- ✓ All four record modes (`none`, `once`, `new_episodes`, `all`) — v1.0.0a1 (Phase 2)
- ✓ `pyproject.toml`/`pytest.ini` configuration (`adbc_cassette_dir`, `adbc_record_mode`, `adbc_dialect`) — v1.0.0a1 (Phase 3)
- ✓ Pytest header shows active record mode — v1.0.0a1 (Phase 3)
- ✓ Pytester E2E integration test against adbc-driver-sqlite — v1.0.0a1 (Phase 3)
- ✓ README with full user documentation ready for PyPI — v1.0.0a1 (Phase 5)
- ✓ PyPI metadata complete (classifiers, URLs, license, keywords) — v1.0.0a1 (Phase 4)
- ✓ GitHub Actions CI (multi-Python matrix) and publish-on-tag workflows — v1.0.0a1 (Phase 7)
- ✓ CHANGELOG.md for v1.0.0 — v1.0.0a1 (Phase 5)
- ✓ `py.typed` marker and `__all__` on public API exports — v1.0.0a1 (Phase 4)
- ✓ Full diataxis-structured MkDocs documentation site — v1.0.0a1 (Phase 6)
- ✓ GitHub Pages deployment on tag push — v1.0.0a1 (Phase 7)
- ✓ Automatic ADBC wrapping via `adbc_auto_patch` ini key (no conftest boilerplate) — v1.0.0a1 (Phase 8)
- ✓ `adbc_connect` function-scoped fixture as escape hatch for session-scoped connections — v1.0.0a1 (Phase 8)
- ✓ `adbc_scrub_keys` ini linelist for config-driven sensitive-data scrubbing — v1.0.0a1 (Phase 9)
- ✓ `adbc_scrubber` fixture with `(params, driver_name)` signature for per-driver scrubbing logic — v1.0.0a1 (Phase 9)
- ✓ `adbc_dialect` as per-driver linelist (`adbc_driver_snowflake: snowflake` pattern) — v1.0.0a1 (Phase 10)

### Active

(None — no active milestone. Define requirements via `/gsd:new-milestone`.)

### Out of Scope

- HTTP recording — use `pytest-recording` for that
- Query correctness validation — cassettes record whatever the live backend returned
- DBAPI2 support — v1 is ADBC only; architecture should not preclude it later
- `SCRUB-02` — callback to scrub Arrow result data (v2 consideration; cassette results are already not plain text)
- Cassette format versioning / migration tooling — v2 consideration
- Cassette miss diff highlighting — v2 consideration

## Context

- **Domain**: pytest plugin ecosystem; mirrors `pytest-recording` / VCR.py conventions
- **Shipped**: v1.0.0a1 — 10 phases, 28 plans, 130 commits, 150 files, 1,719 Python LOC
- **Tech stack**: Python; `pyarrow` (Arrow IPC), `sqlglot` (SQL normalisation), `adbc-driver-manager` (type references), `pytest` — no other core dependencies
- **Why ADBC cursor interception**: VCR.py intercepts HTTP but warehouse connectors vendor their own HTTP libraries, making interception fragile. ADBC cursor interface is uniform, stable, and narrow — the right seam.
- **Key prior art**: `pytest-recording` (model for UX), `snowflake-vcrpy` (avoided due to vendoring conflicts and Snowflake-only scope)
- **Design document**: `_notes/pytest-adbc-replay-design.md`

## Constraints

- **Tech stack**: Python; `pyarrow`, `sqlglot`, `adbc-driver-manager`, `pytest` — no other core dependencies
- **Driver independence**: Specific ADBC drivers (snowflake, databricks, etc.) are provided by consuming projects, not this plugin
- **No vendoring**: Cannot vendor dependencies (avoids the `snowflake-vcrpy` problem)
- **Cassette format**: Arrow IPC (not Parquet) — preserves schema metadata precisely, no extra dependency

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Intercept at ADBC cursor, not HTTP | HTTP layer is fragile due to vendored urllib3 in warehouse connectors | ✓ Good — clean seam, works across all drivers |
| Arrow IPC for cassette results | Precise schema metadata; no extra dependency beyond pyarrow | ✓ Good — round-trips cleanly, schema preserved |
| sqlglot for SQL normalisation | Handles keyword casing/whitespace/quote normalisation; likely in dbt-adjacent dependency trees | ✓ Good — fallback to whitespace-strip when parse fails |
| Directory-per-cassette with numbered files | Human-readable `.sql` files make query changes visible as PR diffs | ✓ Good — core value prop delivered |
| Mirror pytest-recording conventions | Consistent mental model for projects using both plugins | ✓ Good — fixture/marker names feel natural |
| `cast('str|None', config.getoption())` | basedpyright strict mode compliance with pytest config accessors | ✓ Good — no type suppressions needed |
| `--adbc-record` default is `None` sentinel (not `"none"`) | Enables detection of explicit CLI flag vs ini-configured default | ✓ Good — correct precedence behaviour |
| E2E test uses adbc_driver_sqlite.dbapi | Self-contained; two sequential `runpytest` calls prove cassette persists between sessions | ✓ Good |
| `__all__` = four names (CassetteMissError, NormalisationWarning, NO_DEFAULT_SERIALISERS, ReplaySession) | ReplayConnection/ReplayCursor are implementation details | ✓ Good |
| DuckDB for README quick-start example | Self-contained, no credentials — readers can run immediately | ✓ Good |
| cliff.toml filters to feat/fix only | Suppresses GSD planning workflow commit noise | ✓ Good |
| OIDC trusted publisher for PyPI | No stored secrets in CI | ✓ Good — standard approach |
| softprops/action-gh-release@v2 for GitHub Release | Standard action; creates release with dist files + changelog notes | ✓ Good |
| `adbc_auto_patch` as linelist ini key | Supports multiple drivers with one config block; consistent with scrub_keys pattern | ✓ Good — zero-conftest primary path |
| `connect_fn` param on ReplayConnection | Prevents infinite recursion when auto-patch has replaced `driver.connect` | ✓ Good — clean solution |
| `_auto_patch_state` dict container (not module globals) | Avoids basedpyright `reportConstantRedefinition` on reassignment | ✓ Good |
| Eager ReplaySession init in pytest_sessionstart | auto-patch works even before `adbc_replay` fixture is requested | ✓ Good |
| `adbc_scrub_keys` as linelist (colon = per-driver, no colon = global) | Consistent with adbc_auto_patch pattern; additive per-line semantics | ✓ Good |
| Scrubbing pipeline: config-scrub first, then fixture | Fixture receives already-scrubbed params; can add additional logic without duplicating | ✓ Good |
| `adbc_scrubber` two-arg signature: `(params, driver_name)` | Per-driver conditional logic inside one fixture without separate fixtures | ✓ Good |
| REDACTED sentinel (fixed string) | Simple, predictable; no config knob needed | ✓ Good |
| `adbc_dialect` as linelist with per-driver colon syntax | Consistent pattern across all per-driver ini keys | ✓ Good |
| marker `dialect=` reframed as escape hatch | Per-driver ini is the correct primary workflow; per-test marker is rarely needed | ✓ Good |

---
*Last updated: 2026-03-02 after v1.0.0a1 milestone*
