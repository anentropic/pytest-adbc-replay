# Changelog

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
