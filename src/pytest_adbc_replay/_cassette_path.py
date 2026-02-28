"""Cassette path derivation from pytest node IDs."""

from __future__ import annotations

import re
from pathlib import Path  # noqa: TC003


def _slugify(s: str) -> str:
    """Replace non-word characters with underscores; preserve original casing."""
    return re.sub(r"[^\w]", "_", s)


def node_id_to_cassette_path(node_id: str, cassette_dir: Path) -> Path:
    """
    Derive cassette directory path from a pytest node ID.

    Examples:
        tests/foo/test_bar.py::TestClass::test_method
        -> cassette_dir/foo/test_bar/TestClass/test_method

        tests/test_basic.py::test_something[param-1]
        -> cassette_dir/test_basic/test_something_param_1_
    """
    # Strip leading "tests/" prefix if present (cassettes live inside tests/cassettes/)
    path = re.sub(r"^tests/", "", node_id)
    # Split on "::" to separate module path from class/function names
    parts = path.split("::")
    # First part is the module file path — strip .py extension
    module_path = parts[0].removesuffix(".py")
    rest = parts[1:]
    # Build segments: split module path on "/" then append class/function parts
    module_segments = [_slugify(seg) for seg in module_path.split("/")]
    rest_segments = [_slugify(seg) for seg in rest]
    all_segments = module_segments + rest_segments
    return cassette_dir.joinpath(*all_segments)
