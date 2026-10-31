"""Result of an executed query."""

from __future__ import annotations

from typing import Any


class QueryResult:
    """Immutable result: column names, fetched rows and execution metadata."""

    def __init__(
        self,
        statement: str,
        columns: list[str],
        rows: list[tuple[Any, ...]],
        truncated: bool,
        row_limit: int,
        elapsed: float,
    ) -> None:
        self.__statement = statement
        self.__columns = list(columns)
        self.__rows = rows
        self.__truncated = truncated
        self.__row_limit = row_limit
        self.__elapsed = elapsed

    @property
    def statement(self) -> str:
        """Executed statement."""
        return self.__statement

    @property
    def columns(self) -> list[str]:
        """Column names (empty when the statement returned no result set)."""
        return list(self.__columns)

    @property
    def rows(self) -> list[tuple[Any, ...]]:
        """Fetched rows, at most ``row_limit``."""
        return self.__rows

    @property
    def truncated(self) -> bool:
        """True when more rows were available than ``row_limit``."""
        return self.__truncated

    @property
    def row_limit(self) -> int:
        """Row limit applied while fetching."""
        return self.__row_limit

    @property
    def elapsed(self) -> float:
        """Execution plus fetch time, in seconds."""
        return self.__elapsed
