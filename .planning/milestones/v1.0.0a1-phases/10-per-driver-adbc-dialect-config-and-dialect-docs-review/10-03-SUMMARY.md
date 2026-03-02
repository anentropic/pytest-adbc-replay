---
phase: 10-per-driver-adbc-dialect-config-and-dialect-docs-review
plan: "03"
subsystem: docs
tags: [docs, dialect, linelist, mkdocs, configure-via-ini, configuration, markers, explanation]

requires:
  - phase: 10-per-driver-adbc-dialect-config-and-dialect-docs-review
    plan: "01"
    provides: adbc_dialect linelist implementation to document

provides:
  - configure-via-ini.md: updated settings table, rewritten SQL dialect section with per-driver config as primary
  - reference/configuration.md: adbc_dialect type changed to linelist, new adbc_dialect subsection with priority chain
  - reference/markers.md: dialect= reframed as escape hatch
  - explanation/sql-normalisation-design.md: "Per-test dialect override" renamed to "Dialect configuration", per-driver ini presented as primary
  - how-to/multiple-drivers.md: "SQL dialect per connection" section uses per-driver ini as primary example

affects: []

tech-stack:
  added: []
  patterns:
    - "Consistent narrative: auto-detect default, per-driver ini recommended, marker dialect= is escape hatch"

key-files:
  created: []
  modified:
    - docs/src/how-to/configure-via-ini.md
    - docs/src/reference/configuration.md
    - docs/src/reference/markers.md
    - docs/src/explanation/sql-normalisation-design.md
    - docs/src/how-to/multiple-drivers.md

key-decisions:
  - "No em dashes, no AI vocabulary throughout all new prose"
  - "configure-via-ini.md shows adbc_driver_snowflake.dbapi as canonical per-driver example (matches existing auto_patch examples)"
  - "configuration.md adbc_dialect section modelled on existing adbc_scrub_keys section pattern"
  - "multiple-drivers.md 'SQL dialect per connection' section completely rewritten with per-driver ini as leading example"

## Self-Check: PASSED

mkdocs build --strict exits 0. All 5 files updated. Content checks pass for: adbc_driver_duckdb: duckdb in configure-via-ini.md, linelist in configuration.md, escape hatch in markers.md, per-driver in sql-normalisation-design.md, adbc_dialect in multiple-drivers.md.
