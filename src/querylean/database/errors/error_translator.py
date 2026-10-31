"""Translation of driver errors into user-facing messages."""

from __future__ import annotations

import socket

from mysql.connector import errorcode
from mysql.connector import errors as mysql_errors

from querylean.database.errors.database_error import DatabaseError


class ErrorTranslator:
    """Maps mysql-connector exceptions to ``DatabaseError`` without leaking details."""

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
    def translate_connect_error(exc: BaseException, timeout: int) -> DatabaseError:
        """Error raised while opening a connection."""
        if isinstance(exc, socket.timeout | TimeoutError | mysql_errors.ConnectionTimeoutError):
            return ErrorTranslator.__connect_timeout(timeout)
        if isinstance(exc, mysql_errors.Error):
            errno = exc.errno
            text = str(exc).lower()
            if "timed out" in text or "timeout" in text:
                return ErrorTranslator.__connect_timeout(timeout)
            if errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return DatabaseError(
                    "Autenticazione fallita: verifica username e password.", kind="auth"
                )
            if errno in (errorcode.ER_BAD_DB_ERROR, errorcode.ER_DBACCESS_DENIED_ERROR):
                return DatabaseError(
                    "Database inesistente o non accessibile con questo utente: "
                    "verifica il nome del database e i privilegi dell'account.",
                    kind="database",
                )
            if errno in ErrorTranslator.__CONNECTION_ERRNOS:
                return ErrorTranslator.__unreachable()
            if errno == errorcode.ER_HOST_NOT_PRIVILEGED:
                return DatabaseError(
                    "Il server MySQL non consente connessioni da questo host per l'utente "
                    "indicato.",
                    kind="auth",
                )
            return DatabaseError(f"Connessione fallita (errore MySQL {errno}).", kind="connection")
        if isinstance(exc, OSError):
            return ErrorTranslator.__unreachable()
        return DatabaseError("Connessione fallita per un errore imprevisto. Vedi il log.")

    @staticmethod
    def translate_query_error(exc: BaseException) -> DatabaseError:
        """Error raised while executing a query or fetching its results."""
        if isinstance(exc, DatabaseError):
            return exc
        if not isinstance(exc, mysql_errors.Error):
            return DatabaseError(
                "Errore imprevisto durante il recupero dei risultati. Vedi il log."
            )
        errno = exc.errno
        msg = getattr(exc, "msg", None) or ""
        if errno == errorcode.ER_PARSE_ERROR:
            return DatabaseError(f"Errore di sintassi SQL: {msg}", kind="syntax")
        if errno in ErrorTranslator.__PRIVILEGE_ERRNOS:
            return DatabaseError(f"Accesso negato dal server: {msg}", kind="privileges")
        if errno == errorcode.ER_CANT_EXECUTE_IN_READ_ONLY_TRANSACTION:
            return DatabaseError(
                "Operazione rifiutata dal server: la sessione è in sola lettura.", kind="readonly"
            )
        if isinstance(exc, mysql_errors.ReadTimeoutError | mysql_errors.WriteTimeoutError):
            return DatabaseError(
                "Il server non risponde: la connessione è stata chiusa. Riconnettiti e riprova.",
                kind="connection_lost",
            )
        if errno in ErrorTranslator.__CONNECTION_ERRNOS or ErrorTranslator.is_connection_lost(exc):
            return DatabaseError(
                "La connessione al server MySQL è stata persa. Riconnettiti e riprova.",
                kind="connection_lost",
            )
        if errno is not None and msg:
            return DatabaseError(f"Errore MySQL {errno}: {msg}", kind="query")
        return DatabaseError("Errore durante l'esecuzione della query. Vedi il log.")

    @staticmethod
    def is_connection_lost(exc: BaseException) -> bool:
        """True when ``exc`` means the session is no longer usable."""
        if not isinstance(exc, mysql_errors.OperationalError | mysql_errors.InterfaceError):
            return False
        errno = getattr(exc, "errno", None)
        return errno is None or errno in ErrorTranslator.__CONNECTION_ERRNOS

    @staticmethod
    def __connect_timeout(timeout: int) -> DatabaseError:
        return DatabaseError(
            f"Timeout durante la connessione ({timeout} s): il server non ha risposto in tempo.",
            kind="timeout",
        )

    @staticmethod
    def __unreachable() -> DatabaseError:
        return DatabaseError(
            "Impossibile raggiungere il server MySQL: verifica host, porta e connettività di "
            "rete.",
            kind="unreachable",
        )
