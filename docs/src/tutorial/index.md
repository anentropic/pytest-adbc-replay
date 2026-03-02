# Tutorial

This tutorial takes you through recording your first ADBC query cassette and replaying it in a test run that requires no live database connection.

## What you will need

- Python 3.11 or later
- `pytest` installed in your project
- Some code that uses ADBC drivers and db connection
- Basic familiarity with how pytest fixtures work

You do not need a database server or cloud credentials. The tutorial uses DuckDB, which runs in-process.

## What you will have at the end

- A test file with one marked test
- Cassette files committed to version control
- A passing replay run that makes no database calls

## Get started

[Record your first cassette](first-cassette.md)
