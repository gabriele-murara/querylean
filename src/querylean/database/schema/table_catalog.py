"""Listing of the tables visible to the connected user."""

from __future__ import annotations

from typing import Any

from querylean.database.execution.query_executor import QueryExecutor
from querylean.database.schema.table_info import TableInfo
from querylean.log.log_manager import LogManager


class TableCatalog:
    """Lists tables and views of the current database.

    The listing runs through ``QueryExecutor``, so it is validated and
    bounded like a user query. ``SHOW FULL TABLES`` returns only what the
    account may access.
    """

    LIST_STATEMENT = "SHOW FULL TABLES"
    MAX_TABLES = 10000
    __VIEW_TYPES = ("VIEW", "SYSTEM VIEW")
    __log = LogManager.get_logger(__name__)

    def __init__(self, executor: QueryExecutor) -> None:
        self.__executor = executor

    @property
    def executor(self) -> QueryExecutor:
        """Executor running the listing."""
        return self.__executor

    def list_tables(self, timeout: int) -> list[TableInfo]:
        """Tables and views, in the server order (by name). Raises
        ``DatabaseError``."""
        result = self.__executor.execute(
            TableCatalog.LIST_STATEMENT, TableCatalog.MAX_TABLES, timeout
        )
        if result.truncated:
            self.__log.warning(
                "More than {} tables: the list is truncated",
                TableCatalog.MAX_TABLES,
            )
        return [TableCatalog.__table(row) for row in result.rows if row]

    @staticmethod
    def __table(row: tuple[Any, ...]) -> TableInfo:
        name = TableCatalog.__text(row[0])
        kind = TableCatalog.__text(row[1]) if len(row) > 1 else ""
        return TableInfo(name, kind.upper() in TableCatalog.__VIEW_TYPES)

    @staticmethod
    def __text(value: Any) -> str:
        if isinstance(value, bytes | bytearray):
            return bytes(value).decode("utf-8", errors="replace")
        return str(value)
