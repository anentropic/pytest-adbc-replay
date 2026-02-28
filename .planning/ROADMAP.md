# Roadmap: pytest-adbc-replay

## Overview

Build a pytest plugin that intercepts ADBC cursor calls, records query results to cassette files, and replays them without a live warehouse connection. Phase 1 establishes the installable plugin skeleton and cursor proxy with full protocol coverage. Phase 2 implements the core record/replay engine: cassette storage, SQL normalisation, and record mode state machine. Phase 3 adds configuration via pyproject.toml/pytest.ini, developer experience polish, and end-to-end integration tests via pytester to make the plugin publishable.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Plugin Skeleton and Cursor Proxy** - Installable plugin with discoverable fixtures, markers, CLI flag, and a ReplayCursor/ReplayConnection implementing the full ADBC cursor protocol
- [x] **Phase 2: Record/Replay Engine** - Cassette storage, SQL normalisation via sqlglot, and record mode state machine delivering working record/replay across all four modes
- [ ] **Phase 3: Configuration, DX, and Integration Testing** - pyproject.toml/pytest.ini configuration, developer experience polish, and pytester-based end-to-end validation

## Phase Details

### Phase 1: Plugin Skeleton and Cursor Proxy
**Goal**: Users can install the plugin and pytest discovers it; the cursor proxy implements the full ADBC cursor interface with replay-only mode confirmed to work without any ADBC driver installed
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, PROXY-01, PROXY-02, PROXY-03, PROXY-04, PROXY-05, PROXY-06
**Success Criteria** (what must be TRUE):
  1. Running `pytest --co` after installing the plugin shows `adbc_replay` as an available fixture and `--adbc-record` as a recognised CLI option, with no manual imports required
  2. A test decorated with `@pytest.mark.adbc_cassette("my_name")` resolves its cassette path from the marker name; an undecorated test resolves its cassette path from the test node ID
  3. `ReplayConnection` in replay mode (`none`) never imports or references a real ADBC driver -- tests using replay-only mode pass in an environment where no ADBC backend driver is installed
  4. `ReplayCursor` exposes `execute()`, `fetch_arrow_table()`, `fetchall()`, `fetchone()`, `fetchmany()`, `description`, `rowcount`, `close()`, and context manager protocol without raising `AttributeError`
  5. `ReplayCursor` raises a clear `CassetteMissError` (not a generic `KeyError` or `FileNotFoundError`) when a cassette is missing in replay mode
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: Record/Replay Engine
**Goal**: Users can record ADBC query results to cassette files and replay them in subsequent runs across all four record modes, with SQL normalisation ensuring stable cassette keys
**Depends on**: Phase 1
**Requirements**: CASS-01, CASS-02, CASS-03, CASS-04, CASS-05, CASS-06, NORM-01, NORM-02, NORM-03, NORM-04, MODE-01, MODE-02, MODE-03, MODE-04
**Success Criteria** (what must be TRUE):
  1. A test recorded with `--adbc-record=once` produces a cassette directory containing numbered `.sql`, `.arrow`, and `.json` files; the `.sql` file is human-readable pretty-printed SQL; the `.arrow` file round-trips through Arrow IPC with schema metadata preserved
  2. The same test replayed with `--adbc-record=none` (default) passes using only the cassette files -- no database connection is opened
  3. A query written as `SELECT * FROM foo` in one run and `select  *  from  FOO` in the next run matches the same cassette (SQL normalisation handles casing and whitespace)
  4. A test that executes the same SQL query twice receives two distinct results in the correct order (ordered-queue replay, not dict lookup)
  5. All four record modes behave correctly: `none` fails on miss, `once` records only if cassette directory absent, `new_episodes` records only new interactions, `all` re-records everything
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Configuration, DX, and Integration Testing
**Goal**: Users can configure the plugin via pyproject.toml/pytest.ini, see record mode in pytest output, and the full record/replay cycle is validated end-to-end via pytester integration tests
**Depends on**: Phase 2
**Requirements**: CONF-01, CONF-02, CONF-03, DX-01, DX-02
**Success Criteria** (what must be TRUE):
  1. Setting `adbc_cassette_dir`, `adbc_record_mode`, and `adbc_dialect` in pyproject.toml or pytest.ini controls plugin behaviour without any CLI flags or code changes
  2. The pytest header output includes the active record mode (e.g., "adbc-replay: record mode = none") so users can confirm which mode is active
  3. A scrubbing hook interface exists (callable slot) even though the implementation is deferred -- consuming code can register a no-op callback without error
  4. A pytester-based integration test exercises the full record-then-replay cycle against adbc-driver-sqlite, confirming the plugin works end-to-end with a real ADBC driver
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Plugin Skeleton and Cursor Proxy | ?/? | Complete | 2026-02-28 |
| 2. Record/Replay Engine | 4/4 | Complete | 2026-02-28 |
| 3. Configuration, DX, and Integration Testing | 0/? | Not started | - |
