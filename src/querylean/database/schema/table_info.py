"""A table (or view) of the current database."""

from __future__ import annotations

from querylean.database.schema.mysql_identifier import MySqlIdentifier


class TableInfo:
    """Immutable name and kind of a table listed by ``SHOW FULL TABLES``."""

    def __init__(self, name: str, is_view: bool = False) -> None:
        self.__name = name
        self.__is_view = is_view

    @property
    def name(self) -> str:
        """Table name as returned by the server."""
        return self.__name

    @property
    def is_view(self) -> bool:
        """True for views (``VIEW``, ``SYSTEM VIEW``)."""
        return self.__is_view

    @property
    def select_statement(self) -> str:
        """Preview query of the table: ``SELECT * FROM `name` LIMIT 1;``."""
        msg = "SELECT * FROM {} LIMIT 1;"
        return msg.format(MySqlIdentifier.quote(self.__name))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, TableInfo)
            and self.__name == other.name
            and self.__is_view == other.is_view
        )

    def __hash__(self) -> int:
        return hash((self.__name, self.__is_view))

    def __repr__(self) -> str:
        return "TableInfo({!r}, is_view={})".format(self.__name, self.__is_view)
