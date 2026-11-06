"""A table or view, with the preview queries built for it."""

from __future__ import annotations

import re

from querylean.database.schema.mysql_identifier import MySqlIdentifier


class TableInfo:
    """Immutable name and kind of a table listed by ``SHOW FULL TABLES``,
    with the preview queries prepared by the side bar."""

    __QUOTED = re.compile(r"`((?:[^`]|``)*)`")

    def __init__(
        self, name: str, is_view: bool = False, database: str = ""
    ) -> None:
        self.__name = name
        self.__is_view = is_view
        self.__database = database

    @property
    def name(self) -> str:
        """Table name as returned by the server."""
        return self.__name

    @property
    def is_view(self) -> bool:
        """True for views (``VIEW``, ``SYSTEM VIEW``)."""
        return self.__is_view

    @property
    def database(self) -> str:
        """Database of the table when listed from a named database (empty
        for the default database of the session): statements then qualify
        the table (`` `db`.`name` ``)."""
        return self.__database

    @property
    def reference(self) -> str:
        """The table as written in statements: `` `name` `` or
        `` `db`.`name` ``."""
        name = MySqlIdentifier.quote(self.__name)
        if not self.__database:
            return name
        return "{}.{}".format(MySqlIdentifier.quote(self.__database), name)

    @property
    def select_statement(self) -> str:
        """Preview query of the table: ``SELECT * FROM `name` LIMIT 1;``."""
        msg = "SELECT * FROM {} LIMIT 1;"
        return msg.format(self.reference)

    def column_statement(self, column: str) -> str:
        """Preview of a column: ``SELECT `column` FROM `name` LIMIT 1;``."""
        return self.columns_statement([column])

    def columns_statement(self, columns: list[str]) -> str:
        """Preview of some columns: ``SELECT `a`, `b` FROM `name`
        LIMIT 1;`` (``SELECT *`` without columns)."""
        if not columns:
            return self.select_statement
        names = ", ".join(MySqlIdentifier.quote(c) for c in columns)
        msg = "SELECT {} FROM {} LIMIT 1;"
        return msg.format(names, self.reference)

    def selected_columns(self, statement: str) -> list[str] | None:
        """Columns of ``statement`` when it is a preview of this table
        written by ``select_statement``/``columns_statement`` (an empty list
        for ``SELECT *``); None for any other text."""
        text = statement.strip()
        prefix = "SELECT "
        suffix = " FROM {} LIMIT 1;".format(self.reference)
        if not text.startswith(prefix) or not text.endswith(suffix):
            return None
        body = text[len(prefix) : len(text) - len(suffix)]
        if body == "*":
            return []
        names: list[str] = []
        i = 0
        while True:
            match = TableInfo.__QUOTED.match(body, i)
            if match is None:
                return None
            names.append(match.group(1).replace("``", "`"))
            i = match.end()
            if i == len(body):
                return names
            if not body.startswith(", ", i):
                return None
            i += 2

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, TableInfo)
            and self.__name == other.name
            and self.__is_view == other.is_view
            and self.__database == other.database
        )

    def __hash__(self) -> int:
        return hash((self.__name, self.__is_view, self.__database))

    def __repr__(self) -> str:
        text = "TableInfo({!r}, is_view={}, database={!r})"
        return text.format(self.__name, self.__is_view, self.__database)
