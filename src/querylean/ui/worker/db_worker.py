"""Database operations executed outside the GUI thread."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal, Slot

from querylean.config.connection_config import ConnectionConfig
from querylean.database.connection.connection_manager import ConnectionManager
from querylean.database.errors.database_error import DatabaseError
from querylean.database.execution.query_executor import QueryExecutor
from querylean.database.schema.table_catalog import TableCatalog
from querylean.log.log_manager import LogManager


class DbWorker(QObject):
    """Lives in a dedicated ``QThread``. Requests arrive as signals and are
    therefore processed one at a time, in order."""

    UNEXPECTED_ERROR = (
        "Unexpected error. The technical details were written to the log."
    )

    # Requests (GUI -> worker)
    connect_requested = Signal(object, str)
    disconnect_requested = Signal()
    test_requested = Signal(object, str)
    query_requested = Signal(str, int, int)
    tables_requested = Signal(int)  # timeout in seconds

    # Responses (worker -> GUI)
    connected = Signal(object)  # AccountPrivileges of the account
    connect_failed = Signal(str)
    disconnected = Signal()
    test_finished = Signal(bool, str)
    query_finished = Signal(object)
    query_failed = Signal(str, str)  # message, error kind
    tables_loaded = Signal(object)  # list[TableInfo]
    tables_failed = Signal(str)

    __log = LogManager.get_logger(__name__)

    def __init__(self, manager: ConnectionManager | None = None) -> None:
        super().__init__()
        self.__manager = manager or ConnectionManager()
        self.__executor = QueryExecutor(self.__manager)
        self.__catalog = TableCatalog(self.__executor)
        self.connect_requested.connect(self.__on_connect)
        self.disconnect_requested.connect(self.__on_disconnect)
        self.test_requested.connect(self.__on_test)
        self.query_requested.connect(self.__on_query)
        self.tables_requested.connect(self.__on_tables)

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
            self.connected.emit(self.__manager.account_privileges)

    @Slot()
    def __on_disconnect(self) -> None:
        try:
            self.__manager.disconnect()
        finally:
            self.disconnected.emit()

    @Slot(object, str)
    def __on_test(self, config: ConnectionConfig, password: str) -> None:
        try:
            version, privileges = self.__manager.test_connection(
                config, password
            )
        except DatabaseError as exc:
            self.test_finished.emit(False, exc.message)
        except Exception:
            self.__log.exception(
                "Unexpected error while testing the connection"
            )
            self.test_finished.emit(False, DbWorker.UNEXPECTED_ERROR)
        else:
            suffix = " (MySQL server {})".format(version) if version else ""
            msg = "Connection succeeded{}.".format(suffix)
            if not privileges.read_only:
                caution = "{} Caution mode: {}; only read queries are "
                caution += "allowed."
                msg = caution.format(msg, privileges.describe())
            self.test_finished.emit(True, msg)

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

    @Slot(int)
    def __on_tables(self, timeout: int) -> None:
        try:
            tables = self.__catalog.list_tables(timeout)
        except DatabaseError as exc:
            self.tables_failed.emit(exc.message)
        except Exception:
            self.__log.exception("Unexpected error while listing the tables")
            self.tables_failed.emit(DbWorker.UNEXPECTED_ERROR)
        else:
            self.tables_loaded.emit(tables)
