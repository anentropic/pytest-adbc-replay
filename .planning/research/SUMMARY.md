# Project Research Summary

**Project:** pytest-adbc-replay
**Domain:** pytest plugin — record/replay testing of ADBC database connections
**Researched:** 2026-02-28
**Confidence:** HIGH

## Executive Summary

pytest-adbc-replay is a greenfield pytest plugin that fills a genuine gap: no existing tool provides cursor-level record/replay for ADBC (Arrow Database Connectivity) connections. VCR.py and pytest-recording intercept HTTP — useless for warehouse drivers that use native C/C++ transports (Arrow Flight, ODBC). The plugin intercepts at the ADBC cursor interface, records SQL queries and Arrow IPC results to disk, and replays them without any live database connection. The target users are data engineers testing dbt adapters, warehouse integrations, and analytics code against Snowflake, Databricks, BigQuery, and similar backends where spinning up a real warehouse in CI is expensive or impossible.

The recommended approach is a layered architecture with four modules (`_types.py`, `normalise.py`, `cassette.py`, `proxy.py`) beneath a thin `plugin.py` wiring layer. Each layer is independently unit-testable. The cassette format is opinionated: `.sql` files (human-readable, diff-friendly), `.arrow` files (Arrow IPC, schema-faithful), and `.json` files (parameters and options). SQL matching uses sqlglot for dialect-aware normalisation with a whitespace fallback. Record mode semantics mirror VCR.py's four modes (`none`, `once`, `new_episodes`, `all`) so users with pytest-recording experience face zero learning curve.

The key risks are architectural and must be resolved in Phase 1: fixture scope mismatch (session vs. function scope for cassette lifecycle), incomplete cursor protocol coverage (ReplayCursor must implement the full ADBC cursor interface), and the replay-only path must be completely offline with no driver dependency. Phase 2 risks are technical: sqlglot's transpiler can silently rewrite SQL semantics when dialect is unspecified, duplicate queries within a single test require ordered-queue replay (not dict-lookup), and Arrow IPC schema metadata is a precise snapshot tied to the driver version and session settings used during recording.

## Key Findings

### Recommended Stack

The stack is already substantially configured in the project's `pyproject.toml` and `uv.lock`. All version floors are verified against PyPI (Feb 2026). The four runtime dependencies are: `pytest>=8.0,<10` (plugin host), `pyarrow>=17.0` (Arrow IPC cassette format), `sqlglot>=26.0` (SQL normalisation), and `adbc-driver-manager>=1.0` (type references for cursor interface). The dev toolchain uses `uv` as package manager, `uv_build` as build backend, `ruff` for linting/formatting, `basedpyright` for type checking, and `adbc-driver-sqlite` for integration tests against a zero-config local driver.

See [STACK.md](.planning/research/STACK.md) for full version compatibility matrix and alternatives considered.

**Core technologies:**
- `pytest>=8.0,<10`: Plugin host — entry point registered via `pytest11` group, hooks and fixtures defined in `plugin.py`
- `pyarrow>=17.0`: Arrow IPC cassette format — `RecordBatchFileWriter`/`RecordBatchFileReader` preserve schema metadata exactly; no Parquet dependency needed
- `sqlglot>=26.0`: SQL normalisation — `transpile(sql, read=dialect, write=dialect)` for stable cassette keys; dialect-aware, handles keyword casing, whitespace, quote styles
- `adbc-driver-manager>=1.0`: Type references for `dbapi.Cursor` and `dbapi.Connection` — runtime dependency because proxy imports types, but backend drivers (Snowflake, Databricks) are NOT plugin dependencies
- `pytester` (built-in): Plugin self-testing — runs pytest in subprocess; no separate package; requires `pytest_plugins = ["pytester"]` in test conftest

### Expected Features

Research cross-referenced VCR.py 8.1.1, pytest-recording 0.13.4, responses 0.26.0, and pytest-httpserver 1.1.5 directly from PyPI source. No existing pytest plugin for database-level (non-HTTP) record/replay was found, confirming the greenfield opportunity.

See [FEATURES.md](.planning/research/FEATURES.md) for the full feature analysis and competitor matrix.

**Must have (table stakes) — v1.0:**
- `ReplayCursor` and `ReplayConnection` — core interception layer wrapping `execute()`, `fetch_arrow_table()`, `fetchall()`
- Record modes: `none`, `once`, `new_episodes`, `all` — identical semantics to VCR.py; users expect these
- Cassette storage — directory-per-test with numbered `.sql`, `.arrow`, `.json` files
- SQL normalisation via sqlglot — with dialect config and whitespace fallback
- CLI flag `--adbc-record=<mode>` — parallels pytest-recording's `--record-mode`
- `adbc_replay` session-scoped fixture — exposes `.wrap()` for connection wrapping
- `@pytest.mark.adbc_cassette` marker — cassette name and dialect override per test
- `pyproject.toml`/`pytest.ini` configuration — `adbc_cassette_dir`, `adbc_record_mode`, `adbc_dialect`
- Fail-fast error messages on cassette miss — show normalised SQL and available interactions
- Replay without live connection — `ReplayConnection` that never opens a real ADBC driver

**Should have (competitive differentiators):**
- Dialect-aware normalisation with three-level precedence (global default -> marker -> auto-detect)
- Arrow IPC cassette format preserving schema metadata precisely (no alternative serialiser)
- Driver-agnostic proxy via ADBC cursor interface (Snowflake, Databricks, BigQuery, etc.)
- Numbered interaction ordering (`000_`, `001_`) for clean PR diffs
- Parameters and options as part of cassette key — parameterised queries with different bind values get different cassettes

**Defer to v1.x:**
- Sensitive data scrubbing hooks (design the empty hook slot in v1; implement in v1.x)
- Cassette format versioning (`manifest.json`)
- `drop_unused_requests` equivalent
- Better cassette miss diagnostics with closest-match diff

**Defer to v2+:**
- DBAPI2 cursor support
- Combined/multi-cassette loading
- Async cursor support

**Confirmed anti-features (do not build):**
- Custom matchers / pluggable matching (SQL matching has one correct strategy)
- Custom serialisers (Arrow IPC is the only format with schema fidelity)
- Custom persisters (cassettes must be filesystem-committed for PR diffs)
- Network/socket blocking (ADBC drivers use native C/C++ — socket patching does not reach them)

### Architecture Approach

The plugin follows the standard pytest plugin architecture: `pytest11` entry point registration, three-hook bootstrap (`pytest_addoption`, `pytest_configure`, fixture definitions), and a session-scoped manager with per-test cassette state. The domain logic is split across four purpose-specific modules (`_types.py`, `normalise.py`, `cassette.py`, `proxy.py`) beneath a thin `plugin.py` wiring layer. The recommended fixture scoping is: a session-scoped `_adbc_replay_manager` holding immutable config + a function-scoped `adbc_replay` fixture that creates the per-test cassette context from `request.node.nodeid`. The cursor proxy uses `__getattr__` delegation to the real cursor for unimplemented methods in record mode, and raises `NotImplementedError` with a clear message in replay mode.

See [ARCHITECTURE.md](.planning/research/ARCHITECTURE.md) for full data flow diagrams, component boundaries, and anti-patterns.

**Major components:**
1. `plugin.py` — thin wiring layer: pytest hooks, fixture definitions, marker registration, CLI options; no domain logic
2. `proxy.py` — `ReplayConnection` + `ReplayCursor`: transparent proxy intercepting `execute()` and `fetch_*()` calls; delegates to real cursor in record mode, reads cassette in replay mode
3. `cassette.py` — cassette store: directory I/O, `CassetteKey` value object, interaction counter, record/replay mode state machine; owns all filesystem operations
4. `normalise.py` — SQL normalisation: `sqlglot.transpile()` with dialect, whitespace fallback; pure function; cached with LRU
5. `_types.py` — `RecordMode` enum and shared type aliases; prevents circular imports

### Critical Pitfalls

Research identified 9 pitfalls across three severity levels. The five most consequential:

See [PITFALLS.md](.planning/research/PITFALLS.md) for full pitfall catalogue with recovery strategies and the "looks done but isn't" checklist.

1. **Fixture scope mismatch** — Session-scoped `adbc_replay` must not hold per-test cassette state; use session-scoped manager + function-scoped cassette context. Getting this wrong requires a full fixture rearchitecture.
2. **Replay-only path opens a real connection** — In `mode=none`, `wrap()` must never import or reference an ADBC driver. Lazy-import the driver; the replay path must be backed only by `pyarrow` and cassette files. This is the primary CI use case.
3. **Incomplete cursor protocol** — `ReplayCursor` must implement `description`, `rowcount`, `close()`, `__enter__`/`__exit__`, and `executemany()`, or use `__getattr__` delegation. Missing methods produce opaque `AttributeError`s in consuming code.
4. **sqlglot silently rewrites SQL semantics** — Always require a dialect; never auto-detect. Pin sqlglot minor version in CI; document that major sqlglot upgrades may require cassette regeneration.
5. **Duplicate queries need ordered-queue replay** — A test executing the same SQL twice expects two distinct results. Implement replay as an ordered sequence (queue-per-key), not a dict lookup. Must be designed from the start; retrofitting is expensive.

## Implications for Roadmap

The architecture research defines a natural four-phase build order based on component dependencies. Phases 1 and 2 are where all critical pitfalls must be addressed. Phase 3 is polish and developer experience. Phase 4 is integration testing and publication.

### Phase 1: Foundation and Plugin Skeleton
**Rationale:** No other work is possible until the plugin is discoverable by pytest and the cursor protocol boundary is defined. Entry point misconfiguration and fixture scope mismatch are the highest-recovery-cost pitfalls — fix them first.
**Delivers:** Installable plugin that pytest recognises (`--adbc-record` flag visible, `adbc_replay` fixture available, `adbc_cassette` marker registered). `ReplayCursor` and `ReplayConnection` with complete cursor protocol coverage (including `__getattr__` delegation). Session + function fixture hierarchy with per-test cassette path resolution from node ID. Replay-only mode confirmed to work with no ADBC driver installed.
**Addresses features:** Plugin registration, `adbc_replay` fixture, `@pytest.mark.adbc_cassette` marker, CLI flag `--adbc-record`, INI configuration, replay without live connection, cursor wrapper shell.
**Avoids pitfalls:** Entry point not declared (P1), fixture scope mismatch (P2), incomplete cursor protocol (P6), replay-only requires driver (P9), marker not registered (implied by P1).
**Research flag:** Standard patterns — well-documented pytest plugin bootstrap. Skip `research-phase`.

### Phase 2: Core Record/Replay Engine
**Rationale:** The cassette format, SQL normalisation, and record mode state machine are the core value of the plugin. All technically complex pitfalls live here and must be validated with comprehensive tests before Phase 3 adds UX polish.
**Delivers:** Working record/replay cycle with all four modes (`none`, `once`, `new_episodes`, `all`). Cassette directory-per-test structure with numbered `.sql`, `.arrow`, `.json` files. sqlglot-based SQL normalisation with dialect config, whitespace fallback, and LRU cache. Ordered-queue replay engine (not dict-based) to handle duplicate queries. Arrow IPC round-trip verified with schema metadata. `CassetteKey` with deterministic JSON parameter serialisation. Fail-fast error messages on cassette miss.
**Uses stack:** `pyarrow.ipc.RecordBatchFileWriter`/`RecordBatchFileReader` in `cassette.py`; `sqlglot.transpile()` in `normalise.py`.
**Implements architecture:** `cassette.py` and `normalise.py` (Phase 1 in architecture's build order); `proxy.py` wired to cassette store (Phase 2 in architecture's build order).
**Avoids pitfalls:** sqlglot semantic rewrites (P3), Arrow IPC schema mismatch (P4), cassette key collision from duplicate queries (P5), SQL normalisation false matches (P8), test isolation failure (P7).
**Research flag:** Needs `research-phase` for sqlglot dialect edge cases and Arrow IPC streaming patterns for large result sets.

### Phase 3: Plugin Wiring and Developer Experience
**Rationale:** Once the engine works, wire it into pytest properly and make error messages and UX match user expectations from pytest-recording.
**Delivers:** Complete `plugin.py` hook implementations integrating all Phase 1 and Phase 2 components. Record mode printed in pytest header. Empty scrubbing hook slot designed (implementation deferred). `manifest.json` slot in cassette directory for future versioning. `.gitattributes` guidance for `.arrow` binary files. Cassette miss errors showing normalised SQL and available interactions.
**Addresses features:** Configuration via `pyproject.toml`/`pytest.ini`, record mode header output, scrubbing hook interface, cassette format versioning slot.
**Avoids pitfalls:** UX pitfalls (no record mode indication, cassette miss errors without context, missing `.gitattributes` guidance).
**Research flag:** Standard patterns for pytest header output and INI options. Skip `research-phase`.

### Phase 4: Integration Testing and Publication
**Rationale:** pytester-based integration tests validate the full record/replay cycle end-to-end. adbc-driver-sqlite enables a real ADBC cycle without warehouse credentials. Package and publish only after integration tests pass.
**Delivers:** Full pytester-based test suite exercising all four record modes against adbc-driver-sqlite. Parametrised test cassette isolation verified. Cross-contamination tests (tests run together vs. individually). CI configuration with replay-only job (no driver installed). PyPI publication via `uv publish`.
**Uses stack:** `adbc-driver-sqlite>=1.0` as dev dependency for integration tests; `pytester` built-in fixture; CI matrix with `uv run --python 3.x`.
**Implements architecture:** Phase 4 in architecture's build order.
**Avoids pitfalls:** All integration-level pitfalls surfaced via the "looks done but isn't" checklist.
**Research flag:** Standard patterns. Skip `research-phase`.

### Phase Ordering Rationale

- **Phase 1 before Phase 2:** The cursor proxy interface must be defined before the cassette engine is implemented — `cassette.py` is called by `ReplayCursor`, not the reverse.
- **Phase 2 before Phase 3:** Plugin wiring in `plugin.py` is trivial once the domain objects (`Cassette`, `ReplayCursor`, `normalise_sql`) exist. Wiring thin code to incomplete domain objects is a waste.
- **Phase 3 before Phase 4:** Integration tests test the fully wired plugin. Running pytester against incomplete wiring produces misleading test failures.
- **Pitfall prevention is front-loaded:** Fixture scope (P2), cursor protocol (P6), and replay-only path (P9) are all Phase 1. sqlglot semantics (P3), duplicate queries (P5), and Arrow IPC (P4) are all Phase 2. This matches the recovery cost ordering — high-cost pitfalls are addressed earliest.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** sqlglot dialect-specific normalisation edge cases for Snowflake `LATERAL FLATTEN`, Databricks `QUALIFY`, and `MERGE` syntax — needs validation against sqlglot 26+ changelog to confirm which dialect-specific AST nodes are stable vs. in flux.
- **Phase 2:** Arrow IPC streaming for large result sets — `RecordBatchStreamWriter` vs. `RecordBatchFileWriter` trade-offs; need to confirm whether file format supports streaming reads without loading the full table.

Phases with standard patterns (skip research-phase):
- **Phase 1:** pytest plugin bootstrap via `pytest11` entry points is fully documented and verified against pytest-cov source. No novel patterns needed.
- **Phase 3:** pytest INI options and header output are standard hook patterns — `pytest_configure`, `pytest_terminal_summary`. No novel patterns needed.
- **Phase 4:** pytester fixture usage and `uv publish` workflow are standard and well-documented.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All version floors verified from PyPI JSON API (Feb 2026). Entry point pattern verified from pytest-cov source. Existing `pyproject.toml` and `uv.lock` confirm tooling choices. |
| Features | HIGH | Based on direct source inspection of VCR.py 8.1.1, pytest-recording 0.13.4, responses 0.26.0, pytest-httpserver 1.1.5. MVP feature set is well-defined. Competitor landscape confirmed greenfield (no existing ADBC record/replay plugin found on PyPI). |
| Architecture | HIGH | Component boundaries verified against installed pytest-cov source and pluggy 1.6.0. Build order reflects actual module dependency graph. The cassette-key hybrid (sequence-based replay with key validation) is the one area requiring implementation decision. |
| Pitfalls | MEDIUM | Plugin development patterns and VCR.py/pytest-recording prior art are HIGH confidence. sqlglot-specific dialect stability and ADBC cursor full method surface are MEDIUM — warrant validation against installed packages before implementation. |

**Overall confidence:** HIGH

### Gaps to Address

- **Full `adbc_driver_manager.dbapi.Cursor` method audit:** Before writing `ReplayCursor`, run `dir()` against the installed cursor class to enumerate all public methods and properties. The pitfalls research identifies the most important ones but cautions that the full surface may be wider than documented.
- **sqlglot dialect-specific AST stability:** Validate that `sqlglot.transpile(sql, read="snowflake", write="snowflake")` produces identical output across sqlglot 26.x and 29.x for the most common Snowflake-specific constructs (`LATERAL FLATTEN`, `QUALIFY`, `ILIKE`). This determines whether cassette keys are stable across dependency upgrades.
- **Arrow IPC file vs. stream format choice:** Confirm whether `RecordBatchFileWriter` (seekable, supports indexed reads) or `RecordBatchStreamWriter` (non-seekable, lower memory for streaming) is the right default for cassette storage. File format is simpler for v1; stream format is better for large result sets. This decision affects the cassette storage API.
- **Cassette key hybrid decision:** The architecture research identifies a design choice: pure sequence-based replay (simple, matches VCR.py) vs. content-keyed lookup (tolerates reordering). Recommendation is sequence-based with key validation for diagnostics. This must be locked in before implementing `cassette.py`.

## Sources

### Primary (HIGH confidence)
- PyPI JSON API — version floors verified for pyarrow (23.0.1), sqlglot (29.0.1), adbc-driver-manager (1.10.0), pytest (9.0.2), uv-build (0.10.7), pytest-cov (7.0.0), ruff (0.15.4), basedpyright (1.38.2)
- VCR.py 8.1.1 — direct PyPI source inspection of `vcr/config.py`, `vcr/record_mode.py`, `vcr/matchers.py`, `vcr/cassette.py`, `vcr/serialize.py`, `vcr/persisters/filesystem.py`
- pytest-recording 0.13.4 — direct PyPI source inspection of `pytest_recording/plugin.py`, `pytest_recording/_vcr.py`, `pytest_recording/network.py`
- responses 0.26.0, pytest-httpserver 1.1.5 — direct PyPI source inspection
- Installed pytest-cov source (`pytest_cov/plugin.py`) — reference plugin structure and entry_points format
- Installed pytest source (`_pytest/hookspec.py`) — hook specifications
- Project design document (`_notes/pytest-adbc-replay-design.md`) — primary project context

### Secondary (MEDIUM confidence)
- pluggy 1.6.0 source — hook system internals; consistent with documentation
- pytest-recording / VCR.py conventions — cross-validated between source inspection and documentation
- Domain expertise with pytest plugin development patterns — fixture scoping, hook lifecycle, pytester usage

### Tertiary (LOW confidence)
- PyPI search for existing ADBC record/replay plugins — confirmed absence but PyPI search is incomplete; GitHub-only projects may exist
- sqlglot dialect stability across versions — training data knowledge; needs validation against sqlglot changelog for versions 26-29

---
*Research completed: 2026-02-28*
*Ready for roadmap: yes*
