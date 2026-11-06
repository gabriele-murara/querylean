"""Listing of the columns of the tables of a database."""

from __future__ import annotations

from querylean.database.execution.driver_value import DriverValue
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
            last = DriverValue.text(row[0])
            tables.setdefault(last, []).append(
                ColumnInfo(
                    DriverValue.text(row[1]),
                    DriverValue.text(row[2]),
                    nullable=DriverValue.text(row[3]).upper() == "YES",
                    key=DriverValue.text(row[4]),
                    default=DriverValue.optional_text(row[5]),
                    extra=DriverValue.text(row[6]),
                    comment=DriverValue.text(row[7]),
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
                    DriverValue.text(name),
                    DriverValue.text(values.get("type", "")),
                    nullable=DriverValue.text(values.get("null", "")).upper()
                    == "YES",
                    key=DriverValue.text(values.get("key", "")),
                    default=DriverValue.optional_text(values.get("default")),
                    extra=DriverValue.text(values.get("extra", "")),
                    comment=DriverValue.text(values.get("comment", "")),
                )
            )
        return tuple(columns)
