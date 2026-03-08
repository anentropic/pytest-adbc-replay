---
status: complete
phase: 02-pool-clone-support-for-replayconnection
source: 02-01-SUMMARY.md
started: 2026-03-07T21:00:00Z
updated: 2026-03-07T21:05:00Z
---

## Current Test

[testing complete]

## Tests

### 1. adbc_clone() returns a ReplayConnection
expected: Calling `adbc_clone()` on a ReplayConnection returns a new ReplayConnection instance (not the same object). The clone should be usable independently.
result: pass

### 2. Clone shares cassette config
expected: The cloned connection shares the same cassette directory, replay mode, and serialisers as the parent. Both parent and clone operate against the same cassette data.
result: pass

### 3. Shared wipe state prevents double-wipe
expected: In 'all' wipe mode, only the first cursor across parent and all clones triggers the cassette directory wipe. Subsequent cursors from any clone reuse the already-wiped directory without wiping again.
result: pass

### 4. Clone-of-clone works
expected: Calling `adbc_clone()` on a clone produces another valid ReplayConnection. The chain can go to arbitrary depth and all clones share the same wipe state.
result: pass

### 5. Clone cursors have independent replay queues
expected: Each cursor from parent and clone maintains its own independent queue of recorded results. Fetching from one cursor does not affect another.
result: pass

### 6. Closing a clone does not affect parent
expected: Calling `close()` on a clone does not close or invalidate the parent connection or its cursors. The parent continues to function normally after the clone is closed.
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
