# Scrub sensitive values from cassettes

!!! warning "Not yet active in v1"
    The `adbc_scrubber` interface is reserved for a future v1.x release. Registering a scrubber in v1 has no effect — the callback is stored but never called. No scrubbing happens automatically either.

    If you need to keep sensitive values out of cassettes today, see [Workarounds for v1](#workarounds-for-v1) below.

Cassettes are committed to version control. If your tests pass sensitive values as query parameters (API tokens, passwords, account IDs), you will want to scrub those values before they are written to the `.json` cassette file.

## The planned interface

When scrubbing is implemented, you will override the `adbc_scrubber` fixture in your `conftest.py`:

```python
import pytest


@pytest.fixture(scope="session")
def adbc_scrubber():
    def scrub(params):
        if params and "token" in params:
            return {**params, "token": "REDACTED"}
        return params

    return scrub
```

The fixture returns a callable that accepts a parameter dict (or `None`) and returns the modified dict (or `None`). Return `params` unchanged for interactions you do not want to scrub.

Registering this fixture now is harmless and forward-compatible — it will take effect once scrubbing is active in v1.x.

## What will get scrubbed

The scrubber will apply to parameters only — the values passed to `execute()`. It will not touch the Arrow result table stored in `.arrow`. If your query returns sensitive data in the result set, you need test data that does not contain real credentials.

## Workarounds for v1

Until scrubbing is active, two approaches keep sensitive values out of cassettes:

**Use environment variables only at record time.** Pass a fixed placeholder as the parameter value rather than a real token:

```python
import os

TOKEN = os.environ.get("API_TOKEN", "REDACTED")


def test_something(cursor):
    cursor.execute("SELECT * FROM t WHERE token = ?", [TOKEN])
```

When `API_TOKEN` is not set (CI replay mode), `TOKEN` is `"REDACTED"` — a stable value that matches what was stored in the cassette.

**Use test fixtures that never touch real credentials.** For unit tests that only need the cassette to replay, there is no real connection and no real credentials — sensitive values simply never appear.

## Related

- [Fixtures reference](../reference/fixtures.md) — `adbc_scrubber` signature and scope
- [Cassette Format reference](../reference/cassette-format.md) — what `.json` files contain
