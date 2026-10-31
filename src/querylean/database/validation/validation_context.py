"""State shared by the validation stages."""

from __future__ import annotations

from sqlglot import exp

from querylean.database.validation.sql_token import SqlToken


class ValidationContext:
    """Carries the input SQL and what each stage learns about it."""

    def __init__(self, sql: str) -> None:
        self.__sql = sql
        self.__tokens: list[SqlToken] = []
        self.__statement = ""
        self.__first_word = ""
        self.__syntax_tree: exp.Expression | None = None

    @property
    def sql(self) -> str:
        """Original input text."""
        return self.__sql

    @property
    def tokens(self) -> list[SqlToken]:
        """Significant tokens (set by the lexical stage)."""
        return list(self.__tokens)

    @tokens.setter
    def tokens(self, value: list[SqlToken]) -> None:
        self.__tokens = list(value)

    @property
    def statement(self) -> str:
        """Statement text to execute (set by the lexical stage)."""
        return self.__statement

    @statement.setter
    def statement(self, value: str) -> None:
        self.__statement = value

    @property
    def first_word(self) -> str:
        """Upper-case first keyword (set by the keyword stage)."""
        return self.__first_word

    @first_word.setter
    def first_word(self, value: str) -> None:
        self.__first_word = value

    @property
    def syntax_tree(self) -> exp.Expression | None:
        """Parsed statement (set by the syntax-tree stage)."""
        return self.__syntax_tree

    @syntax_tree.setter
    def syntax_tree(self, value: exp.Expression | None) -> None:
        self.__syntax_tree = value
