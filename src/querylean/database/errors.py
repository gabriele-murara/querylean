"""Traduzione degli errori del driver in messaggi comprensibili per l'utente."""

from __future__ import annotations

import socket

from mysql.connector import errorcode
from mysql.connector import errors as mysql_errors


class DatabaseError(Exception):
    """Errore mostrabile all'utente: `message` non contiene dettagli sensibili."""

    def __init__(self, message: str, *, kind: str = "generic") -> None:
        super().__init__(message)
        self.message = message
        self.kind = kind


class QueryCancelled(DatabaseError):
    def __init__(self, message: str = "Esecuzione interrotta dall'utente.") -> None:
        super().__init__(message, kind="cancelled")


class QueryTimeout(DatabaseError):
    def __init__(self, seconds: int) -> None:
        super().__init__(
            f"Timeout: la query ha superato il limite di {seconds} secondi ed è stata interrotta. "
            "Puoi aumentare il timeout nella configurazione.",
            kind="timeout",
        )


_CONNECTION_ERRNOS = {
    errorcode.CR_CONN_HOST_ERROR,  # 2003
    errorcode.CR_UNKNOWN_HOST,  # 2005
    errorcode.CR_CONNECTION_ERROR,  # 2002
    errorcode.CR_SERVER_LOST,  # 2013
    errorcode.CR_SERVER_GONE_ERROR,  # 2006
}


def translate_connect_error(exc: BaseException, timeout: int) -> DatabaseError:
    """Errore durante l'apertura della connessione."""
    if isinstance(exc, socket.timeout | TimeoutError | mysql_errors.ConnectionTimeoutError):
        return _timeout_on_connect(timeout)
    if isinstance(exc, mysql_errors.Error):
        errno = exc.errno
        text = str(exc).lower()
        if "timed out" in text or "timeout" in text:
            return _timeout_on_connect(timeout)
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
        if errno in _CONNECTION_ERRNOS:
            return DatabaseError(
                "Impossibile raggiungere il server MySQL: verifica host, porta e "
                "connettività di rete.",
                kind="unreachable",
            )
        if errno == errorcode.ER_HOST_NOT_PRIVILEGED:
            return DatabaseError(
                "Il server MySQL non consente connessioni da questo host per l'utente indicato.",
                kind="auth",
            )
        return DatabaseError(
            f"Connessione fallita (errore MySQL {errno}).", kind="connection"
        )
    if isinstance(exc, OSError):
        return DatabaseError(
            "Impossibile raggiungere il server MySQL: verifica host, porta e connettività.",
            kind="unreachable",
        )
    return DatabaseError("Connessione fallita per un errore imprevisto. Vedi il log.")


def _timeout_on_connect(timeout: int) -> DatabaseError:
    return DatabaseError(
        f"Timeout durante la connessione ({timeout} s): il server non ha risposto in tempo.",
        kind="timeout",
    )


def is_connection_lost(exc: BaseException) -> bool:
    return isinstance(exc, mysql_errors.OperationalError | mysql_errors.InterfaceError) and (
        getattr(exc, "errno", None) in _CONNECTION_ERRNOS or getattr(exc, "errno", None) is None
    )


def translate_query_error(exc: BaseException) -> DatabaseError:
    """Errore durante l'esecuzione o il recupero dei risultati."""
    if isinstance(exc, DatabaseError):
        return exc
    if isinstance(exc, mysql_errors.Error):
        errno = exc.errno
        msg = getattr(exc, "msg", None) or ""
        if errno == errorcode.ER_PARSE_ERROR:
            return DatabaseError(f"Errore di sintassi SQL: {msg}", kind="syntax")
        if errno in (
            errorcode.ER_TABLEACCESS_DENIED_ERROR,
            errorcode.ER_COLUMNACCESS_DENIED_ERROR,
            errorcode.ER_DBACCESS_DENIED_ERROR,
            errorcode.ER_SPECIFIC_ACCESS_DENIED_ERROR,
        ):
            return DatabaseError(f"Accesso negato dal server: {msg}", kind="privileges")
        if errno == errorcode.ER_CANT_EXECUTE_IN_READ_ONLY_TRANSACTION:
            return DatabaseError(
                "Operazione rifiutata dal server: la sessione è in sola lettura.",
                kind="readonly",
            )
        if isinstance(exc, mysql_errors.ReadTimeoutError | mysql_errors.WriteTimeoutError):
            return DatabaseError(
                "Il server non risponde: la connessione è stata chiusa. Riconnettiti e riprova.",
                kind="connection_lost",
            )
        if errno in _CONNECTION_ERRNOS or is_connection_lost(exc):
            return DatabaseError(
                "La connessione al server MySQL è stata persa. Riconnettiti e riprova.",
                kind="connection_lost",
            )
        if errno is not None and msg:
            return DatabaseError(f"Errore MySQL {errno}: {msg}", kind="query")
        return DatabaseError("Errore durante l'esecuzione della query. Vedi il log.")
    return DatabaseError("Errore imprevisto durante il recupero dei risultati. Vedi il log.")
