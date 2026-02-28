# Pitfalls Research

**Domain:** pytest record/replay plugin for ADBC database connections
**Researched:** 2026-02-28
**Confidence:** MEDIUM (based on domain expertise with pytest plugins, VCR.py patterns, Arrow IPC, and sqlglot; WebSearch/Context7 unavailable for verification)

## Critical Pitfalls

### Pitfall 1: pytest Entry Point Not Declared or Wrongly Named

**What goes wrong:**
The plugin is never loaded by pytest. Tests appear to pass but no recording or replaying occurs. Users install the package and nothing happens -- no `--adbc-record` flag, no `adbc_replay` fixture, no markers recognised.

**Why it happens:**
pytest discovers plugins via the `pytest11` entry point group in packaging metadata. If the entry point is missing from `pyproject.toml`, points to the wrong module, or uses the wrong group name, pytest silently ignores the plugin. The `src` layout (`src/pytest_adbc_replay/`) adds an extra layer where the module path in the entry point must match the installed package path, not the filesystem path.

**How to avoid:**
- Declare the entry point explicitly in `pyproject.toml`:
  ```toml
  [project.entry-points.pytest11]
  adbc_replay = "pytest_adbc_replay.plugin"
  ```
- The entry point name (`adbc_replay`) becomes the plugin name in pytest's plugin manager. Keep it simple and hyphen-free (underscores only).
- Write an integration test that runs `pytest --co` in a subprocess and verifies the plugin is registered (`pytestconfig.pluginmanager.has_plugin("adbc_replay")`).
- Test with `pip install -e .` (not just running from source) to catch packaging issues early.

**Warning signs:**
- `pytest --co -p adbc_replay` says "no module named..." or plugin not found
- `--adbc-record` flag not recognised
- `adbc_replay` fixture not available (fixture not found error)

**Phase to address:**
Phase 1 (plugin skeleton). This is the very first thing to get right -- nothing else works without it.

---

### Pitfall 2: Fixture Scope Mismatch Between adbc_replay and Cassette Lifecycle

**What goes wrong:**
If `adbc_replay` is session-scoped but cassette state is per-test, cassettes from one test bleed into another. Conversely, if the fixture is function-scoped but the underlying connection is expensive, every test opens and closes a real database connection during recording (slow, may hit connection limits).

The design document specifies `adbc_replay` as session-scoped, but cassette directories are per-test. This creates a scope mismatch: a session-scoped fixture must track which test is currently running to route cassette operations to the correct directory.

**Why it happens:**
VCR.py solved this with `use_cassette()` as a context manager per-test, but pytest fixtures have rigid scoping. A session-scoped fixture does not naturally know which test is active. The pytest hook `pytest_runtest_protocol` can signal test boundaries, but coordinating between the hook and the fixture is error-prone.

**How to avoid:**
- Make `adbc_replay` session-scoped for connection management but use a **separate function-scoped fixture** for cassette lifecycle. The function-scoped fixture receives the test's node ID, resolves the cassette directory, and configures the session-scoped replay manager for the current test.
- Alternatively, use `request.node` in the fixture to derive per-test cassette paths. But if the fixture is session-scoped, `request.node` points to the session, not the individual test -- this is the classic trap.
- Pattern: session-scoped `_adbc_replay_manager` (holds config, manages connection pool) + function-scoped `adbc_replay` (creates per-test cassette context using `request.node.nodeid`).

**Warning signs:**
- Tests pass individually but fail when run together (cassette cross-contamination)
- Cassette files appear in wrong directories
- `request.node.nodeid` returns unexpected values in session-scoped fixtures

**Phase to address:**
Phase 1 (plugin skeleton / fixture design). Getting this wrong requires rearchitecting the fixture hierarchy later.

---

### Pitfall 3: sqlglot Transpile Silently Rewrites SQL Semantics

**What goes wrong:**
`sqlglot.transpile()` does not just normalise formatting -- it can silently rewrite SQL semantics when using the wrong dialect or no dialect. Examples:
- `ILIKE` (Snowflake/Postgres) may be rewritten to `LIKE` with a `LOWER()` wrapper in a different dialect
- `QUALIFY` (Snowflake) may be dropped or moved into a subquery
- `LATERAL FLATTEN` (Snowflake) has no equivalent in standard SQL
- `MERGE` syntax differs between dialects; transpile may restructure it
- `STRUCT` type literals in BigQuery may be parsed differently than Databricks

The normalised SQL stored in the cassette then differs from what a different version of sqlglot would produce, causing cassette misses even though the original SQL has not changed.

**Why it happens:**
sqlglot is a transpiler, not just a formatter. When `read` and `write` dialects are the same, semantic rewrites are minimal but not zero -- sqlglot still canonicalises expressions. When no dialect is specified, sqlglot guesses, and the guess may change between versions. Vendor-specific extensions that sqlglot does not fully support may be parsed into a lossy AST.

**How to avoid:**
- **Always require a dialect for normalisation.** The fallback of `dialect=None` should be strongly discouraged in documentation and produce a warning. Auto-detection is the root cause of instability.
- **Pin sqlglot version in CI** and document that upgrading sqlglot may require cassette regeneration (similar to how VCR.py version upgrades can invalidate HTTP cassettes).
- **Use `pretty=False` for the normalisation key** but compare the normalised SQL at record-time vs. replay-time rather than storing the normalised form as the key. Store the raw SQL in the `.sql` file and the normalisation hash as the lookup key.
- **Write tests with known tricky SQL patterns** for each supported dialect to detect sqlglot regressions.
- **The fallback path (whitespace-only normalisation) must produce a stable key too.** Test that `" ".join(sql.split())` handles tabs, newlines, and trailing whitespace consistently.

**Warning signs:**
- Cassettes recorded with sqlglot version X fail with version Y (no SQL change in user code)
- Cassette miss on SQL that "looks the same" in `.sql` files
- Normalised SQL in cassette differs semantically from what the test actually executed

**Phase to address:**
Phase 2 (SQL normalisation). Build a comprehensive test matrix of dialect-specific SQL patterns before relying on normalisation in the cassette key path.

---

### Pitfall 4: Arrow IPC Schema Metadata Mismatch Causes Silent Data Corruption on Replay

**What goes wrong:**
Arrow IPC faithfully preserves schema metadata (field names, types, nullability, custom metadata). But warehouse drivers return schemas that may differ across driver versions, connection settings, or even session parameters. For example:
- Snowflake ADBC may return `INT64` for a column that Databricks ADBC returns as `INT32`
- Timezone-aware `TIMESTAMP_TZ` vs. timezone-naive `TIMESTAMP` depends on session settings
- `DECIMAL(38, 0)` vs. `INT64` for integer columns depends on driver configuration
- Custom metadata keys (e.g., Snowflake column comments) may be present in one recording session and absent in another

On replay, the test receives exactly the schema that was recorded. If the consuming code checks schema details (field types, metadata), replayed data may behave differently than live data.

**Why it happens:**
Arrow IPC is a precise format -- it preserves everything, including things the test author may not have intended to record. This is a feature (high fidelity) but also a hazard (over-specification). The same logical query can produce different Arrow schemas depending on driver version, server-side settings, or session configuration.

**How to avoid:**
- **Document that cassettes are tied to the driver version and connection settings used during recording.** When upgrading drivers, re-record.
- **Do not attempt schema normalisation in v1.** The complexity of mapping between type systems is enormous and out of scope. Accept that cassettes are snapshots of a specific driver's output.
- **Store driver version metadata in the cassette directory** (e.g., in a `manifest.json`) so stale cassettes can be detected.
- **Write tests that verify replay produces identical Arrow tables** (schema + data) to confirm IPC round-trip fidelity.

**Warning signs:**
- Tests pass with replayed cassettes but fail against live database (schema drift)
- `pyarrow.ipc.read_file()` raises on old cassettes after pyarrow upgrade (IPC format version mismatch -- rare but possible across major versions)
- Decimal precision/scale differs between recorded and expected values

**Phase to address:**
Phase 2 (cassette format / Arrow IPC). Address during the serialisation layer, not retroactively.

---

### Pitfall 5: Cassette Key Collision From Duplicate Queries Within a Single Test

**What goes wrong:**
A test executes the same SQL query multiple times (e.g., polling for a result, or executing the same SELECT before and after a mutation). The cassette key is `(normalised_sql, parameters, options)` -- identical for all invocations. The cassette stores one result, but the test expects different results from each call (e.g., row count changes).

In the design, interactions are numbered in execution order (`000_`, `001_`, ...). But the *lookup* during replay must also be order-dependent, not just key-dependent. If replay uses a dict keyed by `(sql, params)`, it returns the same result every time.

**Why it happens:**
VCR.py handles this by replaying interactions in sequence -- first request with matching key returns the first recorded response, second returns the second, etc. This is an ordered-queue-per-key model. If the implementation uses a simple dict lookup instead, duplicate queries break.

**How to avoid:**
- **Implement replay as an ordered sequence, not a dict lookup.** Each cassette is a list of interactions replayed in order. When a matching key is found, consume it (pop from the front of that key's queue). This matches VCR.py's proven model.
- **Fail loudly if replay exhausts all recorded interactions for a key** but the test requests more. This catches tests that changed call counts.
- **In `new_episodes` mode, append new interactions rather than replacing existing ones** -- but be careful about interaction numbering.

**Warning signs:**
- Tests that call the same query multiple times get the same result on replay (when they should get different results)
- Cassette directories have only one `.sql`/`.arrow` pair even though the test executes the query multiple times during recording
- Tests pass in record mode but fail in replay mode with correct cassettes present

**Phase to address:**
Phase 2 (cassette matching / replay engine). Must be designed from the start -- retrofitting ordered replay onto a dict-based implementation requires reworking the core data structure.

---

### Pitfall 6: ReplayCursor Does Not Implement Enough of the Cursor Protocol

**What goes wrong:**
The `ReplayCursor` wrapper implements `execute()`, `fetch_arrow_table()`, `fetchone()`, `fetchmany()`, `fetchall()`, and `fetch_record_batch()`. But consuming code may also use:
- `cursor.description` (DBAPI2 column metadata)
- `cursor.rowcount`
- `cursor.close()`
- `cursor.executemany()`
- `cursor.adbc_ingest()` (ADBC-specific bulk ingest)
- `cursor.adbc_get_table_types()` / `adbc_get_objects()` (ADBC catalog methods)
- Context manager protocol (`__enter__`/`__exit__`)
- `cursor.adbc_statement` (low-level ADBC statement handle)

Missing any of these causes `AttributeError` at runtime, with an unhelpful error that does not point to the replay wrapper as the cause.

**Why it happens:**
The ADBC cursor API surface is wider than the subset needed for basic query-and-fetch. The design document focuses on the core path but consuming applications (especially ORMs, query builders, or dbt adapters) use the full protocol.

**How to avoid:**
- **Start with a complete audit of `adbc_driver_manager.dbapi.Cursor`** to enumerate all public methods and properties. Implement or explicitly raise `NotImplementedError` with a clear message for each.
- **Proxy unknown attribute access** to the real cursor in record mode (`__getattr__` delegation). In replay mode, raise `NotImplementedError("ReplayCursor does not support {attr} in replay mode")`.
- **The `description` property is especially important** -- DBAPI2 code relies on it for column names and types. Derive it from the recorded Arrow schema.
- **Context manager protocol is mandatory** -- cursors are almost always used in `with` statements.

**Warning signs:**
- `AttributeError: 'ReplayCursor' object has no attribute 'description'`
- Tests work with simple `execute()`/`fetchall()` but fail when using cursor metadata
- dbt adapters or SQLAlchemy code fails with the replay cursor

**Phase to address:**
Phase 1 (cursor wrapper). Audit the full API surface before writing the wrapper, not after users report missing methods.

---

### Pitfall 7: Test Isolation Failure When Recording and Replaying in the Same pytest Session

**What goes wrong:**
If a test suite mixes `record` and `replay` modes (e.g., `--adbc-record=new_episodes` records some tests and replays others), the cassette state must be isolated per-test. A common bug: the cassette manager holds mutable state (interaction counter, current cassette path) at the session level, and tests running in parallel or in unexpected order corrupt each other's state.

Even without parallelism, pytest's collection and execution order can surprise: parametrized tests, class-based tests, and fixture finalizers can interleave in unexpected ways.

**Why it happens:**
Session-scoped state shared across tests is the root cause. VCR.py avoids this by using `use_cassette()` as a context manager scoped to each test. If the pytest plugin manages cassette state in a session-scoped fixture without per-test isolation, tests leak state.

**How to avoid:**
- **Each test must get its own `Cassette` instance** with its own interaction counter, file paths, and mode. Never share a `Cassette` object across tests.
- **The `ReplayConnection.cursor()` must create cursors bound to the current test's cassette**, not a shared one.
- **Explicitly reset state in the function-scoped fixture teardown** -- do not rely on garbage collection.
- **Test with `pytest-xdist` early** to surface parallelism bugs. Even if xdist support is not a v1 goal, it reveals shared-state issues.

**Warning signs:**
- Tests pass when run individually (`pytest test_one.py`) but fail when run together (`pytest`)
- Cassette files contain interactions from the wrong test
- Interaction numbering is non-sequential (e.g., `000`, `003`, `001`)

**Phase to address:**
Phase 1 (fixture design) and Phase 2 (cassette manager). The isolation boundary must be established in Phase 1; the cassette manager enforces it in Phase 2.

---

### Pitfall 8: SQL Normalisation False Matches -- Different Queries Normalise to the Same Key

**What goes wrong:**
Two semantically different queries normalise to the same canonical form, causing a cassette hit on the wrong recorded result. Examples:
- `SELECT * FROM foo WHERE a = 1` and `SELECT * FROM foo WHERE a = 1` with different parameter bindings (if parameters are not included in the key, or parameter serialisation is not deterministic)
- Queries differing only in comments (`-- v1` vs `-- v2`) where sqlglot strips comments during normalisation
- `SELECT a, b FROM t` vs `SELECT b, a FROM t` if sqlglot reorders columns (it does not by default, but custom optimisers might)

**Why it happens:**
Normalisation intentionally removes information (formatting, casing, whitespace). If it removes too much (comments, parameter differences), distinct queries collide. The key design `(normalised_sql, parameters, options)` mitigates this but only if parameter serialisation is deterministic and complete.

**How to avoid:**
- **Include parameters in the key with deterministic serialisation.** Use `json.dumps(params, sort_keys=True, default=str)` for dicts; for positional params, serialise as a JSON array. Handle non-JSON-serialisable types (datetime, Decimal, bytes) with a custom encoder.
- **Do not strip SQL comments during normalisation.** Comments may carry semantic meaning (query tags, hints). Either preserve them or document that comments are stripped and will not differentiate cassettes.
- **Test the normalisation function with pairs of queries that should NOT match** -- not just pairs that should match.

**Warning signs:**
- A test replays a result that belongs to a different query (data shape mismatch, wrong column names)
- Parameter changes do not cause cassette misses when they should
- Adding or removing a SQL comment causes unexpected cassette miss or hit

**Phase to address:**
Phase 2 (SQL normalisation and cassette key design). The key structure must be validated with adversarial test cases.

---

### Pitfall 9: Connection-Wrapping Breaks When Real Connection Is Not Needed (Replay-Only Mode)

**What goes wrong:**
In `mode=none` (replay only), no real database connection should be opened -- this is the entire point for CI. But if `ReplayConnection.__init__` requires a real connection object, or if `adbc_replay.wrap()` tries to import and initialise an ADBC driver, the plugin fails in environments without warehouse credentials or driver binaries.

**Why it happens:**
The `wrap()` API in the design takes `driver` and `db_kwargs` as arguments. If the implementation eagerly imports the driver module or calls `connect()` before checking the record mode, it fails. ADBC drivers are native extensions (C/C++ shared libraries) that may not even be installed in CI.

**How to avoid:**
- **In replay-only mode (`none`), `wrap()` must return a `ReplayConnection` that does not import or reference any driver.** The driver name is ignored entirely.
- **Lazy import the driver module.** Only import and connect when the mode requires recording (`all`, `once`, `new_episodes`).
- **Test the replay-only path in a clean environment** without any ADBC driver packages installed. This is the primary CI use case.
- **The `ReplayConnection` in replay mode should be fully self-contained** -- backed only by cassette files and pyarrow, with zero driver dependencies.

**Warning signs:**
- `ImportError: No module named 'adbc_driver_snowflake'` in CI (replay-only mode)
- `wrap()` raises before any test runs because it cannot connect to the database
- Plugin requires warehouse environment variables even when `--adbc-record` is not set

**Phase to address:**
Phase 1 (connection wrapper). This is a core architectural decision -- replay-only must be completely offline. Get it wrong and the plugin's primary value proposition is broken.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip `__getattr__` proxy on ReplayCursor | Simpler implementation | Every new cursor method users need requires a code change | Never -- implement `__getattr__` delegation from day one |
| Use `pickle` for parameter serialisation in cassette keys | Handles arbitrary Python objects | Non-deterministic across Python versions, security risk, not human-readable | Never -- use JSON with a custom encoder |
| Store normalised SQL as the cassette filename | Quick lookup by filename | Filesystem path length limits (255 chars), special characters in SQL, non-portable across OS | Never -- use a hash for the filename, store SQL in a separate `.sql` file (design already does this) |
| Skip manifest/version metadata in cassette directories | Faster to ship v1 | No way to detect stale cassettes or format changes later | Acceptable for v1 MVP, but add the `manifest.json` slot early so the directory structure does not change |
| Hardcode `pyarrow.ipc.write_file` without chunking | Simple for small results | Memory explosion on large result sets (multi-GB Arrow tables) | Acceptable for v1 if documented; add streaming IPC writer in v2 |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| pytest-recording co-existence | Both plugins try to register `--record-mode` flag; name collision | Use `--adbc-record` (already in design) -- never shadow pytest-recording's CLI flags |
| pytest-xdist (parallel tests) | Session-scoped fixtures are instantiated per-worker, not shared | Cassette files must use test-specific paths; no shared mutable state in the cassette manager |
| pyarrow version skew | Arrow IPC files written with pyarrow 15 may have minor format differences from pyarrow 17 | Arrow IPC is forward-compatible but include pyarrow version in manifest for debugging; test with minimum and maximum supported versions |
| sqlglot version skew | sqlglot 21 normalises differently from sqlglot 25 (new dialect features, parser changes) | Pin sqlglot range in dependencies; document cassette regeneration on major sqlglot upgrade |
| adbc-driver-manager type stubs | `adbc_driver_manager.dbapi.Cursor` may not have complete type stubs; basedpyright strict mode fails | Use `TYPE_CHECKING` guards and provide protocol classes for the cursor interface rather than inheriting from the driver manager |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading entire Arrow table into memory on replay | OOM on tests with large result sets | Stream from IPC file using `RecordBatchFileReader` instead of `read_all()` | Result sets > 500 MB |
| Reading all cassette files at session start | Slow test startup when cassette directory has thousands of files | Lazy-load cassettes on first access per test, not at session init | > 200 cassette directories |
| sqlglot.transpile() called on every query even in replay-only mode | Unnecessary CPU overhead; sqlglot parse can be slow on complex queries | Cache normalised SQL (LRU cache keyed on raw SQL string); in replay mode, normalisation is only needed for lookup | Tests with > 50 queries each |
| JSON serialisation of large parameter lists for key generation | Slow key computation when parameters include large data structures | Hash the serialised parameters rather than comparing full strings; use hashlib for O(n) hashing vs O(n^2) string comparison | Parameters with > 10 KB of data |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Recording sensitive data in cassette files (passwords in SQL, PII in results) | Credentials or PII committed to git, visible in PR diffs | Document that cassettes contain raw query results; design the scrubbing hook interface in v1 even if implementation is v2; add `.gitignore` patterns for cassettes in sensitive projects |
| Storing database connection strings in cassette metadata | Warehouse URLs, usernames, and tokens exposed in committed files | Never store connection parameters in cassettes -- only store SQL, parameters, and results |
| Pickle-based parameter serialisation | Arbitrary code execution if malicious cassette files are loaded | Use JSON only; never deserialise untrusted formats; document that cassettes should be treated as trusted test fixtures |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Cassette miss error says "no matching cassette" without showing what was expected vs. what was found | User has no idea why replay failed; must manually diff SQL | Error message should show: normalised query that was looked up, available cassette keys, and the closest match (Levenshtein or similar) |
| No indication of which record mode is active | User runs tests wondering why cassettes are not being created | Print record mode in pytest header (similar to pytest-recording's "VCR record mode: none") |
| Cassette directory grows unboundedly as tests are renamed or deleted | Stale cassettes waste disk and confuse diffs | Provide a `pytest --adbc-cleanup` command or a hook that detects orphaned cassette directories (cassettes with no corresponding test) |
| Marker `@pytest.mark.adbc_cassette` not registered | pytest strict markers mode produces warnings or errors | Register the marker in `pytest_configure` with `config.addinivalue_line("markers", ...)` |
| No guidance on `.gitattributes` for `.arrow` files | Git treats `.arrow` files as text, producing useless diffs and potential corruption | Document and/or generate `.gitattributes` entries: `*.arrow binary` |

## "Looks Done But Isn't" Checklist

- [ ] **Plugin registration:** Entry point declared in `pyproject.toml` under `[project.entry-points.pytest11]` -- verify by running `pytest --co` in a clean venv with only the plugin installed
- [ ] **Marker registration:** `adbc_cassette` marker registered in `pytest_configure` -- verify with `pytest --markers | grep adbc`
- [ ] **Replay without driver:** `mode=none` works without any ADBC driver installed -- verify by running tests in a venv with only `pyarrow` and `sqlglot`
- [ ] **Cursor protocol completeness:** `ReplayCursor` implements `description`, `rowcount`, `close()`, `__enter__`/`__exit__` -- verify with `dir(real_cursor)` comparison
- [ ] **Duplicate query replay:** Same query executed twice returns two different recorded results -- verify with a test that does `SELECT 1` twice with different recorded results
- [ ] **Cassette isolation:** Two tests using the same query get independent cassettes -- verify by running both tests and checking cassette directories are separate
- [ ] **sqlglot dialect fallback:** SQL that sqlglot cannot parse still produces a usable (whitespace-normalised) key -- verify with deliberately unparseable SQL
- [ ] **Arrow IPC round-trip:** Schema metadata (field names, types, nullability, custom metadata) survives write-then-read -- verify with a table containing every Arrow type
- [ ] **Parametrised test cassettes:** `test_query[param1]` and `test_query[param2]` get separate cassette directories -- verify nodeid-based path includes parametrize suffix
- [ ] **`.gitattributes` for binary files:** `.arrow` files marked as binary -- verify git does not try to diff them as text

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong fixture scoping (session vs function) | HIGH | Rearchitect fixture hierarchy; all existing tests may need fixture name changes |
| sqlglot version upgrade breaks cassette keys | LOW | Re-record all cassettes: `pytest --adbc-record=all`; commit new cassettes |
| Missing cursor protocol methods | MEDIUM | Add `__getattr__` delegation; may need to add `description` property derived from Arrow schema |
| Cassette key collision (false match) | MEDIUM | Add parameter hash to key; re-record affected cassettes |
| Arrow IPC version incompatibility | LOW | Re-record cassettes with new pyarrow version; old cassettes are replaced |
| Connection opened in replay-only mode | MEDIUM | Refactor `wrap()` to lazy-import driver; requires changing the construction path |
| Test isolation failure (shared cassette state) | HIGH | Refactor cassette manager to per-test instances; may require rewriting the replay engine core |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Entry point not declared | Phase 1 (plugin skeleton) | `pytest --co` in clean venv loads the plugin |
| Fixture scope mismatch | Phase 1 (fixture design) | Tests pass both individually and in suite; cassette directories are per-test |
| sqlglot semantic rewrites | Phase 2 (SQL normalisation) | Test matrix of dialect-specific SQL; normalised key is stable across sqlglot minor versions |
| Arrow IPC schema metadata | Phase 2 (cassette format) | Round-trip test with all Arrow types; schema equality assertion |
| Cassette key collision (duplicates) | Phase 2 (replay engine) | Test with same query executed multiple times returning different results |
| Incomplete cursor protocol | Phase 1 (cursor wrapper) | `dir()` comparison between ReplayCursor and real cursor; all public methods present |
| Test isolation failure | Phase 1 + Phase 2 | Run full suite with `pytest -x` and `pytest` (no `-x`); verify no cross-contamination |
| SQL normalisation false matches | Phase 2 (normalisation) | Adversarial test pairs: queries that differ only in comments, parameter order, column order |
| Replay-only requires driver | Phase 1 (connection wrapper) | CI job runs with no ADBC drivers installed; all replay tests pass |
| Marker not registered | Phase 1 (plugin skeleton) | `pytest --strict-markers` does not warn about `adbc_cassette` |
| No cleanup for stale cassettes | Phase 3 (UX polish) | Rename a test, run cleanup command, verify orphaned cassette removed |
| Large result set memory explosion | Phase 3 (performance) | Test with 1 GB Arrow table; memory usage stays bounded via streaming IPC |

## Sources

- Domain expertise with pytest plugin development patterns (pluggy entry points, fixture scoping, hook lifecycle) -- MEDIUM confidence
- Known VCR.py/pytest-recording patterns for cassette management (ordered replay queue, `use_cassette` scoping, record modes) -- HIGH confidence from prior art analysis
- sqlglot transpile behaviour (dialect-dependent rewrites, comment stripping, AST canonicalisation) -- MEDIUM confidence; specific version behaviour should be validated against sqlglot docs
- Arrow IPC format characteristics (schema metadata preservation, forward compatibility, streaming vs file format) -- HIGH confidence from Apache Arrow specification
- ADBC cursor interface surface (`adbc_driver_manager.dbapi.Cursor` API) -- MEDIUM confidence; full method audit should be done against installed package

---
*Pitfalls research for: pytest-adbc-replay (pytest record/replay plugin for ADBC database connections)*
*Researched: 2026-02-28*
