# pytest-adbc-replay

## What This Is

`pytest-adbc-replay` is a pytest plugin for record/replay testing of ADBC database connections. It intercepts queries at the ADBC cursor level, records results to cassette files, and replays them in subsequent test runs — eliminating the need for live cloud warehouse access (Snowflake, Databricks, BigQuery, etc.) in CI. It is designed to pair with `pytest-recording` (VCR.py wrapper) in projects that use both HTTP APIs and ADBC connections.

## Core Value

CI tests pass without warehouse credentials — record once locally, replay everywhere, with query changes visible as plain diffs in PRs.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Intercept ADBC cursor `execute()` calls and record results to cassette files
- [ ] Replay recorded cassettes without live warehouse access
- [ ] Support record modes: `none` (default), `once`, `new_episodes`, `all`
- [ ] Cassette format: directory per test, numbered interaction files (`.sql`, `.arrow`, optional `.json` for params/options)
- [ ] SQL normalisation via sqlglot for stable cassette keys across formatting variations
- [ ] Pytest marker `@pytest.mark.adbc_cassette` for cassette naming and dialect override
- [ ] `adbc_replay` session-scoped fixture exposing `.wrap()` for connection wrapping
- [ ] CLI flag `--adbc-record=<mode>` matching pytest-recording conventions
- [ ] Configuration via `pyproject.toml` / `pytest.ini` (cassette dir, record mode, default dialect)
- [ ] Driver-agnostic: works for any ADBC-compatible backend

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
*Last updated: 2026-02-28 after initialization*
