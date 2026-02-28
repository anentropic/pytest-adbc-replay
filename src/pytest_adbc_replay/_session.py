"""ReplaySession: session-scoped plugin state and .wrap() factory."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

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

    def __init__(self, mode: str, cassette_dir: Path = _DEFAULT_CASSETTE_DIR) -> None:
        self.mode = mode
        self.cassette_dir = cassette_dir

    def wrap(
        self,
        driver_module_name: str,
        db_kwargs: dict[str, object] | None = None,
        *,
        request: pytest.FixtureRequest | None = None,
        cassette_name: str | None = None,
        dialect: str | None = None,
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

        Returns:
            ReplayConnection ready for use in the test.
        """
        # Lazy import to avoid circular imports at module level
        from pytest_adbc_replay._connection import ReplayConnection  # noqa: PLC0415

        resolved_name: str | None = cassette_name
        resolved_dialect: str | None = dialect

        if request is not None:
            # Read marker from test item — method marker wins over class marker
            marker = request.node.get_closest_marker("adbc_cassette")
            if marker is not None:
                if marker.args:
                    resolved_name = str(marker.args[0])
                resolved_dialect = marker.kwargs.get("dialect", dialect)

        # Derive cassette path
        if resolved_name is not None:
            cassette_path = self.cassette_dir / resolved_name
        elif request is not None:
            cassette_path = node_id_to_cassette_path(request.node.nodeid, self.cassette_dir)
        else:
            cassette_path = self.cassette_dir / "unknown"

        return ReplayConnection(
            driver_module_name=driver_module_name,
            db_kwargs=db_kwargs or {},
            mode=self.mode,
            cassette_path=cassette_path,
            dialect=resolved_dialect,
        )
