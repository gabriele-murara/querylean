"""Tests of the keywords and functions offered by the completion."""

import pytest

from querylean.completion.sql_vocabulary import SqlVocabulary
from querylean.database.validation.read_only_validator import (
    ReadOnlyValidator,
)


class TestSqlVocabulary:
    """No forbidden word is proposed; identifiers are quoted when needed."""

    def test_functions_exclude_forbidden_ones(self):
        functions = SqlVocabulary.functions()
        assert "COUNT" in functions and "REPLACE" in functions
        assert "TRUNCATE" in functions
        for name in ("INSERT", "GET_LOCK", "LOAD_FILE", "SET_VAR"):
            assert name not in functions
        assert list(functions) == sorted(functions)

    # Argument lists tried for each function: one must be accepted.
    ARGUMENTS = (
        "",
        "1",
        "1, 2",
        "1, 2, 3",
        "d, INTERVAL 1 DAY",
        "1 AS CHAR",
        "DAY FROM d",
        "'a' USING utf8mb4",
    )

    def test_proposed_functions_pass_the_validator(self):
        validator = ReadOnlyValidator()
        for name in SqlVocabulary.functions():
            accepted = any(
                validator.validate(
                    "SELECT {}({}) FROM t".format(name, arguments)
                ).ok
                for arguments in self.ARGUMENTS
            )
            assert accepted, name

    def test_keyword_lists_have_no_forbidden_word(self):
        for phrases in (
            SqlVocabulary.STATEMENT_KEYWORDS,
            SqlVocabulary.AFTER_TABLE_KEYWORDS,
            SqlVocabulary.AFTER_OPERAND_KEYWORDS,
            SqlVocabulary.EXPRESSION_KEYWORDS,
            SqlVocabulary.SELECT_KEYWORDS,
        ):
            for phrase in phrases:
                assert SqlVocabulary.allowed(phrase), phrase

    @pytest.mark.parametrize(
        ("name", "written"),
        [
            ("users", "users"),
            ("created_at", "created_at"),
            ("$x", "$x"),
            ("order", "`order`"),
            ("Select", "`Select`"),
            ("update", "`update`"),
            ("my col", "`my col`"),
            ("1st", "`1st`"),
            ("a`b", "`a``b`"),
            ("città", "`città`"),
        ],
    )
    def test_identifier(self, name, written):
        assert SqlVocabulary.identifier(name) == written
