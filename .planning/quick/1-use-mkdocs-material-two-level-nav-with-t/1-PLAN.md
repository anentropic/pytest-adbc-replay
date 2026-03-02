---
phase: quick
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - mkdocs.yml
autonomous: true
requirements: []
must_haves:
  truths:
    - "Top-level tabs appear: Home, Tutorial, How-To Guides, Reference, Explanation"
    - "Changelog is nested under the Home tab in the sidebar"
    - "mkdocs build completes without errors"
  artifacts:
    - path: "mkdocs.yml"
      provides: "Updated nav structure with tabs and Changelog under Home"
      contains: "navigation.tabs"
  key_links:
    - from: "mkdocs.yml nav.Home"
      to: "changelog.md"
      via: "Changelog sub-item under Home section"
      pattern: "Changelog"
---

<objective>
Configure mkdocs-material to use two-level navigation with top-level tabs: Home, Tutorial, How-To Guides, Reference, Explanation — with Changelog nested under the Home tab.

Purpose: Improve site navigation by surfacing main sections as persistent top tabs while keeping Changelog accessible but not cluttering the top-level tab bar.
Output: Updated mkdocs.yml with navigation.tabs feature and restructured nav.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/paul/Documents/Dev/Personal/pytest-adbc-replay/mkdocs.yml

With mkdocs-material `navigation.tabs`, each top-level nav entry becomes a tab in the horizontal tab bar. For Home to be a tab that also contains Changelog as a sub-page, the Home entry must be defined as a section (a list) rather than a single file. The first item in a section is used as the tab's landing page.

Current nav (top-level keys → will become tabs after change):
- Home: index.md          ← single file, becomes tab
- Tutorial: tutorial/     ← section dir, becomes tab
- How-To Guides: how-to/  ← section dir, becomes tab
- Reference: [sub-items]  ← already a section, becomes tab
- Explanation: explanation/ ← section dir, becomes tab
- Changelog: changelog.md ← currently standalone tab, must move under Home

Target nav structure:
- Home:
  - Overview: index.md
  - Changelog: changelog.md
- Tutorial: tutorial/
- How-To Guides: how-to/
- Reference: [existing sub-items unchanged]
- Explanation: explanation/
</context>

<tasks>

<task type="auto">
  <name>Task 1: Enable navigation.tabs and restructure nav in mkdocs.yml</name>
  <files>/Users/paul/Documents/Dev/Personal/pytest-adbc-replay/mkdocs.yml</files>
  <action>
Make two targeted edits to mkdocs.yml:

1. In the `theme.features` list, add `navigation.tabs` after `navigation.sections`. The full features list becomes:
   ```yaml
   features:
     - navigation.instant
     - navigation.tabs
     - navigation.sections
     - navigation.top
     - navigation.tracking
     - toc.follow
     - content.code.copy
     - content.code.annotate
     - search.suggest
     - search.highlight
   ```

2. Replace the `nav` section entirely with:
   ```yaml
   nav:
     - Home:
       - Overview: index.md
       - Changelog: changelog.md
     - Tutorial: tutorial/
     - How-To Guides: how-to/
     - Reference:
       - Overview: reference/index.md
       - Configuration: reference/configuration.md
       - Record Modes: reference/record-modes.md
       - Fixtures: reference/fixtures.md
       - Markers: reference/markers.md
       - Exceptions: reference/exceptions.md
       - Cassette Format: reference/cassette-format.md
       - API Reference: reference/pytest_adbc_replay/plugin.md
     - Explanation: explanation/
   ```

Note: With `navigation.tabs`, the top-level section keys (Home, Tutorial, How-To Guides, Reference, Explanation) render as horizontal tabs. Changelog moves from a standalone tab to a sub-page under Home. The `section-index` plugin is already enabled so `tutorial/`, `how-to/`, and `explanation/` directories will use their index.md as the section landing page.
  </action>
  <verify>
    <automated>cd /Users/paul/Documents/Dev/Personal/pytest-adbc-replay && mkdocs build --strict 2>&1 | tail -5</automated>
  </verify>
  <done>mkdocs build completes with exit code 0 and no warnings. The site renders five top-level tabs; Changelog appears in the Home tab sidebar.</done>
</task>

</tasks>

<verification>
```bash
cd /Users/paul/Documents/Dev/Personal/pytest-adbc-replay && mkdocs build --strict
```
Build must exit 0 with no errors or warnings.
</verification>

<success_criteria>
- mkdocs.yml has `navigation.tabs` in theme.features
- Nav has exactly 5 top-level tabs: Home, Tutorial, How-To Guides, Reference, Explanation
- Changelog is under Home as a sub-item (not a top-level tab)
- `mkdocs build --strict` exits 0
</success_criteria>

<output>
No SUMMARY.md needed for quick plans. Task is complete when build passes.
</output>
