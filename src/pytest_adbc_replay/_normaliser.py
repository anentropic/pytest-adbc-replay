"""SQL normalisation for cassette key computation."""

from __future__ import annotations

import functools
import warnings

import sqlglot
import sqlglot.errors


class NormalisationWarning(UserWarning):
    """
    Emitted when sqlglot cannot parse SQL and falls back to whitespace normalisation.

    Suppress in pytest: -W ignore::pytest_adbc_replay.NormalisationWarning
    Or in pytest.ini:
        [pytest]
        filterwarnings = ignore::pytest_adbc_replay.NormalisationWarning
    """


@functools.lru_cache(maxsize=256)
def _cached_normalise(sql: str, dialect: str | None) -> str:
    """Cached SQL normalisation — LRU-cached per (sql, dialect) pair."""
    try:
        return sqlglot.parse_one(sql, dialect=dialect).sql(pretty=True, normalize=True)
    except sqlglot.errors.ParseError:
        warnings.warn(
            f"sqlglot could not parse SQL; falling back to whitespace-only normalisation.\n"
            f"  Dialect: {dialect!r}\n"
            f"  SQL: {sql}\n"
            f"  To suppress: -W ignore::pytest_adbc_replay.NormalisationWarning",
            NormalisationWarning,
            stacklevel=4,
        )
        return " ".join(sql.split())


def normalise_sql(sql: str, dialect: str | None = None) -> str:
    """
    Return canonical SQL string for use as a cassette interaction key.

    Normalises keyword casing, whitespace, and quote style via sqlglot. Falls
    back to whitespace-only collapse when sqlglot cannot parse the SQL (e.g.,
    vendor-specific syntax) and emits NormalisationWarning.

    Parameter placeholders (?, %s, $1) are preserved as-is.

    Args:
        sql: Raw SQL string from execute() call.
        dialect: sqlglot dialect string (e.g. 'snowflake', 'duckdb', 'spark').
            None means sqlglot's superset auto-detect grammar.

    Returns:
        Canonical SQL string for use as a cassette key.
    """
    return _cached_normalise(sql, dialect)
