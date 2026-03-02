"""Tests for cassette path derivation from pytest node IDs."""

from __future__ import annotations

from pathlib import Path

from pytest_adbc_replay._cassette_path import node_id_to_cassette_path

_BASE = Path("tests/cassettes")


class TestNodeIdToCassettePath:
    """Tests for the node_id_to_cassette_path function."""

    def test_basic_function_node_id(self) -> None:
        """Simple module + function -> two-segment path."""
        result = node_id_to_cassette_path("tests/test_basic.py::test_something", _BASE)
        assert result == _BASE / "test_basic" / "test_something"

    def test_strips_tests_prefix(self) -> None:
        """tests/ prefix is removed so cassette paths don't double-nest."""
        result = node_id_to_cassette_path("tests/test_basic.py::test_fn", _BASE)
        assert "tests" not in str(result.relative_to(_BASE))

    def test_nested_module(self) -> None:
        """Subdirectory module preserves directory structure."""
        result = node_id_to_cassette_path("tests/foo/test_bar.py::test_fn", _BASE)
        assert result == _BASE / "foo" / "test_bar" / "test_fn"

    def test_class_and_method(self) -> None:
        """Class and method become separate path segments."""
        result = node_id_to_cassette_path("tests/foo/test_bar.py::TestClass::test_method", _BASE)
        assert result == _BASE / "foo" / "test_bar" / "TestClass" / "test_method"

    def test_parametrize_brackets_slugified(self) -> None:
        """Pytest parametrize brackets [param-1] are slugified to _param_1_."""
        result = node_id_to_cassette_path("tests/test_basic.py::test_something[param-1]", _BASE)
        # Brackets and hyphens -> underscores; preserves casing
        assert result == _BASE / "test_basic" / "test_something_param_1_"

    def test_spaces_slugified(self) -> None:
        """Spaces in parametrize values are slugified."""
        result = node_id_to_cassette_path("tests/test_basic.py::test_fn[hello world]", _BASE)
        assert result == _BASE / "test_basic" / "test_fn_hello_world_"

    def test_preserves_original_casing(self) -> None:
        """Casing is NOT lowercased -- TestClass stays TestClass."""
        result = node_id_to_cassette_path("tests/test_file.py::MyTestClass::my_Test_Method", _BASE)
        assert "MyTestClass" in str(result)
        assert "my_Test_Method" in str(result)

    def test_strips_py_extension(self) -> None:
        """Module .py extension is stripped from cassette path."""
        result = node_id_to_cassette_path("tests/test_basic.py::test_fn", _BASE)
        for part in result.parts:
            assert not part.endswith(".py"), f"Part {part!r} still has .py extension"

    def test_custom_cassette_dir(self) -> None:
        """cassette_dir parameter is respected."""
        custom = Path("custom/cassettes")
        result = node_id_to_cassette_path("tests/test_basic.py::test_fn", custom)
        assert result.is_relative_to(custom)

    def test_no_tests_prefix(self) -> None:
        """Node IDs without tests/ prefix work without stripping."""
        result = node_id_to_cassette_path("test_basic.py::test_fn", _BASE)
        assert result == _BASE / "test_basic" / "test_fn"


class TestDriverModuleNameSubdir:
    """Tests for per-driver cassette subdirectory support (Phase 8)."""

    def test_driver_subdir_appended(self) -> None:
        """driver_module_name is appended as the final path component."""
        result = node_id_to_cassette_path(
            "tests/test_foo.py::test_bar",
            _BASE,
            driver_module_name="adbc_driver_snowflake",
        )
        assert result == _BASE / "test_foo" / "test_bar" / "adbc_driver_snowflake"

    def test_driver_subdir_none_unchanged(self) -> None:
        """When driver_module_name is None, result is unchanged from existing behaviour."""
        result_with_none = node_id_to_cassette_path(
            "tests/test_foo.py::test_bar",
            _BASE,
            driver_module_name=None,
        )
        result_default = node_id_to_cassette_path(
            "tests/test_foo.py::test_bar",
            _BASE,
        )
        assert result_with_none == result_default == _BASE / "test_foo" / "test_bar"

    def test_driver_full_name_preserved(self) -> None:
        """Full module name used verbatim — not shortened or slugified."""
        result = node_id_to_cassette_path(
            "tests/test_foo.py::test_bar",
            _BASE,
            driver_module_name="adbc_driver_snowflake",
        )
        # Final segment must be the full module name, not shortened
        assert result.name == "adbc_driver_snowflake"

    def test_driver_subdir_with_dotted_module_name(self) -> None:
        """Driver module names with dots (e.g. adbc_driver_sqlite.dbapi) are preserved verbatim."""
        result = node_id_to_cassette_path(
            "tests/test_foo.py::test_bar",
            _BASE,
            driver_module_name="adbc_driver_sqlite.dbapi",
        )
        assert result == _BASE / "test_foo" / "test_bar" / "adbc_driver_sqlite.dbapi"

    def test_driver_subdir_with_nested_node_id(self) -> None:
        """Per-driver subdir appended after full node path including class name."""
        result = node_id_to_cassette_path(
            "tests/foo/test_bar.py::TestClass::test_method",
            _BASE,
            driver_module_name="adbc_driver_duckdb",
        )
        assert result == (
            _BASE / "foo" / "test_bar" / "TestClass" / "test_method" / "adbc_driver_duckdb"
        )
