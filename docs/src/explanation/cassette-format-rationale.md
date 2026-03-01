# Cassette format rationale

This article covers three design questions: why cassettes are stored as files, why query results use Arrow IPC, and why SQL is stored as human-readable text.

## Why files on disk

Cassettes need to travel with the code. They belong in version control alongside the tests that use them.

A database or remote service would add operational overhead. Something would need to run, authenticate, and stay in sync with the test suite. On a developer's machine, on CI, in a fork — each environment would need access to the same service. Files avoid this entirely. The cassette directory is cloned with the repo.

Files are also transparent. A developer can open a cassette directory and see exactly what queries were recorded and what results came back. There is no query language to learn, no service to connect to — just a directory of files readable by any text editor or Arrow library.

There is also the practical point that files can be reviewed in pull requests, searched with grep, and edited by hand when something goes wrong during development (though manual edits are discouraged in production).

## Why Arrow IPC for query results

ADBC cursors return results as Arrow record batches. Storing those results in Arrow format is the natural choice.

The alternative — converting to JSON, CSV, or some other format — loses information. A column of `Decimal` values becomes strings. `null` and `0` become ambiguous. Timestamps lose timezone metadata. Date formats introduce regional edge cases. Arrow preserves full schema metadata: column types, nullability, dictionary encodings, custom metadata fields. What came out of the database goes back in on replay, unchanged.

Arrow is also language-agnostic. Any language with an Apache Arrow library (Python, Rust, Java, Go, C++) can read the `.arrow` cassette files. If you ever need to inspect or transform cassette data outside of pytest, you can.

The Arrow IPC file format (`RecordBatchFileWriter`, as opposed to the streaming format) is designed for on-disk storage. It supports random access and is stable.

## Why human-readable SQL

The `.sql` file does not store the raw query string as written in the test. It stores the canonicalised, pretty-printed form produced by sqlglot.

This matters for two reasons.

First, normalisation makes the cassette key stable. If a developer reformats a query (changes whitespace, adjusts capitalisation), the normalised form stays the same. The cassette still matches. Without normalisation, any formatting change would invalidate the cassette and cause a spurious `CassetteMissError` in replay mode.

Second, storing the normalised SQL as a plain text file means query changes appear as readable diffs in pull requests. If a test changes from `SELECT id, name FROM users` to `SELECT id, name, email FROM users`, that change shows in the PR diff as a one-line edit to a `.sql` file. Reviewers can see exactly what the test is now querying.

This is the primary visibility feature: CI tests pass from cassettes, but humans see what changed.

See the [Cassette Format reference](../reference/cassette-format.md) for the exact file naming convention and field descriptions.
