# Phase 1: Test compatibility with ADBC Foundry drivers - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Verify that pytest-adbc-replay works correctly with ADBC Foundry drivers (Go-based drivers accessed via `adbc_driver_manager.dbapi`, installed via `dbc` CLI from columnar.tech rather than PyPI). Add integration tests with a real Foundry driver (MySQL via testcontainers). Fix the cassette path differentiation issue for drivers that share a single Python module. Reorganize existing tests into `tests/unit/` and `tests/integration/` split.

</domain>

<decisions>
## Implementation Decisions

### Driver connection path
- Foundry drivers connect via `adbc_driver_manager.dbapi.connect(driver="mysql", **kwargs)` — the `driver=` kwarg identifies which Foundry driver binary to use
- All Foundry drivers share the same Python module (`adbc_driver_manager.dbapi`), unlike PyPI drivers which each have their own module (e.g. `adbc_driver_sqlite.dbapi`)
- The existing `importlib.import_module(driver_module_name)` + `driver.connect(**db_kwargs)` pattern in ReplayConnection should already work since `db_kwargs` passes through the `driver=` kwarg
- Auto-patch monkeypatching `adbc_driver_manager.dbapi.connect` should intercept all Foundry driver connections in one go

### Cassette path differentiation
- Current cassette subdir layout uses the driver module name (e.g. `cassettes/test_name/adbc_driver_sqlite.dbapi/`)
- Problem: all Foundry drivers share `adbc_driver_manager.dbapi` — they'd all land in the same subdir
- Solution: introduce `cassette_differentiator_keys` — a configurable tuple of `db_kwargs` key names whose values get appended to the cassette subdir path
- Example: `adbc_driver_manager.dbapi.connect(driver="mysql")` with `cassette_differentiator_keys=("driver",)` → cassette path `cassettes/test_name/adbc_driver_manager.dbapi/mysql/`
- Default value: `("driver",)` so Foundry drivers work out of the box
- Configuration: both as pytest ini key (`adbc_cassette_differentiator_keys`) for global default AND as per-call kwarg override on `wrap()`/`adbc_connect()`
- Applies to all three connection paths (auto-patch, `wrap()`, `adbc_connect()`)

### Test infrastructure
- Use testcontainers-python with MySQL for real Foundry driver integration tests
- Install `dbc` CLI + MySQL Foundry driver in GitHub Actions CI workflow
- Foundry integration tests require both Docker (testcontainers) and `dbc` CLI

### Test directory reorganization
- Move existing tests from `tests/` into `tests/unit/`
- New Foundry integration tests go in `tests/integration/`
- Done as part of this phase (not a separate phase)

### Test scope
- Core record-then-replay cycle through `adbc_driver_manager.dbapi` with the MySQL Foundry driver
- Auto-patch interception of `adbc_driver_manager.dbapi.connect()`
- Cassette path differentiation (verify `driver=` kwarg produces correct subdir layout)

### Claude's Discretion
- Exact testcontainers setup and fixture design
- How to detect/skip when `dbc` CLI or Docker is unavailable
- CI workflow step ordering and caching for `dbc` binary
- Whether `cassette_differentiator_keys` ini key uses the same linelist pattern as other per-driver ini keys

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ReplayConnection.__init__` (`_connection.py:26-59`): already passes `db_kwargs` through to `driver.connect(**db_kwargs)` — Foundry's `driver=` kwarg should flow through naturally
- `pytest_sessionstart` (`plugin.py:214-260`): auto-patch logic that monkeypatches `driver_mod.connect` — needs to extract `driver=` from kwargs for cassette path
- `_build_session_from_config` (`plugin.py:187-211`): builds ReplaySession from pytest config — will need to parse new `cassette_differentiator_keys` ini key
- `test_integration.py`: existing E2E record-then-replay test pattern using pytester — model for Foundry integration tests

### Established Patterns
- Per-driver ini keys use linelist with colon syntax (`driver_name: value`) — consistent pattern for any new config keys
- Auto-patch stores original connects in `_ORIGINAL_CONNECTS` dict and tracks open connections in `_OPEN_CONNECTIONS` for cleanup
- All E2E tests use pytester subprocess invocations

### Integration Points
- `ReplaySession.wrap_from_item()` (`_session.py`): where cassette path is computed — needs to incorporate differentiator keys
- `_cassette_path.py`: cassette path computation logic — where subdir differentiation would be added
- `plugin.py` `pytest_addoption`: where new ini key would be registered
- `.github/workflows/`: CI workflow needs `dbc` install step + Docker service

</code_context>

<specifics>
## Specific Ideas

- `adbc_driver_manager.dbapi.connect(driver="databricks", **kwargs)` is the real-world Foundry usage pattern — the `driver=` value comes from the `dbc` package manager namespace
- The cassette differentiator approach is intentionally generic — not hardcoded to `driver=` — so it can work with any kwarg that distinguishes connections

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-test-compatibility-with-adbc-foundry-drivers*
*Context gathered: 2026-03-07*
