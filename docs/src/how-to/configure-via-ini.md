# Configure the plugin via ini

Set plugin defaults in `pyproject.toml` or `pytest.ini` so you do not have to pass CLI flags on every run.

## Available settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `adbc_cassette_dir` | ini key (str) | `tests/cassettes` | Directory where cassette subdirectories are stored. Relative to the pytest rootdir. |
| `adbc_record_mode` | ini key (str) | `none` | Default record mode. Overridden by `--adbc-record` for a single run. |
| `adbc_dialect` | ini key (linelist) | `[]` | SQL dialect for sqlglot normalisation. Bare value = global fallback. Per-driver form: `driver_name: dialect`. Empty = auto-detect. |
| `adbc_auto_patch` | ini key (linelist) | `[]` | List of ADBC driver module paths to monkeypatch. Enables zero-conftest record/replay. |
| `--adbc-record` | CLI flag | `none` | Record mode for one run. Choices: `none`, `once`, `new_episodes`, `all`. |

## pyproject.toml

```toml
[tool.pytest.ini_options]
adbc_cassette_dir = "tests/cassettes"
adbc_record_mode = "none"
adbc_dialect = [
    "snowflake",                       # global fallback
    "adbc_driver_duckdb: duckdb",      # per-driver override
]
adbc_auto_patch = [
    "adbc_driver_duckdb.dbapi",
    "adbc_driver_snowflake.dbapi",
]
```

## pytest.ini

```ini
[pytest]
adbc_cassette_dir = tests/cassettes
adbc_record_mode = none
adbc_dialect =
    snowflake
    adbc_driver_duckdb: duckdb
adbc_auto_patch =
    adbc_driver_duckdb.dbapi
    adbc_driver_snowflake.dbapi
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

We're using [sqlglot](https://sqlglot.com/) just for AST-based SQL normalisation, so it's primarily the column and param quoting rules that matter. We would expect sqlglot to auto-detect an appropriate dialect (even if it's not exactly the one you're using, e.g PostgreSQL-compatible) for any queries containign quoted members.

### Default: auto-detect (recommended)

The default is to use sqlglot in "auto-detect" mode. With no config specified that's what will be used. Most projects should need no `adbc_dialect` configuration. If you encounter issues then you have several options for specifying the sqlglot normalisation dialect.

### Per-driver dialect config

This is the recommended way to provide specific dialect selections.

Accepted values are any dialect string that sqlglot recognises. Use an empty list (or omit the `adbc_dialect` key) to get the default behaviour which is to rely on sqlglot's auto-detect.

=== "pyproject.toml"

    Set dialect per driver using a list of `<driver patch path>: <dialect>` strings:

    ```toml
    [tool.pytest.ini_options]
    adbc_dialect = [
        "adbc_driver_snowflake.dbapi: snowflake",
        "adbc_driver_duckdb.dbapi: duckdb",
    ]
    ```

=== "pytest.ini"

    Set dialect per driver using `<driver patch path>: <dialect>` strings in the ini file linelist format:

    ```ini
    adbc_dialect =
        adbc_driver_snowflake.dbapi: snowflake
        adbc_driver_duckdb.dbapi: duckdb
    ```

### Global fallback

(Not recommended for multi-driver scenarios, but simpler config syntax if you only use one)

A bare value (no colon) sets a global default for all drivers not explicitly listed:

=== "pyproject.toml"

    ```toml
    adbc_dialect = [
        "snowflake",
        "adbc_driver_duckdb.dbapi: duckdb",
    ]
    ```

=== "pytest.ini"

    ```ini
    adbc_dialect =
        snowflake
        adbc_driver_duckdb.dbapi: duckdb
    ```

Here, DuckDB tests get `duckdb`, and any other driver gets `snowflake`.

### Per-test override (escape hatch)

The `dialect=` argument on `@pytest.mark.adbc_cassette` is available as a last resort when a single test needs a different dialect than its driver's configured value:

```python
@pytest.mark.adbc_cassette("my_test", dialect="bigquery")
def test_unusual_query(db_conn): ...
```

For most projects, per-driver ini config removes the need for this on individual markers.

## Enabling automatic driver patching

`adbc_auto_patch` lists the ADBC driver module paths the plugin should monkeypatch at session start. Once set, any test decorated with `@pytest.mark.adbc_cassette` will have its `connect()` calls intercepted automatically — no `conftest.py` fixture required.

=== "pyproject.toml"

    ```toml
    [tool.pytest.ini_options]
    adbc_auto_patch = ["adbc_driver_duckdb.dbapi"]
    ```

    Multiple drivers:

    ```toml
    [tool.pytest.ini_options]
    adbc_auto_patch = [
        "adbc_driver_duckdb.dbapi",
        "adbc_driver_snowflake.dbapi",
    ]
    ```

=== "pytest.ini"

    ```ini
    [pytest]
    adbc_auto_patch = adbc_driver_duckdb.dbapi
    ```

    Multiple drivers:

    ```ini
    [pytest]
    adbc_auto_patch =
        adbc_driver_duckdb.dbapi
        adbc_driver_snowflake.dbapi
    ```

With this set, a test needs only a marker:

```python
@pytest.mark.adbc_cassette
def test_revenue(snowflake_conn): ...
```

Tests without `@pytest.mark.adbc_cassette` are not intercepted — their `connect()` calls go to the real driver unchanged.

### Finding the right module path

The value must be the Python module that exposes `connect()` at its top level. For ADBC drivers that follow the DBAPI 2.0 spec, this is always `adbc_driver_<name>.dbapi` — not the top-level package name.

Common drivers:

| Driver package | `adbc_auto_patch` value |
|---|---|
| `adbc-driver-duckdb` | `adbc_driver_duckdb.dbapi` |
| `adbc-driver-snowflake` | `adbc_driver_snowflake.dbapi` |
| `adbc-driver-sqlite` | `adbc_driver_sqlite.dbapi` |
| `adbc-driver-bigquery` | `adbc_driver_bigquery.dbapi` |
| `adbc-driver-flightsql` | `adbc_driver_flightsql.dbapi` |
| `adbc-driver-postgresql` | `adbc_driver_postgresql.dbapi` |

For any driver not listed above, confirm the path with Python — substitute your driver name:

```python
import adbc_driver_duckdb.dbapi

print(adbc_driver_duckdb.dbapi.connect)  # should print a callable
```

If the driver exposes `connect` on the top-level package instead (uncommon), use the package name without `.dbapi`.

!!! note "Session-scoped connections"
    Automatic patching tracks the current test item to resolve cassette paths, so it only works for connections opened within a test (or its function-scoped fixtures). If you open a connection in a `session`- or `module`-scoped fixture, use the [`adbc_connect` fixture](../reference/fixtures.md) instead.

## Related

- [Record Modes reference](../reference/record-modes.md) — full description of each mode's behaviour
- [Configuration reference](../reference/configuration.md) — all settings with types and defaults
