"""A token of SQL text that may be incomplete."""

from __future__ import annotations


class ScanToken:
    """Token produced by ``SqlScanner``: kind, position and whether it is
    terminated (strings, quoted identifiers and comments may not be)."""

    WORD = "word"
    QUOTED = "quoted"
    STRING = "string"
    COMMENT = "comment"
    NUMBER = "number"
    VARIABLE = "variable"
    SYMBOL = "symbol"

    def __init__(
        self, kind: str, text: str, start: int, *, closed: bool = True
    ) -> None:
        self.__kind = kind
        self.__text = text
        self.__start = start
        self.__closed = closed

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
        """Offset of the first character."""
        return self.__start

    @property
    def end(self) -> int:
        """Offset just after the last character."""
        return self.__start + len(self.__text)

    @property
    def closed(self) -> bool:
        """False for a string, quoted identifier or block comment without
        its closing delimiter, and for line comments (they run to the end
        of the line)."""
        return self.__closed

    @property
    def upper(self) -> str:
        """Upper-case text (for keyword checks)."""
        return self.__text.upper()

    @property
    def is_identifier(self) -> bool:
        """True for a word or a quoted identifier."""
        return self.__kind in (ScanToken.WORD, ScanToken.QUOTED)

    @property
    def name(self) -> str:
        """Identifier value: quoted identifiers without backticks and with
        doubled backticks undone."""
        if self.__kind != ScanToken.QUOTED:
            return self.__text
        inner = self.__text[1:-1] if self.__closed else self.__text[1:]
        return inner.replace("``", "`")

    def is_symbol(self, symbol: str) -> bool:
        """True when the token is the symbol ``symbol``."""
        return self.__kind == ScanToken.SYMBOL and self.__text == symbol

    def is_word(self, *words: str) -> bool:
        """True for a word equal (case insensitive) to one of ``words``."""
        return self.__kind == ScanToken.WORD and self.upper in words

    def __repr__(self) -> str:
        text = "ScanToken({}, {!r}, {})"
        return text.format(self.__kind, self.__text, self.__start)
