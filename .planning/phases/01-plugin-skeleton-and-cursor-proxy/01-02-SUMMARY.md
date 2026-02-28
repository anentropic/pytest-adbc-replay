---
phase: 01-plugin-skeleton-and-cursor-proxy
plan: 02
subsystem: proxy
tags: [adbc, cursor, proxy, pyarrow, replay]

requires:
  - phase: 01-01
    provides: CassetteMissError exception and cassette_path types
provides:
  - ReplayCursor implementing full ADBC cursor protocol without AttributeError
  - ReplayConnection with driver import guard (PROXY-02 compliant)
  - execute() in replay mode sets pending to empty Arrow table (Phase 1 placeholder)
  - context manager protocol on both ReplayCursor and ReplayConnection
affects: [01-03, 02, 03]

tech-stack:
  added: []
  patterns:
    - importlib.import_module inside `if mode != 'none'` guard
    - _pending: pa.Table tracks last execute() result
    - _fetch_offset: int enables incremental fetchone/fetchmany

key-files:
  created:
    - src/pytest_adbc_replay/_cursor.py
    - src/pytest_adbc_replay/_connection.py

key-decisions:
  - "Phase 1: execute() in replay mode stores empty Arrow table; Phase 2 will load from cassette files"
  - "real_cursor=None in replay mode; ReplayCursor still implements all protocol methods"
  - "arraysize defaults to 1 per DBAPI2 spec"

patterns-established:
  - "ReplayCursor.__enter__ returns self; __exit__ calls close()"
  - "ReplayConnection.cursor() creates per-call ReplayCursor with same mode/cassette_path"
  - "description property returns None when no columns (empty table); list of 7-tuples otherwise"

requirements-completed:
  - PROXY-01
  - PROXY-02
  - PROXY-03
  - PROXY-04
  - PROXY-05

duration: 20min
completed: 2026-02-28
---

# Phase 01-02: Cursor Proxy Summary

**ReplayCursor and ReplayConnection implement full ADBC cursor protocol; replay mode never imports a real ADBC driver.**

Five requirements (PROXY-01 through PROXY-05) delivered. `ReplayConnection(mode='none', driver_module_name='nonexistent', ...)` succeeds without `ModuleNotFoundError`. All cursor methods callable without `AttributeError`.
