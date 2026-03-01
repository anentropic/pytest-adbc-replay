# Exceptions and Warnings

## `CassetteMissError`

**Module:** `pytest_adbc_replay`
**Import:** `from pytest_adbc_replay import CassetteMissError`

Raised when a query is executed in `none` mode and no matching interaction is found in the cassette directory.

**When it occurs:**

- Record mode is `none` (the default)
- The test executes a SQL query
- The cassette directory does not exist, or the normalised SQL does not match any stored interaction

**Message:** includes the normalised SQL and lists the interactions currently present in the cassette.

**Resolution:** Record the cassette before running in replay mode: `pytest --adbc-record=once`. If you see this in CI, the cassette was not committed or has become out of date.

---

## `NormalisationWarning`

**Module:** `pytest_adbc_replay`
**Import:** `from pytest_adbc_replay import NormalisationWarning`

Issued when sqlglot cannot parse the SQL and the plugin falls back to whitespace-only normalisation.

**When it occurs:**

- The SQL contains syntax that sqlglot does not recognise for the configured dialect
- This is common with vendor-specific SQL extensions

**What happens:** The plugin normalises the SQL using whitespace collapsing only (no AST round-trip). The cassette may still record and replay correctly if the whitespace-normalised form is stable.

**Resolution:** Set the correct SQL dialect. If you see this warning, check the `adbc_dialect` ini setting or the `dialect` argument on `@pytest.mark.adbc_cassette`. If the dialect is correct and sqlglot still cannot parse the SQL, the fallback is intentional — the warning is informational.

## Related

- [Record Modes](record-modes.md) — `none` mode behaviour
- [SQL Normalisation Design](../explanation/sql-normalisation-design.md) — why normalisation is needed and how fallback works
