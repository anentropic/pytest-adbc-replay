# Fixtures

The plugin provides four fixtures: one function-scoped factory (`adbc_connect`) and three session-scoped fixtures.

---

## `adbc_connect`

**Scope:** function
**Type:** `Callable[[str, **Any], ReplayConnection]`

`adbc_connect` is a factory fixture for creating replay connections explicitly. It is the escape hatch for tests that cannot use `adbc_auto_patch` — for example when a session-scoped or module-scoped connection is needed, or when you prefer explicit control over connection creation.

**Interface:**

```text
adbc_connect(driver_module_name: str, **db_kwargs) -> ReplayConnection
```

**Usage:**

```python
import os

import pytest


@pytest.mark.adbc_cassette("my_test")
def test_my_query(adbc_connect):
    conn = adbc_connect("adbc_driver_snowflake.dbapi", uri=os.environ["SNOWFLAKE_URI"])
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
```

The fixture closes all opened connections when the test finishes.

**Cassette path:** `adbc_connect` uses the per-driver cassette subdirectory layout. Cassettes are stored under `{cassette_dir}/{cassette_name}/{driver_module_name}/`.

**Session-scoped connections:** `adbc_connect` is function-scoped and cannot be used directly in session-scoped fixtures. For session-scoped connections, use `adbc_replay.wrap()` instead.

---

## `adbc_replay`

**Scope:** session
**Type:** `ReplaySession`

`adbc_replay` is the main plugin fixture. It tracks recording and replay state for the test session.

**Interface:**

```text
adbc_replay.wrap(driver_module_name, db_kwargs=None, *, request=None, cassette_name=None, dialect=None) -> ReplayConnection
```

`wrap()` creates a `ReplayConnection` for the current test. Pass `request` to let the plugin resolve the cassette path from the test node ID and `@pytest.mark.adbc_cassette` marker automatically.

**Usage:**

```python
import pytest


@pytest.fixture(scope="session")
def db_conn(adbc_replay, request):
    return adbc_replay.wrap(
        "adbc_driver_duckdb.dbapi",
        request=request,
    )
```

`wrap()` can be called multiple times for different driver modules. Each `ReplayConnection` records and replays independently.

**Override:** Override this fixture only if you need to customise `ReplaySession` initialisation. This is uncommon.

---

## `adbc_scrubber`

**Scope:** session
**Type:** `Callable[[dict | None, str], dict | None] | None`
**Default:** `None` (no scrubbing)
**Status:** Active — called at record time for each interaction that has params

`adbc_scrubber` is a hook for custom scrubbing of parameter values before they are written to the
`.json` cassette file. It runs after config-based scrubbing (`adbc_scrub_keys`) has already been
applied.

**Signature:**

```python
def scrub(params: dict | None, driver_name: str) -> dict | None: ...
```

The callable receives two arguments:

- `params` — the already-config-scrubbed parameter dict (or `None` if no parameters were used)
- `driver_name` — the ADBC driver module name string (e.g. `"adbc_driver_snowflake"`)

Return the modified dict to replace the params, or return `None` to leave the config-scrubbed
params unchanged.

**Override:**

```python
import pytest


@pytest.fixture(scope="session")
def adbc_scrubber():
    def scrub(params: dict | None, driver_name: str) -> dict | None:
        if not isinstance(params, dict):
            return params
        return {k: "REDACTED" if k == "token" else v for k, v in params.items()}

    return scrub
```

**Interaction with `adbc_scrub_keys`:**

Config scrubbing (`adbc_scrub_keys`) runs first. The fixture callable receives the already-partially-scrubbed
params, so any keys listed in `adbc_scrub_keys` will already show as `REDACTED` in the dict the
callable sees. Use config for simple key redaction and the fixture for anything more specific.

**Note:** The scrubber applies to parameters only, not to the Arrow result data in `.arrow` files.

---

## `adbc_param_serialisers`

**Scope:** session
**Type:** `dict[type, Callable] | NO_DEFAULT_SERIALISERS`
**Default:** built-in serialisers for standard Python types

`adbc_param_serialisers` extends or replaces the JSON serialisation logic for parameter types not handled by the default encoder.

**Override:**

```python
import numpy as np
import pytest


@pytest.fixture(scope="session")
def adbc_param_serialisers():
    return {np.ndarray: lambda arr: arr.tolist()}
```

The fixture returns a `dict` mapping `type` to a callable. The callable receives the value and must return a JSON-serialisable object.

**`NO_DEFAULT_SERIALISERS` sentinel:**

Return `NO_DEFAULT_SERIALISERS` (importable from `pytest_adbc_replay`) to disable all built-in serialisers. Combine it with `|` to also register your own types — only the types you list will be active, no built-ins are added:

```python
import decimal

import pytest

from pytest_adbc_replay import NO_DEFAULT_SERIALISERS


@pytest.fixture(scope="session")
def adbc_param_serialisers():
    # No built-ins at all:
    return NO_DEFAULT_SERIALISERS

    # Or: no built-ins, but with explicit custom types:
    return NO_DEFAULT_SERIALISERS | {
        decimal.Decimal: {
            "serialise": lambda v: {"__type__": "Decimal", "value": str(v)},
            "deserialise": lambda d: decimal.Decimal(d["value"]),
        },
    }
```

This differs from returning `{decimal.Decimal: ...}` directly, which merges your entry with the built-in registry. The `NO_DEFAULT_SERIALISERS | {...}` form gives you only the types you listed.

## Related

- [Scrub sensitive values](../how-to/scrub-sensitive-values.md) — how-to guide for `adbc_scrubber`
- [Register custom parameter serialisers](../how-to/custom-param-serialisers.md) — how-to guide for `adbc_param_serialisers`
