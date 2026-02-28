# Phase 3: Configuration, DX, and Integration Testing - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the plugin publishable: add pyproject.toml/pytest.ini ini-config support for three keys (cassette dir, record mode, dialect), show active record mode in the pytest header, provide an empty scrubbing hook stub callable slot, and validate the full record-then-replay cycle via a pytester integration test against adbc-driver-sqlite.

Creating or changing cassette file formats, SQL normalisation, or record mode state machine logic are out of scope — those are Phase 2.

</domain>

<decisions>
## Implementation Decisions

### Ini configuration (CONF-01, CONF-02, CONF-03)
- Register three ini keys via `parser.addini()` in `pytest_addoption`:
  - `adbc_cassette_dir` (string, default `"tests/cassettes"`) — replaces hardcoded default in `plugin.py:101`
  - `adbc_record_mode` (string, default `"none"`) — fallback when `--adbc-record` CLI flag is not given
  - `adbc_dialect` (string, default `""`) — global SQL dialect; empty string = sqlglot auto-detect
- CLI flag `--adbc-record` takes precedence over `adbc_record_mode` ini value (standard pytest convention: explicit CLI wins)
- Config is consumed in the `adbc_replay` session fixture; the fixture reads ini values then applies CLI overrides
- Both `[tool.pytest.ini_options]` (pyproject.toml) and `[pytest]` (pytest.ini) sections work automatically via `addini()` — no extra handling needed

### Pytest header line (DX-01)
- Implement `pytest_report_header` hook in `plugin.py`
- Output exactly: `adbc-replay: record mode = {mode}` (matches success criteria wording)
- Do not include cassette dir or dialect in the header line — keep it minimal; those are discoverable from config files

### Scrubbing hook stub (DX-02)
- Follow the `adbc_param_serialisers` fixture pattern — expose as a session-scoped fixture that users override in conftest.py
- Fixture name: `adbc_scrubber` (returns `None` by default)
- `ReplaySession` accepts an optional `scrubber` argument (stores it, never calls it in Phase 3)
- This makes the interface: "override `adbc_scrubber` in your conftest to register a callback" — identical pattern to `adbc_param_serialisers`
- No pluggy hook needed at this stage; a simple fixture override is sufficient for the v2 implementation slot

### Integration test (Phase 3 success criterion 4)
- Add `adbc-driver-sqlite` to `[dependency-groups] dev` in pyproject.toml
- Write one pytester integration test in `tests/test_integration.py` (or `test_e2e.py`) that:
  1. Runs a real pytest subprocess via `pytester.runpytest` with `--adbc-record=once`
  2. The subprocess test connects to an in-memory SQLite DB via adbc-driver-sqlite, executes a real query, and records the cassette
  3. Runs the subprocess again with `--adbc-record=none` (replay-only) — the test must pass without any DB connection
- Test uses `pytester.makepyfile` to generate the test file, matching the pattern already in `test_plugin.py`
- Keep the integration test to a single scenario (record-then-replay); mode-specific edge cases are already covered by unit tests in `test_record_modes.py`

### Claude's Discretion
- Exact `pytest_report_header` signature and return type
- Whether to use `config.getoption` with a fallback or `config.getini` for reading values (standard pattern)
- SQLite query used in the integration test (any simple query is fine, e.g. `SELECT 1` or `CREATE TABLE / INSERT / SELECT`)
- File placement of integration test (`test_integration.py` vs `test_e2e.py`)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The success criteria in the roadmap are precise and serve as the acceptance criteria.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `plugin.py:pytest_addoption` — extend this function with `parser.addini()` calls for the three new keys
- `plugin.py:adbc_replay` fixture — the natural place to read ini values and wire `adbc_scrubber`
- `adbc_param_serialisers` fixture (plugin.py:47) — template for `adbc_scrubber` fixture (same scope, same override pattern)
- `ReplaySession.__init__` (session.py:27) — already accepts `param_serialisers`; add `scrubber` param here
- `tests/test_plugin.py` — extensive pytester test examples; integration test follows the same pattern

### Established Patterns
- Record mode read via `request.config.getoption("--adbc-record", default="none")` (plugin.py:99) — ini fallback slots in before the default
- `pytester.makepyfile` + `pytester.runpytest` pattern is already used across ~10 test methods in test_plugin.py
- Session-scoped fixture override for extensibility (adbc_param_serialisers) — reuse for adbc_scrubber

### Integration Points
- `plugin.py:pytest_addoption` → add `addini()` calls
- `plugin.py:adbc_replay` → read `config.getini("adbc_cassette_dir")` etc.; wire `adbc_scrubber` fixture
- `plugin.py` → add `pytest_report_header` hook
- `_session.py:ReplaySession.__init__` → add `scrubber: ... | None = None` param
- `pyproject.toml:[dependency-groups] dev` → add `adbc-driver-sqlite`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-configuration-dx-and-integration-testing*
*Context gathered: 2026-02-28*
