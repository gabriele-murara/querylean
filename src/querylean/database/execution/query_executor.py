"""Execution of a single read query with a row limit and timeouts."""

from __future__ import annotations

import threading
import time
from typing import Any

from mysql.connector import errorcode
from mysql.connector import errors as mysql_errors

from querylean.database.connection.connection_manager import ConnectionManager
from querylean.database.errors.database_error import DatabaseError
from querylean.database.errors.error_translator import ErrorTranslator
from querylean.database.errors.query_cancelled import QueryCancelled
from querylean.database.errors.query_timeout import QueryTimeout
from querylean.database.execution.query_result import QueryResult
from querylean.database.validation.read_only_validator import ReadOnlyValidator
from querylean.log.log_manager import LogManager


class QueryExecutor:
    """Runs queries on the ``ConnectionManager`` session.

    ``execute`` must be called from the database thread; ``cancel`` may be called from
    any thread and interrupts the running query with ``KILL QUERY`` on a separate
    connection.
    """

    CANCEL_BY_USER = "user"
    CANCEL_BY_TIMEOUT = "timeout"

    __FETCH_BATCH = 500
    # Error returned by MySQL when MAX_EXECUTION_TIME is exceeded.
    __ER_QUERY_TIMEOUT = getattr(errorcode, "ER_QUERY_TIMEOUT", 3024)
    __log = LogManager.get_logger(__name__)

    def __init__(
        self, manager: ConnectionManager, validator: ReadOnlyValidator | None = None
    ) -> None:
        self.__manager = manager
        self.__validator = validator or ReadOnlyValidator()
        self.__cancel_reason: str | None = None
        self.__running = threading.Event()
        self.__session_timeout: tuple[int, int] | None = None  # (connection id, ms)

    @property
    def manager(self) -> ConnectionManager:
        """Connection manager used for execution."""
        return self.__manager

    @property
    def validator(self) -> ReadOnlyValidator:
        """Validator applied before every execution."""
        return self.__validator

    @property
    def running(self) -> bool:
        """True while a query is executing."""
        return self.__running.is_set()

    def cancel(self, reason: str = CANCEL_BY_USER) -> bool:
        """Request the interruption of the running query.

        Blocks for at most the connection timeout: call it outside the GUI thread.
        """
        if not self.__running.is_set():
            return False
        self.__cancel_reason = reason
        return self.__manager.kill_running_query()

    def execute(self, sql: str, row_limit: int, timeout: int) -> QueryResult:
        """Validate and execute ``sql``. Raises ``DatabaseError``."""
        validation = self.__validator.validate(sql)
        if not validation.ok:
            raise DatabaseError(validation.reason, kind="rejected")
        statement = validation.statement

        conn = self.__manager.ensure_connected()
        self.__cancel_reason = None
        self.__running.set()
        started = time.monotonic()
        cursor = None
        try:
            self.__apply_server_timeout(conn, timeout)
            cursor = conn.cursor()  # unbuffered: rows are read only on demand
            cursor.execute(statement)
            columns = [str(col[0]) for col in (cursor.description or [])]
            rows: list[tuple[Any, ...]] = []
            truncated = False
            if columns:
                rows, truncated = QueryExecutor.__fetch_limited(cursor, row_limit)
            elapsed = time.monotonic() - started

            if truncated:
                # Do not download the rest of the result set: drop the session, it is
                # reopened transparently for the next query.
                cursor = None
                self.__manager.abort_session()
            self.__log.info(
                "Query executed: %d rows%s in %.3f s",
                len(rows), " (truncated)" if truncated else "", elapsed,
            )
            return QueryResult(statement, columns, rows, truncated, row_limit, elapsed)
        except Exception as exc:
            self.__log.info("Execution failed: %r", exc)
            raise self.__translate(exc, timeout, conn) from None
        finally:
            self.__running.clear()
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    self.__manager.abort_session()

    # ------------------------------------------------------------------ internals
    def __apply_server_timeout(self, conn: Any, timeout: int) -> None:
        """Set MAX_EXECUTION_TIME (applies to SELECT) only when it changes."""
        ms = int(timeout) * 1000
        key = (self.__manager.connection_id or 0, ms)
        if self.__session_timeout == key:
            return
        cursor = conn.cursor()
        try:
            cursor.execute(f"SET SESSION MAX_EXECUTION_TIME = {ms}")
        except mysql_errors.Error as exc:
            # E.g. MariaDB or MySQL < 5.7.8: the client-side watchdog still applies.
            self.__log.warning("MAX_EXECUTION_TIME not supported: %r", exc)
        finally:
            cursor.close()
        self.__session_timeout = key

    def __translate(self, exc: BaseException, timeout: int, conn: Any) -> DatabaseError:
        reason = self.__cancel_reason
        errno = getattr(exc, "errno", None)
        if errno == QueryExecutor.__ER_QUERY_TIMEOUT:
            result: DatabaseError = QueryTimeout(timeout)
        elif errno == errorcode.ER_QUERY_INTERRUPTED or reason is not None:
            if reason == QueryExecutor.CANCEL_BY_TIMEOUT:
                result = QueryTimeout(timeout)
            else:
                result = QueryCancelled()
        else:
            result = ErrorTranslator.translate_query_error(exc)

        # After an error in the middle of a fetch the session may hold pending results:
        # start again from a clean session.
        if (
            result.kind == "connection_lost"
            or ErrorTranslator.is_connection_lost(exc)
            or getattr(conn, "unread_result", False)
            or reason
        ):
            self.__manager.abort_session()
        return result

    @staticmethod
    def __fetch_limited(cursor: Any, row_limit: int) -> tuple[list[tuple[Any, ...]], bool]:
        """Read at most ``row_limit`` rows (plus one, to know whether more exist)."""
        rows: list[tuple[Any, ...]] = []
        wanted = row_limit + 1
        while len(rows) < wanted:
            batch = cursor.fetchmany(min(QueryExecutor.__FETCH_BATCH, wanted - len(rows)))
            if not batch:
                break
            rows.extend(batch)
        return rows[:row_limit], len(rows) > row_limit
