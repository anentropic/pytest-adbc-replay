# Register custom parameter serialisers

Query parameters are stored in the `.json` cassette file. The plugin serialises them to JSON using a built-in encoder, which handles standard Python types. If your tests pass types like `numpy.ndarray`, `datetime.date` subclasses, or other custom objects, you need to register a serialiser for them.

## Add a serialiser for a custom type

Override the `adbc_param_serialisers` fixture in your `conftest.py`:

```python
import numpy as np
import pytest


@pytest.fixture(scope="session")
def adbc_param_serialisers():
    return {np.ndarray: lambda arr: arr.tolist()}
```

The fixture returns a `dict` mapping `type` to a callable. The callable receives the value and must return something JSON-serialisable.

## Multiple types

```python
import datetime
import decimal
import pytest


@pytest.fixture(scope="session")
def adbc_param_serialisers():
    return {
        decimal.Decimal: str,
        datetime.date: lambda d: d.isoformat(),
    }
```

## Replace all built-in serialisers

To disable built-in serialisers entirely, return the `NO_DEFAULT_SERIALISERS` sentinel. Use this if a built-in serialiser conflicts with your expected output format.

**No serialisers at all:**

```python
from pytest_adbc_replay import NO_DEFAULT_SERIALISERS
import pytest


@pytest.fixture(scope="session")
def adbc_param_serialisers():
    return NO_DEFAULT_SERIALISERS
```

**Start from scratch and add your own types:**

Combine the sentinel with your handlers using `|`. Only the types you list will be active — no built-ins are merged:

```python
import decimal

import pytest

from pytest_adbc_replay import NO_DEFAULT_SERIALISERS


@pytest.fixture(scope="session")
def adbc_param_serialisers():
    return NO_DEFAULT_SERIALISERS | {
        decimal.Decimal: {
            "serialise": lambda v: {"__type__": "Decimal", "value": str(v)},
            "deserialise": lambda d: decimal.Decimal(d["value"]),
        },
    }
```

This is different from returning `{decimal.Decimal: ...}` directly — that merges your entry with the built-ins. The `NO_DEFAULT_SERIALISERS | {...}` form gives you only the types you listed.

## Related

- [Fixtures reference](../reference/fixtures.md) — `adbc_param_serialisers` signature and the `NO_DEFAULT_SERIALISERS` sentinel
- [Cassette Format reference](../reference/cassette-format.md) — what `.json` files store
