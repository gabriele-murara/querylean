"""Significant token produced by the MySQL lexer."""

from __future__ import annotations


class SqlToken:
    """A token outside comments: a word, string, quoted identifier, number or
    symbol."""

    WORD = "word"
    STRING = "string"
    QUOTED_IDENTIFIER = "qident"
    NUMBER = "number"
    SYMBOL = "symbol"

    def __init__(self, kind: str, text: str, start: int) -> None:
        self.__kind = kind
        self.__text = text
        self.__start = start

    @property
    def kind(self) -> str:
        """One of the kind constants of this class."""
        return self.__kind

    @property
    def text(self) -> str:
        """Source text of the token."""
        return self.__text

    @property
    def start(self) -> int:
        """Offset of the token in the source text."""
        return self.__start

    def is_word(self) -> bool:
        """True for unquoted words (keywords and identifiers)."""
        return self.__kind == SqlToken.WORD

    def is_symbol(self, symbol: str) -> bool:
        """True when the token is the given single-character symbol."""
        return self.__kind == SqlToken.SYMBOL and self.__text == symbol

    def __repr__(self) -> str:
        text = "SqlToken({}, {!r}, {})"
        return text.format(self.__kind, self.__text, self.__start)
