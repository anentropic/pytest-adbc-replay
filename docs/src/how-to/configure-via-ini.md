# Configure the plugin via ini

Set plugin defaults in `pyproject.toml` or `pytest.ini` so you do not have to pass CLI flags on every run.

## Available settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `adbc_cassette_dir` | ini key (str) | `tests/cassettes` | Directory where cassette subdirectories are stored. Relative to the pytest rootdir. |
| `adbc_record_mode` | ini key (str) | `none` | Default record mode. Overridden by `--adbc-record` for a single run. |
| `adbc_dialect` | ini key (str) | `""` | SQL dialect for normalisation. Empty string means sqlglot auto-detect. |
| `--adbc-record` | CLI flag | `none` | Record mode for one run. Choices: `none`, `once`, `new_episodes`, `all`. |

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

## When to use ini vs CLI

Set `adbc_record_mode` in ini for the persistent project default — typically `none` so replay is the default for all developers and in CI.

Use `--adbc-record` on the command line to override for a single run:

```bash
# Record new cassettes without changing the ini default
pytest --adbc-record=once
```

The CLI flag takes precedence over the ini setting. Neither changes the other.

## Changing the cassette directory

If your tests are not in `tests/`, or you prefer a different layout, set `adbc_cassette_dir`:

```toml
[tool.pytest.ini_options]
adbc_cassette_dir = "fixtures/cassettes"
```

The path is relative to the pytest rootdir. All cassette directories are created inside this base directory.

## Setting the SQL dialect

If all your tests run against one database, set the dialect globally:

```toml
[tool.pytest.ini_options]
adbc_dialect = "snowflake"
```

Accepted values are any dialect string that sqlglot recognises. Use `""` (empty string) or omit the key to use sqlglot's auto-detect, which works for standard SQL. To override per test, use `@pytest.mark.adbc_cassette("name", dialect="bigquery")`.

## Related

- [Record Modes reference](../reference/record-modes.md) — full description of each mode's behaviour
- [Configuration reference](../reference/configuration.md) — all settings with types and defaults
