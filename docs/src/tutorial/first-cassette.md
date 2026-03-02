# Record your first cassette

This walkthrough takes you from a blank project to a test that runs with no database connection. By the end you will have cassette files on disk and a passing replay run.

## Step 1: Install the plugin and driver

```bash
pip install pytest-adbc-replay adbc-driver-duckdb
```

`pytest-adbc-replay` is the plugin. `adbc-driver-duckdb` is the DuckDB ADBC driver — it runs in-process, so no server setup or credentials are required.

## Step 2: Configure pyproject.toml

Add the `adbc_auto_patch` setting to tell the plugin which driver modules to intercept:

=== "pyproject.toml"

    ```toml
    [tool.pytest.ini_options]
    adbc_auto_patch = ["adbc_driver_duckdb.dbapi"]
    ```

=== "pytest.ini"

    ```ini
    [pytest]
    adbc_auto_patch = adbc_driver_duckdb.dbapi
    ```

`adbc_driver_duckdb.dbapi` is the Python module path where `connect()` lives — see [Finding the right module path](../how-to/configure-via-ini.md#finding-the-right-module-path) for other drivers.

This is all the setup required. No `conftest.py` is needed for the basic case.

## Step 3: Write a test

Create `tests/test_example.py`:

```python
import adbc_driver_duckdb.dbapi as duckdb
import pytest


@pytest.mark.adbc_cassette("first_query")
def test_first_query():
    conn = duckdb.connect()
    with conn.cursor() as cur:
        cur.execute("SELECT 42 AS answer")
        row = cur.fetchone()
        assert row == (42,)
```

The `@pytest.mark.adbc_cassette("first_query")` marker sets the cassette directory name to `first_query`. Without the marker, the plugin derives a name from the test node ID, which works but tends to be longer.

Because `adbc_auto_patch` lists `adbc_driver_duckdb.dbapi`, the plugin intercepts the `duckdb.connect()` call automatically for any test with `@pytest.mark.adbc_cassette`. Tests without the marker receive the real driver unchanged.

## Step 4: Record the cassette

Run pytest with the `--adbc-record=once` flag:

```bash
pytest --adbc-record=once
```

The `once` mode records a cassette the first time and never re-records if the cassette directory already exists. You should see output like:

```
collected 1 item

tests/test_example.py .                                            [100%]

1 passed in 0.12s
```

The test passed by running against a live DuckDB connection. The plugin saved the interaction to disk.

## Step 5: Inspect the cassette files

Look at what was written:

```
tests/cassettes/
└── first_query/
    └── adbc_driver_duckdb.dbapi/
        ├── 000.sql      # normalised SQL
        ├── 000.arrow    # query result as Arrow IPC
        └── 000.json     # query parameters (null in this case)
```

The cassette lives in a subdirectory named after the driver module. This lets you record from multiple drivers in the same test without collisions.

Open `tests/cassettes/first_query/adbc_driver_duckdb.dbapi/000.sql`:

```sql
SELECT
  42 AS answer
```

This is the normalised form of your query. The plugin ran it through sqlglot to produce a canonical representation — uppercase keywords, consistent formatting. This normalised text is what gets stored and used as the cassette key on replay.

Because `000.sql` is plain text, any change to your query appears as a readable diff in a pull request.

Commit the cassette directory to version control:

```bash
git add tests/cassettes/
git commit -m "add cassette for test_first_query"
```

## Step 6: Replay without the database

Run pytest without any flags:

```bash
pytest
```

The default record mode is `none`, which means the plugin never opens a database connection. It reads the cassette and returns the stored result. The test still passes:

```
collected 1 item

tests/test_example.py .                                            [100%]

1 passed in 0.08s
```

Remove the DuckDB driver from your environment if you want to confirm: `pip uninstall adbc-driver-duckdb`. The test will still pass because the plugin does not use the driver at all in replay mode.

## What if a test runs multiple queries?

Each query in a test is stored as a separate interaction. If your test calls `cursor.execute()` twice, you get two sets of files: `000.sql`, `000.arrow`, `000.json` for the first query and `001.sql`, `001.arrow`, `001.json` for the second.

On replay, the plugin returns interactions in the same order they were recorded. The test does not need to do anything differently — cassette lookup is order-based, not key-based within a test.

## What is in the 000.arrow file?

The `.arrow` file stores the full query result as an Arrow IPC file. You can read it with any Arrow library:

```python
import pyarrow as pa

with pa.memory_map("tests/cassettes/first_query/adbc_driver_duckdb.dbapi/000.arrow", "r") as source:
    reader = pa.ipc.open_file(source)
    table = reader.read_all()
    print(table)
```

The table has the same schema (column names and types) as what the database returned. For the tutorial example, you would see a single column named `answer` of type `int64`.

The Arrow format is the reason you do not need to worry about type fidelity on replay. The plugin returns the exact same Arrow record batch that the database produced, with no conversion through JSON or CSV.

## Using an explicit fixture instead

For session-scoped connections, or when you need finer control over the connection lifecycle, use `adbc_replay.wrap()` from a fixture in `conftest.py`:

```python
import adbc_driver_duckdb.dbapi as duckdb
import pytest


@pytest.fixture(scope="session")
def db_conn(adbc_replay, request):
    return adbc_replay.wrap(
        "adbc_driver_duckdb.dbapi",
        request=request,
    )
```

Tests then use `db_conn` directly instead of calling `duckdb.connect()`. Both approaches produce cassettes in the same format. See [Fixtures](../reference/fixtures.md) for the full `adbc_replay.wrap()` and `adbc_connect` reference.

## What's next

The How-To Guides cover specific tasks you are likely to run into:

- [Run tests in CI without warehouse credentials](../how-to/ci-without-credentials.md) — a GitHub Actions job snippet
- [Configure the plugin via ini](../how-to/configure-via-ini.md) — set defaults in pyproject.toml or pytest.ini
- [Name cassettes per test](../how-to/cassette-names.md) — when and how to control cassette directory names

To understand why the plugin stores cassettes the way it does, read the [Explanation](../explanation/index.md) section — in particular, [Cassette format rationale](../explanation/cassette-format-rationale.md) and [Record mode semantics](../explanation/record-mode-semantics.md).
