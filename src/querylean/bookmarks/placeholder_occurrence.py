"""Where a placeholder appears in the text of a mask."""

from __future__ import annotations


class PlaceholderOccurrence:
    """``${NAME}`` found at ``start``–``end``; ``quote`` is the quote of the
    string it is written in (``'`` or ``"``), empty outside strings."""

    def __init__(self, name: str, start: int, end: int, quote: str) -> None:
        self.__name = name
        self.__start = start
        self.__end = end
        self.__quote = quote

    @property
    def name(self) -> str:
        """Placeholder name."""
        return self.__name

    @property
    def start(self) -> int:
        """Offset of ``$``."""
        return self.__start

    @property
    def end(self) -> int:
        """Offset just after ``}``."""
        return self.__end

    @property
    def quote(self) -> str:
        """Quote of the enclosing string, empty when outside strings."""
        return self.__quote

    @property
    def quoted(self) -> bool:
        """True inside a string literal."""
        return bool(self.__quote)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PlaceholderOccurrence) and (
            self.__name,
            self.__start,
            self.__end,
            self.__quote,
        ) == (other.name, other.start, other.end, other.quote)

    def __hash__(self) -> int:
        return hash((self.__name, self.__start, self.__end, self.__quote))

    def __repr__(self) -> str:
        text = "PlaceholderOccurrence({!r}, {}, {}, quote={!r})"
        return text.format(self.__name, self.__start, self.__end, self.__quote)
