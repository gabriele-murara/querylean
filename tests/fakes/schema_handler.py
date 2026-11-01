"""Fake server answers for a database with tables and a view."""

from __future__ import annotations

from typing import Any

from querylean.database.schema.table_catalog import TableCatalog


class SchemaHandler:
    """``FakeConnection.handler`` that lists ``tables`` for
    ``SHOW FULL TABLES`` and returns one row for any other statement.

    ``tables`` holds ``(name, type)`` pairs; ``error``, when set, is
    returned (raised by the cursor) for the listing.
    """

    def __init__(self, tables: list[tuple[Any, Any]] | None = None) -> None:
        self.__tables = list(tables or [])
        self.__error: BaseException | None = None

    @property
    def tables(self) -> list[tuple[Any, Any]]:
        """Listed ``(name, type)`` rows (mutable)."""
        return self.__tables

    @property
    def error(self) -> BaseException | None:
        """Exception for the listing, if any."""
        return self.__error

    @error.setter
    def error(self, value: BaseException | None) -> None:
        self.__error = value

    def __call__(self, sql: str) -> Any:
        if sql == TableCatalog.LIST_STATEMENT:
            if self.__error is not None:
                return self.__error
            return ["Tables_in_app", "Table_type"], list(self.__tables)
        return ["n"], [(1,)]
