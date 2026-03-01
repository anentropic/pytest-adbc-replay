# Roadmap: pytest-adbc-replay

## Overview

Build a pytest plugin that intercepts ADBC cursor calls, records query results to cassette files, and replays them without a live warehouse connection. Phase 1 establishes the installable plugin skeleton and cursor proxy with full protocol coverage. Phase 2 implements the core record/replay engine: cassette storage, SQL normalisation, and record mode state machine. Phase 3 adds configuration via pyproject.toml/pytest.ini, developer experience polish, and end-to-end integration tests via pytester to make the plugin publishable. Phase 4 completes type exports and PyPI package metadata. Phase 5 writes the README and CHANGELOG. Phase 6 builds a full MkDocs documentation site structured with the diataxis framework. Phase 7 delivers CI and publish automation so the package can be released via a version tag push.

## Milestones

- [x] **v0.x Foundation** - Phases 1-3 (complete)
- [ ] **v1.0.0 Docs and Publishing Polish** - Phases 4-7 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>Phases 1-3 (Foundation — Complete)</summary>

- [x] **Phase 1: Plugin Skeleton and Cursor Proxy** - Installable plugin with discoverable fixtures, markers, CLI flag, and a ReplayCursor/ReplayConnection implementing the full ADBC cursor protocol
- [x] **Phase 2: Record/Replay Engine** - Cassette storage, SQL normalisation via sqlglot, and record mode state machine delivering working record/replay across all four modes
- [x] **Phase 3: Configuration, DX, and Integration Testing** - pyproject.toml/pytest.ini configuration, developer experience polish, and pytester-based end-to-end validation

</details>

### v1.0.0 Docs and Publishing Polish

- [x] **Phase 4: Type Exports and PyPI Metadata** - py.typed marker, public API __all__, and complete pyproject.toml classifiers/URLs/keywords (completed 2026-03-01)
- [x] **Phase 5: README and CHANGELOG** - README covering all user-facing features and a CHANGELOG for v1.0.0 (completed 2026-03-01)
- [x] **Phase 6: MkDocs Documentation Site** - Full diataxis-structured documentation site (Tutorial, How-To, Reference, Explanation) with humanizer-polished prose (completed 2026-03-01)
- [ ] **Phase 7: Publishing Automation** - GitHub Actions CI matrix, publish-on-tag workflow, and GitHub Pages deployment (in progress)

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
**Plans**: 3

Plans:
- [x] 01-01: Plugin entry point, conftest hooks, CLI flag, fixture, marker registration
- [x] 01-02: ReplayConnection and ReplayCursor stub with full cursor protocol surface
- [x] 01-03: CassetteMissError, replay-only mode (no driver import), test coverage

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
**Plans**: 4

Plans:
- [x] 02-01: CassetteStore: directory layout, numbered file I/O, Arrow IPC read/write
- [x] 02-02: SQLNormaliser: sqlglot integration, fallback, dialect/parameter handling
- [x] 02-03: Record mode state machine wired through ReplayConnection/ReplayCursor
- [x] 02-04: Test suite for normaliser, cassette I/O, and all record modes

### Phase 3: Configuration, DX, and Integration Testing
**Goal**: Users can configure the plugin via pyproject.toml/pytest.ini, see record mode in pytest output, and the full record/replay cycle is validated end-to-end via pytester integration tests
**Depends on**: Phase 2
**Requirements**: CONF-01, CONF-02, CONF-03, DX-01, DX-02
**Success Criteria** (what must be TRUE):
  1. Setting `adbc_cassette_dir`, `adbc_record_mode`, and `adbc_dialect` in pyproject.toml or pytest.ini controls plugin behaviour without any CLI flags or code changes
  2. The pytest header output includes the active record mode (e.g., "adbc-replay: record mode = none") so users can confirm which mode is active
  3. A scrubbing hook interface exists (callable slot) even though the implementation is deferred -- consuming code can register a no-op callback without error
  4. A pytester-based integration test exercises the full record-then-replay cycle against adbc-driver-sqlite, confirming the plugin works end-to-end with a real ADBC driver
**Plans**: 2

Plans:
- [x] 03-01: Plugin ini config wiring, pytest_report_header, adbc_scrubber fixture, ReplaySession scrubber/dialect params
- [x] 03-02: Unit tests (TestIniConfig, TestReportHeader, TestScrubberFixture) and E2E integration test (adbc-driver-sqlite record-then-replay)

### Phase 4: Type Exports and PyPI Metadata
**Goal**: The package is typed and its public API is explicitly declared; pyproject.toml has all metadata required for a quality PyPI listing
**Depends on**: Phase 3
**Requirements**: TYPE-01, TYPE-02, PUB-01
**Success Criteria** (what must be TRUE):
  1. A downstream project using the package with mypy or pyright finds `py.typed` and gets type information without any `# type: ignore` workarounds
  2. `from pytest_adbc_replay import *` (or inspection of `__all__`) exposes exactly the names intended for public use and nothing else
  3. `pip install pytest-adbc-replay` followed by inspecting the PyPI project page shows correct classifiers (Python versions, pytest compatibility, license, development status), project URLs (source, issues), and keywords
**Plans**: 1

Plans:
- [x] 04-01-PLAN.md — Verify py.typed wheel inclusion, confirm __all__, add full PyPI classifiers/URLs/keywords

### Phase 5: README and CHANGELOG
**Goal**: Users arriving at the PyPI page or GitHub repository have everything they need to install, configure, and use the plugin without reading source code
**Depends on**: Phase 4
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04
**Success Criteria** (what must be TRUE):
  1. A new user can follow the README from installation through their first recorded and replayed test run using only the README (no source reading required)
  2. All four record modes, all three configuration keys, the CLI flag, and the `adbc_replay` fixture are documented with examples in the README
  3. The cassette directory structure (`.sql`, `.arrow`, `.json` naming convention) is shown in the README so users understand what to commit to version control
  4. CHANGELOG.md exists and documents v1.0.0 with a summary of what the release delivers
**Plans**: 1

Plans:
- [x] 05-01-PLAN.md — Write README.md (install, quick-start, modes, config, cassette layout) and generate CHANGELOG.md via git-cliff with cliff.toml

### Phase 6: MkDocs Documentation Site
**Goal**: A full documentation site structured with the diataxis framework (Tutorial, How-To, Reference, Explanation) is built with MkDocs Material, contains complete content, and all prose reads as natural technical writing
**Depends on**: Phase 5
**Requirements**: DOC-05, DOC-06, DOC-07, DOC-08, DOC-09, DOC-10
**Success Criteria** (what must be TRUE):
  1. `mkdocs serve` runs without errors and the site is navigable with Material theme
  2. The Tutorial section walks a new user from installation to their first successful record-then-replay cycle with step-by-step instructions
  3. The How-To section contains at least four task-oriented guides (CI setup, ini configuration, per-test cassette naming, multiple drivers)
  4. The Reference section lists every configuration key, CLI flag, fixture, marker, record mode, and public type — all accurate against the implementation
  5. The Explanation section covers cassette format rationale, SQL normalisation design, and record mode semantics in prose that reads naturally (no AI vocabulary, no em-dash overuse)
**Plans**: 5

Plans:
- [x] 06-01-PLAN.md — MkDocs nav wiring, index.md Quick Start, verify mkdocs build passes
- [x] 06-02-PLAN.md — Tutorial: step-by-step DuckDB walkthrough from install to first replay
- [x] 06-03-PLAN.md — How-To guides: six task-oriented guides (CI, ini config, cassette names, multi-driver, scrubber, serialisers)
- [x] 06-04-PLAN.md — Reference pages: configuration, record modes, fixtures, markers, exceptions, cassette format
- [x] 06-05-PLAN.md — Explanation articles: cassette format rationale, SQL normalisation design, record mode semantics

### Phase 7: Publishing Automation
**Goal**: Pushing a version tag triggers a verified PyPI release and GitHub Pages docs deployment; every push and PR runs the test suite across all supported Python versions
**Depends on**: Phase 6
**Requirements**: PUB-02, PUB-03, PUB-04
**Success Criteria** (what must be TRUE):
  1. Opening a pull request or pushing to any branch triggers a CI run that executes the test suite on Python 3.11, 3.12, 3.13, and 3.14 and reports pass/fail status on the PR
  2. Pushing a tag matching `v*.*.*` triggers the publish workflow which builds the distribution and uploads it to PyPI without manual intervention
  3. Pushing a tag matching `v*.*.*` also triggers the docs deployment workflow which builds and pushes the MkDocs site to GitHub Pages
**Plans**: 3

Plans:
- [x] 07-01-PLAN.md — Create reusable _test.yml workflow, add tag trigger to docs.yml, add Python 3.14 classifier
- [ ] 07-02-PLAN.md — Update ci.yml and pr.yml to call reusable workflow (PUB-02)
- [ ] 07-03-PLAN.md — Fix and complete release.yml: quality gate, cookiecutter bug, GitHub Release creation

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Plugin Skeleton and Cursor Proxy | 3/3 | Complete | 2026-02-28 |
| 2. Record/Replay Engine | 4/4 | Complete | 2026-02-28 |
| 3. Configuration, DX, and Integration Testing | 2/2 | Complete | 2026-03-01 |
| 4. Type Exports and PyPI Metadata | 1/1 | Complete   | 2026-03-01 |
| 5. README and CHANGELOG | 1/1 | Complete | 2026-03-01 |
| 6. MkDocs Documentation Site | 5/5 | Complete | 2026-03-01 |
| 7. Publishing Automation | 1/3 | In progress | - |
