"""Redaction of named keys in recorded result tables (adbc_scrub_result_keys)."""

from __future__ import annotations

import json
from typing import Any

import pyarrow as pa

REDACTED = "REDACTED"


def result_keys_for_driver(
    global_keys: list[str],
    per_driver_keys: dict[str, list[str]],
    driver_name: str | None,
) -> frozenset[str]:
    """
    Return the result keys to redact for one driver.

    Args:
        global_keys: Key names to redact for all drivers.
        per_driver_keys: Mapping of driver module name → keys to redact for that driver only.
        driver_name: ADBC driver module name (e.g. ``"adbc_driver_snowflake"``).

    Returns:
        The union of the global keys and the keys listed for ``driver_name``.
    """
    return frozenset(global_keys) | frozenset(per_driver_keys.get(driver_name or "", []))


def _is_string_type(data_type: pa.DataType) -> bool:
    """Return True for Arrow string types that can hold the REDACTED sentinel."""
    if pa.types.is_string(data_type) or pa.types.is_large_string(data_type):
        return True
    is_string_view = getattr(pa.types, "is_string_view", None)
    return bool(is_string_view is not None and is_string_view(data_type))


def _redact_json(value: Any, keys: frozenset[str]) -> tuple[Any, bool]:
    """
    Redact matching keys in a decoded JSON value, at any depth.

    Returns:
        Tuple of ``(new_value, changed)``.
    """
    if isinstance(value, dict):
        changed = False
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key in keys:
                result[key] = REDACTED
                changed = changed or item != REDACTED
            else:
                result[key], item_changed = _redact_json(item, keys)
                changed = changed or item_changed
        return result, changed
    if isinstance(value, list):
        changed = False
        items: list[Any] = []
        for item in value:
            new_item, item_changed = _redact_json(item, keys)
            items.append(new_item)
            changed = changed or item_changed
        return items, changed
    return value, False


def _redact_json_text(text: str | None, keys: frozenset[str]) -> str | None:
    """
    Redact matching keys inside a string cell that holds a JSON object or array.

    Cells that are not JSON, and JSON cells with no matching key, are returned
    unchanged byte for byte. A cell that changed is re-serialised compactly with
    its key order kept.
    """
    if text is None or text.lstrip()[:1] not in ("{", "["):
        return text
    try:
        decoded = json.loads(text)
    except ValueError:
        return text
    redacted, changed = _redact_json(decoded, keys)
    if not changed:
        return text
    return json.dumps(redacted, ensure_ascii=False, separators=(",", ":"))


def scrub_result_table(table: pa.Table, keys: frozenset[str]) -> pa.Table:
    """
    Redact named keys in a result table before it is written to a cassette.

    For each string column:

    - if the column name is one of ``keys``, every non-null value becomes ``"REDACTED"``;
    - otherwise, any cell holding a JSON object or array has the value of each
      matching key replaced with ``"REDACTED"``, at any depth (for example the
      ``owner`` field in Databricks ``DESCRIBE ... AS JSON`` output).

    Columns that are not strings are left unchanged. The schema, including
    field and schema metadata, is kept as it was.

    Args:
        table: Result table fetched from the real cursor.
        keys: Column names / JSON keys to redact (exact, case-sensitive match).

    Returns:
        The scrubbed table, or ``table`` itself when nothing matched.
    """
    if not keys:
        return table
    for index, field in enumerate(table.schema):
        if not _is_string_type(field.type):
            continue
        values: list[str | None] = table.column(index).to_pylist()
        if field.name in keys:
            scrubbed = [None if value is None else REDACTED for value in values]
        else:
            scrubbed = [_redact_json_text(value, keys) for value in values]
        if scrubbed == values:
            continue
        new_column = pa.chunked_array([pa.array(scrubbed, type=field.type)], type=field.type)
        table = table.set_column(index, field, new_column)
    return table
