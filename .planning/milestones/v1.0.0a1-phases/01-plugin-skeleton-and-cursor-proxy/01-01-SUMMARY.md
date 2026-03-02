---
phase: 01-plugin-skeleton-and-cursor-proxy
plan: 01
subsystem: infra
tags: [pytest, plugin, entry-point, fixture, marker, cli]

requires: []
provides:
  - pytest11 entry point auto-discovers the plugin from installed package
  - --adbc-record CLI option with none/once/new_episodes/all choices
  - adbc_replay session-scoped fixture returning ReplaySession
  - adbc_cassette marker registered (no PytestUnknownMarkWarning)
  - CassetteMissError exception with two distinct factory methods
  - ReplaySession.wrap() resolves cassette path from marker or node ID
  - node_id_to_cassette_path() strips tests/, .py, slugifies special chars
affects: [01-02, 01-03, 02, 03]

tech-stack:
  added:
    - adbc-driver-manager==1.10.0
    - pyarrow==23.0.1
    - sqlglot==29.0.1
  patterns:
    - session-scoped fixture holding config; per-test state via .wrap()
    - marker resolution at function scope via request.node.get_closest_marker
    - pyproject.toml-level basedpyright exemptions for missing stubs

key-files:
  created:
    - src/pytest_adbc_replay/plugin.py
    - src/pytest_adbc_replay/_exceptions.py
    - src/pytest_adbc_replay/_cassette_path.py
    - src/pytest_adbc_replay/_session.py
  modified:
    - src/pytest_adbc_replay/__init__.py
    - pyproject.toml

key-decisions:
  - "adbc_replay is session-scoped; per-test state created by wrap() from function-scoped user fixture"
  - "dialect= kwarg resolved from marker.kwargs at wrap() call time, not at session init"
  - "Path is kept at runtime (noqa: TC003) in _cassette_path.py and _exceptions.py since it is used in function bodies"
  - "basedpyright: reportMissingTypeStubs/reportUnknownMemberType disabled at project level for pyarrow"

patterns-established:
  - "Plugin hooks: pytest_addoption + pytest_configure in plugin.py"
  - "Cassette path: node_id_to_cassette_path(node_id, cassette_dir) -> Path"
  - "CassetteMissError factory methods: .directory_missing() and .interaction_missing()"

requirements-completed:
  - INFRA-01
  - INFRA-02
  - INFRA-03
  - INFRA-04
  - INFRA-05
  - INFRA-06
  - PROXY-06

duration: 25min
completed: 2026-02-28
---

# Phase 01: Plugin Skeleton Summary

**Plugin auto-discovered by pytest via pytest11 entry point; fixture, CLI option, and marker all registered with no manual imports.**

All seven requirements (INFRA-01 through INFRA-06, PROXY-06) delivered. Key design: session-scoped `adbc_replay` fixture holds only config; cassette state created per-test via `.wrap()` to avoid scope mismatch.
