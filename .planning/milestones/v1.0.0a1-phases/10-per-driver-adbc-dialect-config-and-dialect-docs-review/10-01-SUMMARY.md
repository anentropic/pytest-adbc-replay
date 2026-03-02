---
phase: 10-per-driver-adbc-dialect-config-and-dialect-docs-review
plan: "01"
subsystem: plugin
tags: [dialect, linelist, ini, adbc_dialect, per-driver]

requires:
  - phase: 9-adbc-scrubber
    provides: _parse_scrub_keys pattern used as template for _parse_dialect

provides:
  - _parse_dialect() function in plugin.py
  - adbc_dialect ini key registered as type="linelist" (was "string")
  - ReplaySession.dialect_global and ReplaySession.dialect_per_driver attributes
  - wrap() per-driver dialect resolution chain
  - wrap_from_item() per-driver dialect resolution chain

affects: [tests/test_plugin.py, docs (phase 10-03)]

tech-stack:
  added: []
  patterns:
    - "_parse_dialect mirrors _parse_scrub_keys: bare line = global, 'driver: dialect' = per-driver"
    - "dialect_per_driver.get(driver_module_name) or dialect_global priority chain"

key-files:
  created: []
  modified:
    - src/pytest_adbc_replay/plugin.py
    - src/pytest_adbc_replay/_session.py
    - tests/test_plugin.py

key-decisions:
  - "adbc_dialect ini type changed from 'string' to 'linelist' — no backward compat needed (project unreleased)"
  - "_parse_dialect returns (str | None, dict[str, str]) — dialect values are single strings, unlike _parse_scrub_keys which returns lists of keys"
  - "dialect_global replaces self.dialect on ReplaySession — cleaner naming, avoids ambiguity"
  - "Priority chain in wrap(): explicit wrap(dialect=) arg > marker > per-driver ini > global ini > None"
  - "Priority chain in wrap_from_item(): marker > per-driver ini > global ini > None"
  - "Existing test_plugin.py tests updated: adbc_replay.dialect -> adbc_replay.dialect_global"

patterns-established:
  - "Per-driver linelist pattern: same as adbc_scrub_keys — bare line = global, 'driver_name: value' = per-driver"

## Self-Check: PASSED

All 188 existing tests pass. Type checking clean (0 errors). Smoke checks pass.
