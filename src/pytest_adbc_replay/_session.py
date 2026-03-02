"""ReplaySession: session-scoped plugin state and .wrap() factory."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pytest_adbc_replay._cassette_path import node_id_to_cassette_path

if TYPE_CHECKING:
    import pytest

    from pytest_adbc_replay._connection import ReplayConnection


_DEFAULT_CASSETTE_DIR = Path("tests/cassettes")


class ReplaySession:
    """
    Session-scoped plugin state.

    Holds configuration (mode, cassette dir). Per-test cassette state
    is created via .wrap(), called from function-scoped user fixtures.
    """

    def __init__(
        self,
        mode: str,
        cassette_dir: Path = _DEFAULT_CASSETTE_DIR,
        param_serialisers: dict[Any, dict[str, Any]] | None = None,
        scrubber: object = None,
        dialect: str | None = None,
    ) -> None:
        self.mode = mode
        self.cassette_dir = cassette_dir
        self.param_serialisers = param_serialisers
        self.scrubber = scrubber  # stored; never called in v1
        self.dialect = dialect  # global dialect fallback from ini config

    def wrap(
        self,
        driver_module_name: str,
        db_kwargs: dict[str, object] | None = None,
        *,
        request: pytest.FixtureRequest | None = None,
        cassette_name: str | None = None,
        dialect: str | None = None,
        param_serialisers: dict[Any, dict[str, Any]] | None = None,
    ) -> ReplayConnection:
        """
        Create a ReplayConnection for the current test.

        Args:
            driver_module_name: ADBC driver module name (e.g. "adbc_driver_snowflake").
                Required but ignored in replay mode (none). Never imported in replay mode.
            db_kwargs: Keyword arguments forwarded to the real driver's connect() in
                record mode. Ignored in replay mode.
            request: pytest FixtureRequest from the calling fixture.
                Used to resolve cassette path from node ID and marker.
                If provided, marker takes precedence over cassette_name.
            cassette_name: Override cassette name. If None, derived from node ID.
            dialect: SQL dialect for normalisation (sqlglot dialect string, e.g. "snowflake").
            param_serialisers: Per-call override of custom parameter serialisers.
                If None, falls back to the session-level param_serialisers set on
                this ReplaySession (typically from the adbc_param_serialisers fixture).

        Returns:
            ReplayConnection ready for use in the test.
        """
        # Lazy import to avoid circular imports at module level
        from pytest_adbc_replay._connection import ReplayConnection  # noqa: PLC0415

        resolved_name: str | None = cassette_name
        # Priority: explicit wrap(dialect=...) arg > session global > None
        resolved_dialect: str | None = dialect if dialect is not None else self.dialect

        if request is not None:
            # Read marker from test item — method marker wins over class marker
            marker = request.node.get_closest_marker("adbc_cassette")
            if marker is not None:
                if marker.args:
                    resolved_name = str(marker.args[0])
                # Marker wins over both explicit arg and session global
                resolved_dialect = marker.kwargs.get("dialect", resolved_dialect)

        # Derive cassette path
        if resolved_name is not None:
            cassette_path = self.cassette_dir / resolved_name
        elif request is not None:
            cassette_path = node_id_to_cassette_path(request.node.nodeid, self.cassette_dir)
        else:
            cassette_path = self.cassette_dir / "unknown"

        # Per-call param_serialisers wins over session-level fallback
        resolved_serialisers = (
            param_serialisers if param_serialisers is not None else self.param_serialisers
        )

        return ReplayConnection(
            driver_module_name=driver_module_name,
            db_kwargs=db_kwargs or {},
            mode=self.mode,
            cassette_path=cassette_path,
            dialect=resolved_dialect,
            param_serialisers=resolved_serialisers,
        )

    def wrap_from_item(
        self,
        driver_module_name: str,
        item: pytest.Item,
        db_kwargs: dict[str, object] | None = None,
    ) -> ReplayConnection:
        """
        Create a ReplayConnection for a test item (not a FixtureRequest).

        Used by the monkeypatched connect() to resolve cassette path from the
        currently-running test item without needing a FixtureRequest. Per-driver
        cassette subdirectory is always applied.

        Args:
            driver_module_name: ADBC driver module name (e.g. "adbc_driver_snowflake").
                Appended as the final cassette path segment for per-driver separation.
            item: The currently-running pytest test item.
            db_kwargs: Keyword arguments forwarded to the real driver in record mode.

        Returns:
            ReplayConnection ready for use in the test.
        """
        # Lazy import to avoid circular imports at module level
        from pytest_adbc_replay._connection import ReplayConnection  # noqa: PLC0415

        # Priority: marker dialect > session global > None
        resolved_dialect: str | None = self.dialect

        marker = item.get_closest_marker("adbc_cassette")
        if marker is not None:
            resolved_dialect = marker.kwargs.get("dialect", resolved_dialect)
            if marker.args:
                # Named cassette: cassette_dir / name / driver_module_name
                cassette_path = self.cassette_dir / str(marker.args[0]) / driver_module_name
            else:
                # No name argument: derive from node ID with driver subdir
                cassette_path = node_id_to_cassette_path(
                    item.nodeid, self.cassette_dir, driver_module_name=driver_module_name
                )
        else:
            # No marker: derive from node ID with driver subdir
            cassette_path = node_id_to_cassette_path(
                item.nodeid, self.cassette_dir, driver_module_name=driver_module_name
            )

        return ReplayConnection(
            driver_module_name=driver_module_name,
            db_kwargs=db_kwargs or {},
            mode=self.mode,
            cassette_path=cassette_path,
            dialect=resolved_dialect,
            param_serialisers=self.param_serialisers,
        )
