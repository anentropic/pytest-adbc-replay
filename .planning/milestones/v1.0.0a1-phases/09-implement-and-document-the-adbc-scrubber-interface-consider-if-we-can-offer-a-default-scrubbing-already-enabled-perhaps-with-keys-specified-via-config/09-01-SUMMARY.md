---
plan: 09-01
status: complete
wave: 1
---

# 09-01 Summary: Core scrubbing implementation (TDD)

## What was done

Implemented the scrubbing pipeline in `_cursor.py`, then wired scrub_keys and scrubber through
`_connection.py`, `_session.py`, and `plugin.py`.

### Task 1: Scrubbing helpers and ReplayCursor (TDD)

RED phase: Created `tests/test_scrubbing.py` with 17 unit tests for `_apply_config_scrubbing`
and `apply_scrubbing`. Tests intentionally failed (functions did not exist). Committed with
`--no-verify` as required for TDD red phase.

GREEN phase: Added two module-level functions to `_cursor.py`:

- `_apply_config_scrubbing(params_raw, global_keys, per_driver_keys, driver_name)`: Applies
  config-based key redaction to dict params. Replaces matched key values with `"REDACTED"`.
  Non-dict params returned unchanged.
- `apply_scrubbing(params_raw, global_keys, per_driver_keys, driver_name, scrubber)`: Full
  pipeline — config scrubbing first, then fixture callable if provided. Callable returns
  `None` to keep config result, or a dict to replace it.

Updated `ReplayCursor.__init__` to accept `scrub_keys_global`, `scrub_keys_per_driver`,
`driver_name`, and `scrubber`. Updated `_record_interaction()` to call `apply_scrubbing`
between `serialise_params` and `write_params_json`.

All 17 unit tests pass. Total: 168 tests pass.

### Task 2: Wire through session/connection/plugin

- `_connection.py`: Added `scrub_keys_global`, `scrub_keys_per_driver`, `scrubber` to
  `__init__`; updated `cursor()` to pass them + `driver_name` to `ReplayCursor`.
- `_session.py`: Added `scrub_keys_global`, `scrub_keys_per_driver` to `__init__` and
  `self.*` storage; updated `wrap()` and `wrap_from_item()` to pass them to `ReplayConnection`.
- `plugin.py`: Added `adbc_scrub_keys` `linelist` ini key; added `_parse_scrub_keys()` helper
  parsing global/per-driver lines; updated `_build_session_from_config()` to parse and pass
  scrub keys; updated `adbc_replay` fixture to read and pass scrub keys; updated
  `adbc_scrubber` docstring to reflect active two-arg signature `(params, driver_name)`.

All 168 tests pass after Task 2.

## Key decisions

- `adbc_scrub_keys` is a `linelist` ini key (not dot-notation subkeys, which pytest `addini`
  cannot register dynamically). Lines with `:` are per-driver; lines without `:` are global.
- Scrubbing only affects dict params — list params have no key names and pass through unchanged.
- Sentinel value is `"REDACTED"` (string literal, not configurable in v1).
- `apply_scrubbing` pipeline order: config first, then fixture callable.
- Fixture callable returning `None` means "keep config result unchanged".

## Files changed

- `src/pytest_adbc_replay/_cursor.py` — scrubbing helpers, ReplayCursor updates
- `src/pytest_adbc_replay/_connection.py` — thread scrub params through
- `src/pytest_adbc_replay/_session.py` — thread scrub params through
- `src/pytest_adbc_replay/plugin.py` — ini key, parser, fixture wiring
- `tests/test_scrubbing.py` — 17 new unit tests (new file)
