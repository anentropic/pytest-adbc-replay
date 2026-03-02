# Configure the plugin via ini

Set plugin defaults in `pyproject.toml` or `pytest.ini` so you do not have to pass CLI flags on every run.

## Available settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `adbc_cassette_dir` | ini key (str) | `tests/cassettes` | Directory where cassette subdirectories are stored. Relative to the pytest rootdir. |
| `adbc_record_mode` | ini key (str) | `none` | Default record mode. Overridden by `--adbc-record` for a single run. |
| `adbc_dialect` | ini key (str) | `""` | SQL dialect for normalisation. Empty string means sqlglot auto-detect. |
| `adbc_auto_patch` | ini key (str) | `""` | Space-separated list of ADBC driver modules to monkeypatch. Enables zero-conftest record/replay. |
| `--adbc-record` | CLI flag | `none` | Record mode for one run. Choices: `none`, `once`, `new_episodes`, `all`. |

## pyproject.toml

```toml
[tool.pytest.ini_options]
adbc_cassette_dir = "tests/cassettes"
adbc_record_mode = "none"
adbc_dialect = ""
adbc_auto_patch = "adbc_driver_snowflake adbc_driver_duckdb"
```

## pytest.ini

```ini
[pytest]
adbc_cassette_dir = tests/cassettes
adbc_record_mode = none
adbc_dialect =
adbc_auto_patch = adbc_driver_snowflake adbc_driver_duckdb
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

## Enabling automatic driver patching

`adbc_auto_patch` lists the ADBC driver modules the plugin should monkeypatch at session start. Once set, any test decorated with `@pytest.mark.adbc_cassette` will have its `connect()` calls intercepted automatically — no `conftest.py` fixture required.

```toml
[tool.pytest.ini_options]
adbc_auto_patch = "adbc_driver_snowflake"
```

Multiple drivers are space-separated:

```toml
adbc_auto_patch = "adbc_driver_snowflake adbc_driver_duckdb"
```

With this set, a test needs only a marker:

```python
@pytest.mark.adbc_cassette
def test_revenue(snowflake_conn): ...
```

Tests without `@pytest.mark.adbc_cassette` are not intercepted — their `connect()` calls go to the real driver unchanged.

!!! note "Session-scoped connections"
    Automatic patching tracks the current test item to resolve cassette paths, so it only works for connections opened within a test (or its function-scoped fixtures). If you open a connection in a `session`- or `module`-scoped fixture, use the [`adbc_connect` fixture](../reference/fixtures.md) instead.

## Related

- [Record Modes reference](../reference/record-modes.md) — full description of each mode's behaviour
- [Configuration reference](../reference/configuration.md) — all settings with types and defaults
