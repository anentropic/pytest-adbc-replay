# Phase 6: MkDocs Documentation Site - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Build out the diataxis-structured documentation site content: Tutorial, How-To, Reference, and Explanation sections. Wire them into the MkDocs navigation. The `mkdocs.yml` scaffold, Material theme config, and `docs/scripts/gen_ref_pages.py` already exist — this phase writes the actual content. Publishing to GitHub Pages is Phase 7.

</domain>

<decisions>
## Implementation Decisions

### Tutorial shape
- Use DuckDB as the example driver (no credentials, no warehouse — installs with a single pip command)
- Covers: install plugin + driver → write conftest.py → write a test → `pytest --adbc-record=once` (record) → `pytest` (replay) → inspect the cassette files on disk
- Copy-pasteable code at every step; no branching paths
- Assumes basic Python/pytest familiarity — does not explain how to install Python or create a virtualenv
- End state: reader has a working conftest.py, a test file, cassette files committed to git, and a passing replay run

### How-To scope
Four guides (matching the roadmap minimum):
1. **Run in CI without credentials** — paste a GitHub Actions job snippet, point at the cassette directory, explain why no credentials are needed
2. **Configure via ini** — `pyproject.toml` and `pytest.ini` snippets for all four ini keys with plain-English descriptions
3. **Name cassettes per test** — when and why to use `@pytest.mark.adbc_cassette("name")` vs the auto-derived node ID default
4. **Use multiple drivers** — wrapping different connection objects in the same session; driver-specific notes (DuckDB, Snowflake, BigQuery pattern)

Two additional guides (the scrubber and serialisers fixtures are discoverable via reference but warrant task guides):
5. **Scrub sensitive values** — implementing and wiring up `adbc_scrubber` to remove tokens/passwords before cassettes are written
6. **Register custom parameter serialisers** — implementing `adbc_param_serialisers` for non-JSON-native types (e.g. numpy arrays, custom date wrappers)

### Reference approach
- **Auto-generated**: mkdocstrings renders module docstrings for `pytest_adbc_replay.plugin` and any public modules. The `gen_ref_pages.py` script already handles this; it skips private modules (leading `_`).
- **Hand-crafted reference pages** for items that aren't naturally expressed as Python docstrings:
  - Configuration keys table (ini keys + CLI flags, types, defaults, descriptions)
  - Record modes table (all four modes, behaviour, when to use)
  - Fixtures catalogue (`adbc_replay`, `adbc_scrubber`, `adbc_param_serialisers` — scope, signature, override pattern)
  - Markers catalogue (`adbc_cassette` — arguments, defaults, effect)
  - Exceptions (`CassetteMissError`, `NormalisationWarning`)
  - Cassette file format (the three-file structure: `.sql`, `.arrow`, `.json`)
- The `nav` in `mkdocs.yml` must be updated to include Tutorial, How-To, Explanation alongside the auto-generated Reference section

### Explanation depth
Three articles — "why" focused, accessible to any pytest user, not an internals deep-dive:
1. **Cassette format rationale** — why files on disk (not a database), why Arrow IPC for results (schema preservation, language-agnostic), why human-readable `.sql` (git diffs, code review)
2. **SQL normalisation design** — why cassette keys need normalisation (whitespace/casing shouldn't break replay), what sqlglot does, per-test dialect override
3. **Record mode semantics** — when to use `once` vs `new_episodes` vs `all`, common workflows (initial recording, CI-only replay, refreshing cassettes)

### Prose quality (DOC-10)
- All hand-written prose passes humanizer review before committing
- No em-dash overuse, no AI vocabulary (leverage, seamlessly, etc.), no inflated symbolism
- Write in second person ("you") for Tutorial and How-To; third person for Reference; neutral for Explanation

### Claude's Discretion
- Exact wording and sentence structure of all prose
- Whether to use admonitions (Note/Warning/Tip) and where
- Internal navigation between pages (e.g. cross-links from Tutorial to Explanation)
- Whether to include a Mermaid diagram in Explanation (record mode state machine would be a good fit)
- Index page (`docs/src/index.md`) — fill in the Quick Start TODO and add navigation links to sections

</decisions>

<specifics>
## Specific Ideas

- The README Quick Start is a solid reference for the Tutorial — the tutorial should go deeper (explain what the cassette files contain, show the git diff angle)
- Phase success criteria explicitly requires `mkdocs serve` to run without errors — verify plugin dependencies are in `pyproject.toml` dev extras
- The existing `gen_ref_pages.py` skips `__init__`, `__main__`, `conftest`, and private (`_`-prefixed) modules. Public API lives in `pytest_adbc_replay/__init__.py`. The hand-crafted reference pages are the primary surface for user-facing reference.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `mkdocs.yml`: Already configured — Material theme, all plugins (mkdocstrings, gen-files, literate-nav, section-index), markdown extensions (admonitions, superfences, tabbed, mermaid). No changes needed to build config.
- `docs/scripts/gen_ref_pages.py`: Auto-generates `reference/SUMMARY.md` and per-module `.md` files. Handles literate-nav wiring automatically.
- `docs/src/index.md`: Skeleton exists; has `## Installation` and a `## Quick Start` with a TODO placeholder.
- `README.md`: Phase 5 output — complete user-facing doc with Quick Start, Configuration Reference tables, Record Modes table, Advanced section. Authoritative source of truth for content accuracy.
- `CHANGELOG.md`: Already linked from nav.

### Established Patterns
- Source layout: `docs/src/` for hand-authored content; auto-generated files go to virtual filesystem via `gen_ref_pages.py`
- Navigation: The `mkdocs.yml` nav uses `API Reference: reference/` which is resolved by literate-nav from `reference/SUMMARY.md` (auto-generated)
- Diataxis sections will be new top-level nav entries: `Tutorial: tutorial/`, `How-To: how-to/`, `Explanation: explanation/`

### Integration Points
- `mkdocs.yml` nav block must be updated to add Tutorial, How-To, Explanation sections
- New directories needed: `docs/src/tutorial/`, `docs/src/how-to/`, `docs/src/explanation/`
- Public API surface (`__init__.py` exports): `CassetteMissError`, `NormalisationWarning`, `NO_DEFAULT_SERIALISERS`, `ReplaySession` — these feed into hand-crafted reference pages
- Plugin configuration surface (from `plugin.py`): `--adbc-record` CLI flag, `adbc_cassette_dir`, `adbc_record_mode`, `adbc_dialect` ini keys; `adbc_replay`, `adbc_scrubber`, `adbc_param_serialisers` fixtures; `adbc_cassette` marker

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 06-mkdocs-documentation-site*
*Context gathered: 2026-03-01*
