# Phase 3: Update docs with pool clone support - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Document the `adbc_clone()` / connection pooling support added in Phase 2 so users know how to use pytest-adbc-replay with connection pools. Covers a new how-to guide, a dedicated reference page, additions to the fixtures reference, and a brief explanation article. No code changes — documentation only.

</domain>

<decisions>
## Implementation Decisions

### Doc placement
- New how-to guide: "Use with connection pools" in `docs/src/how-to/`
- New dedicated reference page: "Connection Pooling" in `docs/src/reference/` covering adbc_clone() behaviour, shared cassette semantics, wipe state, limitations
- Add `adbc_clone()` to existing `fixtures.md` alongside the other fixtures
- New explanation article: "Connection pooling and replay" in `docs/src/explanation/`
- All pages nest under existing nav sections (how-to list, reference list, explanation list) — no nav restructuring
- Update `mkdocs.yml` nav entries for new pages

### Content depth — how-to guide
- Practical focus: config, fixture setup, test patterns
- Link to explanation article for clone internals
- Don't explain shared wipe state or `__new__` bypass in the how-to

### Content depth — dedicated reference page
- Full adbc_clone() method behaviour, shared cassette semantics
- Mention clone-of-clone support briefly (matches ADBC spec)
- Limitations section with sequential-access constraint

### Content depth — explanation article
- Design rationale: why clones share cassette path, why wipe state is shared
- Full pool replay lifecycle walkthrough: source created → clones created → cursors execute → cassettes shared → pool disposed
- Explain the concurrent-access failure mode (what goes wrong if two cursors execute simultaneously)
- Document wipe state sharing in 'all' record mode: only the first cursor across all clones wipes the cassette directory

### Code examples
- Primary pattern: conftest fixture with pool (realistic project setup)
- Show both auto-patch and explicit `wrap()` approaches with pools
- Use real adbc-poolhouse API (import adbc_poolhouse, show create_pool() + pool.connect() + pool.dispose())
- Generic note that any pool library calling adbc_clone() works the same way
- No separate CI section — link to existing ci-without-credentials.md

### Limitations framing
- MkDocs Material warning admonition box in the how-to guide
- Note that in typical single-threaded test code this is not a problem — the limitation only matters for multi-threaded integration tests where multiple threads hold pool connections and execute concurrently
- Explanation article covers the failure mode in detail (replay queues are per-cursor, interleaved execute() calls could match results to wrong queries)

### Claude's Discretion
- Exact admonition wording and placement within pages
- How much of the explanation lifecycle to diagram vs prose
- Whether to use mermaid diagrams for the lifecycle
- Cross-linking between the four new/updated pages

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ReplayConnection.adbc_clone()` (`_connection.py:64-87`): the method being documented — creates clone sharing config, cassette path, and wipe state
- Existing how-to guides: established pattern for task-oriented docs with pyproject.toml/pytest.ini tabbed examples
- `multiple-drivers.md`: closest existing guide pattern — shows both auto-patch and wrap() approaches, good model

### Established Patterns
- Diataxis framework: tutorial/how-to/reference/explanation split consistently applied
- Material for MkDocs tabbed code blocks (`=== "pyproject.toml"` / `=== "pytest.ini"`)
- Reference pages use tables for settings, method signatures with `**Interface:**` blocks
- How-to guides assume tutorial completion, link to reference for details
- `mkdocs.yml` nav uses literate-nav plugin with section-index

### Integration Points
- `mkdocs.yml` nav: add entries under how-to, reference, and explanation sections
- `docs/src/how-to/index.md`: add link to new pool guide
- `docs/src/reference/index.md`: add link to new connection pooling reference page
- `docs/src/explanation/index.md`: add link to new explanation article
- `docs/src/reference/fixtures.md`: add adbc_clone() section

</code_context>

<specifics>
## Specific Ideas

- Use real adbc-poolhouse API in examples — this is the known consumer that motivated the feature
- Warning box should reassure: "In typical single-threaded pytest runs, this is not a concern. Sequential access is only a limitation when testing multi-threaded server code with concurrent pool connections."
- The explanation article's lifecycle walkthrough should match the real adbc-poolhouse flow: `create_pool(config)` → `source.adbc_clone()` → `pool.connect()` returns clones → cursor operations → `pool.dispose()`

</specifics>

<deferred>
## Deferred Ideas

- Phase 1's `cassette_differentiator_keys` feature is also undocumented — separate docs phase needed
- Foundry driver documentation (how to use with `adbc_driver_manager.dbapi`) — separate docs phase

</deferred>

---

*Phase: 03-update-docs-with-pool-clone-support*
*Context gathered: 2026-03-07*
