# Quick Task 2: Fix cassette path resolution broken for pool-based connections - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Task Boundary

Fix cassette path resolution broken for pool-based connections. When `adbc_driver_manager.dbapi.connect(driver=..., ...)` is called through a pool, the `driver` kwarg value (which can be a short name like `"databricks"` or a full `.so` path) is used unsafely as a cassette path component, breaking path resolution.

</domain>

<decisions>
## Implementation Decisions

### Absolute path safety
- Sanitize differentiator values to stem: `/path/to/libadbc_driver_snowflake.so` → `libadbc_driver_snowflake`
- This applies to ALL differentiator segment values, not just .so paths specifically
- Use `Path(value).stem` or equivalent to strip directory components and extension

### Differentiator default
- Keep `["driver"]` as the default for `adbc_cassette_differentiator_keys`
- Foundry drivers sharing `adbc_driver_manager.dbapi` need disambiguation
- With stem sanitization, .so paths become safe
- Users who don't want it can set the config to empty

### Backward compatibility
- Breaking cassette layout is OK since this is pre-release (1.0.0a2)
- No backward-compat shim needed
- Users re-record cassettes

</decisions>

<specifics>
## Specific Ideas

- The fix lives in `_extract_differentiator_segments` in `_session.py` — sanitize values there before returning
- Bug note at `_notes/pool-cassette-path-bug.md` has full details and expected vs actual paths
- `Path.joinpath()` with an absolute path replaces the entire path — this is the critical failure mode

</specifics>
