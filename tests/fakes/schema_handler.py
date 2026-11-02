"""Fake server answers for a database with tables and a view."""

from __future__ import annotations

from typing import Any

from querylean.database.schema.column_catalog import ColumnCatalog
from querylean.database.schema.table_catalog import TableCatalog


class SchemaHandler:
    """``FakeConnection.handler`` that lists ``tables`` for
    ``SHOW FULL TABLES``, their ``columns`` for the column listings and
    returns one row for any other statement.

    ``tables`` holds ``(name, type)`` pairs; ``columns`` maps a table name
    to ``(name, type, null, key, default, extra, comment)`` rows.
    ``error``, when set, is returned (raised by the cursor) for the table
    listing, ``columns_error`` for both column listings.
    """

    SHOW_COLUMNS = [
        "Field",
        "Type",
        "Collation",
        "Null",
        "Key",
        "Default",
        "Extra",
        "Privileges",
        "Comment",
    ]

    def __init__(
        self,
        tables: list[tuple[Any, Any]] | None = None,
        columns: dict[str, list[tuple[Any, ...]]] | None = None,
    ) -> None:
        self.__tables = list(tables or [])
        self.__columns = dict(columns or {})
        self.__error: BaseException | None = None
        self.__columns_error: BaseException | None = None
        self.__statements: list[str] = []

    @property
    def tables(self) -> list[tuple[Any, Any]]:
        """Listed ``(name, type)`` rows (mutable)."""
        return self.__tables

    @property
    def columns(self) -> dict[str, list[tuple[Any, ...]]]:
        """Column rows by table (mutable)."""
        return self.__columns

    @property
    def statements(self) -> list[str]:
        """Statements received, in order."""
        return self.__statements

    @property
    def columns_error(self) -> BaseException | None:
        """Exception for the column listings, if any."""
        return self.__columns_error

    @columns_error.setter
    def columns_error(self, value: BaseException | None) -> None:
        self.__columns_error = value

    @property
    def error(self) -> BaseException | None:
        """Exception for the listing, if any."""
        return self.__error

    @error.setter
    def error(self, value: BaseException | None) -> None:
        self.__error = value

    def __call__(self, sql: str) -> Any:
        self.__statements.append(sql)
        if sql == ColumnCatalog.ALL_STATEMENT:
            if self.__columns_error is not None:
                return self.__columns_error
            rows = [
                (table, *row)
                for table in sorted(self.__columns)
                for row in self.__columns[table]
            ]
            return [
                "TABLE_NAME",
                "COLUMN_NAME",
                "COLUMN_TYPE",
                "NULL",
                "KEY",
                "DEFAULT",
                "EXTRA",
                "COMMENT",
            ], rows
        for table, rows in self.__columns.items():
            if sql == ColumnCatalog.table_statement(table):
                if self.__columns_error is not None:
                    return self.__columns_error
                return SchemaHandler.SHOW_COLUMNS, [
                    (r[0], r[1], None, r[2], r[3], r[4], r[5], "select", r[6])
                    for r in rows
                ]
        if sql == TableCatalog.LIST_STATEMENT:
            if self.__error is not None:
                return self.__error
            return ["Tables_in_app", "Table_type"], list(self.__tables)
        return ["n"], [(1,)]
