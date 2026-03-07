---
status: complete
phase: 01-test-compatibility-with-adbc-foundry-drivers
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md]
started: 2026-03-07T16:00:00Z
updated: 2026-03-07T16:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. cassette_differentiator_keys ini option
expected: In pyproject.toml, `adbc_cassette_differentiator_keys` accepts a linelist of space-separated key names. Run `uv run pytest --co -q` to verify collection works with the plugin loaded. Check `uv run python -c "import pytest_adbc_replay"` imports cleanly.
result: pass

### 2. Default differentiator transparency for PyPI drivers
expected: Without any `adbc_cassette_differentiator_keys` config, existing tests using PyPI drivers (e.g. adbc_driver_sqlite) produce cassette paths identical to before (no extra path segments). Run `uv run pytest tests/unit/ -x -q` — all unit tests pass.
result: pass

### 3. Test directory reorganization
expected: Tests are split into `tests/unit/` and `tests/integration/` directories. Run `ls tests/unit/test_*.py | wc -l` (should show 11+ test files) and `ls tests/integration/` (should show conftest.py and test_foundry_mysql.py).
result: pass

### 4. Integration tests fail fast without Docker
expected: Without Docker running (or without dbc CLI installed), run `uv run pytest tests/integration/ -v`. Integration tests should fail fast with a clear error — not silently skip.
result: pass

### 5. Integration tests run with Docker and dbc
expected: With Docker running and dbc MySQL driver installed, run `uv run pytest tests/integration/ -v`. Tests should start a MySQL container via testcontainers and run record-then-replay, auto-patch, and cassette path differentiation tests. All 3 pass.
result: pass

### 6. CI workflow includes integration test job
expected: Check `.github/workflows/_test.yml` — it should have an integration test job that installs dbc CLI and runs integration tests with Docker. The dbc install step should have `continue-on-error: true`.
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
