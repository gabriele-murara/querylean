"""Database operations executed outside the GUI thread."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal, Slot

from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.connection_config import ConnectionConfig
from querylean.database.connection.connection_manager import ConnectionManager
from querylean.database.errors.database_error import DatabaseError
from querylean.database.execution.query_executor import QueryExecutor
from querylean.database.schema.column_catalog import ColumnCatalog
from querylean.database.schema.database_catalog import DatabaseCatalog
from querylean.database.schema.table_catalog import TableCatalog
from querylean.log.log_manager import LogManager


class DbWorker(QObject):
    """Lives in a dedicated ``QThread``. Requests arrive as signals and are
    therefore processed one at a time, in order.

    In the schema requests an empty database means the default database
    of the session."""

    UNEXPECTED_ERROR = (
        "Unexpected error. The technical details were written to the log."
    )
    WRONG_TARGET = "The bookmarked query was not run: it was saved for "
    WRONG_TARGET += "another connection."
    WRONG_TARGET_KIND = "bookmark_target"

    # Requests (GUI -> worker)
    connect_requested = Signal(object, str)
    disconnect_requested = Signal()
    test_requested = Signal(object, str)
    query_requested = Signal(str, int, int)
    # Bookmarked query: sql, target it was saved for, row limit, timeout.
    bookmark_requested = Signal(str, str, int, int)
    databases_requested = Signal(int)  # timeout in seconds
    database_requested = Signal(str)  # make it the active database
    tables_requested = Signal(str, int)  # database, timeout in seconds
    columns_requested = Signal(str, int)  # all the columns of a database
    table_columns_requested = Signal(str, str, int)  # database, table

    # Responses (worker -> GUI)
    connected = Signal(object)  # AccountCheck of the session
    connect_failed = Signal(str)
    disconnected = Signal()
    test_finished = Signal(bool, str, object)  # ok, message, AccountCheck
    query_finished = Signal(object)
    query_failed = Signal(str, str)  # message, error kind
    databases_loaded = Signal(object)  # list[str]
    databases_failed = Signal(str)
    database_changed = Signal(str)
    database_failed = Signal(str, str)  # database, message
    tables_loaded = Signal(str, object)  # database, list[TableInfo]
    tables_failed = Signal(str, str)  # database, message
    columns_loaded = Signal(str, object)  # database, dict of columns
    columns_failed = Signal(str, str)  # database, message
    table_columns_loaded = Signal(str, str, object)  # database, table, cols
    table_columns_failed = Signal(str, str, str)  # database, table, message

    __log = LogManager.get_logger(__name__)

    def __init__(self, manager: ConnectionManager | None = None) -> None:
        super().__init__()
        self.__manager = manager or ConnectionManager()
        self.__executor = QueryExecutor(self.__manager)
        self.__catalog = TableCatalog(self.__executor)
        self.__columns = ColumnCatalog(self.__executor)
        self.__databases = DatabaseCatalog(self.__executor)
        self.connect_requested.connect(self.__on_connect)
        self.disconnect_requested.connect(self.__on_disconnect)
        self.test_requested.connect(self.__on_test)
        self.query_requested.connect(self.__on_query)
        self.bookmark_requested.connect(self.__on_bookmark)
        self.databases_requested.connect(self.__on_databases)
        self.database_requested.connect(self.__on_database)
        self.tables_requested.connect(self.__on_tables)
        self.columns_requested.connect(self.__on_columns)
        self.table_columns_requested.connect(self.__on_table_columns)

    @property
    def manager(self) -> ConnectionManager:
        """Connection manager owned by the worker."""
        return self.__manager

    @property
    def executor(self) -> QueryExecutor:
        """Query executor owned by the worker."""
        return self.__executor

    def cancel_query(self, reason: str = QueryExecutor.CANCEL_BY_USER) -> None:
        """Send KILL QUERY from a separate thread without blocking the GUI.
        Callable from any thread."""
        threading.Thread(
            target=self.__executor.cancel,
            args=(reason,),
            name="querylean-cancel",
            daemon=True,
        ).start()

    @Slot(object, str)
    def __on_connect(self, config: ConnectionConfig, password: str) -> None:
        try:
            self.__manager.connect(config, password)
        except DatabaseError as exc:
            self.connect_failed.emit(exc.message)
        except Exception:
            self.__log.exception("Unexpected error while connecting")
            self.connect_failed.emit(DbWorker.UNEXPECTED_ERROR)
        else:
            self.connected.emit(self.__manager.account_check)

    @Slot()
    def __on_disconnect(self) -> None:
        try:
            self.__manager.disconnect()
        finally:
            self.disconnected.emit()

    @Slot(object, str)
    def __on_test(self, config: ConnectionConfig, password: str) -> None:
        try:
            version, check = self.__manager.test_connection(config, password)
        except DatabaseError as exc:
            self.test_finished.emit(False, exc.message, None)
        except Exception:
            self.__log.exception(
                "Unexpected error while testing the connection"
            )
            self.test_finished.emit(False, DbWorker.UNEXPECTED_ERROR, None)
        else:
            suffix = " (MySQL server {})".format(version) if version else ""
            msg = "Connection succeeded{}.".format(suffix)
            if check.refused:
                text = "{} The account can change data in {}: accept "
                text += "these databases below to use them in caution mode "
                text += "(only read queries are allowed)."
                msg = text.format(msg, check.describe(check.refused))
            elif check.caution:
                text = "{} Caution mode: the account can change data in {}; "
                text += "only read queries are allowed."
                msg = text.format(msg, check.describe())
            self.test_finished.emit(True, msg, check)

    @Slot(str, int, int)
    def __on_query(self, sql: str, row_limit: int, timeout: int) -> None:
        try:
            result = self.__executor.execute(sql, row_limit, timeout)
        except DatabaseError as exc:
            self.query_failed.emit(exc.message, exc.kind)
        except Exception:
            self.__log.exception("Unexpected error while executing the query")
            self.query_failed.emit(DbWorker.UNEXPECTED_ERROR, "generic")
        else:
            self.query_finished.emit(result)

    @Slot(str, str, int, int)
    def __on_bookmark(
        self, sql: str, target: str, row_limit: int, timeout: int
    ) -> None:
        """Run a bookmarked query only on a session opened for the target it
        was saved for."""
        # Without a session the executor reports "not connected".
        config = self.__manager.config
        if config is not None and QueryBookmark.target_of(config) != target:
            self.__log.warning("Bookmarked query refused: different target")
            self.query_failed.emit(
                DbWorker.WRONG_TARGET, DbWorker.WRONG_TARGET_KIND
            )
            return
        self.__on_query(sql, row_limit, timeout)

    @Slot(int)
    def __on_databases(self, timeout: int) -> None:
        try:
            databases = self.__databases.list_databases(timeout)
        except DatabaseError as exc:
            self.databases_failed.emit(exc.message)
        except Exception:
            self.__log.exception("Unexpected error while listing databases")
            self.databases_failed.emit(DbWorker.UNEXPECTED_ERROR)
        else:
            self.databases_loaded.emit(databases)

    @Slot(str)
    def __on_database(self, database: str) -> None:
        try:
            self.__manager.use_database(database)
        except DatabaseError as exc:
            self.database_failed.emit(database, exc.message)
        except Exception:
            self.__log.exception("Unexpected error while changing database")
            self.database_failed.emit(database, DbWorker.UNEXPECTED_ERROR)
        else:
            self.database_changed.emit(database)

    @Slot(str, int)
    def __on_tables(self, database: str, timeout: int) -> None:
        try:
            tables = self.__catalog.list_tables(timeout, database)
        except DatabaseError as exc:
            self.tables_failed.emit(database, exc.message)
        except Exception:
            self.__log.exception("Unexpected error while listing the tables")
            self.tables_failed.emit(database, DbWorker.UNEXPECTED_ERROR)
        else:
            self.tables_loaded.emit(database, tables)

    @Slot(str, int)
    def __on_columns(self, database: str, timeout: int) -> None:
        try:
            columns = self.__columns.list_all(timeout, database)
        except DatabaseError as exc:
            self.columns_failed.emit(database, exc.message)
        except Exception:
            self.__log.exception("Unexpected error while listing the columns")
            self.columns_failed.emit(database, DbWorker.UNEXPECTED_ERROR)
        else:
            self.columns_loaded.emit(database, columns)

    @Slot(str, str, int)
    def __on_table_columns(
        self, database: str, table: str, timeout: int
    ) -> None:
        try:
            columns = self.__columns.list_for(table, timeout, database)
        except DatabaseError as exc:
            self.table_columns_failed.emit(database, table, exc.message)
        except Exception:
            self.__log.exception(
                "Unexpected error while listing the columns of a table"
            )
            self.table_columns_failed.emit(
                database, table, DbWorker.UNEXPECTED_ERROR
            )
        else:
            self.table_columns_loaded.emit(database, table, columns)
