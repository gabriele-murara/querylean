"""A named query saved for one connection."""

from __future__ import annotations

from typing import Any

from querylean.config.connection_config import ConnectionConfig


class QueryBookmark:
    """Query saved with a name for a target database.

    ``target`` identifies the database and account the query was saved for
    (``user@host:port/database``, ``/*`` with all the databases, see
    ``target_of``): a bookmark is offered
    and executed only on a session with the same target.
    """

    MAX_NAME_LENGTH = 100

    def __init__(self, name: str, sql: str, target: str) -> None:
        self.__name = name
        self.__sql = sql
        self.__target = target

    @property
    def name(self) -> str:
        """Name chosen by the user."""
        return self.__name

    @property
    def sql(self) -> str:
        """Text of the query."""
        return self.__sql

    @property
    def target(self) -> str:
        """``user@host:port/database`` the query was saved for."""
        return self.__target

    @staticmethod
    def target_of(config: ConnectionConfig) -> str:
        """Target of the sessions opened with ``config``."""
        return "{}@{}:{}/{}".format(
            config.username, config.host, config.port, config.scope_label()
        )

    @staticmethod
    def clean_name(name: str) -> str:
        """``name`` on one line, without surrounding spaces."""
        return " ".join(str(name).split())

    def same_name(self, name: str) -> bool:
        """True when ``name`` matches this name, ignoring case."""
        return (
            self.__name.casefold() == QueryBookmark.clean_name(name).casefold()
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializable representation."""
        return {"name": self.__name, "sql": self.__sql, "target": self.__target}

    @staticmethod
    def from_dict(data: object) -> QueryBookmark | None:
        """Bookmark from untrusted data; None when a field is missing, empty
        or of the wrong type."""
        if not isinstance(data, dict):
            return None
        values = [data.get(key) for key in ("name", "sql", "target")]
        if not all(isinstance(value, str) and value for value in values):
            return None
        name = QueryBookmark.clean_name(values[0])
        if not name or len(name) > QueryBookmark.MAX_NAME_LENGTH:
            return None
        return QueryBookmark(name, values[1], values[2])

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, QueryBookmark)
            and self.to_dict() == other.to_dict()
        )

    def __hash__(self) -> int:
        return hash((self.__name, self.__sql, self.__target))

    def __repr__(self) -> str:
        text = "QueryBookmark(name={!r}, target={!r})"
        return text.format(self.__name, self.__target)
