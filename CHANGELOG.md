# Changelog

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
