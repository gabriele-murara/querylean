"""Listing of the tables visible to the connected user."""

from __future__ import annotations

from typing import Any

from querylean.database.execution.driver_value import DriverValue
from querylean.database.execution.query_executor import QueryExecutor
from querylean.database.schema.mysql_identifier import MySqlIdentifier
from querylean.database.schema.table_info import TableInfo
from querylean.log.log_manager import LogManager


class TableCatalog:
    """Lists tables and views of the default database of the session, or
    of a named database.

    The listing runs through ``QueryExecutor``, so it is validated and
    bounded like a user query. ``SHOW FULL TABLES`` returns only what the
    account may access.
    """

    LIST_STATEMENT = "SHOW FULL TABLES"
    LIST_FROM_STATEMENT = "SHOW FULL TABLES FROM {}"
    MAX_TABLES = 10000
    __VIEW_TYPES = ("VIEW", "SYSTEM VIEW")
    __log = LogManager.get_logger(__name__)

    def __init__(self, executor: QueryExecutor) -> None:
        self.__executor = executor

    @property
    def executor(self) -> QueryExecutor:
        """Executor running the listing."""
        return self.__executor

    @staticmethod
    def list_statement(database: str = "") -> str:
        """Listing of the default database, or of ``database``."""
        if not database:
            return TableCatalog.LIST_STATEMENT
        return TableCatalog.LIST_FROM_STATEMENT.format(
            MySqlIdentifier.quote(database)
        )

    def list_tables(self, timeout: int, database: str = "") -> list[TableInfo]:
        """Tables and views of the default database, or of ``database``
        (then each ``TableInfo`` is qualified with it), in the server order
        (by name). Raises ``DatabaseError``."""
        result = self.__executor.execute(
            TableCatalog.list_statement(database),
            TableCatalog.MAX_TABLES,
            timeout,
        )
        if result.truncated:
            self.__log.warning(
                "More than {} tables: the list is truncated",
                TableCatalog.MAX_TABLES,
            )
        return [
            TableCatalog.__table(row, database) for row in result.rows if row
        ]

    @staticmethod
    def __table(row: tuple[Any, ...], database: str) -> TableInfo:
        name = DriverValue.text(row[0])
        kind = DriverValue.text(row[1]) if len(row) > 1 else ""
        return TableInfo(
            name, kind.upper() in TableCatalog.__VIEW_TYPES, database
        )
