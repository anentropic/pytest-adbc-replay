"""
Introspection parity test for the ReplayCursor public surface (PARITY-01, D-01).

Asserts that every public member of the real ``adbc_driver_manager.dbapi.Cursor``
is covered by ``ReplayCursor`` with no bare ``AttributeError``, and fails loudly
when ADBC grows a member that is not in the explicit expected-surface map.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyarrow as pa
import pytest
from adbc_driver_manager.dbapi import Cursor as RealCursor
from adbc_driver_manager.dbapi import NotSupportedError, ProgrammingError

from pytest_adbc_replay._cassette_io import (
    interaction_file_paths,
    write_arrow_table,
    write_params_json,
    write_sql_file,
)
from pytest_adbc_replay._connection import ReplayConnection
from pytest_adbc_replay._cursor import ReplayCursor
from pytest_adbc_replay._exceptions import CassetteMissError
from pytest_adbc_replay._normaliser import normalise_sql

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Module-local cassette / cursor helpers (project convention: conftest is empty,
# each test module defines its own — see test_cursor_fetch.py / test_cursor_dbapi.py).
# ---------------------------------------------------------------------------


def _populate_cassette(cassette: Path, sql: str, table: pa.Table) -> None:
    """Pre-populate a cassette directory with one interaction."""
    cassette.mkdir(parents=True, exist_ok=True)
    canonical = normalise_sql(sql)
    sql_path, arrow_path, params_path = interaction_file_paths(cassette, 0)
    write_sql_file(canonical, sql_path)
    write_arrow_table(table, arrow_path)
    write_params_json(None, params_path)


def _replay_connection(tmp_path: Path) -> ReplayConnection:
    """Build a replay-mode ReplayConnection (no real driver imported)."""
    return ReplayConnection(
        driver_module_name="adbc_driver_sqlite",
        db_kwargs={},
        mode="none",
        cassette_path=tmp_path / "cass",
    )


# ---------------------------------------------------------------------------
# Expected-surface map (D-01 loud-on-drift mechanism).
#
# Every public member of the real adbc_driver_manager.dbapi.Cursor maps to its
# replay-mode category. This map is the single source of truth that the DOC-01
# table (docs/src/reference/cursor-surface.md) mirrors — keep both in sync; if
# you change one, change the other. Categories:
#   implemented   — faithful replay-mode behavior
#   derived       — derived from the cassette (e.g. schema from the recorded table)
#   no-op         — silently does nothing in replay (delegates only in record mode)
#   not-supported — raises NotSupportedError in replay
#   lenient       — works but deviates from real ADBC (re-consumable results, Dimension 2)
# ---------------------------------------------------------------------------

EXPECTED_SURFACE: dict[str, str] = {
    # DBAPI core
    "execute": "implemented",
    "executemany": "implemented",
    "executescript": "no-op",
    "close": "implemented",
    "next": "implemented",
    "nextset": "not-supported",
    "callproc": "not-supported",
    "setinputsizes": "no-op",
    "setoutputsize": "no-op",
    "arraysize": "implemented",
    "rowcount": "implemented",
    "rownumber": "implemented",
    "description": "implemented",
    "connection": "implemented",
    # Arrow & DataFrame fetch
    "fetch_record_batch": "implemented",
    "fetch_arrow": "implemented",
    "fetch_df": "implemented",
    "fetch_polars": "implemented",
    "fetch_arrow_table": "lenient",
    "fetchall": "lenient",
    "fetchone": "lenient",
    "fetchmany": "lenient",
    "fetchallarrow": "lenient",
    # ADBC extension
    "adbc_execute_schema": "derived",
    "adbc_cancel": "no-op",
    "adbc_prepare": "no-op",
    "adbc_ingest": "not-supported",
    "adbc_execute_partitions": "not-supported",
    "adbc_read_partition": "not-supported",
    "adbc_statement": "not-supported",
}


def _real_public_surface() -> set[str]:
    """Introspect the public member names of the real ADBC Cursor."""
    return {name for name in dir(RealCursor) if not name.startswith("_")}


# Members invoked as methods during the no-AttributeError sweep are probed with
# representative arguments; the rest are accessed as properties via getattr.
_METHOD_ARGS: dict[str, tuple[object, ...]] = {
    "execute": ("SELECT 1",),
    "executemany": ("SELECT 1", []),
    "executescript": ("SELECT 1",),
    "close": (),
    "next": (),
    "nextset": (),
    "callproc": ("proc", []),
    "setinputsizes": ([],),
    "setoutputsize": (0,),
    "fetch_record_batch": (),
    "fetch_arrow": (),
    "fetch_df": (),
    "fetch_polars": (),
    "fetch_arrow_table": (),
    "fetchall": (),
    "fetchone": (),
    "fetchmany": (),
    "fetchallarrow": (),
    "adbc_execute_schema": ("SELECT 1",),
    "adbc_cancel": (),
    "adbc_prepare": ("SELECT 1",),
    "adbc_ingest": ("t", pa.table({"x": [1]})),
    "adbc_execute_partitions": ("SELECT 1",),
    "adbc_read_partition": (b"partition",),
}

# Intentional exceptions are ALLOWED outcomes — only a bare AttributeError is a
# parity violation. StopIteration covers next() at end-of-stream; record-only
# RuntimeError("no real cursor") is allowed; TypeError covers probe-arg mismatch;
# CassetteMissError covers re-probing execute-like methods that drain the single
# recorded interaction.
_ALLOWED_EXCEPTIONS = (
    NotSupportedError,
    ProgrammingError,
    RuntimeError,
    StopIteration,
    TypeError,
    CassetteMissError,
)


# ---------------------------------------------------------------------------
# PARITY-01: real Cursor surface is fully covered, loud on drift
# ---------------------------------------------------------------------------


class TestSurfaceParity:
    def test_expected_surface_has_thirty_members(self) -> None:
        assert len(EXPECTED_SURFACE) == 30

    def test_expected_surface_categories_are_valid(self) -> None:
        valid = {"implemented", "derived", "no-op", "not-supported", "lenient"}
        unknown = {cat for cat in EXPECTED_SURFACE.values() if cat not in valid}
        assert unknown == set(), f"unknown replay categories: {sorted(unknown)}"

    def test_completeness_and_loud_on_drift(self) -> None:
        """Equality (not subset) so a NEW real-Cursor member fails the test (D-01)."""
        real = sorted(_real_public_surface())
        expected = sorted(EXPECTED_SURFACE)
        # Sorted lists in the assertion give a human-readable diff on ADBC upgrade.
        assert real == expected, (
            "Real ADBC Cursor surface drifted from EXPECTED_SURFACE.\n"
            f"  New on real Cursor (add to map + DOC-01): "
            f"{sorted(set(real) - set(expected))}\n"
            f"  In map but gone from real Cursor: {sorted(set(expected) - set(real))}"
        )

    def test_every_member_resolves_on_replay_cursor(self, tmp_path: Path) -> None:
        """Fast guard: every expected member resolves on ReplayCursor (no AttributeError)."""
        cursor = ReplayCursor(real_cursor=None, mode="none", cassette_path=tmp_path / "c")
        for name in EXPECTED_SURFACE:
            assert hasattr(type(cursor), name), f"{name} is missing from ReplayCursor"

    def test_no_bare_attribute_error_sweep(self, tmp_path: Path) -> None:
        """Probe every expected member on a valid replay cursor; only AttributeError fails."""
        table = pa.table({"id": [1, 2, 3]})
        for name in sorted(EXPECTED_SURFACE):
            # Use a connection-owned, executed cursor so `connection` is non-None
            # and result-consuming members have a loaded _pending table.
            conn = _replay_connection(tmp_path / name)
            cursor = conn.cursor()
            cassette = tmp_path / name / "cass"
            _populate_cassette(cassette, "SELECT 1", table)
            cursor.execute("SELECT 1")

            if name in _METHOD_ARGS:
                args = _METHOD_ARGS[name]
                try:
                    getattr(cursor, name)(*args)
                except _ALLOWED_EXCEPTIONS:
                    pass
                except AttributeError:  # pragma: no cover - parity guard
                    pytest.fail(f"{name}() raised a bare AttributeError (parity violation)")
            else:
                try:
                    _ = getattr(cursor, name)
                except _ALLOWED_EXCEPTIONS:
                    pass
                except AttributeError:  # pragma: no cover - parity guard
                    pytest.fail(f"{name} raised a bare AttributeError (parity violation)")
