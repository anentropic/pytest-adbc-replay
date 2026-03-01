# SQL normalisation design

This article explains why cassette keys are normalised, what sqlglot does during normalisation, and how per-test dialect override works.

## Why cassette keys need normalisation

The naive approach to matching a query against a cassette is to use the raw SQL string as the key. This breaks down quickly in practice.

Developers reformat SQL. A query written as `SELECT * FROM foo WHERE id=1` might become `SELECT * FROM foo WHERE id = 1` after a linter pass, or `select * from foo where id=1` after copying from a different context. These are semantically identical queries, but as raw strings they are different. Without normalisation, any of these changes would invalidate the cassette and cause a `CassetteMissError` in replay mode, even though no actual query logic changed.

Whitespace and case differences are the most common source of spurious cassette misses. Normalisation removes them by reducing every query to a canonical form before computing the cassette key.

## What sqlglot does

sqlglot parses the SQL string into an abstract syntax tree and serialises it back to a canonical form. The output has:

- Uppercase keywords (`SELECT`, `FROM`, `WHERE`)
- Single spaces between tokens
- Consistent quote style
- Pretty-printed multi-line formatting (`pretty=True`)

This canonicalised text is both the cassette key and the content of the `.sql` cassette file. The key and the human-readable file are the same string.

When sqlglot cannot parse the SQL (vendor-specific syntax it does not recognise), the plugin falls back to whitespace-only normalisation — it collapses multiple spaces into one and strips leading/trailing whitespace, but does not change keywords or quoting. The plugin emits a `NormalisationWarning` to indicate this happened. The cassette may still work if the whitespace-normalised form is stable across runs, but the protection against keyword case differences is lost.

## Per-test dialect override

Different databases use different SQL dialects. Snowflake has `QUALIFY`. BigQuery uses backtick quoting. DuckDB has its own extensions. sqlglot needs to know the dialect to parse correctly.

The global `adbc_dialect` ini key sets a project-wide default. For many test suites, this is all you need.

In suites that test against multiple databases, individual tests can override the dialect:

```python
@pytest.mark.adbc_cassette("snowflake_report", dialect="snowflake")
def test_snowflake_query(snow_conn): ...
```

The `dialect` argument is passed directly to sqlglot. It accepts any dialect string sqlglot recognises (`"snowflake"`, `"bigquery"`, `"duckdb"`, and others). An empty string or `None` triggers sqlglot's auto-detect, which works for standard SQL.

The per-test override is stored only in the marker. It does not affect other tests or the global setting.

See the [Configuration reference](../reference/configuration.md) for the `adbc_dialect` ini key.
