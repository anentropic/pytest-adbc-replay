# How-To Guides

These guides assume you have completed the [Tutorial](../tutorial/index.md) and have a working record-replay setup. Each guide solves one specific task.

## Guides

- [Run in CI without warehouse credentials](ci-without-credentials.md) — configure GitHub Actions to use cassettes instead of a live database
- [Configure the plugin via ini](configure-via-ini.md) — set defaults in `pyproject.toml` or `pytest.ini`
- [Name cassettes per test](cassette-names.md) — control cassette directory names with the marker
- [Use multiple drivers in one session](multiple-drivers.md) — wrap connections to different databases
- [Scrub sensitive values from cassettes](scrub-sensitive-values.md) — remove tokens or passwords before cassettes are written to disk
- [Register custom parameter serialisers](custom-param-serialisers.md) — handle parameter types not covered by the default JSON encoder
