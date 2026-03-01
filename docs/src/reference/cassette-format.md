# Cassette File Format

Each cassette is a directory containing one set of files per recorded interaction.

## Directory layout

```
tests/cassettes/
└── {cassette_name}/
    ├── 000.sql      # Interaction 0: normalised SQL
    ├── 000.arrow    # Interaction 0: query result as Arrow IPC
    ├── 000.json     # Interaction 0: parameters and driver options
    ├── 001.sql      # Interaction 1 (if the test executed two queries)
    ├── 001.arrow
    └── 001.json
```

`{cassette_name}` is either the value passed to `@pytest.mark.adbc_cassette("name")` or a name derived from the test node ID.

Interactions are numbered sequentially starting at `000`. A test that executes three queries produces three sets of files (`000.*`, `001.*`, `002.*`).

## File descriptions

### `.sql`

The canonicalised, pretty-printed SQL produced by sqlglot. Example:

```sql
SELECT
  42 AS answer
```

This file is the cassette key. On replay, the plugin normalises the incoming query and looks for a `.sql` file with a matching name. Plain text: changes to queries appear as readable diffs in pull request reviews.

### `.arrow`

The query result serialised as an Arrow IPC file (`RecordBatchFileWriter`). Full schema metadata is preserved, including column types, nullability, and dictionary encodings. Any language with an Apache Arrow library can read this file.

### `.json`

The parameters passed to `cursor.execute()` and any driver options. `null` when no parameters were used. Written after the scrubber runs, if one is registered.

Example with parameters:

```json
{"user_id": 42, "status": "active"}
```

Example with no parameters:

```json
null
```

## Version compatibility

The cassette format is not versioned in v1.0.0. Do not modify cassette files by hand — the internal structure may change in a future release.

## Related

- [Cassette Format Rationale](../explanation/cassette-format-rationale.md) — why this format was chosen
- [Scrub sensitive values](../how-to/scrub-sensitive-values.md) — how to redact values from `.json` files
