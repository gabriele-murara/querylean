"""Listing of the databases visible to the connected user."""

from __future__ import annotations

from typing import Any

from querylean.database.execution.query_executor import QueryExecutor
from querylean.log.log_manager import LogManager


class DatabaseCatalog:
    """Lists the databases through ``QueryExecutor`` (validated and bounded
    like a user query). ``SHOW DATABASES`` returns only those the account
    can access, unless it has the global SHOW DATABASES privilege."""

    LIST_STATEMENT = "SHOW DATABASES"
    MAX_DATABASES = 10000
    __log = LogManager.get_logger(__name__)

    def __init__(self, executor: QueryExecutor) -> None:
        self.__executor = executor

    @property
    def executor(self) -> QueryExecutor:
        """Executor running the listing."""
        return self.__executor

    def list_databases(self, timeout: int) -> list[str]:
        """Database names, in the server order. Raises ``DatabaseError``."""
        result = self.__executor.execute(
            DatabaseCatalog.LIST_STATEMENT,
            DatabaseCatalog.MAX_DATABASES,
            timeout,
        )
        if result.truncated:
            self.__log.warning(
                "More than {} databases: the list is truncated",
                DatabaseCatalog.MAX_DATABASES,
            )
        return [DatabaseCatalog.__text(row[0]) for row in result.rows if row]

    @staticmethod
    def __text(value: Any) -> str:
        if isinstance(value, bytes | bytearray):
            return bytes(value).decode("utf-8", errors="replace")
        return str(value)
