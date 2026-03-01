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

To disable built-in serialisers entirely and provide a fully custom set, return the `NO_DEFAULT_SERIALISERS` sentinel:

```python
from pytest_adbc_replay import NO_DEFAULT_SERIALISERS
import pytest


@pytest.fixture(scope="session")
def adbc_param_serialisers():
    return NO_DEFAULT_SERIALISERS
```

When `NO_DEFAULT_SERIALISERS` is returned, only your registered serialisers apply. Use this if a built-in serialiser conflicts with your expected output format.

## Related

- [Fixtures reference](../reference/fixtures.md) — `adbc_param_serialisers` signature and the `NO_DEFAULT_SERIALISERS` sentinel
- [Cassette Format reference](../reference/cassette-format.md) — what `.json` files store
