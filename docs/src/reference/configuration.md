# Configuration

All configuration surfaces for the plugin.

## Settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `--adbc-record` | CLI flag | `none` | Record mode for this run. Overrides `adbc_record_mode`. Choices: `none`, `once`, `new_episodes`, `all`. |
| `adbc_cassette_dir` | ini key (str) | `tests/cassettes` | Directory where cassette subdirectories are stored. Relative to the pytest rootdir. |
| `adbc_record_mode` | ini key (str) | `none` | Default record mode. Overridden by `--adbc-record` for a single run. |
| `adbc_dialect` | ini key (str) | `""` | SQL dialect for normalisation passed to sqlglot. Empty string triggers auto-detect. Per-test override via the `adbc_cassette` marker. |
| `adbc_auto_patch` | ini key (str) | `""` | Space-separated list of ADBC driver module names whose `connect()` function is intercepted automatically. Only active for tests with `@pytest.mark.adbc_cassette`. |
| `adbc_scrub_keys` | ini key (linelist) | `[]` | Parameter key names to redact from `.json` cassette files. Global form: space-separated keys. Per-driver form: `driver_name: key1 key2`. |

## pyproject.toml

```toml
[tool.pytest.ini_options]
adbc_cassette_dir = "tests/cassettes"
adbc_record_mode = "none"
adbc_dialect = ""
adbc_auto_patch = ""  # e.g. "adbc_driver_duckdb.dbapi adbc_driver_snowflake.dbapi"
adbc_scrub_keys = []  # e.g. ["token password", "adbc_driver_snowflake: account_id"]
```

## pytest.ini

```ini
[pytest]
adbc_cassette_dir = tests/cassettes
adbc_record_mode = none
adbc_dialect =
adbc_auto_patch =
adbc_scrub_keys =
```

### `adbc_scrub_keys`

`adbc_scrub_keys` is a `linelist` ini key. Each line is either a space-separated list of global
key names, or a per-driver line with the driver module name followed by a colon:

```toml
[tool.pytest.ini_options]
adbc_scrub_keys = [
    # Global: redact these keys for all drivers
    "token password api_key",
    # Per-driver: only for adbc_driver_snowflake
    "adbc_driver_snowflake: account_id warehouse",
]
```

- Global keys and per-driver keys are combined (unioned) when scrubbing for a given driver.
- Only dictionary params are affected. List params have no key names and are written unchanged.
- Keys not present in the params dict are silently ignored.
- Matched values are replaced with the sentinel string `REDACTED`.

Multiple global lines are merged into a single flat list. Multiple per-driver lines for the same
driver are accumulated. See [Scrub sensitive values](../how-to/scrub-sensitive-values.md) for a
how-to guide.

## Notes

The `--adbc-record` CLI flag takes precedence over `adbc_record_mode` for the duration of that pytest run. Neither modifies the stored configuration.

`adbc_dialect` accepts any dialect string that sqlglot recognises (`"snowflake"`, `"bigquery"`, `"duckdb"`, etc.). An empty string or `None` triggers sqlglot's auto-detect mode, which works for standard SQL.

### Precedence

`--adbc-record` (CLI flag) > `adbc_record_mode` (ini key)

When both are set, the CLI flag wins for that session only.

### Per-test dialect

The `adbc_dialect` ini key sets a project-wide default. To override for one test, use the `dialect` argument on `@pytest.mark.adbc_cassette`:

```python
@pytest.mark.adbc_cassette("my_test", dialect="bigquery")
def test_something(db_conn): ...
```

### Automatic patching

`adbc_auto_patch` accepts a space-separated list of Python module names, e.g.:

```
adbc_auto_patch = adbc_driver_duckdb.dbapi adbc_driver_snowflake.dbapi
```

Each value must be the module that exposes `connect()` at its top level — for ADBC drivers this is always `adbc_driver_<name>.dbapi`. See [Finding the right module path](../how-to/configure-via-ini.md#finding-the-right-module-path).

Key behaviours:

- Only drivers in this list have their `connect()` intercepted.
- Only tests with `@pytest.mark.adbc_cassette` are intercepted — unmarked tests receive the real `connect()` unchanged.
- If a listed driver module is not installed, the plugin skips it silently. This means replay-only CI environments do not need the driver installed.
- Session-scoped and module-scoped connections cannot use auto-patching (the monkeypatch fires once per test). Use the `adbc_connect` fixture or `adbc_replay.wrap()` for those cases.

### Rootdir

`adbc_cassette_dir` is resolved relative to the pytest rootdir, not the current working directory. Pytest determines rootdir from the location of `pyproject.toml`, `pytest.ini`, `setup.py`, or `setup.cfg`.

## Related

- [Record Modes](record-modes.md) — behaviour of each mode value
- [Markers](markers.md) — per-test dialect override via `@pytest.mark.adbc_cassette`
