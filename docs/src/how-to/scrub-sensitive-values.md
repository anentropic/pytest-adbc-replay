# Scrub sensitive values from cassettes

Cassettes are committed to version control. If your tests pass sensitive values as query parameters
(API tokens, passwords, account IDs), you will want to scrub those values before they are written
to the `.json` cassette file.

Two approaches are available: config-based key redaction via `adbc_scrub_keys`, and a fixture
callable for custom scrubbing logic.

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

## Scope

Scrubbing applies to params only — the values passed to `execute()`. The Arrow result table stored
in `.arrow` files is not touched. If your query results contain sensitive data, use test data that
does not include real credentials.

## See also

- [`adbc_scrubber` fixture reference](../reference/fixtures.md) — signature, scope, return values
- [`adbc_scrub_keys` configuration reference](../reference/configuration.md) — ini key syntax
