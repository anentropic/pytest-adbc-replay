---
phase: "10"
phase_name: per-driver-adbc-dialect-config-and-dialect-docs-review
status: passed
verified: "2026-03-02"
---

# Phase 10 Verification

## Goal

`adbc_dialect` ini key becomes per-driver (e.g. `adbc_driver_snowflake: snowflake`) following the same pattern as `adbc_scrub_keys`; docs explain that the default is auto-detect, per-driver config is the usual override path, and the per-test marker `dialect=` is reframed as an edge-case escape hatch rather than a primary workflow.

## Requirements Checked

| Requirement | Status | Evidence |
|-------------|--------|---------|
| DIAL-01 | PASS | `_parse_dialect()` added to plugin.py, returns `(str \| None, dict[str, str])`. Smoke checks pass. `adbc_dialect` ini registered as `type="linelist"`. |
| DIAL-02 | PASS | `ReplaySession.__init__` has `dialect_global` + `dialect_per_driver`. `wrap()` and `wrap_from_item()` resolve: explicit arg > marker > per-driver ini > global ini > None. |
| DIAL-03 | PASS | Five doc pages updated. configure-via-ini.md shows linelist syntax. configuration.md shows `linelist` type. markers.md contains "escape hatch". sql-normalisation-design.md presents per-driver ini as primary. multiple-drivers.md shows per-driver ini as the primary example. mkdocs build passes. |

## Must-Haves Verification

### DIAL-01/DIAL-02 (plan 10-01)

- [x] `adbc_dialect` ini key registered as `type="linelist"` (not `"string"`)
- [x] `_parse_dialect()` added to `plugin.py`, mirrors `_parse_scrub_keys` pattern
- [x] `_parse_dialect(["snowflake"])` returns `("snowflake", {})`
- [x] `_parse_dialect(["adbc_driver_duckdb: duckdb"])` returns `(None, {"adbc_driver_duckdb": "duckdb"})`
- [x] `_parse_dialect([])` returns `(None, {})`
- [x] `ReplaySession.dialect_global` and `ReplaySession.dialect_per_driver` attributes exist
- [x] No bare `self.dialect` references remain in `_session.py`
- [x] `wrap()` priority chain: explicit arg > marker > per-driver ini > global ini > None
- [x] `wrap_from_item()` priority chain: marker > per-driver ini > global ini > None
- [x] All 199 tests pass (188 existing + 11 new)

### DIAL-01/DIAL-02 (plan 10-02 — TDD)

- [x] `TestParseDialect`: 8 unit tests covering empty, blank, global, per-driver, mixed, multiple per-driver, last-wins, whitespace — all pass
- [x] `TestPerDriverDialect`: 3 pytester integration tests for per-driver lookup, global fallback, explicit-arg override — all pass

### DIAL-03 (plan 10-03 — Docs)

- [x] `configure-via-ini.md`: settings table shows `linelist` type; "Setting the SQL dialect" section shows per-driver ini as primary; pyproject.toml and pytest.ini linelist examples present
- [x] `reference/configuration.md`: `adbc_dialect` row type is `ini key (linelist)`, default `[]`; `adbc_dialect` subsection documents format and priority chain
- [x] `reference/markers.md`: `dialect=` description explicitly says "escape hatch" and recommends per-driver ini instead
- [x] `explanation/sql-normalisation-design.md`: section renamed to "Dialect configuration"; per-driver ini presented as primary multi-driver approach; marker dialect= is under "escape hatch" subsection
- [x] `how-to/multiple-drivers.md`: "SQL dialect per connection" section shows `adbc_dialect` linelist config as the primary example; simplified test code without `dialect=` markers shown
- [x] `mkdocs build --strict` exits 0, no new errors

## Automated Checks

```
uv run pytest tests/ -q → 199 passed
uv run basedpyright src/ → 0 errors, 0 warnings, 0 notes
uv run python -m mkdocs build --strict → Documentation built (no errors)
```

## Verdict

Status: **PASSED**

All three requirement IDs verified. Implementation is clean and consistent with the adbc_scrub_keys pattern. Documentation narrative is consistent across all five pages. Test suite expands from 188 to 199 tests with no regressions.
