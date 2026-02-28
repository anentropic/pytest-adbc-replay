"""Tests for cassette file I/O (CASS-01 through CASS-05)."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pyarrow as pa

from pytest_adbc_replay._cassette_io import (
    cassette_has_interactions,
    count_interactions,
    interaction_file_paths,
    load_all_interactions,
    make_interaction_prefix,
    read_arrow_table,
    read_params_json,
    read_sql_file,
    write_arrow_table,
    write_params_json,
    write_sql_file,
)


class TestInteractionFileNaming:
    """CASS-02: Interaction file naming scheme."""

    def test_prefix_zero(self) -> None:
        """Index 0 -> '000'."""
        assert make_interaction_prefix(0) == "000"

    def test_prefix_one(self) -> None:
        """Index 1 -> '001'."""
        assert make_interaction_prefix(1) == "001"

    def test_prefix_twelve(self) -> None:
        """Index 12 -> '012'."""
        assert make_interaction_prefix(12) == "012"

    def test_prefix_nine_nine_nine(self) -> None:
        """Index 999 -> '999'."""
        assert make_interaction_prefix(999) == "999"

    def test_file_paths_naming(self, tmp_path: Path) -> None:
        """interaction_file_paths returns correct file names."""
        cassette = tmp_path / "test"
        sql_path, arrow_path, params_path = interaction_file_paths(cassette, 0)
        assert sql_path.name == "000_query.sql"
        assert arrow_path.name == "000_result.arrow"
        assert params_path.name == "000_params.json"

    def test_file_paths_index_5(self, tmp_path: Path) -> None:
        """interaction_file_paths at index 5 uses '005' prefix."""
        cassette = tmp_path / "test"
        sql_path, arrow_path, params_path = interaction_file_paths(cassette, 5)
        assert sql_path.name == "005_query.sql"
        assert arrow_path.name == "005_result.arrow"
        assert params_path.name == "005_params.json"

    def test_file_paths_parent_is_cassette(self, tmp_path: Path) -> None:
        """interaction_file_paths returns files inside the cassette directory."""
        cassette = tmp_path / "mycassette"
        sql_path, arrow_path, params_path = interaction_file_paths(cassette, 0)
        assert sql_path.parent == cassette
        assert arrow_path.parent == cassette
        assert params_path.parent == cassette


class TestArrowIPCRoundTrip:
    """CASS-04: Arrow IPC file preserves schema and data."""

    def test_basic_table_round_trip(self, tmp_path: Path) -> None:
        """Basic table survives write/read round-trip."""
        table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        path = tmp_path / "test.arrow"
        write_arrow_table(table, path)
        result = read_arrow_table(path)
        assert result.num_rows == 3
        assert result.column("id").to_pylist() == [1, 2, 3]
        assert result.column("name").to_pylist() == ["a", "b", "c"]

    def test_schema_metadata_preserved(self, tmp_path: Path) -> None:
        """Schema-level metadata survives Arrow IPC round-trip (CASS-04)."""
        schema = pa.schema(
            [pa.field("x", pa.int64()), pa.field("y", pa.string())],
            metadata={"source": b"test_db", "version": b"1"},
        )
        table = pa.table({"x": [1], "y": ["hello"]}, schema=schema)
        path = tmp_path / "meta.arrow"
        write_arrow_table(table, path)
        result = read_arrow_table(path)
        assert result.schema.metadata == {b"source": b"test_db", b"version": b"1"}

    def test_empty_table_round_trip(self, tmp_path: Path) -> None:
        """Empty table (0 rows) survives round-trip."""
        schema = pa.schema([pa.field("id", pa.int64())])
        table = pa.table({"id": pa.array([], type=pa.int64())}, schema=schema)
        path = tmp_path / "empty.arrow"
        write_arrow_table(table, path)
        result = read_arrow_table(path)
        assert result.num_rows == 0
        assert result.schema == schema

    def test_multiple_column_types(self, tmp_path: Path) -> None:
        """Table with various column types survives round-trip."""
        table = pa.table(
            {
                "int_col": pa.array([1, 2], type=pa.int32()),
                "float_col": pa.array([1.5, 2.5], type=pa.float64()),
                "str_col": pa.array(["x", "y"], type=pa.string()),
                "bool_col": pa.array([True, False], type=pa.bool_()),
            }
        )
        path = tmp_path / "types.arrow"
        write_arrow_table(table, path)
        result = read_arrow_table(path)
        assert result.num_rows == 2
        assert result.column("float_col").to_pylist() == [1.5, 2.5]
        assert result.column("bool_col").to_pylist() == [True, False]


class TestSqlFileRoundTrip:
    """CASS-03: SQL stored as human-readable text."""

    def test_basic_sql_round_trip(self, tmp_path: Path) -> None:
        """Canonical SQL text survives write/read round-trip."""
        sql = "SELECT\n  *\nFROM foo"
        path = tmp_path / "test.sql"
        write_sql_file(sql, path)
        result = read_sql_file(path)
        assert result == sql

    def test_sql_with_pretty_print(self, tmp_path: Path) -> None:
        """Pretty-printed SQL (with indentation) survives round-trip."""
        sql = "SELECT\n  id,\n  name\nFROM users\nWHERE id > 0"
        path = tmp_path / "pretty.sql"
        write_sql_file(sql, path)
        result = read_sql_file(path)
        assert result == sql

    def test_trailing_whitespace_stripped_on_read(self, tmp_path: Path) -> None:
        """read_sql_file() strips trailing whitespace."""
        path = tmp_path / "ws.sql"
        path.write_text("SELECT 1\n\n", encoding="utf-8")
        result = read_sql_file(path)
        assert result == "SELECT 1"

    def test_write_adds_trailing_newline(self, tmp_path: Path) -> None:
        """write_sql_file adds trailing newline to file on disk."""
        path = tmp_path / "nl.sql"
        write_sql_file("SELECT 1", path)
        raw = path.read_text(encoding="utf-8")
        assert raw.endswith("\n")


class TestParamsJsonRoundTrip:
    """CASS-05: Parameters stored as JSON."""

    def test_none_round_trip(self, tmp_path: Path) -> None:
        """None params write as JSON null, read back as None."""
        path = tmp_path / "none.json"
        write_params_json(None, path)
        result = read_params_json(path)
        assert result is None

    def test_list_round_trip(self, tmp_path: Path) -> None:
        """List params survive JSON round-trip."""
        params = [1, "hello", None]
        path = tmp_path / "list.json"
        write_params_json(params, path)
        result = read_params_json(path)
        assert result == params

    def test_type_tagged_dict_round_trip(self, tmp_path: Path) -> None:
        """Type-tagged dict survives JSON round-trip."""
        params = {"__type__": "datetime", "value": "2024-01-15T12:00:00"}
        path = tmp_path / "tagged.json"
        write_params_json(params, path)
        result = read_params_json(path)
        assert result == params

    def test_empty_list_round_trip(self, tmp_path: Path) -> None:
        """Empty list params survive JSON round-trip."""
        path = tmp_path / "empty.json"
        write_params_json([], path)
        result = read_params_json(path)
        assert result == []


class TestCountAndLoadInteractions:
    """Cassette interaction counting and loading."""

    def test_count_missing_dir(self, tmp_path: Path) -> None:
        """count_interactions returns 0 for missing directory."""
        assert count_interactions(tmp_path / "nonexistent") == 0

    def test_count_empty_dir(self, tmp_path: Path) -> None:
        """count_interactions returns 0 for empty directory."""
        empty = tmp_path / "empty"
        empty.mkdir()
        assert count_interactions(empty) == 0

    def test_cassette_has_interactions_false_for_empty(self, tmp_path: Path) -> None:
        """cassette_has_interactions returns False for empty directory (CONTEXT.md: once mode)."""
        empty = tmp_path / "empty"
        empty.mkdir()
        assert cassette_has_interactions(empty) is False

    def test_cassette_has_interactions_false_for_missing(self, tmp_path: Path) -> None:
        """cassette_has_interactions returns False for non-existent directory."""
        assert cassette_has_interactions(tmp_path / "none") is False

    def test_count_one_interaction(self, tmp_path: Path) -> None:
        """count_interactions counts one *_query.sql file."""
        cassette = tmp_path / "one"
        cassette.mkdir()
        (cassette / "000_query.sql").write_text("SELECT 1\n")
        assert count_interactions(cassette) == 1
        assert cassette_has_interactions(cassette) is True

    def test_count_multiple_interactions(self, tmp_path: Path) -> None:
        """count_interactions counts multiple *_query.sql files."""
        cassette = tmp_path / "many"
        cassette.mkdir()
        for i in range(3):
            (cassette / f"{i:03d}_query.sql").write_text(f"SELECT {i}\n")
        assert count_interactions(cassette) == 3

    def test_load_all_interactions_empty_dir(self, tmp_path: Path) -> None:
        """load_all_interactions returns empty list for missing dir."""
        result = load_all_interactions(tmp_path / "none")
        assert result == []

    def test_load_all_interactions_one(self, tmp_path: Path) -> None:
        """load_all_interactions returns one interaction correctly."""
        cassette = tmp_path / "test"
        cassette.mkdir()
        sql_path, arrow_path, params_path = interaction_file_paths(cassette, 0)
        table = pa.table({"x": [42]})
        write_arrow_table(table, arrow_path)
        write_sql_file("SELECT 1", sql_path)
        write_params_json(None, params_path)

        interactions = load_all_interactions(cassette)
        assert len(interactions) == 1
        sql, loaded_table, params = interactions[0]
        assert sql == "SELECT 1"
        assert loaded_table.column("x").to_pylist() == [42]
        assert params is None

    def test_load_all_interactions_in_order(self, tmp_path: Path) -> None:
        """load_all_interactions returns interactions in index order."""
        cassette = tmp_path / "ordered"
        cassette.mkdir()
        for i in range(3):
            sql_path, arrow_path, params_path = interaction_file_paths(cassette, i)
            write_arrow_table(pa.table({"n": [i]}), arrow_path)
            write_sql_file(f"SELECT {i}", sql_path)
            write_params_json(None, params_path)

        interactions = load_all_interactions(cassette)
        assert len(interactions) == 3
        for i, (sql, table, _) in enumerate(interactions):
            assert sql == f"SELECT {i}"
            assert table.column("n").to_pylist() == [i]

    def test_load_all_interactions_with_params(self, tmp_path: Path) -> None:
        """load_all_interactions preserves params correctly."""
        cassette = tmp_path / "withparams"
        cassette.mkdir()
        sql_path, arrow_path, params_path = interaction_file_paths(cassette, 0)
        write_arrow_table(pa.table({"r": [1]}), arrow_path)
        write_sql_file("SELECT :val", sql_path)
        write_params_json({"__type__": "str", "value": "test"}, params_path)

        interactions = load_all_interactions(cassette)
        assert len(interactions) == 1
        _, _, params = interactions[0]
        assert params == {"__type__": "str", "value": "test"}
