"""Tables and columns of the connected database, for the completion."""

from __future__ import annotations

from collections.abc import Mapping

from querylean.database.schema.column_info import ColumnInfo
from querylean.database.schema.table_info import TableInfo


class SchemaModel:
    """In-memory copy of the tables and columns read from the server.

    Lookups ignore case. ``columns_of`` returns None for a table whose
    columns have not been read yet (they can be requested on demand) and
    an empty tuple when they could not be read.
    """

    def __init__(self) -> None:
        self.__database = ""
        self.__tables: list[TableInfo] = []
        self.__by_name: dict[str, TableInfo] = {}
        self.__columns: dict[str, tuple[ColumnInfo, ...]] = {}

    @property
    def database(self) -> str:
        """Name of the current database."""
        return self.__database

    @database.setter
    def database(self, value: str) -> None:
        self.__database = value

    @property
    def tables(self) -> list[TableInfo]:
        """Tables and views, in the server order."""
        return list(self.__tables)

    def clear(self) -> None:
        """Forget everything (on disconnection)."""
        self.__database = ""
        self.__tables = []
        self.__by_name = {}
        self.__columns = {}

    def set_tables(self, tables: list[TableInfo]) -> None:
        """Replace the list of tables (known columns are kept)."""
        self.__tables = list(tables)
        self.__by_name = {t.name.casefold(): t for t in self.__tables}

    def table(self, name: str) -> TableInfo | None:
        """Table called ``name`` (case insensitive), if listed."""
        return self.__by_name.get(name.casefold())

    def columns_of(self, table: str) -> tuple[ColumnInfo, ...] | None:
        """Columns of ``table`` in their order; None when not read yet."""
        return self.__columns.get(table.casefold())

    def has_columns(self, table: str) -> bool:
        """True when the columns of ``table`` have been read (or failed)."""
        return table.casefold() in self.__columns

    def set_columns(self, table: str, columns: tuple[ColumnInfo, ...]) -> None:
        """Store the columns of ``table`` (empty when they cannot be
        read)."""
        self.__columns[table.casefold()] = tuple(columns)

    def set_all_columns(
        self, columns: Mapping[str, tuple[ColumnInfo, ...]]
    ) -> None:
        """Store the columns of many tables at once."""
        for table, table_columns in columns.items():
            self.set_columns(table, table_columns)
