# Reference

This section provides complete, accurate specifications for all user-facing surfaces of the plugin.

Reference pages are for lookup. If you know what you are looking for, go directly to the relevant page. If you are new to the plugin, start with the [Tutorial](../tutorial/index.md). If you want to understand the design reasoning behind these choices, see the [Explanation](../explanation/index.md) section.

All values listed here match the implementation. The [README](https://github.com/anentropic/pytest-adbc-replay) is also an accurate source if you want a condensed view.

## Hand-crafted pages

- [Configuration](configuration.md) — all CLI flags and ini keys with types, defaults, and descriptions
- [Record Modes](record-modes.md) — the four record modes and their behaviour
- [Fixtures](fixtures.md) — `adbc_replay`, `adbc_scrubber`, and `adbc_param_serialisers`
- [Markers](markers.md) — `@pytest.mark.adbc_cassette` arguments and effects
- [Exceptions](exceptions.md) — `CassetteMissError` and `NormalisationWarning`
- [Cassette Format](cassette-format.md) — file structure, naming convention, and field descriptions

## Auto-generated API reference

- [API Reference](pytest_adbc_replay/plugin.md) — Python docstrings rendered from `pytest_adbc_replay.plugin`
