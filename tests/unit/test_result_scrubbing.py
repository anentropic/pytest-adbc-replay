"""Tests for adbc_scrub_result_keys: redacting named keys in recorded result tables."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from unittest.mock import MagicMock

import pyarrow as pa
import pytest  # noqa: TC002

from pytest_adbc_replay._cassette_io import interaction_file_paths, read_arrow_table
from pytest_adbc_replay._cursor import ReplayCursor
from pytest_adbc_replay._result_scrubbing import result_keys_for_driver, scrub_result_table

# A trimmed Databricks ``DESCRIBE TABLE EXTENDED ... AS JSON`` row.
_DESCRIBE_JSON = json.dumps(
    {
        "table_name": "sales_view",
        "columns": [{"name": "country", "type": {"name": "string"}, "owner": "nested@x.com"}],
        "owner": "someone@example.com",
        "created_time": "2026-10-14T09:39:05Z",
        "type": "METRIC_VIEW",
    },
    separators=(",", ":"),
)


def _describe_table() -> pa.Table:
    field = pa.field(
        "json_metadata",
        pa.string(),
        nullable=False,
        metadata={"Spark:DataType:SqlName": "STRING"},
    )
    return pa.Table.from_arrays(
        [pa.array([_DESCRIBE_JSON])],
        schema=pa.schema([field], metadata={"origin": "databricks"}),
    )


class TestScrubResultTable:
    """Unit tests for scrub_result_table."""

    def test_no_keys_returns_same_table(self) -> None:
        table = _describe_table()
        assert scrub_result_table(table, frozenset()) is table

    def test_json_cell_keys_redacted(self) -> None:
        scrubbed = scrub_result_table(_describe_table(), frozenset({"owner", "created_time"}))
        decoded = json.loads(scrubbed.column("json_metadata")[0].as_py())
        assert decoded["owner"] == "REDACTED"
        assert decoded["created_time"] == "REDACTED"
        assert decoded["table_name"] == "sales_view"
        assert decoded["type"] == "METRIC_VIEW"

    def test_json_cell_nested_keys_redacted(self) -> None:
        scrubbed = scrub_result_table(_describe_table(), frozenset({"owner"}))
        decoded = json.loads(scrubbed.column("json_metadata")[0].as_py())
        assert decoded["columns"][0]["owner"] == "REDACTED"
        assert decoded["columns"][0]["name"] == "country"

    def test_scrubbed_json_has_no_trace_of_value(self) -> None:
        scrubbed = scrub_result_table(_describe_table(), frozenset({"owner"}))
        text = scrubbed.column("json_metadata")[0].as_py()
        assert "example.com" not in text
        assert "nested@x.com" not in text

    def test_json_key_order_kept(self) -> None:
        scrubbed = scrub_result_table(_describe_table(), frozenset({"owner"}))
        decoded = json.loads(scrubbed.column("json_metadata")[0].as_py())
        assert list(decoded) == list(json.loads(_DESCRIBE_JSON))

    def test_schema_and_metadata_kept(self) -> None:
        table = _describe_table()
        scrubbed = scrub_result_table(table, frozenset({"owner"}))
        assert scrubbed.schema.equals(table.schema, check_metadata=True)

    def test_json_without_matching_key_unchanged_byte_for_byte(self) -> None:
        text = '{ "a" : 1,   "b": [1, 2] }'
        table = pa.table({"j": [text]})
        scrubbed = scrub_result_table(table, frozenset({"owner"}))
        assert scrubbed.column("j")[0].as_py() == text

    def test_non_json_strings_unchanged(self) -> None:
        table = pa.table({"s": ["owner", "{not json", None, "[1, 2"]})
        scrubbed = scrub_result_table(table, frozenset({"owner"}))
        assert scrubbed.column("s").to_pylist() == ["owner", "{not json", None, "[1, 2"]

    def test_json_array_cell_redacted(self) -> None:
        table = pa.table({"j": ['[{"owner":"me@x.com"},{"other":1}]']})
        scrubbed = scrub_result_table(table, frozenset({"owner"}))
        assert json.loads(scrubbed.column("j")[0].as_py()) == [{"owner": "REDACTED"}, {"other": 1}]

    def test_matching_string_column_redacted_nulls_kept(self) -> None:
        """A string column named like a key (e.g. Snowflake SHOW ... owner) is redacted."""
        table = pa.table({"name": ["v1", "v2", "v3"], "owner": ["ROLE_A", None, "ROLE_B"]})
        scrubbed = scrub_result_table(table, frozenset({"owner"}))
        assert scrubbed.column("owner").to_pylist() == ["REDACTED", None, "REDACTED"]
        assert scrubbed.column("name").to_pylist() == ["v1", "v2", "v3"]

    def test_matching_large_string_column_redacted(self) -> None:
        table = pa.table({"owner": pa.array(["a", "b"], type=pa.large_string())})
        scrubbed = scrub_result_table(table, frozenset({"owner"}))
        assert scrubbed.column("owner").to_pylist() == ["REDACTED", "REDACTED"]
        assert scrubbed.schema.field("owner").type == pa.large_string()

    def test_multi_chunk_column_redacted(self) -> None:
        chunked = pa.chunked_array([["a@x.com"], ['{"owner":"b@x.com"}']])
        table = pa.table({"owner": chunked, "j": chunked})
        scrubbed = scrub_result_table(table, frozenset({"owner"}))
        assert scrubbed.column("owner").to_pylist() == ["REDACTED", "REDACTED"]
        assert scrubbed.column("j").to_pylist() == ["a@x.com", '{"owner":"REDACTED"}']

    def test_non_string_column_unchanged(self) -> None:
        table = pa.table({"owner": [1, 2]})
        scrubbed = scrub_result_table(table, frozenset({"owner"}))
        assert scrubbed.column("owner").to_pylist() == [1, 2]

    def test_key_match_is_case_sensitive(self) -> None:
        table = pa.table({"OWNER": ["a"], "j": ['{"Owner":"b"}']})
        scrubbed = scrub_result_table(table, frozenset({"owner"}))
        assert scrubbed.to_pylist() == [{"OWNER": "a", "j": '{"Owner":"b"}'}]


class TestResultKeysForDriver:
    def test_union_of_global_and_matching_driver(self) -> None:
        keys = result_keys_for_driver(["owner"], {"drv": ["created_time"], "other": ["x"]}, "drv")
        assert keys == frozenset({"owner", "created_time"})

    def test_other_driver_keys_excluded(self) -> None:
        assert result_keys_for_driver([], {"other": ["owner"]}, "drv") == frozenset()


def _mock_real_cursor(table: pa.Table) -> MagicMock:
    mock = MagicMock()
    mock.fetch_arrow_table.return_value = table
    return mock


class TestRecordWritesScrubbedResult:
    """ReplayCursor scrubs the result before writing it, in every record mode."""

    @pytest.mark.parametrize("mode", ["once", "new_episodes", "all"])
    def test_cassette_arrow_is_scrubbed(self, tmp_path: Path, mode: str) -> None:
        cassette = tmp_path / "c"
        cursor = ReplayCursor(
            real_cursor=_mock_real_cursor(_describe_table()),
            mode=mode,
            cassette_path=cassette,
            scrub_result_keys_global=["owner"],
            driver_name="adbc_driver_test",
        )
        cursor.execute('DESCRIBE EXTENDED "sales_view" AS JSON')

        _, arrow_path, _ = interaction_file_paths(cassette, 0)
        recorded = read_arrow_table(arrow_path)
        text = recorded.column("json_metadata")[0].as_py()
        assert "someone@example.com" not in text
        assert json.loads(text)["owner"] == "REDACTED"

    def test_recording_test_sees_scrubbed_result(self, tmp_path: Path) -> None:
        """The recording run returns what replay will return, not the live value."""
        cursor = ReplayCursor(
            real_cursor=_mock_real_cursor(_describe_table()),
            mode="once",
            cassette_path=tmp_path / "c",
            scrub_result_keys_global=["owner"],
        )
        cursor.execute("DESCRIBE x")
        text = cursor.fetch_arrow_table().column("json_metadata")[0].as_py()
        assert json.loads(text)["owner"] == "REDACTED"

    def test_replay_returns_scrubbed_result(self, tmp_path: Path) -> None:
        cassette = tmp_path / "c"
        recorder = ReplayCursor(
            real_cursor=_mock_real_cursor(_describe_table()),
            mode="once",
            cassette_path=cassette,
            scrub_result_keys_global=["owner"],
        )
        recorder.execute("DESCRIBE x")

        replayer = ReplayCursor(real_cursor=None, mode="none", cassette_path=cassette)
        replayer.execute("DESCRIBE x")
        text = replayer.fetch_arrow_table().column("json_metadata")[0].as_py()
        assert json.loads(text)["owner"] == "REDACTED"

    def test_per_driver_keys_apply_only_to_that_driver(self, tmp_path: Path) -> None:
        for driver, expected in (("drv_a", "REDACTED"), ("drv_b", "someone@example.com")):
            cassette = tmp_path / driver
            cursor = ReplayCursor(
                real_cursor=_mock_real_cursor(_describe_table()),
                mode="once",
                cassette_path=cassette,
                scrub_result_keys_per_driver={"drv_a": ["owner"]},
                driver_name=driver,
            )
            cursor.execute("DESCRIBE x")
            _, arrow_path, _ = interaction_file_paths(cassette, 0)
            text = read_arrow_table(arrow_path).column("json_metadata")[0].as_py()
            assert json.loads(text)["owner"] == expected

    def test_no_keys_writes_result_unchanged(self, tmp_path: Path) -> None:
        cassette = tmp_path / "c"
        table = _describe_table()
        cursor = ReplayCursor(
            real_cursor=_mock_real_cursor(table), mode="once", cassette_path=cassette
        )
        cursor.execute("DESCRIBE x")
        _, arrow_path, _ = interaction_file_paths(cassette, 0)
        assert read_arrow_table(arrow_path).equals(table)


class TestScrubResultKeysIni:
    """adbc_scrub_result_keys is read from config and reaches every recording cursor."""

    def test_ini_parsed_onto_session(self, pytester: pytest.Pytester) -> None:
        pytester.makeini(
            "[pytest]\nadbc_scrub_result_keys =\n    owner\n    adbc_driver_x: created_time\n"
        )
        pytester.makepyfile(
            """
            def test_keys(adbc_replay):
                assert adbc_replay.scrub_result_keys_global == ["owner"]
                assert adbc_replay.scrub_result_keys_per_driver == {
                    "adbc_driver_x": ["created_time"]
                }
            """
        )
        pytester.runpytest("-v").assert_outcomes(passed=1)

    def test_record_through_plugin_and_clone(self, pytester: pytest.Pytester) -> None:
        """End to end with SQLite: the cassette written by a cloned connection is scrubbed."""
        pytester.makeini("[pytest]\nadbc_scrub_result_keys = owner\n")
        pytester.makepyfile(
            """
            import pytest

            QUERY = (
                "SELECT 'me@example.com' AS owner, "
                "'{\\"owner\\":\\"me@example.com\\",\\"n\\":1}' AS meta"
            )

            @pytest.fixture
            def db_conn(adbc_replay, request):
                return adbc_replay.wrap("adbc_driver_sqlite.dbapi", request=request)

            def test_scrubbed(db_conn):
                cursor = db_conn.adbc_clone().cursor()
                cursor.execute(QUERY)
                row = cursor.fetch_arrow_table().to_pylist()[0]
                assert row == {"owner": "REDACTED", "meta": '{"owner":"REDACTED","n":1}'}
            """
        )
        pytester.runpytest("--adbc-record=once", "-v").assert_outcomes(passed=1)

        arrow_files = list((pytester.path / "tests" / "cassettes").rglob("*_result.arrow"))
        assert len(arrow_files) == 1
        assert b"me@example.com" not in arrow_files[0].read_bytes()

        pytester.runpytest("-v").assert_outcomes(passed=1)
