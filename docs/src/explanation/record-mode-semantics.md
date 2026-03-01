# Record mode semantics

This article explains the four record modes and how they fit different points in a test suite's lifecycle.

## Why four modes

A single record/replay toggle would force a binary choice: either re-record everything or replay everything. This is too blunt.

Test suites evolve. A test might add a new query to an existing flow. A dataset might change and require fresh cassettes. CI should never record, but a developer adding a new test needs to record without disturbing existing cassettes. The four modes address these different situations.

## Mode-by-mode

**`none`** — replay only. The default. The plugin never opens a database connection in this mode. If a cassette directory is missing or the normalised SQL does not match any stored interaction, the test fails immediately with `CassetteMissError`. Use `none` in CI and as the daily development default once cassettes are established.

**`once`** — record if absent, replay if present. Records a cassette the first time a test runs, then never re-records. If the cassette directory already exists, the plugin replays from it. This protects against accidental re-recording: running `pytest --adbc-record=once` twice does not overwrite existing cassettes. Use `once` when adding a new test to a suite where other tests already have cassettes.

**`new_episodes`** — replay existing interactions, record new ones. If an interaction (normalised SQL + parameters) is already in the cassette, the plugin replays it. If the interaction is not found, the plugin records it. Use `new_episodes` when you have added new queries to an existing test and want to record only the new interactions without touching the ones already recorded.

**`all`** — re-record everything. Overwrites all existing cassette files on every run. Always opens a database connection. Use `all` when the live data has changed and all cassettes need refreshing.

## Common workflows

**Initial recording:** The first time a test suite runs, use `--adbc-record=once` to record all cassettes. Commit the cassette directory. Switch back to `none` (the default) for all subsequent runs.

**Adding a query to an existing test:** Use `--adbc-record=new_episodes` to record only the new interaction. The existing recorded interactions in that cassette are replayed, not re-recorded.

**Refreshing stale cassettes:** Use `--adbc-record=all` to re-record everything against the current live data. Review the diffs in the `.sql` files to confirm what changed.

**CI-only replay:** Set `adbc_record_mode = none` in `pyproject.toml`. CI never records; local developers record when needed with `--adbc-record`.

## Decision logic

```mermaid
stateDiagram-v2
    [*] --> Execute_query
    Execute_query --> Check_cassette : mode=none / once / new_episodes
    Execute_query --> Record : mode=all
    Check_cassette --> Replay : interaction found
    Check_cassette --> Error : mode=none, interaction absent
    Check_cassette --> Record : mode=once, cassette dir absent
    Check_cassette --> Replay : mode=once, cassette dir present
    Check_cassette --> Record : mode=new_episodes, interaction absent
```

See [Run in CI without credentials](../how-to/ci-without-credentials.md) for a GitHub Actions job that uses replay mode.

See the [Record Modes reference](../reference/record-modes.md) for the exact behaviour of each mode.
