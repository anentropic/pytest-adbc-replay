# Feature Research

**Domain:** pytest record/replay plugin for ADBC database connections
**Researched:** 2026-02-28
**Confidence:** HIGH (based on direct source code inspection of vcrpy 8.1.1, pytest-recording 0.13.4, responses 0.26.0, pytest-httpserver 1.1.5)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist based on prior art (VCR.py, pytest-recording). Missing these and users immediately reach for VCR.py instead or reject the plugin as incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Record modes: `none`, `once`, `new_episodes`, `all`** | VCR.py defines these four modes; pytest-recording exposes them via `--record-mode`. Users expect identical semantics. `none`=replay only, `once`=record if cassette missing, `new_episodes`=append new interactions, `all`=re-record everything. | MEDIUM | Core state machine. VCR.py also has `any` mode but it is undocumented and rarely used. pytest-recording adds `rewrite` (deletes cassette then records as `new_episodes`). Implement the four standard modes first. |
| **CLI flag `--adbc-record=<mode>`** | pytest-recording uses `--record-mode`. Users expect a CLI flag to switch modes without code changes. Essential for CI (`none`) vs local dev (`once`/`all`) workflows. | LOW | Single `pytest_addoption` call plus `record_mode` session-scoped fixture. |
| **Cassette storage on filesystem** | VCR.py stores YAML files; users commit cassettes to repos. Must persist to disk in a reviewable format. | LOW | Directory-per-test with numbered `.sql`/`.arrow` files (per design doc). |
| **Default cassette naming from test node ID** | pytest-recording auto-names cassettes from `module/TestClass.test_name`. Users do not want to manually name every cassette. | LOW | Derive from `request.node.nodeid`. pytest-recording uses `module.dirname/cassettes/module.purebasename/test_name`. |
| **Marker for cassette name override** | `@pytest.mark.vcr` in pytest-recording, `@vcr.use_cassette("name")` in VCR.py. Users need per-test cassette name control. | LOW | `@pytest.mark.adbc_cassette("name")`. |
| **Fail-fast on cassette miss in replay mode** | VCR.py raises `CannotOverwriteExistingCassetteException` with detailed diff when request not found. Clear error messages are table stakes for debuggability. | MEDIUM | Need good error messages showing the SQL that missed, the normalised form attempted, and available cassette interactions. VCR.py's `find_requests_with_most_matches` is a good UX pattern to study. |
| **Configuration via `pyproject.toml` / `pytest.ini`** | pytest standard. Users expect `adbc_cassette_dir`, `adbc_record_mode`, and `adbc_dialect` as ini options. | LOW | `pytest_addoption` with `parser.addini()`. |
| **Session-scoped fixture for connection wrapping** | Users need a fixture to wrap their ADBC connections. This is the primary API surface -- analogous to `vcr_config` in pytest-recording. | MEDIUM | `adbc_replay` session-scoped fixture exposing `.wrap()` method. Must handle both record (real connection + proxy cursor) and replay (no connection needed) modes. |
| **Replay without live connection** | The entire point. In `none` mode, no database connection is opened. VCR.py does this by not making HTTP calls; we must not open ADBC connections. | MEDIUM | `ReplayConnection` that returns `ReplayCursor` without a backing cursor. Must raise clear error on cassette miss rather than attempting network access. |
| **Cassette format: human-readable SQL diffs** | Core value proposition from design doc. `.sql` files make query changes visible in PRs. VCR.py YAML cassettes are human-readable; our equivalent must be at least as good. | LOW | `.sql` files with `pretty=True` sqlglot formatting. Already specified in design doc. |

### Differentiators (Competitive Advantage)

Features that no existing tool provides well in this domain, or that set pytest-adbc-replay apart from VCR.py-based approaches.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **SQL normalisation via sqlglot** | VCR.py matches HTTP requests by URI/method/headers/body. SQL matching needs normalisation: `SELECT * FROM t` and `select  *  from t` must match the same cassette. No existing tool does this. sqlglot handles keyword casing, whitespace, quote style in one pass. | MEDIUM | `sqlglot.transpile(sql, read=dialect, write=dialect, pretty=False)[0]` for key; `pretty=True` for stored `.sql` file. Fallback to whitespace-only normalisation on parse failure. Dialect-aware (Snowflake, Databricks, etc.). |
| **Arrow IPC cassette format** | Results stored as Arrow IPC (`.arrow` files), not YAML/JSON. Preserves schema metadata precisely (column types, nullability, metadata). No Parquet dependency. Binary but schema-faithful. VCR.py stores HTTP response bodies as strings in YAML; we store structured tabular data natively. | LOW | `pyarrow.ipc.new_file()` / `pyarrow.ipc.open_file()`. Already a required dependency. |
| **Dialect-aware normalisation with three-level precedence** | Global default in `pyproject.toml`, per-test override via marker (`@pytest.mark.adbc_cassette(dialect="snowflake")`), fallback to auto-detect. VCR.py has no equivalent -- HTTP has no "dialect". Critical for multi-warehouse projects. | LOW | Configuration plumbing only; the hard work is in sqlglot. |
| **Driver-agnostic via ADBC cursor interface** | Works for any ADBC-compatible backend: Snowflake, Databricks, BigQuery, Flight SQL, DuckDB, PostgreSQL. VCR.py is HTTP-only. `snowflake-vcrpy` is Snowflake-only. No other tool provides cross-warehouse cursor-level record/replay. | LOW (architectural) | The cursor interface is narrow (`execute`, `fetch_arrow_table`, `fetch_record_batch`). Being driver-agnostic is a design property, not a feature to implement. |
| **Companion to pytest-recording** | Projects using both HTTP APIs and ADBC can use both plugins with consistent conventions (`--record-mode=all --adbc-record=all`). No existing tool provides this pairing story. | LOW | Convention alignment only. No code coupling. |
| **Parameters and options as part of cassette key** | VCR.py matches on HTTP method + URI + optional body/headers. We match on `(normalised_sql, parameters, driver_options)`. Parameterised queries with different bind values get different cassettes. No HTTP tool handles this. | MEDIUM | Parameters serialised to JSON for matching. Must handle various Python types (None, int, str, datetime, etc.) via JSON serialisation with a canonical form. |
| **Numbered interaction ordering** | Cassettes use `000_query.sql`, `001_query.sql` etc. Execution order is preserved and visible. VCR.py stores all interactions in a single YAML file with implicit ordering; our per-file approach makes individual query changes show up as clean PR diffs. | LOW | Already specified in design doc. Incremental counter during recording. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create complexity, maintenance burden, or wrong abstractions for this domain.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Custom matchers / pluggable matching** | VCR.py has 10+ matchers (method, uri, host, scheme, port, path, query, headers, raw_body, body) plus `register_matcher()`. Users may want to match SQL by substring or regex. | SQL matching has exactly one meaningful strategy: normalised SQL + parameters + options. HTTP has many dimensions; SQL does not. Custom matchers add API surface and testing burden for a problem that does not exist at the database cursor level. If sqlglot normalisation fails, the whitespace fallback handles it. | Invest in sqlglot normalisation robustness instead. If a user's SQL cannot be normalised, they can file a bug against sqlglot or use the whitespace fallback. |
| **Custom serializers (YAML, JSON alternatives for cassettes)** | VCR.py supports YAML and JSON serializers plus `register_serializer()`. | Arrow IPC is the only format that preserves schema metadata precisely. YAML/JSON cannot faithfully represent Arrow schemas with metadata, nested types, or decimal precision. Supporting multiple formats creates a compatibility matrix that is not justified. `.sql` files are already human-readable. | Arrow IPC for results. `.sql` for queries. `.json` for params/options. This is the single, opinionated format. |
| **Custom persisters (database backend, S3, etc.)** | VCR.py has `register_persister()` to store cassettes in non-filesystem locations. | Cassettes must be committed to the repo for PR diffs. Non-filesystem persisters defeat this core value. Adding abstraction for a use case that conflicts with the design goal is wrong. | Filesystem only. Document that cassettes are committed to the repo. |
| **Sensitive data scrubbing in v1** | VCR.py has `filter_headers`, `filter_query_parameters`, `filter_post_data_parameters`, `before_record_request`, `before_record_response`. Users will ask about scrubbing credentials from SQL parameters. | Adds significant API surface and edge cases (nested JSON, binary data in Arrow columns, etc.). The design doc already identifies this as a v2 consideration. For v1, the right answer is "don't record sensitive data" or "add scrubbing to your test fixtures". | Design the cassette write path with a filter callback hook point (empty in v1). Document that sensitive data scrubbing is planned for v2. Users can scrub in their own fixture code wrapping `adbc_replay.wrap()`. |
| **DBAPI2 support** | Natural extension. Many projects use DBAPI2 cursors rather than ADBC. | Doubles the API surface and testing matrix. ADBC cursor interface is narrow and uniform; DBAPI2 has more variation (fetchone/fetchmany/fetchall return tuples, not Arrow). The design doc explicitly defers this. | Architecture should not preclude DBAPI2 (and current design does not). Implement when the ADBC core is stable and validated. |
| **Network blocking / socket patching** | pytest-recording patches `socket.connect` and pycurl to block network access in replay mode. Provides defence-in-depth against accidental live calls. | ADBC connections do not go through Python's `socket` module in a way that is patchable -- drivers use native C/C++ libraries (Arrow Flight, ODBC, etc.). Socket-level blocking would not prevent ADBC connections. It would add complexity and false confidence. | Rely on not opening real connections in replay mode. The `ReplayConnection` never calls the driver. If a test accidentally uses a real connection, it will fail because credentials are not available in CI. |
| **`allow_playback_repeats`** | VCR.py allows the same cassette response to be replayed multiple times (for retry logic, polling, etc.). | SQL queries are typically not retried in the same way HTTP requests are. Adding replay counting logic increases complexity for a use case that rarely occurs at the database layer. | If needed later, add as a simple boolean flag on the cassette. Do not build upfront. |
| **`drop_unused_requests` / cassette hygiene** | VCR.py can save only the interactions that were actually played, dropping unused ones from the cassette. Keeps cassettes clean. | Nice-to-have but not essential for v1. Adds complexity to the save path. Users can re-record with `--adbc-record=all` to clean cassettes. | Defer to v1.x. Implement after core is stable. |
| **`rewrite` record mode** | pytest-recording adds a `rewrite` mode that deletes the cassette then records fresh. | Can be achieved with `--adbc-record=all`. Adding a fifth mode increases cognitive load for marginal convenience. pytest-recording implements it by deleting the file then using `new_episodes` internally. | Document `--adbc-record=all` as the way to re-record. If demand exists, add `rewrite` in v1.x. |
| **Combined/multi-cassette loading** | pytest-recording's `CombinedPersister` loads multiple cassette files into a single test (shared setup cassettes). | Adds significant complexity. For database queries, shared cassettes are less useful than for HTTP (where base URL auth flows are common). | Users can structure their test fixtures to share database state without needing multi-cassette loading. Defer. |
| **`--disable-recording` flag** | pytest-recording has `--disable-recording` to turn off VCR entirely. | The default mode is `none` (replay). If users want to run without the plugin at all, they can use `-p no:adbc_replay`. Adding a separate flag is redundant. | Document `-p no:adbc_replay` as the disable mechanism. |

## Feature Dependencies

```
[SQL Normalisation (sqlglot)]
    └──requires──> [Dialect Configuration]
                       └──enhances──> [Per-test marker with dialect override]

[Record Modes (none/once/new_episodes/all)]
    └──requires──> [Cassette Storage (filesystem)]
                       └──requires──> [Default Cassette Naming]
                       └──requires──> [Arrow IPC Serialisation]
                       └──requires──> [SQL File Storage]

[CLI flag --adbc-record]
    └──controls──> [Record Modes]

[Session-scoped fixture (adbc_replay)]
    └──requires──> [ReplayCursor / ReplayConnection]
                       └──requires──> [Cassette Matching (normalised key)]
                                          └──requires──> [SQL Normalisation]

[Marker @pytest.mark.adbc_cassette]
    └──enhances──> [Default Cassette Naming]
    └──enhances──> [Dialect Configuration]

[Replay without live connection]
    └──requires──> [ReplayConnection (connectionless mode)]
    └──requires──> [Cassette Storage]

[Fail-fast error messages]
    └──requires──> [Cassette Matching]
    └──enhances──> [Developer Experience]
```

### Dependency Notes

- **SQL Normalisation requires Dialect Configuration:** sqlglot needs a dialect hint for vendor-specific SQL (Snowflake `FLATTEN`, Databricks functions). Without dialect config, normalisation falls back to best-effort which may mismatch on vendor extensions.
- **All record modes require Cassette Storage:** The mode state machine controls when to read/write cassettes. Storage must exist first.
- **Session-scoped fixture requires ReplayCursor:** The fixture is the entry point; the cursor proxy is the mechanism. Building the fixture without the cursor does nothing.
- **Marker enhances Default Cassette Naming:** The marker overrides the default; if default naming is not implemented, the marker has nothing to override.

## MVP Definition

### Launch With (v1.0)

Minimum viable product -- what is needed to validate that ADBC cursor-level record/replay works and is useful.

- [ ] **ReplayCursor and ReplayConnection** -- the core interception layer that wraps `execute()`, `fetch_arrow_table()`, and `fetchall()`
- [ ] **Cassette storage** -- directory-per-test with numbered `.sql`, `.arrow`, `.json` files
- [ ] **Record modes: `none`, `once`, `new_episodes`, `all`** -- the four standard VCR.py modes
- [ ] **SQL normalisation via sqlglot** -- with dialect configuration and whitespace fallback
- [ ] **CLI flag `--adbc-record=<mode>`** -- matching pytest-recording conventions
- [ ] **`adbc_replay` session-scoped fixture** -- exposing `.wrap()` for connection wrapping
- [ ] **`@pytest.mark.adbc_cassette` marker** -- for cassette name and dialect override
- [ ] **`pyproject.toml` / `pytest.ini` configuration** -- `adbc_cassette_dir`, `adbc_record_mode`, `adbc_dialect`
- [ ] **Fail-fast error messages on cassette miss** -- showing normalised SQL and available interactions
- [ ] **Replay without live connection** -- `ReplayConnection` that does not open a real ADBC connection

### Add After Validation (v1.x)

Features to add once the core is working and users provide feedback.

- [ ] **Sensitive data scrubbing hooks** -- callback on the cassette write path for filtering parameters and result columns
- [ ] **Cassette format versioning** -- `manifest.json` with format version field for migration tooling
- [ ] **`drop_unused_requests` equivalent** -- save only played interactions, removing stale ones
- [ ] **`rewrite` record mode** -- if users find `--adbc-record=all` insufficient
- [ ] **Better cassette miss diagnostics** -- show closest matching interaction with diff (like VCR.py's `find_requests_with_most_matches`)

### Future Consideration (v2+)

Features to defer until the ADBC core is proven stable and adoption justifies the investment.

- [ ] **DBAPI2 cursor support** -- extend the proxy pattern to DBAPI2 `execute()`/`fetchall()` with Arrow conversion
- [ ] **Combined/multi-cassette loading** -- shared setup cassettes across tests
- [ ] **Cassette migration tooling** -- automated format upgrades between versions
- [ ] **Async cursor support** -- if ADBC async interfaces emerge

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| ReplayCursor / ReplayConnection | HIGH | HIGH | P1 |
| Record modes (none/once/new_episodes/all) | HIGH | MEDIUM | P1 |
| Cassette storage (dir + .sql + .arrow + .json) | HIGH | MEDIUM | P1 |
| SQL normalisation (sqlglot) | HIGH | MEDIUM | P1 |
| CLI flag --adbc-record | HIGH | LOW | P1 |
| Session-scoped fixture (adbc_replay) | HIGH | MEDIUM | P1 |
| Configuration (pyproject.toml / pytest.ini) | MEDIUM | LOW | P1 |
| Marker @pytest.mark.adbc_cassette | MEDIUM | LOW | P1 |
| Fail-fast error messages | MEDIUM | MEDIUM | P1 |
| Replay without live connection | HIGH | MEDIUM | P1 |
| Sensitive data scrubbing hooks | MEDIUM | HIGH | P2 |
| Cassette format versioning (manifest.json) | LOW | LOW | P2 |
| drop_unused_requests equivalent | LOW | MEDIUM | P2 |
| rewrite record mode | LOW | LOW | P3 |
| DBAPI2 support | MEDIUM | HIGH | P3 |
| Combined cassette loading | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | VCR.py | pytest-recording | responses | pytest-httpserver | Our Approach |
|---------|--------|------------------|-----------|-------------------|--------------|
| **Record modes** | `none`, `once`, `new_episodes`, `all`, `any` | Same + `rewrite` | Record decorator (no modes) | No recording (mock only) | `none`, `once`, `new_episodes`, `all` |
| **Cassette format** | YAML or JSON (single file) | Same (via VCR.py) | YAML (single file) | N/A | Directory per test: `.sql` + `.arrow` + `.json` files |
| **Matching strategy** | Composable: method, uri, host, scheme, port, path, query, headers, body; custom matchers via `register_matcher()` | Same (via VCR.py) | URL + method + body/json/query matchers; custom matchers | URI pattern + method + headers + query + body matching | `(normalised_sql, parameters, options)` -- single fixed strategy |
| **Normalisation** | None (exact HTTP request match) | None | None | None | sqlglot SQL normalisation with dialect awareness |
| **Data filtering** | `filter_headers`, `filter_query_parameters`, `filter_post_data_parameters`, `before_record_request`, `before_record_response` | Inherits from VCR.py via `vcr_config` fixture | N/A | N/A | v2 consideration; hook point designed in v1 |
| **Fixture/marker UX** | Decorator `@vcr.use_cassette()` | `@pytest.mark.vcr`, `vcr_config` fixture, `vcr_cassette_dir` fixture, `default_cassette_name` fixture | `@responses.activate` decorator | `httpserver` fixture | `@pytest.mark.adbc_cassette`, `adbc_replay` fixture |
| **CLI integration** | N/A (library, not pytest plugin) | `--record-mode`, `--block-network`, `--disable-recording`, `--allowed-hosts` | N/A | N/A | `--adbc-record=<mode>` |
| **Network blocking** | N/A | Socket + pycurl patching with `@pytest.mark.block_network` | Implicit (mocks prevent real calls) | N/A (real server) | Not applicable (ADBC uses native drivers, not Python sockets) |
| **Custom serializers** | `register_serializer()` (YAML, JSON built-in) | Inherits | N/A | N/A | Not supported; Arrow IPC is the single opinionated format |
| **Custom persisters** | `register_persister()` | Inherits | N/A | N/A | Not supported; filesystem only |
| **Playback repeats** | `allow_playback_repeats` flag | Inherits | Automatic (responses remain registered) | Ordered or unordered handlers | Not in v1; defer |
| **Drop unused** | `drop_unused_requests` flag | Inherits | N/A | `assert_no_log` for unmatched | Defer to v1.x |
| **Hooks** | `before_record_request`, `before_record_response` | `pytest_recording_configure` hook (VCR instance customisation) | N/A | Request/response hooks | Hook point designed in v1, empty; scrubbing in v2 |
| **Cassette versioning** | `CASSETTE_FORMAT_VERSION = 1` with migration script | Inherits | N/A | N/A | `manifest.json` planned for v1.x |
| **Error diagnostics** | `find_requests_with_most_matches` shows closest request with per-matcher diff | Inherits | ConnectionError with reason | 500 response on no handler | Show normalised SQL + available interactions |
| **Async support** | aiohttp stubs, httpcore stubs | Inherits | N/A | N/A (thread-based server) | Defer; ADBC async not yet common |

## Sources

- **VCR.py 8.1.1** -- direct source code inspection of `vcr/config.py`, `vcr/record_mode.py`, `vcr/matchers.py`, `vcr/filters.py`, `vcr/cassette.py`, `vcr/serialize.py`, `vcr/persisters/filesystem.py`, `vcr/errors.py`, `vcr/patch.py` (downloaded from PyPI, HIGH confidence)
- **pytest-recording 0.13.4** -- direct source code inspection of `pytest_recording/plugin.py`, `pytest_recording/_vcr.py`, `pytest_recording/network.py`, `pytest_recording/hooks.py`, `pytest_recording/utils.py` (downloaded from PyPI, HIGH confidence)
- **responses 0.26.0** -- direct source code inspection of `responses/__init__.py`, `responses/_recorder.py`, `responses/matchers.py`, `responses/registries.py` (downloaded from PyPI, HIGH confidence)
- **pytest-httpserver 1.1.5** -- direct source code inspection of `pytest_httpserver/httpserver.py`, `pytest_httpserver/pytest_plugin.py` (downloaded from PyPI, HIGH confidence)
- **Project design document** -- `_notes/pytest-adbc-replay-design.md` (local file, PRIMARY context)
- **Database record/replay landscape** -- no existing pytest plugin was found for database-level (non-HTTP) record/replay. `snowflake-vcrpy` is not available on PyPI (checked 2026-02-28). `pytest-replay` is a test execution replay tool, not data replay. This confirms the greenfield opportunity. (MEDIUM confidence -- PyPI search is limited; a GitHub-only project could exist)

---
*Feature research for: pytest record/replay plugin for ADBC database connections*
*Researched: 2026-02-28*
