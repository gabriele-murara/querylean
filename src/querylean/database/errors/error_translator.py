"""Translation of driver errors into user-facing messages."""

from __future__ import annotations

import socket

from mysql.connector import errorcode
from mysql.connector import errors as mysql_errors

from querylean.database.errors.database_error import DatabaseError


class ErrorTranslator:
    """Maps mysql-connector exceptions to ``DatabaseError`` without leaking
    details."""

    __CONNECTION_ERRNOS = frozenset(
        {
            errorcode.CR_CONN_HOST_ERROR,  # 2003
            errorcode.CR_UNKNOWN_HOST,  # 2005
            errorcode.CR_CONNECTION_ERROR,  # 2002
            errorcode.CR_SERVER_LOST,  # 2013
            errorcode.CR_SERVER_GONE_ERROR,  # 2006
        }
    )
    __PRIVILEGE_ERRNOS = frozenset(
        {
            errorcode.ER_TABLEACCESS_DENIED_ERROR,
            errorcode.ER_COLUMNACCESS_DENIED_ERROR,
            errorcode.ER_DBACCESS_DENIED_ERROR,
            errorcode.ER_SPECIFIC_ACCESS_DENIED_ERROR,
        }
    )

    @staticmethod
    def translate_connect_error(
        exc: BaseException, timeout: int
    ) -> DatabaseError:
        """Error raised while opening a connection."""
        if isinstance(
            exc,
            socket.timeout | TimeoutError | mysql_errors.ConnectionTimeoutError,
        ):
            return ErrorTranslator.__connect_timeout(timeout)
        if isinstance(exc, mysql_errors.Error):
            errno = exc.errno
            text = str(exc).lower()
            if "timed out" in text or "timeout" in text:
                return ErrorTranslator.__connect_timeout(timeout)
            if errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return DatabaseError(
                    "Authentication failed: check username and password.",
                    kind="auth",
                )
            if errno in (
                errorcode.ER_BAD_DB_ERROR,
                errorcode.ER_DBACCESS_DENIED_ERROR,
            ):
                msg = "The database does not exist or this user cannot "
                msg += "access it: check the database name and the account "
                msg += "privileges."
                return DatabaseError(msg, kind="database")
            if errno in ErrorTranslator.__CONNECTION_ERRNOS:
                return ErrorTranslator.__unreachable()
            if errno == errorcode.ER_HOST_NOT_PRIVILEGED:
                msg = "The MySQL server does not allow connections from this "
                msg += "host for the given user."
                return DatabaseError(msg, kind="auth")
            msg = "Connection failed (MySQL error {})."
            return DatabaseError(msg.format(errno), kind="connection")
        if isinstance(exc, OSError):
            return ErrorTranslator.__unreachable()
        return DatabaseError(
            "Connection failed because of an unexpected error. See the log."
        )

    @staticmethod
    def translate_query_error(exc: BaseException) -> DatabaseError:
        """Error raised while executing a query or fetching its results."""
        if isinstance(exc, DatabaseError):
            return exc
        if not isinstance(exc, mysql_errors.Error):
            msg = "Unexpected error while fetching the results. "
            msg += "See the log."
            return DatabaseError(msg)
        errno = exc.errno
        msg = getattr(exc, "msg", None) or ""
        if errno == errorcode.ER_PARSE_ERROR:
            text = "SQL syntax error: {}".format(msg)
            return DatabaseError(text, kind="syntax")
        if errno in ErrorTranslator.__PRIVILEGE_ERRNOS:
            text = "Access denied by the server: {}".format(msg)
            return DatabaseError(text, kind="privileges")
        if errno == errorcode.ER_CANT_EXECUTE_IN_READ_ONLY_TRANSACTION:
            text = "Operation refused by the server: the session is "
            text += "read-only."
            return DatabaseError(text, kind="readonly")
        if isinstance(
            exc, mysql_errors.ReadTimeoutError | mysql_errors.WriteTimeoutError
        ):
            text = "The server is not responding: the connection was closed. "
            text += "Reconnect and try again."
            return DatabaseError(text, kind="connection_lost")
        if (
            errno in ErrorTranslator.__CONNECTION_ERRNOS
            or ErrorTranslator.is_connection_lost(exc)
        ):
            text = "The connection to the MySQL server was lost. "
            text += "Reconnect and try again."
            return DatabaseError(text, kind="connection_lost")
        if errno is not None and msg:
            text = "MySQL error {}: {}".format(errno, msg)
            return DatabaseError(text, kind="query")
        return DatabaseError("Error while running the query. See the log.")

    @staticmethod
    def is_connection_lost(exc: BaseException) -> bool:
        """True when ``exc`` means the session is no longer usable."""
        if not isinstance(
            exc, mysql_errors.OperationalError | mysql_errors.InterfaceError
        ):
            return False
        errno = getattr(exc, "errno", None)
        return errno is None or errno in ErrorTranslator.__CONNECTION_ERRNOS

    @staticmethod
    def __connect_timeout(timeout: int) -> DatabaseError:
        msg = "Timeout while connecting ({} s): the server did not "
        msg += "answer in time."
        return DatabaseError(msg.format(timeout), kind="timeout")

    @staticmethod
    def __unreachable() -> DatabaseError:
        msg = "Cannot reach the MySQL server: check host, port and "
        msg += "network connectivity."
        return DatabaseError(msg, kind="unreachable")
