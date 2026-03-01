# Configuration

All configuration surfaces for the plugin.

## Settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `--adbc-record` | CLI flag | `none` | Record mode for this run. Overrides `adbc_record_mode`. Choices: `none`, `once`, `new_episodes`, `all`. |
| `adbc_cassette_dir` | ini key (str) | `tests/cassettes` | Directory where cassette subdirectories are stored. Relative to the pytest rootdir. |
| `adbc_record_mode` | ini key (str) | `none` | Default record mode. Overridden by `--adbc-record` for a single run. |
| `adbc_dialect` | ini key (str) | `""` | SQL dialect for normalisation passed to sqlglot. Empty string triggers auto-detect. Per-test override via the `adbc_cassette` marker. |

## pyproject.toml

```toml
[tool.pytest.ini_options]
adbc_cassette_dir = "tests/cassettes"
adbc_record_mode = "none"
adbc_dialect = ""
```

## pytest.ini

```ini
[pytest]
adbc_cassette_dir = tests/cassettes
adbc_record_mode = none
adbc_dialect =
```

## Notes

The `--adbc-record` CLI flag takes precedence over `adbc_record_mode` for the duration of that pytest run. Neither modifies the stored configuration.

`adbc_dialect` accepts any dialect string that sqlglot recognises (`"snowflake"`, `"bigquery"`, `"duckdb"`, etc.). An empty string or `None` triggers sqlglot's auto-detect mode, which works for standard SQL.

## Related

- [Record Modes](record-modes.md) — behaviour of each mode value
- [Markers](markers.md) — per-test dialect override via `@pytest.mark.adbc_cassette`
