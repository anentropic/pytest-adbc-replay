# Cursor Surface

The real ADBC `Cursor` exposes thirty public members. `ReplayCursor` covers all of
them. This page lists each member, grouped by category, with the behavior you get in
replay mode. Use it to check whether a given cursor method or property does what you
expect when there is no live database connection.

## Behavior labels

Each member carries one of five labels:

- **implemented** — returns recorded data or behaves as the real driver would.
- **derived** — computed from the cassette rather than the database (for example, a
  schema read off the recorded result).
- **no-op** — does nothing in replay and returns silently. In record mode it delegates
  to the real cursor.
- **not supported (raises)** — raises `NotSupportedError` in replay. The replay model
  cannot honor it, so it fails with an actionable error rather than a wrong answer.
- **lenient (deviates from ADBC)** — works, but does not match ADBC exactly. Results are
  re-readable in replay, whereas real ADBC consumes a result stream once.

<!-- Keep this table in sync with EXPECTED_SURFACE in tests/unit/test_cursor_parity.py -->

## DBAPI core

| Member | Replay-mode behavior | Notes |
|---|---|---|
| `execute` | implemented | Looks up the recorded interaction by normalised SQL and loads the result. |
| `executemany` | no-op | Delegates to the real cursor in record mode; no-op in replay (does not load a result). Real ADBC `executemany` produces no result set either. |
| `executescript` | no-op | Silent in replay; DDL side effects are already baked into recorded results. Delegates in record mode. |
| `fetchone` | lenient (deviates from ADBC) | Re-readable result. Raises `ProgrammingError` if called before `execute()`. |
| `fetchmany` | lenient (deviates from ADBC) | Re-readable result. Raises `ProgrammingError` if called before `execute()`. |
| `fetchall` | lenient (deviates from ADBC) | Re-readable result. Raises `ProgrammingError` if called before `execute()`. |
| `next` | implemented | Iteration protocol; returns the next recorded row. |
| `nextset` | not supported (raises) | Raises `NotSupportedError`, matching real ADBC. |
| `callproc` | not supported (raises) | Raises `NotSupportedError`, matching real ADBC. |
| `close` | implemented | Releases the cursor state. |
| `setinputsizes` | no-op | Accepted and ignored, as in DBAPI. |
| `setoutputsize` | no-op | Accepted and ignored, as in DBAPI. |
| `arraysize` | implemented | Read/write property; controls `fetchmany` default size. |
| `rowcount` | implemented | Property; reflects the recorded result. |
| `rownumber` | implemented | Property; `None` before `execute()`, then the current fetch position. |
| `description` | implemented | Property; column metadata derived from the recorded result. |
| `connection` | implemented | Property; the owning `ReplayConnection`. |

## Arrow & DataFrame fetch

| Member | Replay-mode behavior | Notes |
|---|---|---|
| `fetch_record_batch` | implemented | Returns the recorded result as a `pyarrow.RecordBatchReader`. |
| `fetch_arrow` | implemented | Returns the recorded result as a raw Arrow C stream. Single-consumption contract (as in real ADBC): may be called only once, and must be called before any other consuming fetch — otherwise raises `ProgrammingError`. Raises `ProgrammingError` if called before `execute()`. |
| `fetch_df` | implemented | Returns a pandas DataFrame (pandas imported lazily). |
| `fetch_polars` | implemented | Returns a polars DataFrame (polars imported lazily). |
| `fetch_arrow_table` | lenient (deviates from ADBC) | Re-readable result. Raises `ProgrammingError` if called before `execute()`. |
| `fetchallarrow` | lenient (deviates from ADBC) | Alias of `fetch_arrow_table`; inherits its pre-execute guard. |

## ADBC extension

| Member | Replay-mode behavior | Notes |
|---|---|---|
| `adbc_execute_schema` | derived | Returns the schema of the recorded result. See the note below for record-mode behavior. |
| `adbc_cancel` | no-op | Silent in replay; delegates in record mode. |
| `adbc_prepare` | no-op | Silent in replay; delegates in record mode. |
| `adbc_ingest` | not supported (raises) | Raises `NotSupportedError`; ingestion has no replay analog. |
| `adbc_execute_partitions` | not supported (raises) | Raises `NotSupportedError`; partitioned execution has no replay analog. |
| `adbc_read_partition` | not supported (raises) | Raises `NotSupportedError`; partition reads have no replay analog. |
| `adbc_statement` | not supported (raises) | Property; raises `NotSupportedError`. The underlying ADBC statement is not available in replay. |

!!! note "Record-mode schema reflects live DB"
    In any record mode (`once`, `new_episodes`, `all`), `adbc_execute_schema` always
    delegates to the live database — it never reads the cassette. `execute()` behaves
    differently: in `once`/`new_episodes` it replays a matching recorded interaction
    when one exists (recording only on a miss), and in `all` it always records against
    the live database. So a schema obtained from `adbc_execute_schema` reflects the live
    database at record time even when the corresponding `execute()` was served from the
    cassette. (Phase 3 design / WR-02.)

!!! warning "Re-consumable results (deviation from ADBC)"
    In replay, fetch results are re-readable, because the recorded result is held in a
    materialised table. Real ADBC consumes a result stream once. Pre-execute fetches do
    now raise `ProgrammingError`, which matches ADBC.

## Related

- [Record Modes](record-modes.md) — when replay happens and when interactions are recorded.
- [Exceptions](exceptions.md) — `CassetteMissError` and `NormalisationWarning`.
  `NotSupportedError` and `ProgrammingError` shown above are ADBC's own exception types,
  re-exported from `adbc_driver_manager.dbapi`; they are not defined by this plugin.
