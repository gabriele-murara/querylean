"""Listing of the columns of the tables of the current database."""

from __future__ import annotations

from typing import Any

from querylean.database.execution.query_executor import QueryExecutor
from querylean.database.schema.column_info import ColumnInfo
from querylean.database.schema.mysql_identifier import MySqlIdentifier
from querylean.database.schema.mysql_literal import MySqlLiteral
from querylean.log.log_manager import LogManager


class ColumnCatalog:
    """Reads column definitions through ``QueryExecutor``, so the
    statements are validated and bounded like user queries.

    ``list_all`` reads the whole database in one query (used by the
    autocompletion); ``list_for`` reads one table, for the tables that the
    first listing could not include.
    """

    MAX_COLUMNS = 10000
    ALL_STATEMENT = "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, "
    ALL_STATEMENT += "IS_NULLABLE, COLUMN_KEY, COLUMN_DEFAULT, EXTRA, "
    ALL_STATEMENT += "COLUMN_COMMENT FROM information_schema.COLUMNS "
    ALL_STATEMENT += "WHERE TABLE_SCHEMA = {} "
    ALL_STATEMENT += "ORDER BY TABLE_NAME, ORDINAL_POSITION"
    __CURRENT_DATABASE = "DATABASE()"
    TABLE_STATEMENT = "SHOW FULL COLUMNS FROM {}"
    __log = LogManager.get_logger(__name__)

    def __init__(self, executor: QueryExecutor) -> None:
        self.__executor = executor

    @property
    def executor(self) -> QueryExecutor:
        """Executor running the listings."""
        return self.__executor

    @staticmethod
    def all_statement(database: str = "") -> str:
        """Columns of every table of the default database, or of
        ``database``."""
        schema = (
            MySqlLiteral.quote(database)
            if database
            else ColumnCatalog.__CURRENT_DATABASE
        )
        return ColumnCatalog.ALL_STATEMENT.format(schema)

    @staticmethod
    def table_statement(table: str, database: str = "") -> str:
        """``SHOW FULL COLUMNS`` statement for ``table`` (of ``database``
        when given)."""
        name = MySqlIdentifier.quote(table)
        if database:
            name = "{}.{}".format(MySqlIdentifier.quote(database), name)
        return ColumnCatalog.TABLE_STATEMENT.format(name)

    def list_all(
        self, timeout: int, database: str = ""
    ) -> dict[str, tuple[ColumnInfo, ...]]:
        """Columns of every table of the default database (or of
        ``database``), by table name, in their order. When the listing is
        cut at ``MAX_COLUMNS`` the last (partial) table is left out. Raises
        ``DatabaseError``."""
        result = self.__executor.execute(
            ColumnCatalog.all_statement(database),
            ColumnCatalog.MAX_COLUMNS,
            timeout,
        )
        tables: dict[str, list[ColumnInfo]] = {}
        last = ""
        for row in result.rows:
            if len(row) < 8:
                continue
            last = ColumnCatalog.__text(row[0])
            tables.setdefault(last, []).append(
                ColumnInfo(
                    ColumnCatalog.__text(row[1]),
                    ColumnCatalog.__text(row[2]),
                    nullable=ColumnCatalog.__text(row[3]).upper() == "YES",
                    key=ColumnCatalog.__text(row[4]),
                    default=ColumnCatalog.__optional(row[5]),
                    extra=ColumnCatalog.__text(row[6]),
                    comment=ColumnCatalog.__text(row[7]),
                )
            )
        if result.truncated and last:
            self.__log.warning(
                "More than {} columns: some tables are read on demand",
                ColumnCatalog.MAX_COLUMNS,
            )
            tables.pop(last, None)
        return {name: tuple(columns) for name, columns in tables.items()}

    def list_for(
        self, table: str, timeout: int, database: str = ""
    ) -> tuple[ColumnInfo, ...]:
        """Columns of ``table`` (of ``database`` when given) in their order.
        Raises ``DatabaseError``."""
        result = self.__executor.execute(
            ColumnCatalog.table_statement(table, database),
            ColumnCatalog.MAX_COLUMNS,
            timeout,
        )
        names = [str(name).casefold() for name in result.columns]
        columns = []
        for row in result.rows:
            values = dict(zip(names, row, strict=False))
            name = values.get("field")
            if name is None:
                continue
            columns.append(
                ColumnInfo(
                    ColumnCatalog.__text(name),
                    ColumnCatalog.__text(values.get("type", "")),
                    nullable=ColumnCatalog.__text(
                        values.get("null", "")
                    ).upper()
                    == "YES",
                    key=ColumnCatalog.__text(values.get("key", "")),
                    default=ColumnCatalog.__optional(values.get("default")),
                    extra=ColumnCatalog.__text(values.get("extra", "")),
                    comment=ColumnCatalog.__text(values.get("comment", "")),
                )
            )
        return tuple(columns)

    @staticmethod
    def __optional(value: Any) -> str | None:
        return None if value is None else ColumnCatalog.__text(value)

    @staticmethod
    def __text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes | bytearray):
            return bytes(value).decode("utf-8", errors="replace")
        return str(value)
