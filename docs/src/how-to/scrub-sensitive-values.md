# Scrub sensitive values from cassettes

Cassettes are committed to version control. If your tests pass sensitive values as query parameters (API tokens, passwords, account IDs), you can scrub those values before they are written to the `.json` cassette file.

## When this matters

The `.json` file in each cassette interaction stores the parameters passed to `cursor.execute()`. If a test passes an API token as a parameter, that token ends up in the cassette. Scrubbing replaces it with a placeholder before the file is written.

## Implement a scrubber

Override the `adbc_scrubber` fixture in your `conftest.py`:

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

The fixture must return a callable that accepts a parameter dict (or `None`) and returns the modified dict (or `None`). Return the original `params` unchanged for interactions you do not want to scrub.

## What gets scrubbed

The scrubber applies to parameters only — the values passed to `execute()`. It does not touch the Arrow result table stored in `.arrow`. If your query returns sensitive data in the result set, you need a different approach (for example, using test data that does not contain real credentials).

## Consistent placeholders

!!! warning
    The scrubbed value is what gets stored in the cassette and compared on replay. If you record with `token = "REDACTED"` but replay with `token = "some-real-value"`, the cassette key lookup will fail because parameters are part of the interaction key.

Use a consistent placeholder across all runs. If your scrubber replaces the token with `"REDACTED"`, then any test running against the cassette must also pass `"REDACTED"` — or use a separate cassette recorded with the same placeholder.

In practice, the easiest pattern is to scrub values that are only present at record time and not present at replay time (because in `none` mode, the real token is never used anyway).

## Related

- [Fixtures reference](../reference/fixtures.md) — `adbc_scrubber` signature and scope
- [Cassette Format reference](../reference/cassette-format.md) — what `.json` files contain
