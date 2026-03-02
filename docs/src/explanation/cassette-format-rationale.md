# Cassette format rationale

This article covers three design questions: why cassettes are stored as files, why query results use Arrow IPC, and why SQL is stored as human-readable text.

## Why files on disk

Cassettes need to travel with the code. They belong in version control alongside the tests that use them.

A database or remote service would add operational overhead. Something would need to run, authenticate, and stay in sync with the test suite. On a developer's machine, on CI, in a fork — each environment would need access to the same service. Files avoid this entirely. The cassette directory is cloned with the repo.

Files are also transparent. A developer can open a cassette directory and see exactly what queries were recorded and what results came back. There is no query language to learn, no service to connect to — just a directory of files readable by any text editor or Arrow library.

There is also the practical point that files can be reviewed in pull requests, searched with grep, and edited by hand when something goes wrong during development (though manual edits are discouraged in production).

The VCR pattern (which pytest-adbc-replay adapts for ADBC) made the same choice for HTTP: cassettes as files in the repository. The pattern works because the recorded data is small relative to a codebase, stable once recorded, and introspectable without special tools.

## Why Arrow IPC for query results

ADBC cursors return results as Arrow record batches. Storing those results in Arrow format is the natural choice.

The alternative — converting to JSON, CSV, or some other format — loses information. A column of `Decimal` values becomes strings. `null` and `0` become ambiguous. Timestamps lose timezone metadata. Date formats introduce regional edge cases. Arrow preserves full schema metadata: column types, nullability, dictionary encodings, custom metadata fields. What came out of the database goes back in on replay, unchanged.

Arrow is also language-agnostic. Any language with an Apache Arrow library (Python, Rust, Java, Go, C++) can read the `.arrow` cassette files. If you ever need to inspect or transform cassette data outside of pytest, you can.

The Arrow IPC file format (`RecordBatchFileWriter`, as opposed to the streaming format) is designed for on-disk storage. It supports random access and is stable.

There is a performance angle too. ADBC's native interface returns Arrow batches directly; converting to JSON and back would add serialisation overhead on every replay. With Arrow IPC, replay is a file read followed by zero-copy memory mapping — no parsing, no conversion.

## Why human-readable SQL

The `.sql` file does not store the raw query string as written in the test. It stores the canonicalised, pretty-printed form produced by [sqlglot](https://sqlglot.com/).

This matters for two reasons.

First, normalisation makes the cassette key stable. If a developer reformats a query (changes whitespace, adjusts capitalisation), the normalised form stays the same. The cassette still matches. Without normalisation, any formatting change would invalidate the cassette and cause a spurious `CassetteMissError` in replay mode.

Second, storing the normalised SQL as a plain text file means query changes appear as readable diffs in pull requests. If a test changes from `SELECT id, name FROM users` to `SELECT id, name, email FROM users`, that change shows in the PR diff as a one-line edit to a `.sql` file. Reviewers can see exactly what the test is now querying.

This is the primary visibility feature: CI tests pass from cassettes, but humans see what changed.

The choice to store SQL as a separate `.sql` file (rather than embedding it in JSON alongside the results) is intentional. It makes the SQL immediately accessible without parsing a container format. You can `cat` the `.sql` file, open it in your editor's SQL syntax highlighter, or diff it in a code review without any tooling.

See the [Cassette Format reference](../reference/cassette-format.md) for the exact file naming convention and field descriptions.

## The three-file design

Separating each interaction into three files (`.sql`, `.arrow`, `.json`) rather than one container file was a deliberate choice.

A single JSON container could hold all three — SQL, results, parameters — but it would require a custom reader to inspect the results. Splitting them means:

- The `.sql` file is readable by anything that can open a text file
- The `.arrow` file is readable by any Apache Arrow library in any language
- The `.json` file is readable by any JSON parser

Each file type is independently inspectable with standard tools. If you want to write a script that finds all cassettes containing a particular table name, you can `grep -r "users" tests/cassettes/` and get results from the `.sql` files immediately, without parsing a container format.

The tradeoff is three file operations per interaction instead of one. For the scale of typical test suites (tens to hundreds of cassette interactions), this cost is negligible.

## What this design is not trying to do

The cassette format is not designed for compactness. Arrow IPC files carry schema metadata on every write, which adds overhead per file. For large result sets this is fine; for a suite with thousands of very small interactions, the overhead of many small Arrow files could become measurable.

The cassette format is not versioned. There is no migration path if the format changes in a future release, although we think this is unlikely. Cassettes should be treated as regenerable — if the format changes, re-record with the new version.

## Relation to VCR

"VCR" testing libraries record and replay HTTP interactions by capturing request/response pairs. `pytest-adbc-replay` adapts this pattern to ADBC cursor interactions: the "request" is a SQL query with parameters, and the "response" is an Arrow record batch.

The VCR libraries ([vcrpy](https://vcrpy.readthedocs.io/), [betamax](https://betamax.readthedocs.io/)) use YAML or JSON cassette files because HTTP responses are already text or JSON-serialisable. ADBC responses are Arrow batches, so the cassette format uses Arrow IPC instead. The three-file structure (.sql, .arrow, .json) maps to (request-key, response-body, request-metadata) in VCR terms.

Unlike HTTP VCR libraries, `pytest-adbc-replay` does not need to handle request matching heuristics (headers, body matching modes, URI patterns). SQL normalisation provides a deterministic match: two queries either normalise to the same canonical string or they do not. This makes cassette lookup simpler and more predictable than HTTP cassette matching.

HTTP VCR libraries also face the challenge that HTTP bodies can be large and binary (images, compressed data). For ADBC, both the request (SQL) and response (Arrow batch) are well-structured data that serialise cleanly to domain-appropriate formats.

## When to regenerate cassettes

Cassettes should be regenerated when the underlying query logic changes in a way that alters results — new columns, changed filters, or different source data. The regeneration workflow is:

1. Delete the cassette directory (or run with `--adbc-record=all` to overwrite)
2. Run the test suite against a live database
3. Review the diffs in the regenerated `.sql` files
4. Commit the updated cassettes alongside the code change

Because cassettes are files under version control, regeneration produces a diff. That diff is the record of what changed — both in the query and in the results schema.
