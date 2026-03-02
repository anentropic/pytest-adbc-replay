# Phase 9: adbc_scrubber Implementation - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire up the `adbc_scrubber` fixture so it is actually called during cassette recording (currently stored but never called). Add config-based auto-scrubbing via `adbc_scrub_keys` ini key. Update all documentation to remove "not yet active" warnings. Add tests for the full scrubbing pipeline.

Out of scope: scrubbing Arrow result data (.arrow files), replay-time validation, any changes to cassette key matching or SQL normalisation.

</domain>

<decisions>
## Implementation Decisions

### Config-based auto-scrubbing
- Add `adbc_scrub_keys` as a new pytest ini key — a space-separated list of param key names to auto-redact
- **Global form:** `adbc_scrub_keys = token password api_key` — applies to all drivers
- **Per-driver form:** `adbc_scrub_keys.adbc_driver_snowflake = account_id warehouse` — applies only to that driver
- Both can coexist: global keys apply first, then per-driver keys are added on top (union)
- Matching is **exact key name only** (no substring, no regex)
- Applies to **dict params only** — list/positional params are silently skipped (no names to match)
- Matched values are replaced with the fixed string `"REDACTED"` — no configurable sentinel

### Scrubber scope
- Applies to **params only** — the `.json` cassette files
- Does **not** touch Arrow result data in `.arrow` files
- Applied at **record time only** (before `write_params_json()`) — replay reads what was written, no re-scrubbing

### Fixture signature update
- The `adbc_scrubber` callable now receives two arguments: `scrub(params: dict | None, driver_name: str) -> dict | None`
- `driver_name` is the ADBC driver module name (e.g. `"adbc_driver_snowflake"`)
- Allows per-driver conditional logic in a single session-scoped fixture
- If the callable returns `None`, treat as "no change" — write original params unchanged

### Fixture + config composition
- **Order:** config-based scrubbing runs first, then the fixture receives the (possibly already-partially-scrubbed) params
- This means: global keys → per-driver keys → fixture callable, applied sequentially
- If no scrubber fixture is registered (returns `None` from the fixture), config-based scrubbing still applies

### Claude's Discretion
- Internal implementation details: how `adbc_scrub_keys.{driver}` is read from pytest ini (pytest supports dotted ini keys via `addini` with type "linelist" or similar — Claude picks the right approach)
- How to thread `driver_name` through `ReplaySession → ReplayConnection → ReplayCursor → _record_interaction()` — extend existing param passing pattern
- Test structure: whether new scrubber tests live in a new file or extend existing test files

</decisions>

<specifics>
## Specific Ideas

- Scrubbing should feel like a layered pipeline: global config → per-driver config → fixture. Each layer can add further scrubbing.
- `adbc_scrub_keys.adbc_driver_snowflake` syntax follows the same dotted ini pattern already used elsewhere in pytest plugins

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_cursor.py:91 _record_interaction()` — this is where scrubbing should be applied, immediately before `write_params_json(params_raw, params_path)`
- `_params.py: serialise_params()` — produces `params_raw` (the JSON-safe structure); scrubbing applies to this output, not the raw params
- `plugin.py:235 adbc_scrubber` fixture — exists, returns `None`, needs to be wired through to `ReplayCursor`
- `plugin.py:59 parser.addini()` calls — add `adbc_scrub_keys` here alongside existing ini keys

### Established Patterns
- `ReplaySession.__init__` already accepts `scrubber` param and stores it; needs to also read/store the config-derived scrub keys
- `ReplayConnection` is created by `ReplaySession.wrap()` — scrubber and scrub_keys need to flow through to `ReplayCursor.__init__`
- `ReplayCursor.__init__` accepts `param_serialisers` as a dict — similar pattern can be used for scrub_keys
- `plugin.py:105 _build_session_from_config()` — currently reads mode, cassette_dir, dialect; needs to also read `adbc_scrub_keys`

### Integration Points
- `plugin.py: adbc_replay` fixture creates `ReplaySession` — this is where `adbc_scrubber` fixture value is passed in; `adbc_scrub_keys` (from config) also needs to be passed here
- `plugin.py:126 pytest_sessionstart` → `_build_session_from_config()` — the eager init path also needs to pick up scrub config
- Cassette recording in `_cursor.py:96-106` — the write pipeline needs a scrubbing step between `serialise_params()` and `write_params_json()`

</code_context>

<deferred>
## Deferred Ideas

- Configurable replacement sentinel (e.g. `adbc_scrub_sentinel = ***`) — not needed for this phase; `REDACTED` is sufficient
- Scrubbing Arrow result data in `.arrow` files — explicitly out of scope; test data should not contain real credentials
- Replay-time validation (checking cassette doesn't contain sensitive values) — deferred; adds complexity without clear immediate benefit
- Regex or substring key matching — exact match is sufficient and predictable

</deferred>

---

*Phase: 09-implement-and-document-the-adbc-scrubber-interface*
*Context gathered: 2026-03-02*
