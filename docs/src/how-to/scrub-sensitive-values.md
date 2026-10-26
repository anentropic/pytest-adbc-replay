# Scrub sensitive values from cassettes

Cassettes are committed to version control. If your tests pass sensitive values as query parameters
(API tokens, passwords, account IDs), you will want to scrub those values before they are written
to the `.json` cassette file.

Two approaches are available: config-based key redaction via `adbc_scrub_keys`, and a fixture
callable for custom scrubbing logic. Query results can hold sensitive values too, such as the owner's
email address in Databricks `DESCRIBE ... AS JSON` output. To redact those, see
[Scrub values in query results](#scrub-values-in-query-results).

## Automatic scrubbing with `adbc_scrub_keys`

The simplest approach is to list key names in `pyproject.toml`. Any parameter dict key matching
a listed name will have its value replaced with `REDACTED` before the cassette is written:

```toml
[tool.pytest.ini_options]
adbc_scrub_keys = ["token password api_key"]
```

This is a `linelist` ini key. Each line is processed as a space-separated list of key names.
Only dictionary params are affected — positional params (lists) have no key names and are written
unchanged.

### Per-driver scrubbing

To redact keys only for a specific driver, prefix the line with the driver module name and a colon:

```toml
[tool.pytest.ini_options]
adbc_scrub_keys = [
    "token",
    "adbc_driver_snowflake: account_id warehouse",
]
```

Global keys and per-driver keys are combined. The global `token` key is redacted for all drivers;
`account_id` and `warehouse` are redacted only for `adbc_driver_snowflake`.

Keys not present in the params dict are silently ignored.

## Custom scrubbing with the `adbc_scrubber` fixture

For logic that cannot be expressed as a key list — for example, redacting values that match a
pattern or applying different replacements per type — override `adbc_scrubber` in your
`conftest.py`:

```python
import pytest


@pytest.fixture(scope="session")
def adbc_scrubber():
    def scrub(params: dict | None, driver_name: str) -> dict | None:
        if not isinstance(params, dict):
            return params
        # Redact any value whose key ends with "_token"
        return {k: "REDACTED" if k.endswith("_token") else v for k, v in params.items()}

    return scrub
```

The callable receives two arguments:

- `params` — the parameter dict after config-based scrubbing has already been applied
  (or `None` if no parameters were used)
- `driver_name` — the ADBC driver module name string (e.g. `"adbc_driver_snowflake"`)

Return the modified dict, or return `None` to leave the params unchanged after config scrubbing.

### Combining both approaches

Config-based scrubbing (`adbc_scrub_keys`) always runs first. The fixture callable then receives
the already-config-scrubbed params. Use config for simple key redaction and the fixture for
everything else.

## Scrub values in query results

`adbc_scrub_keys` and `adbc_scrubber` only see params, the values passed to `execute()`. To redact
values in the result tables stored in `.arrow` files, list column names or JSON keys under
`adbc_scrub_result_keys`:

```toml
[tool.pytest.ini_options]
adbc_scrub_result_keys = [
    "owner created_by created_time last_access",
]
```

It uses the same global and per-driver line forms as `adbc_scrub_keys`. At record time, before the
result is written, the plugin:

- replaces every non-null value of a string column whose name is listed with `REDACTED`
- in any other string cell that holds a JSON object or array, replaces the value of each listed key
  with `REDACTED`, at any depth

The second rule covers drivers that return metadata as a JSON document in one string column. For
example, Databricks `DESCRIBE TABLE EXTENDED ... AS JSON` returns the view owner's email in an
`owner` field. A JSON cell that changed is re-serialised compactly, with its key order kept. Cells
that hold no listed key stay byte-for-byte the same.

Matching is exact and case-sensitive. Dictionary-encoded string columns are scrubbed like plain
ones. Columns that aren't strings are left unchanged, and so are strings nested inside struct or
list columns.

The recording run gets the scrubbed table too, so a test sees the same rows when it records as when
it replays. If a test asserts on a value you scrub, it fails while recording, not later in CI.

Scrubbing changes only what is written from then on. To clean cassettes you recorded earlier,
re-record them with `--adbc-record=all`. Copies already committed stay in your git history.

## See also

- [`adbc_scrubber` fixture reference](../reference/fixtures.md) — signature, scope, return values
- [`adbc_scrub_keys` and `adbc_scrub_result_keys` configuration reference](../reference/configuration.md) — ini key syntax
