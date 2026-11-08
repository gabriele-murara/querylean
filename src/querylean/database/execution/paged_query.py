"""Statements that count and read the pages of a truncated result."""

from __future__ import annotations

from querylean.database.validation.mysql_lexer import MySqlLexer
from querylean.database.validation.sql_token import SqlToken
from querylean.database.validation.validation_rejected import (
    ValidationRejected,
)


class PagedQuery:
    """Count and page statements of a query whose result was truncated.

    The statement (as accepted by ``ReadOnlyValidator``, the text the user
    ran) goes unchanged inside a derived table:
    ``SELECT COUNT(*) FROM (…) AS querylean_count`` and
    ``SELECT * FROM (…) AS querylean_page LIMIT size OFFSET n``. It ends
    on a line of its own, so a final ``--``/``#`` comment cannot hide the
    closing parenthesis. The statements built here are never trusted:
    they run through ``QueryExecutor``, hence the validator, like any query.

    Only ``SELECT``/``WITH`` queries (also in parentheses or with
    ``UNION``) have pages: ``SHOW``, ``DESCRIBE`` and ``EXPLAIN`` cannot be
    a derived table.
    """

    COUNT_ALIAS = "querylean_count"
    PAGE_ALIAS = "querylean_page"
    __QUERY_WORDS = ("SELECT", "WITH")

    @staticmethod
    def is_pageable(statement: str) -> bool:
        """True when ``statement`` is a ``SELECT``/``WITH`` query."""
        try:
            tokens = MySqlLexer.tokenize(statement).tokens
        except ValidationRejected:
            return False
        for token in tokens:
            if token.is_symbol("("):
                continue
            return (
                token.kind == SqlToken.WORD
                and token.text.upper() in PagedQuery.__QUERY_WORDS
            )
        return False

    @staticmethod
    def count_statement(statement: str) -> str:
        """Statement that counts the rows of ``statement``."""
        sql = "SELECT COUNT(*) FROM (\n{}\n) AS {}"
        return sql.format(statement, PagedQuery.COUNT_ALIAS)

    @staticmethod
    def page_statement(statement: str, size: int, page: int) -> str:
        """Statement that reads page ``page`` (from 0) of ``size`` rows."""
        size = max(int(size), 1)
        page = max(int(page), 0)
        sql = "SELECT * FROM (\n{}\n) AS {} LIMIT {} OFFSET {}"
        return sql.format(statement, PagedQuery.PAGE_ALIAS, size, size * page)

    @staticmethod
    def page_count(rows: int, size: int) -> int:
        """Pages of ``size`` rows needed for ``rows`` (at least 1)."""
        size = max(int(size), 1)
        return max((int(rows) + size - 1) // size, 1)
