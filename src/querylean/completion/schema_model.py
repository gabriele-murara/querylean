"""Databases, tables and columns of the session, for the side bar and the
completion."""

from __future__ import annotations

from collections.abc import Mapping

from querylean.database.schema.column_info import ColumnInfo
from querylean.database.schema.table_info import TableInfo


class SchemaModel:
    """In-memory copy of the databases, tables and columns read from the
    server.

    ``database`` is the active (default) database: lookups without a
    database use it. Lookups ignore case. ``columns_of`` returns None for
    a table whose columns have not been read yet (they can be requested on
    demand) and an empty tuple when they could not be read; ``tables_of``
    works the same way for the tables of a database.
    """

    def __init__(self) -> None:
        self.__database = ""
        self.__databases: list[str] = []
        self.__tables: dict[str, list[TableInfo]] = {}
        self.__by_name: dict[tuple[str, str], TableInfo] = {}
        self.__columns: dict[tuple[str, str], tuple[ColumnInfo, ...]] = {}

    @property
    def database(self) -> str:
        """Name of the active database (empty when none)."""
        return self.__database

    @database.setter
    def database(self, value: str) -> None:
        self.__database = value

    @property
    def databases(self) -> list[str]:
        """Databases of the session (all the accessible ones, or the
        configured one)."""
        return list(self.__databases)

    @property
    def tables(self) -> list[TableInfo]:
        """Tables and views of the active database, in the server order."""
        return list(self.tables_of(self.__database) or [])

    def clear(self) -> None:
        """Forget everything (on disconnection)."""
        self.__database = ""
        self.__databases = []
        self.__tables = {}
        self.__by_name = {}
        self.__columns = {}

    def set_databases(self, databases: list[str]) -> None:
        """Replace the list of databases (known tables are kept)."""
        self.__databases = list(databases)

    def find_database(self, name: str) -> str | None:
        """Database called ``name`` (case insensitive), if known."""
        wanted = name.casefold()
        for database in [self.__database, *self.__databases]:
            if database and database.casefold() == wanted:
                return database
        return None

    def tables_of(self, database: str | None = None) -> list[TableInfo] | None:
        """Tables of ``database`` (default: the active one); None when not
        read yet."""
        tables = self.__tables.get(self.__key(database))
        return None if tables is None else list(tables)

    def has_tables(self, database: str | None = None) -> bool:
        """True when the tables of ``database`` have been read."""
        return self.__key(database) in self.__tables

    def set_tables(
        self, tables: list[TableInfo], database: str | None = None
    ) -> None:
        """Replace the tables of ``database`` (known columns are kept)."""
        key = self.__key(database)
        self.__tables[key] = list(tables)
        self.__by_name = {
            k: v for k, v in self.__by_name.items() if k[0] != key
        }
        for table in tables:
            self.__by_name[(key, table.name.casefold())] = table

    def table(self, name: str, database: str | None = None) -> TableInfo | None:
        """Table called ``name`` (case insensitive) in ``database``."""
        return self.__by_name.get((self.__key(database), name.casefold()))

    def columns_of(
        self, table: str, database: str | None = None
    ) -> tuple[ColumnInfo, ...] | None:
        """Columns of ``table`` in their order; None when not read yet."""
        return self.__columns.get((self.__key(database), table.casefold()))

    def has_columns(self, table: str, database: str | None = None) -> bool:
        """True when the columns of ``table`` have been read (or failed)."""
        return (self.__key(database), table.casefold()) in self.__columns

    def set_columns(
        self,
        table: str,
        columns: tuple[ColumnInfo, ...],
        database: str | None = None,
    ) -> None:
        """Store the columns of ``table`` (empty when they cannot be
        read)."""
        key = (self.__key(database), table.casefold())
        self.__columns[key] = tuple(columns)

    def set_all_columns(
        self,
        columns: Mapping[str, tuple[ColumnInfo, ...]],
        database: str | None = None,
    ) -> None:
        """Store the columns of many tables of ``database`` at once."""
        for table, table_columns in columns.items():
            self.set_columns(table, table_columns, database)

    def __key(self, database: str | None) -> str:
        return (self.__database if database is None else database).casefold()
