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
**Type:** `Callable[[dict | None], dict | None] | None`
**Default:** `None` (no scrubbing)

`adbc_scrubber` is an optional hook for scrubbing parameter values before they are written to the `.json` cassette file.

**Signature:**

```python
def scrub(params: dict | None) -> dict | None: ...
```

The callable receives the parameter dict passed to `cursor.execute()` (or `None` if no parameters were used) and must return the modified dict (or `None`).

**Override:**

```python
@pytest.fixture(scope="session")
def adbc_scrubber():
    def scrub(params):
        if params and "token" in params:
            return {**params, "token": "REDACTED"}
        return params

    return scrub
```

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
