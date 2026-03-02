---
plan: 09-03
status: complete
wave: 2
---

# 09-03 Summary: Documentation updates for active scrubbing

## What was done

### Task 1: Rewrote scrub-sensitive-values.md

Completely replaced the how-to guide:

- Removed the `!!! warning "Not yet active in v1"` admonition block
- Removed "The planned interface" and "Workarounds for v1" sections
- Added "Automatic scrubbing with `adbc_scrub_keys`" section with pyproject.toml TOML examples
  showing global form and per-driver colon syntax
- Added "Custom scrubbing with the `adbc_scrubber` fixture" section with two-arg callable
  example and explanation of (params, driver_name) arguments
- Added "Combining both approaches" explanation of pipeline order
- Added "Scope" section (params only, not Arrow results)
- Added "See also" links to fixtures.md and configuration.md

### Task 2: Updated fixtures.md, configuration.md, and README.md

**fixtures.md** adbc_scrubber section:
- Changed status from "Reserved — not called in v1" to "Active — called at record time"
- Updated type annotation to `Callable[[dict | None, str], dict | None] | None`
- Updated signature to `def scrub(params, driver_name)`
- Updated example to two-arg signature with inline dict comprehension
- Added "Interaction with adbc_scrub_keys" note about pipeline order

**configuration.md**:
- Added `adbc_scrub_keys` row to the settings table
- Added `adbc_scrub_keys` to pyproject.toml and pytest.ini examples
- Added detailed `adbc_scrub_keys` section with global/per-driver syntax, TOML example,
  and behavior notes (union, dict-only, silent ignore for missing keys, REDACTED sentinel)

**README.md**:
- Added `adbc_scrub_keys` to the Configuration Reference table
- Updated minimal pyproject.toml snippet to include `adbc_scrub_keys`
- Added "Scrubbing Sensitive Values" section with adbc_scrub_keys config example,
  per-driver example, and adbc_scrubber fixture two-arg example

mkdocs build passes with `--strict`. No "not yet active" / "stored but not called" language
anywhere in docs.

## Files changed

- `docs/src/how-to/scrub-sensitive-values.md` — rewritten
- `docs/src/reference/fixtures.md` — adbc_scrubber section updated
- `docs/src/reference/configuration.md` — adbc_scrub_keys added
- `README.md` — config table, pyproject example, and scrubbing section updated
