# Run in CI without warehouse credentials

If your cassette files are committed to the repository, CI can run your test suite without any database connection. The plugin's default record mode is `none`, which means it never opens a connection — it reads from cassette files only.

## GitHub Actions job

Add this job to your workflow:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install pytest-adbc-replay pytest

      - name: Run tests
        run: pytest
```

No database credentials, no VPN, no warehouse. The `pytest` call uses the default `none` mode, so the plugin reads from `tests/cassettes/` and replays all interactions.

!!! warning
    If cassette files are missing or out of date, tests fail with `CassetteMissError`. Record locally before pushing: `pytest --adbc-record=once`. Then commit the cassette files.

## Why this works

The plugin intercepts cursor calls on wrapped connections. In `none` mode, no real cursor is ever created — the plugin reads the stored Arrow IPC result and parameters from disk and returns them directly to the test. The ADBC driver package does not need to be installed in CI at all.

## What to commit

Commit your entire cassette directory:

```bash
git add tests/cassettes/
git commit -m "add cassettes for test suite"
```

Individual cassette directories contain three files per interaction (`.sql`, `.arrow`, `.json`). The `.sql` files are plain text, so reviewers can see query changes in pull request diffs.

## Related

- [Name cassettes per test](cassette-names.md) — naming cassettes consistently avoids cross-environment mismatches
- [Configure the plugin via ini](configure-via-ini.md) — set `adbc_record_mode = none` as the project default
