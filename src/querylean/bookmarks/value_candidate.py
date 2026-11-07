"""A value of a query that could become a placeholder."""

from __future__ import annotations

from querylean.bookmarks.placeholder import Placeholder


class ValueCandidate:
    """Literal (or ``IN (…)`` list of literals) at ``start``–``end`` of a
    query, with the placeholder it would become: suggested name, type and
    default inferred from the value. ``compared`` is True when the value
    is compared with a column (``cli = '…'``), the usual place for a
    placeholder."""

    def __init__(
        self,
        start: int,
        end: int,
        text: str,
        placeholder: Placeholder,
        *,
        compared: bool,
    ) -> None:
        self.__start = start
        self.__end = end
        self.__text = text
        self.__placeholder = placeholder
        self.__compared = compared

    @property
    def start(self) -> int:
        """Offset of the first character of the value."""
        return self.__start

    @property
    def end(self) -> int:
        """Offset just after the value."""
        return self.__end

    @property
    def text(self) -> str:
        """Value as written in the query (quotes included)."""
        return self.__text

    @property
    def placeholder(self) -> Placeholder:
        """Placeholder the value would become."""
        return self.__placeholder

    @property
    def compared(self) -> bool:
        """True when the value is compared with a column."""
        return self.__compared

    def __repr__(self) -> str:
        text = "ValueCandidate({!r}, {}, {}, {!r})"
        return text.format(
            self.__text, self.__start, self.__end, self.__placeholder.name
        )
