"""Owner of the database thread."""

from __future__ import annotations

from PySide6.QtCore import QThread

from querylean.database.connection.connection_manager import ConnectionManager
from querylean.database.execution.query_executor import QueryExecutor
from querylean.log.log_manager import LogManager
from querylean.ui.worker.db_worker import DbWorker


class DbThread:
    """Creates the ``QThread``, moves a ``DbWorker`` into it and stops it
    cleanly."""

    __DEFAULT_SHUTDOWN_MS = 5000
    __LAST_RESORT_WAIT_MS = 1000
    __log = LogManager.get_logger(__name__)

    def __init__(self, manager: ConnectionManager | None = None) -> None:
        self.__thread = QThread()
        self.__thread.setObjectName("querylean-db")
        self.__worker = DbWorker(manager)
        self.__worker.moveToThread(self.__thread)
        self.__thread.start()

    @property
    def thread(self) -> QThread:
        """Thread running the worker."""
        return self.__thread

    @property
    def worker(self) -> DbWorker:
        """Worker processing database requests."""
        return self.__worker

    def shutdown(self, timeout_ms: int = __DEFAULT_SHUTDOWN_MS) -> bool:
        """Interrupt any running query, stop the thread and close the
        connection."""
        if self.__worker.executor.running:
            self.__worker.executor.cancel(QueryExecutor.CANCEL_BY_USER)
        self.__thread.quit()
        finished = bool(self.__thread.wait(timeout_ms))
        if finished:
            # the thread is stopped: safe access
            self.__worker.manager.disconnect()
        else:
            self.__log.warning(
                "Database thread did not stop within %d ms", timeout_ms
            )
            self.__worker.manager.abort_session()
            finished = bool(self.__thread.wait(DbThread.__LAST_RESORT_WAIT_MS))
        return finished
