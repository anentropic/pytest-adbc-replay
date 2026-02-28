"""Cassette file I/O: Arrow IPC, JSON params, and SQL text read/write."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from typing import Any

import pyarrow as pa


def make_interaction_prefix(index: int) -> str:
    """
    Return zero-padded 3-digit prefix for interaction index.

    Examples:
        make_interaction_prefix(0)   -> "000"
        make_interaction_prefix(1)   -> "001"
        make_interaction_prefix(12)  -> "012"
        make_interaction_prefix(999) -> "999"
    """
    return f"{index:03d}"


def interaction_file_paths(
    cassette_path: Path,
    index: int,
) -> tuple[Path, Path, Path]:
    """
    Return (sql_path, arrow_path, params_path) for interaction at given index.

    File naming (CASS-02):
        {index:03d}_query.sql    — canonical SQL (pretty-printed, UTF-8 text)
        {index:03d}_result.arrow — Arrow IPC file (schema + tabular data)
        {index:03d}_params.json  — JSON-serialised parameters (null when absent)

    Args:
        cassette_path: Path to the cassette directory for this test.
        index: Zero-based interaction index within the cassette.

    Returns:
        Tuple of (sql_path, arrow_path, params_path).
    """
    prefix = make_interaction_prefix(index)
    sql_path = cassette_path / f"{prefix}_query.sql"
    arrow_path = cassette_path / f"{prefix}_result.arrow"
    params_path = cassette_path / f"{prefix}_params.json"
    return sql_path, arrow_path, params_path


def write_arrow_table(table: pa.Table, path: Path) -> None:
    """
    Write a pyarrow.Table to an Arrow IPC file (RecordBatchFileWriter).

    Uses the Arrow IPC File format (not Stream format) — produces a seekable
    file with a footer containing schema and batch offsets. Schema metadata
    (including ADBC extension type metadata in field.metadata) is preserved.

    Args:
        table: The pyarrow.Table to write.
        path: Destination .arrow file path.
    """
    with pa.ipc.new_file(str(path), table.schema) as writer:
        writer.write_table(table)


def read_arrow_table(path: Path) -> pa.Table:
    """
    Read a pyarrow.Table from an Arrow IPC file.

    Args:
        path: Source .arrow file path.

    Returns:
        pyarrow.Table with schema and data as written.
    """
    with pa.ipc.open_file(str(path)) as reader:
        return reader.read_all()


def write_params_json(params_raw: Any, path: Path) -> None:
    """
    Write serialised parameters to a JSON cassette file.

    Args:
        params_raw: JSON-safe parameter structure from serialise_params(), or None.
        path: Destination .json file path.
    """
    path.write_text(json.dumps(params_raw, indent=2, sort_keys=True), encoding="utf-8")


def read_params_json(path: Path) -> Any:
    """
    Read serialised parameters from a JSON cassette file.

    Args:
        path: Source .json file path.

    Returns:
        JSON-decoded value (None, list, or dict).
    """
    return json.loads(path.read_text(encoding="utf-8"))


def write_sql_file(canonical_sql: str, path: Path) -> None:
    """
    Write canonical (normalised) SQL to a .sql cassette file.

    The SQL is written as-is (already normalised by normalise_sql()). No
    additional formatting is applied. UTF-8 encoding with a trailing newline.

    Args:
        canonical_sql: Normalised SQL string from normalise_sql().
        path: Destination .sql file path.
    """
    path.write_text(canonical_sql + "\n", encoding="utf-8")


def read_sql_file(path: Path) -> str:
    """
    Read canonical SQL from a .sql cassette file.

    Args:
        path: Source .sql file path.

    Returns:
        Normalised SQL string (trailing whitespace stripped).
    """
    return path.read_text(encoding="utf-8").strip()


def count_interactions(cassette_path: Path) -> int:
    """
    Count the number of recorded interactions in a cassette directory.

    Counts by scanning for *_query.sql files. If the directory does not
    exist, returns 0.

    Args:
        cassette_path: Path to the cassette directory.

    Returns:
        Number of interactions (0 if directory missing or empty).
    """
    if not cassette_path.exists():
        return 0
    return sum(1 for _ in cassette_path.glob("*_query.sql"))


def cassette_has_interactions(cassette_path: Path) -> bool:
    """
    Return True if the cassette directory exists and has at least one interaction.

    Used by 'once' mode to determine whether to replay or re-record.
    An empty directory is treated as NOT having interactions (=> re-record).

    Args:
        cassette_path: Path to the cassette directory.

    Returns:
        True if cassette_path exists and contains at least one *_query.sql file.
    """
    return count_interactions(cassette_path) > 0


def load_all_interactions(
    cassette_path: Path,
) -> list[tuple[str, pa.Table, Any]]:
    """
    Load all interactions from a cassette directory in order.

    Returns a list of (canonical_sql, table, params_raw) tuples, one per
    interaction, in index order (000, 001, 002, ...).

    This is used to pre-populate the replay queue at the start of a test.

    Args:
        cassette_path: Path to the cassette directory.

    Returns:
        Ordered list of (canonical_sql, pyarrow.Table, params_raw) tuples.
        Empty list if directory does not exist.
    """
    if not cassette_path.exists():
        return []

    interactions: list[tuple[str, pa.Table, Any]] = []
    # Scan for SQL files in sorted order (000_, 001_, ...)
    sql_files = sorted(cassette_path.glob("*_query.sql"))

    for sql_path in sql_files:
        prefix = sql_path.name.split("_")[0]  # "000", "001", etc.
        arrow_path = cassette_path / f"{prefix}_result.arrow"
        params_path = cassette_path / f"{prefix}_params.json"

        canonical_sql = read_sql_file(sql_path)
        table = read_arrow_table(arrow_path)
        params_raw = read_params_json(params_path) if params_path.exists() else None

        interactions.append((canonical_sql, table, params_raw))

    return interactions
