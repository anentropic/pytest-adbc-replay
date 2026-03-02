# SQL normalisation design

This article explains why cassette keys are normalised, what [sqlglot](https://sqlglot.com/) does during normalisation, and how dialect configuration works.

## Why cassette keys need normalisation

The naive approach to matching a query against a cassette is to use the raw SQL string as the key. This breaks down quickly in practice.

Developers reformat SQL. A query written as `SELECT * FROM foo WHERE id=1` might become `SELECT * FROM foo WHERE id = 1` after a linter pass, or `select * from foo where id=1` after copying from a different context. These are semantically identical queries, but as raw strings they are different. Without normalisation, any of these changes would invalidate the cassette and cause a `CassetteMissError` in replay mode, even though no actual query logic changed.

Whitespace and case differences are the most common source of spurious cassette misses. Normalisation removes them by reducing every query to a canonical form before computing the cassette key.

SQL normalisation is also why the `.sql` cassette file contains pretty-printed SQL rather than the raw query string: the normalised form is both the key and the stored record. Two developers can independently reformat a query and still get a cassette match, because both reformatted versions normalise to the same canonical text.

## What sqlglot does

sqlglot parses the SQL string into an abstract syntax tree and serialises it back to a canonical form. The output has:

- Uppercase keywords (`SELECT`, `FROM`, `WHERE`)
- Single spaces between tokens
- Consistent quote style
- Pretty-printed multi-line formatting (`pretty=True`)

This canonicalised text is both the cassette key and the content of the `.sql` cassette file. The key and the human-readable file are the same string.

When sqlglot cannot parse the SQL (vendor-specific syntax it does not recognise), the plugin falls back to whitespace-only normalisation — it collapses multiple spaces into one and strips leading/trailing whitespace, but does not change keywords or quoting. The plugin emits a `NormalisationWarning` to indicate this happened. The cassette may still work if the whitespace-normalised form is stable across runs, but the protection against keyword case differences is lost.

sqlglot is a pure-Python SQL parser with no native extensions. It is not a database connection — it never runs queries. The plugin uses it only for parsing and re-serialising SQL strings at cassette record and replay time. This makes normalisation deterministic and portable: the same SQL string produces the same canonical form regardless of database state or version.

See the [Exceptions reference](../reference/exceptions.md) for details on `NormalisationWarning`.

## Dialect configuration

Different databases use different SQL dialects. Snowflake has `QUALIFY`. BigQuery uses backtick quoting. DuckDB has its own extensions. sqlglot needs to know the dialect to parse correctly.

The recommended path for projects with multiple drivers is to configure dialect per-driver in `adbc_dialect`:

```toml
[tool.pytest.ini_options]
adbc_dialect = [
    "adbc_driver_snowflake.dbapi: snowflake",
    "adbc_driver_duckdb.dbapi: duckdb",
]
```

With this set, the correct dialect is resolved automatically from the driver module name. Tests using Snowflake get `snowflake`, tests using DuckDB get `duckdb`. No `dialect=` on individual markers.

The dialect resolution priority chain is: explicit `wrap(dialect=)` argument > marker `dialect=` > per-driver ini > global ini fallback > auto-detect.

A bare value (no colon) sets a global fallback for any driver not explicitly listed:

```toml
adbc_dialect = [
    "snowflake",                            # global fallback
    "adbc_driver_duckdb.dbapi: duckdb",     # per-driver override
]
```

The `dialect` argument is passed directly to sqlglot. It accepts any dialect string sqlglot recognises (`"snowflake"`, `"bigquery"`, `"duckdb"`, and others). An empty list or no configuration triggers sqlglot's auto-detect, which works for standard SQL.

### Per-test override (escape hatch)

If one specific test uses a query that trips up auto-detect even though the driver's dialect is configured correctly, the marker `dialect=` argument overrides for that test only:

```python
@pytest.mark.adbc_cassette("unusual_query", dialect="bigquery")
def test_unusual_syntax(snow_conn): ...
```

This is an edge case. For most projects, per-driver ini config handles all dialect needs without per-test overrides.

The per-test override is stored only in the marker. It does not affect other tests or the global setting.

See the [Configuration reference](../reference/configuration.md) for the `adbc_dialect` ini key and full priority chain documentation.

## What normalisation does not cover

Normalisation removes whitespace and case differences. It does not:

- Substitute parameter values — `SELECT * FROM foo WHERE id = ?` with parameter `42` is a different cassette key than the same query with parameter `99`, because parameters are recorded separately in the `.json` file
- Detect semantic equivalence — `SELECT a, b FROM foo` and `SELECT b, a FROM foo` are different canonical forms even though they return the same data (column order matters for Arrow schema)
- Handle dynamic SQL fragments — if your test constructs SQL by string concatenation with variable identifiers, the cassette key changes with the identifiers. Use query parameters for variable values instead.

## Why sqlglot rather than a simpler approach

The simplest normalisation is lowercasing the SQL and collapsing whitespace. This handles the most common cases, but it is fragile: `select "Foo" from bar` and `select "foo" from bar` become the same string, even though quoted identifiers are case-sensitive in most databases.

sqlglot's AST round-trip approach is more reliable. It parses the SQL into a structured representation where keywords, identifiers, and literals are distinct nodes. The canonical serialisation applies consistent rules to each node type — keywords uppercase, identifiers in their parsed form, literals unchanged. The result is a canonical string that reflects SQL structure rather than surface-level characters.

## Interaction with parameters

SQL normalisation applies to the query string only, not to bound parameters. A query like `SELECT * FROM users WHERE id = ?` with parameters `(42,)` and the same query with parameters `(99,)` produce the same normalised SQL but different cassette entries, because parameters are stored separately in the `.json` file and compared exactly.

This is the expected behaviour: two queries with different parameter values are different interactions, even if the SQL template is identical. The cassette stores them as separate entries and replays them in order.

See the [Cassette Format reference](../reference/cassette-format.md) for how interactions are numbered and ordered within a cassette.

## Replay matching

On replay, the plugin normalises the incoming SQL query using the same sqlglot path, then looks for a `.sql` file in the cassette directory that matches the normalised text. If found, it reads the corresponding `.arrow` and `.json` files and returns the stored result.

This means the cassette match is always an exact string comparison of two normalised forms — not a fuzzy match, not a similarity score. If the normalised form of the replay query matches the normalised form stored in the cassette, the interaction is replayed. If it does not match, the plugin raises `CassetteMissError`.

Within a single cassette, multiple interactions are stored as numbered files (`000.sql`, `001.sql`, etc.) in recording order. On replay, the plugin iterates through them in order — it does not use SQL content to select which interaction to return. This means a test that runs the same query twice returns the first recorded result on the first call and the second on the second call, even if both calls have the same normalised SQL.

The order-based replay model is a deliberate choice: it avoids the complexity of content-based dispatch and makes the replay sequence predictable from the recording order.
