# Phase 10: per-driver adbc_dialect config and dialect docs review - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform `adbc_dialect` from a global string ini key into a per-driver linelist (matching the `adbc_scrub_keys` pattern). Update all affected documentation to tell a new story: auto-detect is the default, per-driver ini config is the recommended override path, and `dialect=` on the `adbc_cassette` marker is an edge-case escape hatch — not the primary workflow.

</domain>

<decisions>
## Implementation Decisions

### Config format
- `adbc_dialect` keeps the same key name but changes `type` from `"string"` to `"linelist"` (matching `adbc_scrub_keys`)
- Line format: bare value (no colon) = global fallback; `driver_name: dialect` = per-driver override
- Mirrors `adbc_scrub_keys` parsing pattern — both global and per-driver forms coexist
- Documentation must show both `pytest.ini` linelist syntax and the TOML array equivalent for `pyproject.toml`

```ini
# pytest.ini
adbc_dialect =
    snowflake               ; global fallback
    adbc_driver_duckdb: duckdb  ; per-driver override
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
adbc_dialect = [
    "snowflake",
    "adbc_driver_duckdb: duckdb",
]
```

### Backward compatibility
- Project is unreleased — no migration path, deprecation warning, or silent compat needed
- Just change the implementation cleanly

### Marker dialect= fate
- Keep the `dialect=` argument on `@pytest.mark.adbc_cassette` in code — it still works
- Reframe in docs as an escape hatch, not a primary workflow
- The documented use case: overriding auto-detect for one specific test where the query trips up auto-detect, even though the driver's global dialect is set correctly
- Per-driver ini config is the recommended path; marker `dialect=` is a footnote

### Claude's Discretion
- Exact `_parse_dialect` function naming and structure (mirror `_parse_scrub_keys` pattern)
- Where in `ReplaySession.__init__` and `wrap()` per-driver dialect lookup logic sits
- Priority chain implementation: `wrap(dialect=)` > marker `dialect=` > per-driver ini > global ini > None

</decisions>

<specifics>
## Specific Ideas

- The parsing logic should follow `_parse_scrub_keys()` as closely as possible — the user wants consistent patterns across the plugin
- Per-driver dialect lookup in `ReplaySession.wrap()` should use the `driver_module_name` to find the per-driver value, falling back to global, then None (same priority resolution as scrub_keys)
- Docs narrative arc: "Auto-detect works for standard SQL. If your driver needs a specific dialect, configure it per-driver in your ini file. Only use the marker as a last resort for unusual per-test cases."

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_parse_scrub_keys()` in `plugin.py:117` — direct template for the new `_parse_dialect()` function. Same colon-prefix linelist format.
- `ReplaySession` in `_session.py` — stores `dialect: str | None` (global) and `scrub_keys_global/scrub_keys_per_driver` (split). Will need `dialect_global: str | None` and `dialect_per_driver: dict[str, str]`.
- `_build_session_from_config()` in `plugin.py:149` — needs updating to call new parse function and pass split values to ReplaySession.
- `adbc_replay` fixture at `plugin.py:340` — also calls `config.getini("adbc_dialect")` and builds a session; needs same update as `_build_session_from_config`.

### Established Patterns
- `adbc_scrub_keys` linelist: global lines + `driver: values` per-driver lines. Parsed by `_parse_scrub_keys()` into `(list, dict)`. Same pattern applies to dialect.
- Priority chain in `ReplaySession.wrap()`: explicit arg > marker > session-level fallback. For dialect, session-level fallback will change from a single `str | None` to a per-driver lookup using `driver_module_name`.

### Integration Points
- `parser.addini("adbc_dialect")` in `plugin.py:71` — change `type="string"` to `type="linelist"`, update help text
- `ReplaySession.__init__` — replace `dialect: str | None` with `dialect_global: str | None` and `dialect_per_driver: dict[str, str]`
- `ReplaySession.wrap()` — resolve dialect by checking `dialect_per_driver.get(driver_module_name)`, then `dialect_global`, then `None`
- `ReplaySession.connect()` (auto-patch path at `_session.py:146`) — same resolution logic
- Docs pages: `configure-via-ini.md`, `reference/configuration.md`, `reference/markers.md`, `explanation/sql-normalisation-design.md`, `how-to/multiple-drivers.md`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 10-per-driver-adbc-dialect-config-and-dialect-docs-review*
*Context gathered: 2026-03-02*
