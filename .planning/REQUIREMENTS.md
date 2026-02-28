# Requirements: pytest-adbc-replay

**Defined:** 2026-02-28
**Core Value:** CI tests pass without warehouse credentials — record once locally, replay everywhere, with query changes visible as plain diffs in PRs.

## v1 Requirements

### Plugin Infrastructure

- [ ] **INFRA-01**: Plugin is discoverable by pytest via `pytest11` entry point (no manual import needed)
- [ ] **INFRA-02**: User can set record mode via `--adbc-record=<mode>` CLI flag
- [ ] **INFRA-03**: User can use `adbc_replay` session-scoped fixture that exposes `.wrap()` for connection wrapping
- [ ] **INFRA-04**: User can apply `@pytest.mark.adbc_cassette("name")` marker to override cassette name per test
- [ ] **INFRA-05**: User can apply `@pytest.mark.adbc_cassette("name", dialect="snowflake")` to override SQL dialect per test
- [ ] **INFRA-06**: Default cassette name is derived from test node ID (module + test name) when no marker is present

### Cursor Proxy

- [ ] **PROXY-01**: `ReplayConnection.cursor()` returns a `ReplayCursor` wrapping the real cursor in record mode
- [ ] **PROXY-02**: In replay mode (`none`), `ReplayConnection` does not open or import a real ADBC driver
- [ ] **PROXY-03**: `ReplayCursor.execute()` executes the query on the real cursor and records result to cassette in record mode
- [ ] **PROXY-04**: `ReplayCursor.execute()` loads result from cassette in replay mode
- [ ] **PROXY-05**: `ReplayCursor` implements full cursor protocol: `fetch_arrow_table()`, `fetchall()`, `fetchone()`, `fetchmany()`, `description`, `rowcount`, `close()`, `__enter__`/`__exit__`
- [ ] **PROXY-06**: `ReplayCursor` raises clear `CassetteMissError` on cassette miss in replay mode, showing normalised SQL and available interactions

### Cassette Storage

- [x] **CASS-01**: Cassettes are stored in a configurable directory (default: `tests/cassettes`)
- [x] **CASS-02**: Each cassette is a directory per test; each interaction is a numbered set of files (`000_query.sql`, `000_result.arrow`, `000_params.json`)
- [x] **CASS-03**: SQL is stored as human-readable pretty-printed `.sql` files (canonical dialect, pretty=True)
- [x] **CASS-04**: Results are stored as Arrow IPC `.arrow` files (`RecordBatchFileWriter`) preserving schema metadata
- [x] **CASS-05**: Parameters and driver options are stored as `.json` files (null when absent)
- [x] **CASS-06**: Cassette key is `(normalised_sql, parameters, driver_options)`; duplicate queries in a test use ordered-queue replay

### SQL Normalisation

- [x] **NORM-01**: SQL is normalised via sqlglot before use as cassette key (handles keyword casing, whitespace, quote style)
- [x] **NORM-02**: Normalisation falls back to whitespace-only stripping when sqlglot cannot parse the SQL (no exception raised)
- [x] **NORM-03**: Dialect configurable at three levels: global config → per-test marker → `None` (sqlglot auto-detect)
- [x] **NORM-04**: Parameter placeholders (`?`, `%s`, `$1`) are preserved as-is in SQL keys (not normalised)

### Record Modes

- [ ] **MODE-01**: `none` mode (default) — replay only; fail with clear error on cassette miss; never contacts warehouse
- [ ] **MODE-02**: `once` mode — record if cassette directory does not exist; replay if it does
- [ ] **MODE-03**: `new_episodes` mode — replay existing interactions; record any that are not in the cassette
- [ ] **MODE-04**: `all` mode — re-record everything, overwriting existing cassettes

### Configuration

- [ ] **CONF-01**: User can configure cassette directory via `adbc_cassette_dir` in `pyproject.toml`/`pytest.ini`
- [ ] **CONF-02**: User can configure default record mode via `adbc_record_mode` in `pyproject.toml`/`pytest.ini`
- [ ] **CONF-03**: User can configure default SQL dialect via `adbc_dialect` in `pyproject.toml`/`pytest.ini`

### Developer Experience

- [ ] **DX-01**: Record mode is printed in pytest header output so users know what mode is active
- [ ] **DX-02**: Plugin provides an empty scrubbing hook slot (interface design only — implementation deferred to v1.x)

## v2 Requirements

### Sensitive Data

- **SCRUB-01**: User can register a callback to scrub sensitive values from recorded parameters before writing to disk
- **SCRUB-02**: User can register a callback to scrub sensitive values from recorded Arrow results before writing to disk

### Cassette Management

- **MGMT-01**: Cassette directory contains `manifest.json` with format version for future migration tooling
- **MGMT-02**: Plugin warns when cassette interactions are recorded but never replayed in a test run

### Extended Protocol

- **EXT-01**: User can use plugin with DBAPI2 cursors (non-ADBC) using the same cassette format
- **EXT-02**: Plugin supports async ADBC cursor operations

### Diagnostics

- **DIAG-01**: Cassette miss error shows closest-match interaction with diff highlighting what changed

## Out of Scope

| Feature | Reason |
|---------|--------|
| HTTP recording | Use `pytest-recording` for HTTP — this plugin is ADBC cursor-level only |
| Query correctness validation | Cassettes record whatever the live backend returned; no semantic checking |
| Custom matchers / pluggable matching | SQL matching has one correct strategy (normalised key); pluggability adds complexity without value |
| Custom serialisers | Arrow IPC is the only format with full schema fidelity; alternatives lose type information |
| Network/socket blocking | ADBC drivers use native C/C++ transports — socket patching does not reach them |
| Custom persisters | Cassettes must be committed to the repo for PR diffs; filesystem-only is correct |
| Specific ADBC driver dependencies | Drivers (snowflake, databricks, etc.) are provided by consuming projects |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| INFRA-05 | Phase 1 | Pending |
| INFRA-06 | Phase 1 | Pending |
| PROXY-01 | Phase 1 | Pending |
| PROXY-02 | Phase 1 | Pending |
| PROXY-03 | Phase 1 | Pending |
| PROXY-04 | Phase 1 | Pending |
| PROXY-05 | Phase 1 | Pending |
| PROXY-06 | Phase 1 | Pending |
| CASS-01 | Phase 2 | Complete |
| CASS-02 | Phase 2 | Complete |
| CASS-03 | Phase 2 | Complete |
| CASS-04 | Phase 2 | Complete |
| CASS-05 | Phase 2 | Complete |
| CASS-06 | Phase 2 | Complete |
| NORM-01 | Phase 2 | Complete |
| NORM-02 | Phase 2 | Complete |
| NORM-03 | Phase 2 | Complete |
| NORM-04 | Phase 2 | Complete |
| MODE-01 | Phase 2 | Pending |
| MODE-02 | Phase 2 | Pending |
| MODE-03 | Phase 2 | Pending |
| MODE-04 | Phase 2 | Pending |
| CONF-01 | Phase 3 | Pending |
| CONF-02 | Phase 3 | Pending |
| CONF-03 | Phase 3 | Pending |
| DX-01 | Phase 3 | Pending |
| DX-02 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 31 total
- Mapped to phases: 31
- Unmapped: 0

---
*Requirements defined: 2026-02-28*
*Last updated: 2026-02-28 after roadmap creation*
