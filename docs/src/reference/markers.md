# Markers

## `@pytest.mark.adbc_cassette`

Sets the cassette directory name and optional SQL dialect for a test.

**Signature:**

```text
@pytest.mark.adbc_cassette(name: str, *, dialect: str | None = None)
```

**Arguments:**

| Argument | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | required | The cassette directory name. The cassette is stored at `{adbc_cassette_dir}/{name}/`. |
| `dialect` | `str \| None` | `None` | SQL dialect for normalisation. Overrides the global `adbc_dialect` ini setting for this test. |

**Without the marker:**

If the marker is not applied, the cassette name is derived from the test node ID (module path + test function name):

- Test at `tests/test_example.py::test_my_query`
- Cassette at `tests/cassettes/tests__test_example__test_my_query/`

**Example:**

```python
@pytest.mark.adbc_cassette("user_report", dialect="snowflake")
def test_user_report(db_conn): ...
```

Cassette path: `tests/cassettes/user_report/`
Dialect: `"snowflake"` (used by sqlglot when normalising the SQL)

## Related

- [Name cassettes per test](../how-to/cassette-names.md) — when and how to use the marker
- [Configuration](configuration.md) — global `adbc_dialect` ini key
