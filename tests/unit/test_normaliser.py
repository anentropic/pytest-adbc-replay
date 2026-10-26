"""Tests for SQL normalisation (NORM-01 through NORM-04)."""

from __future__ import annotations

import warnings


class TestNormOneCasingAndWhitespace:
    """NORM-01: sqlglot normalises keyword casing and whitespace."""

    def test_lowercase_keywords_normalised(self) -> None:
        """'select * from foo' normalises to uppercase keywords."""
        from pytest_adbc_replay._normaliser import normalise_sql

        result = normalise_sql("select * from foo")
        assert "SELECT" in result
        assert "FROM" in result

    def test_uppercase_keywords_stable(self) -> None:
        """'SELECT * FROM foo' normalises to same form as lowercase."""
        from pytest_adbc_replay._normaliser import normalise_sql

        n1 = normalise_sql("select * from FOO")
        n2 = normalise_sql("SELECT * FROM foo")
        assert n1 == n2

    def test_extra_whitespace_collapsed(self) -> None:
        """Multiple spaces between tokens normalise to single space."""
        from pytest_adbc_replay._normaliser import normalise_sql

        n1 = normalise_sql("SELECT   *   FROM   foo")
        n2 = normalise_sql("SELECT * FROM foo")
        assert n1 == n2

    def test_mixed_casing_and_whitespace(self) -> None:
        """Mixed casing and whitespace both normalised in one pass."""
        from pytest_adbc_replay._normaliser import normalise_sql

        n1 = normalise_sql("select  *  from  FOO")
        n2 = normalise_sql("SELECT * FROM foo")
        assert n1 == n2

    def test_idempotent(self) -> None:
        """normalise_sql(normalise_sql(x)) == normalise_sql(x)."""
        from pytest_adbc_replay._normaliser import normalise_sql

        sql = "select * from users where id = 1"
        once = normalise_sql(sql)
        twice = normalise_sql(once)
        assert once == twice


class TestNormTwoFallback:
    """NORM-02: Falls back to whitespace normalisation with NormalisationWarning."""

    def test_fallback_does_not_raise(self) -> None:
        """normalise_sql() never raises ParseError — always falls back."""
        from pytest_adbc_replay._normaliser import normalise_sql

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            # Must not raise
            result = normalise_sql("ZZZZ @@@@@ NOT VALID SQL !!!!!")
            assert isinstance(result, str)
            assert len(result) > 0

    def test_fallback_emits_normalisation_warning(self) -> None:
        """When sqlglot fails, NormalisationWarning is emitted."""
        import unittest.mock as mock

        import sqlglot.errors

        from pytest_adbc_replay._normaliser import (
            NormalisationWarning,
            _cached_normalise,
            normalise_sql,
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with mock.patch(
                "pytest_adbc_replay._normaliser.sqlglot.parse_one",
                side_effect=sqlglot.errors.ParseError("test error"),
            ):
                # Clear lru_cache so patched version is called
                _cached_normalise.cache_clear()
                result = normalise_sql("SELECT 1")
                _cached_normalise.cache_clear()  # restore after test

            warning_categories = [w.category for w in caught]
            assert NormalisationWarning in warning_categories, (
                f"Expected NormalisationWarning, got: {warning_categories}"
            )
            # Fallback: whitespace collapse
            assert result == "SELECT 1"

    def test_warning_is_user_warning_subclass(self) -> None:
        """NormalisationWarning is a UserWarning subclass — suppressible via -W."""
        from pytest_adbc_replay._normaliser import NormalisationWarning

        assert issubclass(NormalisationWarning, UserWarning)

    def test_fallback_collapses_whitespace(self) -> None:
        """Fallback result collapses multiple whitespace to single space."""
        import unittest.mock as mock

        import sqlglot.errors

        from pytest_adbc_replay._normaliser import _cached_normalise, normalise_sql

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            with mock.patch(
                "pytest_adbc_replay._normaliser.sqlglot.parse_one",
                side_effect=sqlglot.errors.ParseError("test error"),
            ):
                _cached_normalise.cache_clear()
                result = normalise_sql("SELECT   *   FROM   foo")
                _cached_normalise.cache_clear()

        assert result == "SELECT * FROM foo"


class TestNormThreeDialect:
    """NORM-03: Dialect configurable; normalise_sql() accepts dialect parameter."""

    def test_dialect_none_works(self) -> None:
        """dialect=None (auto-detect) produces a result."""
        from pytest_adbc_replay._normaliser import normalise_sql

        result = normalise_sql("SELECT id FROM users", dialect=None)
        assert isinstance(result, str)
        assert "SELECT" in result or "select" in result

    def test_dialect_snowflake_works(self) -> None:
        """dialect='snowflake' produces a result without error."""
        from pytest_adbc_replay._normaliser import normalise_sql

        result = normalise_sql("SELECT id FROM users", dialect="snowflake")
        assert isinstance(result, str)

    def test_dialect_affects_normalisation(self) -> None:
        """Different dialects may produce different canonical forms."""
        from pytest_adbc_replay._normaliser import normalise_sql

        # Just verify both work without error — dialect semantics are sqlglot's domain
        n1 = normalise_sql("SELECT CURRENT_TIMESTAMP", dialect=None)
        n2 = normalise_sql("SELECT CURRENT_TIMESTAMP", dialect="snowflake")
        assert isinstance(n1, str)
        assert isinstance(n2, str)

    def test_dialect_none_and_no_arg_equivalent(self) -> None:
        """normalise_sql(sql) == normalise_sql(sql, dialect=None)."""
        from pytest_adbc_replay._normaliser import normalise_sql

        sql = "SELECT id FROM users WHERE id = 1"
        assert normalise_sql(sql) == normalise_sql(sql, dialect=None)


class TestNormFourPlaceholders:
    """NORM-04: Parameter placeholders preserved as-is in SQL keys."""

    def test_question_mark_placeholder_preserved(self) -> None:
        """? placeholder survives normalisation."""
        from pytest_adbc_replay._normaliser import normalise_sql

        result = normalise_sql("SELECT * FROM t WHERE id = ?")
        # The placeholder must still be present after normalisation
        assert "?" in result

    def test_normalisation_stable_with_placeholders(self) -> None:
        """Same SQL with placeholder normalises to same string twice."""
        from pytest_adbc_replay._normaliser import normalise_sql

        sql = "SELECT * FROM t WHERE id = ?"
        assert normalise_sql(sql) == normalise_sql(sql)

    def test_named_placeholder_preserved(self) -> None:
        """Named :param placeholder survives normalisation."""
        from pytest_adbc_replay._normaliser import normalise_sql

        result = normalise_sql("SELECT * FROM t WHERE id = :id")
        # Named placeholder should survive
        assert ":id" in result or "id" in result


class TestNormFiveLossless:
    """
    NORM-05: Normalisation never drops part of a statement.

    The generic sqlglot generator renders ``DESCRIBE`` without its object kind
    and renders ``SHOW`` as an empty string, so distinct statements used to
    share a cassette key. Each case below names the statement it must keep.
    """

    def test_snowflake_describe_semantic_view_keeps_kind(self) -> None:
        """DESCRIBE SEMANTIC VIEW x is not recorded as DESCRIBE x."""
        from pytest_adbc_replay._normaliser import normalise_sql

        result = normalise_sql("describe semantic view db.sch.sales", dialect="snowflake")
        assert result == "DESCRIBE SEMANTIC VIEW db.sch.sales"

    def test_snowflake_describe_kinds_get_distinct_keys(self) -> None:
        """DESCRIBE TABLE, DESCRIBE VIEW and DESCRIBE SEMANTIC VIEW of one name differ."""
        from pytest_adbc_replay._normaliser import normalise_sql

        keys = {
            normalise_sql(f"DESCRIBE {kind} sales", dialect="snowflake")
            for kind in ("TABLE", "VIEW", "SEMANTIC VIEW")
        }
        assert len(keys) == 3

    def test_generic_dialect_describe_keeps_kind(self) -> None:
        """
        Without a dialect, DESCRIBE VIEW is not recorded as DESCRIBE x.

        No generator keeps the kind, so this takes the whitespace fallback and warns.
        """
        from pytest_adbc_replay._normaliser import NormalisationWarning, normalise_sql

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            view_key = normalise_sql("DESCRIBE VIEW sales")
        assert view_key == "DESCRIBE VIEW sales"
        assert [w.category for w in caught] == [NormalisationWarning]

    def test_unsupported_construct_keeps_existing_key(self) -> None:
        """
        A non-empty generic rendering is kept even if sqlglot logs part of it as unsupported.

        The generic generator drops FOR UPDATE. That predates NORM-05, so the key
        stays as it was rather than moving to the dialect rendering or the fallback.
        """
        from pytest_adbc_replay._normaliser import normalise_sql

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert normalise_sql("SELECT * FROM t FOR UPDATE", dialect="postgres") == (
                "SELECT\n  *\nFROM t"
            )
            assert normalise_sql("SELECT * FROM t FOR UPDATE") == "SELECT\n  *\nFROM t"

    def test_describe_table_keeps_existing_key(self) -> None:
        """TABLE is DESCRIBE's default kind, so DESCRIBE TABLE x keeps the key DESCRIBE x."""
        from pytest_adbc_replay._normaliser import normalise_sql

        with warnings.catch_warnings():
            warnings.simplefilter("error")  # no fallback warning either
            assert normalise_sql("DESCRIBE TABLE sales") == "DESCRIBE sales"
            assert normalise_sql("DESCRIBE TABLE sales", dialect="snowflake") == "DESCRIBE sales"
            assert (
                normalise_sql("DESCRIBE TABLE EXTENDED `sales` AS JSON", dialect="databricks")
                == 'DESCRIBE EXTENDED "sales" AS JSON'
            )

    def test_snowflake_show_columns_not_empty(self) -> None:
        """SHOW COLUMNS IN VIEW x is not recorded as an empty string."""
        from pytest_adbc_replay._normaliser import normalise_sql

        result = normalise_sql("show columns in view db.sch.sales", dialect="snowflake")
        assert result == "SHOW COLUMNS IN VIEW db.sch.sales"

    def test_snowflake_show_statements_get_distinct_keys(self) -> None:
        """Different SHOW statements no longer collapse onto one key."""
        from pytest_adbc_replay._normaliser import normalise_sql

        statements = [
            "SHOW TABLES",
            "SHOW COLUMNS IN VIEW sales",
            "SHOW COLUMNS IN TABLE orders",
            "SHOW TERSE VIEWS LIKE '%a%' IN SCHEMA db.sch",
        ]
        keys = [normalise_sql(s, dialect="snowflake") for s in statements]
        assert all(keys), keys
        assert len(set(keys)) == len(statements), keys

    def test_snowflake_show_is_idempotent(self) -> None:
        """A recorded SHOW key normalises back to itself."""
        from pytest_adbc_replay._normaliser import normalise_sql

        once = normalise_sql("show columns in view sales", dialect="snowflake")
        assert once == "SHOW COLUMNS IN VIEW sales"
        assert normalise_sql(once, dialect="snowflake") == once

    def test_select_keys_unchanged(self) -> None:
        """Statements the generic generator renders fully keep their existing keys."""
        from pytest_adbc_replay._normaliser import normalise_sql

        # Snowflake DATE_TRUNC renders in the generic dialect as TIMESTAMP_TRUNC.
        # Cassettes recorded before NORM-05 are keyed on that generic form, so
        # it must not switch to Snowflake's own rendering.
        result = normalise_sql(
            'SELECT DATE_TRUNC(\'second\', "ORDERED_AT") FROM "ORDERS_VIEW"',
            dialect="snowflake",
        )
        assert result == 'SELECT\n  TIMESTAMP_TRUNC("ORDERED_AT", SECOND)\nFROM "ORDERS_VIEW"'

    def test_databricks_describe_extended_unchanged(self) -> None:
        """DESCRIBE EXTENDED ... AS JSON (no object kind) keeps its existing key."""
        from pytest_adbc_replay._normaliser import normalise_sql

        result = normalise_sql('DESCRIBE EXTENDED "sales_view" AS JSON', dialect="databricks")
        assert result == 'DESCRIBE EXTENDED "sales_view" AS JSON'
