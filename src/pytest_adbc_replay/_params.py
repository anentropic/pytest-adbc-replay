"""Parameter serialisation for cassette key computation and storage."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID


class _NoDefaultSerialisers(dict):  # type: ignore[type-arg]
    """
    Sentinel dict subclass.

    Instances preserve sentinel identity through ``|`` merges so that
    ``build_registry`` can detect them and skip the built-in merge::

        NO_DEFAULT_SERIALISERS | {MyType: handler}
        → _NoDefaultSerialisers({MyType: handler})
        → build_registry returns {MyType: handler}  (no built-ins)
    """

    def __or__(self, other: dict) -> _NoDefaultSerialisers:  # type: ignore[override]
        return _NoDefaultSerialisers(other)

    def __ror__(self, other: dict) -> _NoDefaultSerialisers:  # type: ignore[override]
        return _NoDefaultSerialisers(other)


NO_DEFAULT_SERIALISERS: _NoDefaultSerialisers = _NoDefaultSerialisers()


# ---------------------------------------------------------------------------
# Built-in serialise/deserialise helpers with explicit types
# ---------------------------------------------------------------------------


def _ser_datetime(v: datetime) -> dict[str, str]:
    return {"__type__": "datetime", "value": v.isoformat()}


def _des_datetime(d: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(str(d["value"]))


def _ser_date(v: date) -> dict[str, str]:
    return {"__type__": "date", "value": v.isoformat()}


def _des_date(d: dict[str, Any]) -> date:
    return date.fromisoformat(str(d["value"]))


def _ser_time(v: time) -> dict[str, str]:
    return {"__type__": "time", "value": v.isoformat()}


def _des_time(d: dict[str, Any]) -> time:
    return time.fromisoformat(str(d["value"]))


def _ser_decimal(v: Decimal) -> dict[str, str]:
    return {"__type__": "Decimal", "value": str(v)}


def _des_decimal(d: dict[str, Any]) -> Decimal:
    return Decimal(str(d["value"]))


def _ser_bytes(v: bytes) -> dict[str, str]:
    return {"__type__": "bytes", "value": v.hex()}


def _des_bytes(d: dict[str, Any]) -> bytes:
    return bytes.fromhex(str(d["value"]))


def _ser_uuid(v: UUID) -> dict[str, str]:
    return {"__type__": "UUID", "value": str(v)}


def _des_uuid(d: dict[str, Any]) -> UUID:
    return UUID(str(d["value"]))


# Built-in type registry — covers the most common non-JSON-native Python types.
# Note: datetime must appear before date because datetime is a subclass of date.
_BUILTIN_SERIALISERS: dict[type[Any], dict[str, Any]] = {
    datetime: {"serialise": _ser_datetime, "deserialise": _des_datetime},
    date: {"serialise": _ser_date, "deserialise": _des_date},
    time: {"serialise": _ser_time, "deserialise": _des_time},
    Decimal: {"serialise": _ser_decimal, "deserialise": _des_decimal},
    bytes: {"serialise": _ser_bytes, "deserialise": _des_bytes},
    UUID: {"serialise": _ser_uuid, "deserialise": _des_uuid},
}

# Lookup: __type__ string -> deserialise callable
_BUILTIN_TYPE_TAGS: dict[str, Any] = {
    "datetime": _des_datetime,
    "date": _des_date,
    "time": _des_time,
    "Decimal": _des_decimal,
    "bytes": _des_bytes,
    "UUID": _des_uuid,
}


def build_registry(
    user_serialisers: dict[type[Any], dict[str, Any]] | None,
) -> dict[type[Any], dict[str, Any]]:
    """
    Build serialiser registry by merging built-ins with user-provided serialisers.

    Three behaviours:

    * ``None`` → built-in registry only (default when fixture is not overridden).
    * ``_NoDefaultSerialisers`` instance (including ``NO_DEFAULT_SERIALISERS`` and
      ``NO_DEFAULT_SERIALISERS | {types}``) → only the entries in that dict, no
      built-ins added.
    * Any other non-empty dict → built-ins merged with user entries; user wins on
      conflict.

    Args:
        user_serialisers: User registry from adbc_param_serialisers fixture, or None.

    Returns:
        Merged registry dict.
    """
    if user_serialisers is None:
        return dict(_BUILTIN_SERIALISERS)
    if isinstance(user_serialisers, _NoDefaultSerialisers):
        return dict(user_serialisers)
    if not user_serialisers:
        return {}
    return {**_BUILTIN_SERIALISERS, **user_serialisers}


def _serialise_value(v: Any, registry: dict[type[Any], dict[str, Any]]) -> Any:
    """Serialise a single parameter value to a JSON-safe form."""
    if v is None:
        return None
    # JSON-native types pass through unchanged
    if isinstance(v, bool):
        return v  # bool before int — bool is a subclass of int
    if isinstance(v, (int, float, str)):
        return v
    # Check registry in insertion order
    for typ, handler in registry.items():
        if isinstance(v, typ):
            result: Any = handler["serialise"](v)
            return result
    raise TypeError(
        f"Cannot serialise parameter of type {type(v).__qualname__!r}.\n"
        f"Register a custom handler via the adbc_param_serialisers fixture:\n\n"
        f"    @pytest.fixture(scope='session')\n"
        f"    def adbc_param_serialisers():\n"
        f"        return {{\n"
        f"            {type(v).__qualname__}: {{\n"
        f"                'serialise': lambda v: ...,\n"
        f"                'deserialise': lambda d: ...,\n"
        f"            }},\n"
        f"        }}"
    )


def serialise_params(
    params: Any,
    registry: dict[type[Any], dict[str, Any]],
) -> Any:
    """
    Serialise execute() parameters to a JSON-safe structure.

    Handles None, sequences (list/tuple), and dicts by recursing into elements.
    Non-JSON-native types are encoded with type tags using the registry.

    Args:
        params: Parameters from ReplayCursor.execute(). May be None, list, tuple, or dict.
        registry: Serialiser registry from build_registry().

    Returns:
        JSON-safe structure (None, list, or dict).

    Raises:
        TypeError: If a parameter value cannot be serialised by any registry entry.
    """
    if params is None:
        return None
    if isinstance(params, (list, tuple)):
        return [_serialise_value(v, registry) for v in params]
    if isinstance(params, dict):
        return {str(k): _serialise_value(v, registry) for k, v in params.items()}
    # Single value (rare — most ADBC drivers use list/tuple)
    return _serialise_value(params, registry)


def _deserialise_value(v: Any, user_registry: dict[type[Any], dict[str, Any]]) -> Any:
    """Deserialise a single JSON-decoded value, restoring type-tagged objects."""
    if not isinstance(v, dict) or "__type__" not in v:
        return v
    type_tag: str = v["__type__"]
    # Use built-in deserialisers (user override support deferred to v2)
    if type_tag in _BUILTIN_TYPE_TAGS:
        builtin_result: Any = _BUILTIN_TYPE_TAGS[type_tag](v)
        return builtin_result
    # Unknown type tag — return as-is (forward compatibility)
    return v


def deserialise_params(
    raw: Any,
    user_serialisers: dict[type[Any], dict[str, Any]] | None = None,
) -> Any:
    """
    Deserialise parameters from JSON-decoded cassette data.

    Inverse of serialise_params(). Restores Python objects from type-tagged JSON.

    Args:
        raw: JSON-decoded parameter data from cassette file.
        user_serialisers: User registry for custom type deserialisation (reserved for v2).

    Returns:
        Original Python parameter values.
    """
    user_reg = user_serialisers or {}
    if raw is None:
        return None
    if isinstance(raw, list):
        return [_deserialise_value(v, user_reg) for v in raw]
    if isinstance(raw, dict) and "__type__" not in raw:
        return {k: _deserialise_value(v, user_reg) for k, v in raw.items()}
    return _deserialise_value(raw, user_reg)


def params_to_cache_key(params: Any, registry: dict[type[Any], dict[str, Any]]) -> str:
    """
    Serialise parameters to a stable JSON string for use as part of a cassette key.

    Uses sort_keys=True for deterministic ordering of dict params.
    Returns 'null' when params is None.
    """
    serialised = serialise_params(params, registry)
    return json.dumps(serialised, sort_keys=True)
