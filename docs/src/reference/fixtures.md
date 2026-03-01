# Fixtures

The plugin provides three session-scoped fixtures.

---

## `adbc_replay`

**Scope:** session
**Type:** `ReplaySession`

`adbc_replay` is the main plugin fixture. It tracks recording and replay state for the test session.

**Interface:**

```text
adbc_replay.wrap(conn) -> connection
```

`wrap()` accepts an ADBC connection object and returns a wrapped connection. The wrapped connection intercepts cursor calls to record or replay interactions depending on the current record mode.

**Usage:**

```python
import adbc_driver_duckdb.dbapi as duckdb
import pytest


@pytest.fixture(scope="session")
def db_conn(adbc_replay):
    with duckdb.connect() as conn:
        yield adbc_replay.wrap(conn)
```

`wrap()` can be called multiple times for different connections. Each wrapped connection records and replays independently.

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

Return `NO_DEFAULT_SERIALISERS` (importable from `pytest_adbc_replay`) to disable all built-in serialisers and provide a fully custom set:

```python
from pytest_adbc_replay import NO_DEFAULT_SERIALISERS
import pytest


@pytest.fixture(scope="session")
def adbc_param_serialisers():
    return NO_DEFAULT_SERIALISERS
```

## Related

- [Scrub sensitive values](../how-to/scrub-sensitive-values.md) — how-to guide for `adbc_scrubber`
- [Register custom parameter serialisers](../how-to/custom-param-serialisers.md) — how-to guide for `adbc_param_serialisers`
