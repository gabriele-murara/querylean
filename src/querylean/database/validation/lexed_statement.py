"""Output of the MySQL lexer."""

from __future__ import annotations

from querylean.database.validation.sql_token import SqlToken


class LexedStatement:
    """Significant tokens of a single statement plus its text without the final
    ``;``."""

    def __init__(self, tokens: list[SqlToken], statement: str) -> None:
        self.__tokens = list(tokens)
        self.__statement = statement

    @property
    def tokens(self) -> list[SqlToken]:
        """Tokens outside comments, in source order."""
        return list(self.__tokens)

    @property
    def statement(self) -> str:
        """Statement text, stripped, without the trailing semicolon."""
        return self.__statement
