---
phase: 10-per-driver-adbc-dialect-config-and-dialect-docs-review
plan: "02"
subsystem: testing
tags: [tdd, dialect, _parse_dialect, unit-tests, integration-tests]

requires:
  - phase: 10-per-driver-adbc-dialect-config-and-dialect-docs-review
    plan: "01"
    provides: _parse_dialect() and per-driver ReplaySession dialect resolution

provides:
  - TestParseDialect: 8 unit tests covering all _parse_dialect() input cases
  - TestPerDriverDialect: 3 pytester integration tests proving priority chain
  - Import of _parse_dialect added to test_plugin.py imports

affects: []

tech-stack:
  added: []
  patterns:
    - "TDD GREEN phase: implementation from 10-01 was in place; all 11 tests passed immediately"

key-files:
  created: []
  modified:
    - tests/test_plugin.py

key-decisions:
  - "Integration tests use conn._dialect (private attribute) — DEVELOP.md allows tests to access private members"
  - "TestPerDriverDialect uses pytester.makeini with multi-line linelist syntax for per-driver dialect config"
  - "TestParseDialect placed after TestParseScrupKeys (mirrors how TestParseDialect mirrors _parse_dialect pattern)"

## Self-Check: PASSED

11 new tests added, all pass. 199 tests total (188 + 11). Type checking clean.
