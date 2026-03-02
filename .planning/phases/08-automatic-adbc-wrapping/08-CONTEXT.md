# Phase 8: Automatic ADBC Wrapping - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminate the explicit `adbc_replay.wrap()` conftest fixture boilerplate. Users configure which ADBC driver modules to auto-patch in `pyproject.toml`, apply `@pytest.mark.adbc_cassette` to their tests, and call `driver.connect()` normally — the plugin intercepts the call and returns a `ReplayConnection` transparently. An `adbc_connect` factory fixture is also shipped as an escape hatch for session/module-scoped connections.

This phase does not change cassette format, record modes, SQL normalisation, or any other plugin behaviour — only the connection wiring surface.

</domain>

<decisions>
## Implementation Decisions

### Interception mechanism
- Primary mechanism: monkeypatch `adbc_driver_X.dbapi.connect()` at pytest session start for each driver listed in `adbc_auto_patch`
- Plugin tracks the currently-running test item via `pytest_runtest_setup` / `pytest_runtest_teardown` hooks; the patched `connect()` reads that item to resolve cassette path and marker
- Plugin auto-closes all connections opened during a test in `pytest_runtest_teardown`
- Escape hatch: ship an `adbc_connect` factory fixture that handles `request` injection internally (simpler than current `adbc_replay.wrap()` but still explicit)
- Session/module-scoped connections MUST use `adbc_connect` — monkeypatching is intentionally scoped to function-level test items only; no fallback, no warning, this is documented as the contract

### Driver configuration
- New ini key: `adbc_auto_patch` — space-separated list of driver module names
  ```toml
  [tool.pytest.ini_options]
  adbc_auto_patch = "adbc_driver_snowflake adbc_driver_duckdb"
  ```
- Multiple drivers supported; each is patched independently
- User still passes real `db_kwargs` to `connect()` in their code — plugin forwards them to the real driver in record mode, ignores them in replay mode
- No stripping of sensitive kwargs — plain forward

### Opt-in / opt-out
- Marker-gated: the monkeypatch only activates interception for tests with `@pytest.mark.adbc_cassette`
- Tests without the marker: `connect()` passes through to the real driver unchanged (monkeypatch intercepts the call but checks for the marker, then calls the original if absent)
- Matches VCR.py / pytest-recording convention — users already familiar with this pattern

### Multi-driver cassette layout
- Always use per-driver subdirectories, even for single-driver tests
- Format: `{cassette_dir}/{cassette_name}/{driver_module_name}/{interaction_number}.*`
  - Example: `tests/cassettes/test_query/adbc_driver_snowflake/000.sql`
- Full module name used as the subdirectory name (not shortened)
- This replaces the current flat layout (`cassette/my_test/000...`) for auto-wrapped connections
- Cassettes recorded with the old `adbc_replay.wrap()` approach retain the flat layout (the `adbc_connect` escape hatch also uses per-driver subdirs for consistency)

### Documentation updates (required as part of this phase)
- README quick-start must show the new `adbc_auto_patch` ini key + zero-conftest example
- MkDocs Tutorial must be updated to use the new approach (currently shows `adbc_replay.wrap()`)
- MkDocs How-To guides must be updated: `how-to/index.md` prerequisite, `how-to/multiple-drivers.md` examples
- MkDocs Reference — fixtures section must document `adbc_connect` factory fixture and `adbc_auto_patch` ini key
- MkDocs site index (`docs/src/index.md`) quick-start snippet updated
- `adbc_replay.wrap()` and the manual conftest pattern remain valid and documented as the explicit/escape-hatch path

### Claude's Discretion
- Exact pytest hook ordering (whether `pytest_runtest_call` or `pytest_runtest_setup` is better for item tracking)
- Internal data structure for tracking open connections per test
- Whether to use `monkeypatch` fixture or direct `sys.modules` manipulation for patching
- Error message wording when `connect()` is called outside test scope with a patched driver

</decisions>

<specifics>
## Specific Ideas

- The `adbc_connect` factory fixture should have a simpler call signature than `adbc_replay.wrap()`: `adbc_connect("adbc_driver_snowflake", uri=..., token=...)` using `**db_kwargs` rather than `db_kwargs={}` dict literal
- The `@pytest.mark.adbc_cassette` marker continues to control cassette name and dialect — no new marker needed
- VCR.py / pytest-recording is the explicit design precedent for the opt-in behaviour

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ReplaySession.wrap()` (`_session.py`): already handles cassette path resolution from node ID and marker — the monkeypatch path will call a variant of this using a stored current item instead of `request`
- `_cassette_path.node_id_to_cassette_path()`: derives cassette path from node ID — will need extending to support per-driver subdirectory layout
- `ReplayConnection` (`_connection.py`): already receives `driver_module_name`, `db_kwargs`, `mode`, `cassette_path` — no interface changes needed
- `plugin.py` `pytest_report_header`: pattern to follow for new session hooks

### Established Patterns
- Session-scoped `adbc_replay` fixture wires config from ini and CLI — new `adbc_auto_patch` ini key follows the same pattern as `adbc_record_mode` / `adbc_cassette_dir`
- `ReplayConnection` already guards driver import behind `if mode != "none"` — the monkeypatch path must preserve this guarantee (in replay mode the real driver is never imported)
- `adbc_cassette` marker is already registered in `pytest_configure` — marker-gated activation reuses it unchanged

### Integration Points
- `plugin.py`: add `pytest_addoption`/`pytest_configure` for `adbc_auto_patch`, add `pytest_runtest_setup`/`pytest_runtest_teardown` hooks for item tracking and connection cleanup
- `_session.py`: add method for use by patched `connect()` that accepts a pytest item rather than a `request` object
- `_cassette_path.py`: extend to support optional driver subdir in the path hierarchy

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-automatic-adbc-wrapping*
*Context gathered: 2026-03-02*
