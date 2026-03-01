# Record Modes

The plugin has four record modes controlling when interactions are recorded and when they are replayed from cassette.

## Modes

| Mode | Behaviour |
|---|---|
| `none` | Replay only. Raises `CassetteMissError` if the cassette directory is absent or the interaction is not found. No database connection is opened. Default. |
| `once` | Records if the cassette directory does not exist. Replays from cassette if the directory exists. Does not re-record interactions already in the cassette. |
| `new_episodes` | Replays interactions that are present in the cassette. Records any interaction not found in the cassette. Opens a database connection only when a new interaction is encountered. |
| `all` | Re-records all interactions on every run, overwriting existing cassette files. Always opens a database connection. |

## Setting the mode

Set a persistent default with `adbc_record_mode` in `pyproject.toml` or `pytest.ini`. Override for a single run with `--adbc-record` on the command line.

The CLI flag always takes precedence over the ini setting for the duration of that run. Neither changes the stored configuration.

```bash
# Record new cassettes without changing the ini default
pytest --adbc-record=once

# Refresh all cassettes
pytest --adbc-record=all
```

## When to use each mode

**`none`** — the default for all runs. Set `adbc_record_mode = none` in `pyproject.toml` so developers and CI use replay by default. Override on the command line when you need to record.

**`once`** — use when adding a new test to a suite that already has cassettes. Existing cassettes are untouched. The new test records its cassette; subsequent runs replay it.

**`new_episodes`** — use when you have extended an existing test with additional queries. The existing recorded interactions replay from cassette; only the new interactions (not yet in the cassette) are recorded against the live database.

**`all`** — use when the underlying data has changed and all cassettes need to be regenerated. All cassette files are overwritten, regardless of whether they already exist.

## Related

- [Configuration](configuration.md) — `adbc_record_mode` ini key and `--adbc-record` flag
- [Record Mode Semantics](../explanation/record-mode-semantics.md) — when to use each mode
