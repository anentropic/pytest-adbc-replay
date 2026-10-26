# Changelog

## [1.2.0] - 2026-10-26

### Features

- New `adbc_scrub_result_keys` setting redacts values in recorded query results, not just params. A string column with a listed name has its values replaced with `REDACTED`. So does each listed key inside a string cell that holds JSON, such as the `owner` email in Databricks `DESCRIBE ... AS JSON` output. The recording run gets the scrubbed table too, so recording and replay return the same rows.

### Fixes

- Snowflake `SHOW` statements were recorded with an empty cassette key, so every `SHOW` in a test shared one key. `DESCRIBE` with any object kind other than `TABLE` (`DESCRIBE SEMANTIC VIEW x`, `DESCRIBE VIEW x`, `DESCRIBE SCHEMA x`, `DESCRIBE FUNCTION f` and so on) was recorded as plain `DESCRIBE x`. These statements now keep their full text, which changes their keys, so re-record cassettes that hold them. With no `adbc_dialect` set, no sqlglot generator keeps a `DESCRIBE` kind, so those statements take the whitespace-only fallback and emit `NormalisationWarning`: their keys keep keyword case as written. Keys for all other statements, including `DESCRIBE TABLE x`, are unchanged.

## [1.1.2] - 2026-10-14

### Changes

- The project moved to the s-layer GitHub organisation. The package's Homepage, Source, Issues and Documentation links now point at github.com/s-layer/pytest-adbc-replay and s-layer.github.io/pytest-adbc-replay. No code changes.

## [1.1.1] - 2026-06-23

### Fixes

- Record mode now preserves the real driver's `connect()` signature on the auto-patched module (`functools.wraps`). Callers that introspect `inspect.signature(driver.connect).parameters` to choose their call convention — notably adbc-poolhouse distinguishing `db_kwargs={...}` "Family A" drivers (Snowflake, PostgreSQL, BigQuery, FlightSQL) from `**kwargs` "Family B" drivers (DuckDB, SQLite) — previously saw the patched `(**kwargs)` signature, mis-detected a Family-A driver as Family B, and flat-unpacked its options. The real driver then received `db_kwargs=None`, surfacing (for Snowflake) as `OperationalError: 260000: account is empty`. The bug affected record mode only against Family-A drivers; replay never opens a real connection, and Family-B drivers genuinely want flat unpacking, so it was previously invisible.

## [1.1.0] - 2026-06-14

### Breaking Changes

- Cursor fetch methods (`fetch_arrow_table`, `fetchall`, `fetchone`, `fetchmany`, and `fetchallarrow` via delegation) now raise `ProgrammingError` when called before `execute()`, matching real ADBC. They previously returned an empty result or `None`. Migration: call a fetch method only after `execute()`.

### Features

- Full ADBC Cursor API parity for ReplayCursor (FETCH-01..05, DBAPI-01..07, ADBCX-01..04)
- Arrow and DataFrame fetch methods: `fetch_record_batch`, `fetch_arrow`, `fetchallarrow`, `fetch_df`, `fetch_polars` (pandas and polars imported lazily, no packaging extras)
- DBAPI completeness: iteration via `next`, `rownumber`, `connection`, no-op `setinputsizes`/`setoutputsize`, and intentional `NotSupportedError` for `nextset`/`callproc`
- ADBC extension methods: record mode delegates to the real cursor; replay derives `adbc_execute_schema` from the cassette, no-ops `adbc_cancel`/`adbc_prepare`, and raises `NotSupportedError` for `adbc_ingest`, partition methods, and `adbc_statement`
- Introspection parity test (PARITY-01) asserting the full real Cursor surface is covered and failing loudly when ADBC adds a member
- Cursor Surface reference page (DOC-01) documenting every member and its replay-mode behavior

## [1.0.0] - 2026-03-01

### Features

- Record ADBC cursor queries to cassette files and replay them without a live database connection
- Four record modes: none (replay-only), once, new_episodes, all
- SQL normalisation via sqlglot for stable cassette keys across whitespace and casing variations
- Arrow IPC cassette storage preserving schema metadata
- pyproject.toml / pytest.ini configuration (adbc_cassette_dir, adbc_record_mode, adbc_dialect)
- Scrubber hook slot for sensitive data redaction (adbc_scrubber fixture)
- Public types: CassetteMissError, NormalisationWarning, NO_DEFAULT_SERIALISERS, ReplaySession
- PEP 561 py.typed marker for downstream type-checker support
- Implement plugin skeleton and cursor proxy
- Add SQL normaliser with normalise_sql() and NormalisationWarning
- Add parameter serialisation registry with type-tagged JSON serialisation
- Add cassette I/O with Arrow IPC, JSON, and SQL file storage
- Wire record/replay state machine through connection stack
- Wire ini config, report header, and scrubber fixture
