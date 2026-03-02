---
plan: 09-02
status: complete
wave: 2
---

# 09-02 Summary: Integration tests and _parse_scrub_keys unit tests

## What was done

### Task 1: Integration tests added to test_scrubbing.py

Added `TestScrubKeysIntegration` class (7 tests) using direct `ReplayCursor` + mock cursor
pattern to verify cassette JSON content:

- `test_global_scrub_key_redacted_in_cassette` — global key appears as REDACTED in JSON
- `test_per_driver_scrub_key_targets_correct_driver` — per-driver key redacted for matching driver
- `test_per_driver_scrub_key_does_not_redact_wrong_driver` — key not redacted for non-matching driver
- `test_none_params_written_as_null` — None params written as JSON null, not touched by scrubbing
- `test_fixture_scrubber_called_at_record_time` — callable invoked with (params, driver_name)
- `test_fixture_scrubber_return_wins_over_config` — fixture return value replaces config-scrubbed result
- `test_global_and_per_driver_keys_combined` — global + per-driver keys are unioned

Added `TestScrubberFixturePytester` class (3 pytester tests):

- `test_scrubber_two_arg_callable_stored` — two-arg adbc_scrubber stored on ReplaySession
- `test_scrub_keys_ini_sets_global_keys_on_session` — adbc_scrub_keys ini parsed into session
- `test_per_driver_scrub_keys_ini_sets_per_driver_on_session` — per-driver keys parsed correctly

### Task 2: test_plugin.py updates

- Updated `TestScrubberFixture.test_scrubber_stored_when_overridden` to use two-arg signature
  `my_scrubber(params, driver_name)` instead of old single-arg `my_scrubber(data)`.
- Added `TestParseScrupKeys` class (10 unit tests) for `_parse_scrub_keys`:
  - empty list, blank lines, global single line, global multiple lines
  - per-driver single line, multiple drivers, same driver accumulated across lines
  - global + per-driver coexist, colon-only line ignored, driver with no keys ignored

All 188 tests pass.

## Files changed

- `tests/test_scrubbing.py` — 10 new integration tests
- `tests/test_plugin.py` — updated one test signature, added 10 _parse_scrub_keys unit tests
