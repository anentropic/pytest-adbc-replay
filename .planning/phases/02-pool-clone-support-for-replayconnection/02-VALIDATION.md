---
phase: 2
slug: pool-clone-support-for-replayconnection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/unit/test_clone.py -x` |
| **Full suite command** | `uv run pytest tests/unit/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_clone.py -x`
- **After every plan wave:** Run `uv run pytest tests/unit/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | CLONE-01 | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_clone_returns_replay_connection -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | CLONE-02 | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_clone_shares_cassette_path -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | CLONE-03 | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_clone_replay_mode_no_real_conn -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | CLONE-04 | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_clone_record_mode_delegates -x` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 1 | CLONE-05 | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_clone_cursor_independent_queue -x` | ❌ W0 | ⬜ pending |
| 02-01-06 | 01 | 1 | CLONE-06 | unit | `uv run pytest tests/unit/test_clone.py::TestSharedWipeState::test_first_cursor_wipes -x` | ❌ W0 | ⬜ pending |
| 02-01-07 | 01 | 1 | CLONE-07 | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_clone_of_clone -x` | ❌ W0 | ⬜ pending |
| 02-01-08 | 01 | 1 | CLONE-08 | unit | `uv run pytest tests/unit/test_clone.py::TestAdBCClone::test_close_isolation -x` | ❌ W0 | ⬜ pending |
| 02-01-09 | 01 | 1 | CLONE-09 | unit | `uv run pytest tests/unit/ -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_clone.py` — stubs for CLONE-01 through CLONE-08

*Existing infrastructure covers framework and conftest needs.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
