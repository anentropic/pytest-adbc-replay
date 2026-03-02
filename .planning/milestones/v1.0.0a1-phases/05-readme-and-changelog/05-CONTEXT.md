# Phase 5: README and CHANGELOG - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Two Markdown files: README.md and CHANGELOG.md. README gives PyPI visitors and GitHub repo browsers a what/why/how intro and quick start. CHANGELOG documents v1.0.0 and is generated from commits via git-cliff. No source code changes.

</domain>

<decisions>
## Implementation Decisions

### README style and structure
- Follow the adbc-poolhouse README as a reference: short and punchy
- Shape: tagline → one-liner what/why → install → quick example → cassette layout block → links → license
- No wall of text — brief enough that a new user groks the tool in 60 seconds
- Full reference documentation belongs in the MkDocs site (Phase 6)

### Audience
- Primary: new users who found the plugin via PyPI/GitHub search
- They need a quick what/why/how intro — brief VCR-style framing is sufficient context
- Not written for ADBC experts who already know the ecosystem

### Quick example
- Use DuckDB — self-contained, no credentials, reader can run it immediately
- Mirrors the adbc-poolhouse approach (same author, same ecosystem)
- Example should show: conftest.py fixture definition (calling `adbc_replay.wrap()`) + one test with `@pytest.mark.adbc_cassette` + how to record then replay

### README depth
- Happy path + link to docs — not full inline reference
- Advanced features (`adbc_scrubber`, `adbc_param_serialisers`, per-marker dialect) are mentioned briefly or linked, not fully documented
- Note: Phase 5 success criteria (#2) requires all four modes, three config keys, CLI flag, and fixture to appear in README. Satisfy this with a compact reference table/section, not a tutorial for each — keeps brevity while meeting the spec

### Cassette layout in README
- Show an inline file-tree block — brief, visual, satisfies the requirement
- Example:
  ```
  tests/cassettes/
  └── test_my_query/
      ├── 000.sql
      ├── 000.arrow
      └── 000.json
  ```
- One sentence: these files should be committed to version control

### CHANGELOG format
- Generated via git-cliff — add `cliff.toml` to project root as part of this phase
- cliff.toml should use conventional commits format
- CHANGELOG includes: feat and fix commits only — filters out docs/test/chore/wip/plan noise from the GSD planning workflow
- Phase 7 publishing automation will use this same cliff.toml; adding it now is the right time

### Spelling and tone
- British spelling throughout — matches codebase conventions: normalise, serialise, cassette
- Tone: direct and technical, like the adbc-poolhouse README — no marketing language

</decisions>

<specifics>
## Specific Ideas

- "See ../adbc-poolhouse for example README" — reference project by same author, same ecosystem, same minimal style
- DuckDB example preferred because readers can run it without any setup (mirrors adbc-poolhouse's DuckDB quick example)
- git-cliff for CHANGELOG generation — conventional commits are already in place (feat/fix/docs/test/chore/wip/plan)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `adbc_replay` fixture (session-scoped, plugin.py:127) — primary entry point; quick example should show this
- `adbc_scrubber` fixture (plugin.py:103) — mention in README as advanced option, don't explain in detail
- `adbc_param_serialisers` fixture (plugin.py:72) — same, mention or link
- `CassetteMissError` (public type) — worth naming so users know what to catch
- `@pytest.mark.adbc_cassette(name, dialect=None)` — show in quick example

### Established Patterns
- CLI: `--adbc-record` with choices: none / once / new_episodes / all
- Ini config keys: `adbc_cassette_dir`, `adbc_record_mode`, `adbc_dialect`
- Cassette layout: `{cassette_dir}/{cassette_name}/000.sql`, `000.arrow`, `000.json` (numbered per interaction)
- Conventional commits already in use: feat, fix, docs, test, chore, wip, plan

### Integration Points
- README.md referenced by `pyproject.toml` (`readme = "README.md"`) — file must exist at project root
- CHANGELOG.md — place at project root; Phase 6 MkDocs site will link to it
- cliff.toml — place at project root; Phase 7 CI will use it for release notes automation

</code_context>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-readme-and-changelog*
*Context gathered: 2026-03-01*
