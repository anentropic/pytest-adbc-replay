---
phase: 01-plugin-skeleton-and-cursor-proxy
plan: 03
subsystem: tests
tags: [pytest, tdd, pytester, cursor, cassette-path, exceptions]

requires:
  - phase: 01-01
    provides: plugin skeleton, CassetteMissError, node_id_to_cassette_path, ReplaySession
  - phase: 01-02
    provides: ReplayCursor, ReplayConnection
provides:
  - test_cassette_path.py with 10 unit tests for node_id_to_cassette_path
  - test_cursor.py with 19 unit tests for ReplayCursor protocol and CassetteMissError
  - test_plugin.py with 13 pytester integration tests for plugin discovery and hooks
  - conftest.py enabling pytester plugin
affects: []

tech-stack:
  added: []
  patterns:
    - pytester fixture for plugin integration testing (runpytest subprocess)
    - TYPE_CHECKING guard for pytest import in test_plugin.py (TC002 compliance)
    - ruff D403 compliance: capitalise first word of docstrings

key-files:
  created:
    - tests/test_cassette_path.py
    - tests/test_cursor.py
    - tests/test_plugin.py
  modified:
    - tests/conftest.py

key-decisions:
  - "pytest import in test_plugin.py moved to TYPE_CHECKING block (TC002) — annotations are lazy with from __future__ import annotations"
  - "All 43 tests pass green immediately (testing existing code, not writing code first)"
  - "pytester runs subprocess pytest — plugin is discovered via pytest11 entry point in the subprocess"

patterns-established:
  - "pytester.makepyfile(...) + pytester.runpytest() pattern for plugin integration tests"
  - "result.assert_outcomes(passed=N) for concise outcome assertions"
  - "TYPE_CHECKING block for third-party imports used only as type annotations in test files"

requirements-completed:
  - INFRA-01
  - INFRA-02
  - INFRA-03
  - INFRA-04
  - INFRA-05
  - INFRA-06
  - PROXY-01
  - PROXY-02
  - PROXY-03
  - PROXY-04
  - PROXY-05
  - PROXY-06

duration: 15min
completed: 2026-02-28
---

# Phase 01-03: Test Suite Summary

**All 43 tests pass; ruff and basedpyright report 0 errors. All 12 Phase 1 requirements verified.**

Three test modules cover the full Phase 1 contract:

- `test_cassette_path.py` (10 tests): `node_id_to_cassette_path` slug transformation for all edge cases — basic function, nested module, class+method, parametrize brackets, spaces, casing preservation, `.py` stripping, custom cassette dir, no `tests/` prefix.
- `test_cursor.py` (19 tests): `ReplayCursor` full ADBC cursor protocol compliance (PROXY-05); `ReplayConnection` driver import guard in replay mode (PROXY-02); `CassetteMissError` type hierarchy and distinct error messages for `directory_missing` and `interaction_missing` (PROXY-06).
- `test_plugin.py` (13 tests): pytester integration — plugin auto-discovery via pytest11 entry point (INFRA-01); `--adbc-record` CLI option with all four modes and invalid-mode rejection (INFRA-02); `adbc_cassette` marker registration without `PytestUnknownMarkWarning` (INFRA-04/05); cassette path resolution from node ID and marker (INFRA-06); full replay-mode workflow without any ADBC driver installed (PROXY-02/03/04).
