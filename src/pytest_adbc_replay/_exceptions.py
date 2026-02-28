"""Custom exceptions for pytest-adbc-replay."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003


class CassetteMissError(Exception):
    """
    Raised when a cassette interaction is not found during replay mode.

    Provides two distinct messages:
    - When the cassette directory does not exist at all (record first)
    - When the cassette directory exists but the specific interaction is missing
    """

    @classmethod
    def directory_missing(
        cls,
        raw_sql: str,
        normalised_sql: str,
        cassette_path: Path,
    ) -> CassetteMissError:
        """Create error for when the cassette directory does not exist."""
        msg = (
            f"Cassette directory does not exist — record first.\n"
            f"  Cassette path: {cassette_path}\n"
            f"  Raw SQL:        {raw_sql!r}\n"
            f"  Normalised SQL: {normalised_sql!r}\n"
            f"Run with --adbc-record=once to record this cassette."
        )
        return cls(msg)

    @classmethod
    def interaction_missing(
        cls,
        interaction_index: int,
        raw_sql: str,
        normalised_sql: str,
        cassette_path: Path,
    ) -> CassetteMissError:
        """Create error for when interaction N is not found in an existing cassette."""
        msg = (
            f"Interaction {interaction_index} not found in cassette.\n"
            f"  Cassette path:  {cassette_path}\n"
            f"  Raw SQL:        {raw_sql!r}\n"
            f"  Normalised SQL: {normalised_sql!r}\n"
            f"The cassette exists but does not have enough interactions. "
            f"Run with --adbc-record=new_episodes to record new interactions."
        )
        return cls(msg)
