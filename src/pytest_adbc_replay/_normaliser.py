"""SQL normalisation for cassette key computation."""

from __future__ import annotations

import functools
import warnings

import sqlglot
import sqlglot.errors
from sqlglot import exp
from sqlglot.errors import ErrorLevel


class NormalisationWarning(UserWarning):
    """
    Emitted when sqlglot cannot parse SQL and falls back to whitespace normalisation.

    Suppress in pytest: -W ignore::pytest_adbc_replay.NormalisationWarning
    Or in pytest.ini:
        [pytest]
        filterwarnings = ignore::pytest_adbc_replay.NormalisationWarning
    """


def _drops_describe_kind(expression: exp.Expr, rendered: str) -> bool:
    """
    Return True if ``rendered`` lost the object kind of a DESCRIBE statement.

    sqlglot's generic generator renders ``DESCRIBE SEMANTIC VIEW x`` and
    ``DESCRIBE VIEW x`` alike as ``DESCRIBE x``, without reporting it as
    unsupported, so this loss has to be checked for explicitly. ``TABLE`` is the
    default kind (``DESCRIBE TABLE x`` and ``DESCRIBE x`` are the same statement),
    so dropping it loses nothing and existing keys for it stay as they were.
    """
    if not isinstance(expression, exp.Describe):
        return False
    kind = " ".join(str(expression.args.get("kind") or "").upper().split())
    if kind in ("", "TABLE"):
        return False
    return f" {kind} " not in f" {' '.join(rendered.split())} "


def _render(expression: exp.Expr, dialect: str | None) -> str | None:
    """
    Render a parsed statement as a cassette key, or return None if every rendering is lossy.

    The generic (dialect-less) rendering comes first, so the keys of existing
    cassettes stay as they were. When the generic generator cannot represent the
    statement (for example Snowflake ``SHOW``, which it renders as an empty
    string) or drops a DESCRIBE object kind, the source dialect's own generator
    is tried next.
    """
    candidates: list[str | None] = [None]
    if dialect is not None:
        candidates.append(dialect)
    for target in candidates:
        try:
            rendered = expression.sql(
                dialect=target,
                pretty=True,
                normalize=True,
                unsupported_level=ErrorLevel.RAISE,
            )
        except sqlglot.errors.UnsupportedError:
            continue
        if rendered.strip() and not _drops_describe_kind(expression, rendered):
            return rendered
    return None


def _whitespace_fallback(sql: str, dialect: str | None, reason: str) -> str:
    """Collapse whitespace and emit NormalisationWarning explaining why."""
    warnings.warn(
        f"{reason}; falling back to whitespace-only normalisation.\n"
        f"  Dialect: {dialect!r}\n"
        f"  SQL: {sql}\n"
        f"  To suppress: -W ignore::pytest_adbc_replay.NormalisationWarning",
        NormalisationWarning,
        stacklevel=5,
    )
    return " ".join(sql.split())


@functools.lru_cache(maxsize=256)
def _cached_normalise(sql: str, dialect: str | None) -> str:
    """Cached SQL normalisation — LRU-cached per (sql, dialect) pair."""
    try:
        expression = sqlglot.parse_one(sql, dialect=dialect)
    except sqlglot.errors.ParseError:
        return _whitespace_fallback(sql, dialect, "sqlglot could not parse SQL")
    rendered = _render(expression, dialect)
    if rendered is None:
        return _whitespace_fallback(
            sql, dialect, "sqlglot could not render SQL without dropping part of it"
        )
    return rendered


def normalise_sql(sql: str, dialect: str | None = None) -> str:
    """
    Return canonical SQL string for use as a cassette interaction key.

    Normalises keyword casing, whitespace, and quote style via sqlglot. The
    generic sqlglot rendering is used where it keeps the whole statement; where
    it would drop part of it (Snowflake ``SHOW``, the object kind of
    ``DESCRIBE``), the source dialect's rendering is used instead. Falls back to
    whitespace-only collapse, and emits NormalisationWarning, when sqlglot
    cannot parse the SQL (e.g. vendor-specific syntax) or no rendering keeps it
    whole.

    Parameter placeholders (?, %s, $1) are preserved as-is.

    Args:
        sql: Raw SQL string from execute() call.
        dialect: sqlglot dialect string (e.g. 'snowflake', 'duckdb', 'spark').
            None means sqlglot's superset auto-detect grammar.

    Returns:
        Canonical SQL string for use as a cassette key.
    """
    return _cached_normalise(sql, dialect)
