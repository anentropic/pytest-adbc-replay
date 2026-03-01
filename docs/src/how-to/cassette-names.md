# Name cassettes per test

By default, the plugin derives a cassette name from the test node ID. For most tests this is fine, but you can set an explicit name with the `adbc_cassette` marker when the auto-derived name is too long or when multiple tests should share a cassette.

## Auto-derived names

Without a marker, the cassette directory name is derived from the test's node ID. For a test at `tests/test_example.py::test_my_query`, the cassette lands at:

```
tests/cassettes/tests__test_example__test_my_query/
```

This works without any marker. The name is unique per test, which is usually what you want.

## Setting an explicit name

Use `@pytest.mark.adbc_cassette("name")` to set the directory name directly:

```python
@pytest.mark.adbc_cassette("user_activity_jan")
def test_user_activity(db_conn): ...
```

The cassette writes to `tests/cassettes/user_activity_jan/`. Choose this when:

- The auto-derived name is unwieldy or path-dependent
- You want a name that stays stable even if the test file is renamed or moved
- Multiple tests share the same recorded interactions (see below)

## Sharing a cassette between tests

Two tests can use the same cassette name to share recorded data:

```python
@pytest.mark.adbc_cassette("product_catalog")
def test_product_count(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM products")
        count = cur.fetchone()[0]
        assert count > 0


@pytest.mark.adbc_cassette("product_catalog")
def test_product_names(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("SELECT name FROM products LIMIT 5")
        rows = cur.fetchall()
        assert len(rows) == 5
```

Both tests read from the same `tests/cassettes/product_catalog/` directory.

## Naming constraints

Cassette names map directly to directory names on disk. Avoid characters that filesystems restrict: `/`, `:`, `*`, `?`, `"`, `<`, `>`, `|`, and null bytes. Alphanumeric characters, underscores, and hyphens are safe on all major platforms.

## Per-test dialect override

The marker also accepts a `dialect` keyword argument to override the global `adbc_dialect` ini setting for one test:

```python
@pytest.mark.adbc_cassette("snowflake_report", dialect="snowflake")
def test_snowflake_query(db_conn): ...
```

This is useful in test suites that connect to multiple databases with different SQL dialects.

## Related

- [Use multiple drivers in one session](multiple-drivers.md) — wrapping connections to different databases
- [Markers reference](../reference/markers.md) — full marker signature
