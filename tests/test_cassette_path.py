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
