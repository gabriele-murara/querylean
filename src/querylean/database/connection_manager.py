"""Gestione dell'unica connessione MySQL dell'applicazione."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import mysql.connector
from mysql.connector.constants import ClientFlag

from querylean.config.config_manager import ConnectionConfig
from querylean.database.errors import DatabaseError, translate_connect_error
from querylean.utils.logging_config import redacting_filter

log = logging.getLogger(__name__)

SOCKET_TIMEOUT_GRACE = 30  # secondi oltre il timeout della query

# Istruzioni interne, fisse, eseguite all'apertura di ogni sessione.
_SESSION_SETUP = (
    # Barriera lato server aggiuntiva ai privilegi dell'account.
    "SET SESSION TRANSACTION READ ONLY",
    # Allinea il lexing del server a quello del validatore (escape con backslash).
    "SET SESSION sql_mode = REPLACE(@@SESSION.sql_mode, 'NO_BACKSLASH_ESCAPES', '')",
)


@dataclass(frozen=True)
class ConnectionParams:
    config: ConnectionConfig
    password: str

    def __repr__(self) -> str:  # evita che la password finisca nei log
        return f"ConnectionParams(config={self.config!r}, password='***')"


def build_connect_kwargs(params: ConnectionParams) -> dict[str, Any]:
    cfg = params.config
    return {
        "host": cfg.host,
        "port": cfg.port,
        "database": cfg.database,
        "user": cfg.username,
        "password": params.password,
        "connection_timeout": cfg.connect_timeout,
        # Ultima difesa se il server smette di rispondere (es. rete caduta) e KILL QUERY
        # non può raggiungerlo: il timeout normale è gestito da MAX_EXECUTION_TIME/watchdog.
        "read_timeout": cfg.query_timeout + SOCKET_TIMEOUT_GRACE,
        "write_timeout": cfg.query_timeout + SOCKET_TIMEOUT_GRACE,
        "autocommit": True,
        "use_pure": True,
        "charset": "utf8mb4",
        # Una sola istruzione per richiesta: niente multi-statement né LOCAL INFILE.
        "client_flags": [-ClientFlag.MULTI_STATEMENTS, -ClientFlag.MULTI_RESULTS,
                         -ClientFlag.LOCAL_FILES],
        "allow_local_infile": False,
        "get_warnings": False,
        "raise_on_warnings": False,
    }


Connector = Callable[..., Any]


class ConnectionManager:
    """Apre, mantiene e chiude la connessione. Non thread-safe: va usato da un solo thread,
    ad eccezione di `kill_running_query`, che apre una connessione separata."""

    def __init__(self, connector: Connector | None = None) -> None:
        self._connector = connector or mysql.connector.connect
        self._conn: Any = None
        self._params: ConnectionParams | None = None
        self._lock = threading.Lock()  # protegge _params e _connection_id
        self._connection_id: int | None = None

    # -- apertura / chiusura ------------------------------------------------
    def _open(self, params: ConnectionParams) -> Any:
        redacting_filter.register_secret(params.password)
        cfg = params.config
        log.info("Connessione a %s:%s/%s come %s", cfg.host, cfg.port, cfg.database,
                 cfg.username)
        try:
            conn = self._connector(**build_connect_kwargs(params))
        except Exception as exc:
            log.warning("Connessione fallita: %r", exc)
            raise translate_connect_error(exc, cfg.connect_timeout) from None
        try:
            cursor = conn.cursor()
            try:
                for statement in _SESSION_SETUP:
                    cursor.execute(statement)
            finally:
                cursor.close()
        except Exception as exc:
            log.warning("Inizializzazione della sessione fallita: %r", exc)
            _close_quietly(conn)
            raise DatabaseError(
                "Connessione aperta ma impossibile impostare la sessione in sola lettura. "
                "Vedi il log per i dettagli."
            ) from None
        return conn

    def connect(self, config: ConnectionConfig, password: str) -> None:
        self.disconnect()
        params = ConnectionParams(config.normalized(), password)
        conn = self._open(params)
        with self._lock:
            self._conn = conn
            self._params = params
            self._connection_id = getattr(conn, "connection_id", None)
        log.info("Connesso (id sessione %s)", self._connection_id)

    def test_connection(self, config: ConnectionConfig, password: str) -> str:
        """Verifica raggiungibilità e credenziali. Restituisce la versione del server."""
        conn = self._open(ConnectionParams(config.normalized(), password))
        try:
            version = conn.get_server_info() if hasattr(conn, "get_server_info") else ""
            return str(version or "")
        finally:
            _close_quietly(conn)

    def disconnect(self) -> None:
        with self._lock:
            conn, self._conn = self._conn, None
            self._params = None
            self._connection_id = None
        if conn is not None:
            _close_quietly(conn)
            log.info("Disconnesso")

    def abort_session(self) -> None:
        """Chiude bruscamente la sessione corrente (es. risultati non letti) mantenendo i
        parametri: la prossima `ensure_connected` riaprirà una nuova sessione."""
        with self._lock:
            conn, self._conn = self._conn, None
            self._connection_id = None
        if conn is not None:
            _shutdown_quietly(conn)

    # -- stato ----------------------------------------------------------------
    @property
    def has_params(self) -> bool:
        return self._params is not None

    @property
    def connection_id(self) -> int | None:
        with self._lock:
            return self._connection_id

    def is_connected(self) -> bool:
        return self._params is not None

    def ensure_connected(self) -> Any:
        """Restituisce una connessione attiva, riaprendola se la sessione è stata chiusa."""
        if self._params is None:
            raise DatabaseError("Non connesso: premi «Connetti» prima di eseguire una query.",
                                kind="not_connected")
        if self._conn is not None:
            try:
                if self._conn.is_connected():
                    return self._conn
            except Exception:
                pass
            _shutdown_quietly(self._conn)
            self._conn = None
        conn = self._open(self._params)
        with self._lock:
            self._conn = conn
            self._connection_id = getattr(conn, "connection_id", None)
        log.info("Sessione riaperta (id %s)", self._connection_id)
        return conn

    # -- interruzione ---------------------------------------------------------
    def kill_running_query(self) -> bool:
        """Invia KILL QUERY per la sessione corrente da una connessione separata.
        Sicuro da chiamare da un thread diverso da quello che esegue la query."""
        with self._lock:
            params, target = self._params, self._connection_id
        if params is None or target is None:
            return False
        try:
            conn = self._connector(**build_connect_kwargs(params))
        except Exception as exc:
            log.warning("Connessione per KILL QUERY fallita: %r", exc)
            return False
        try:
            cursor = conn.cursor()
            cursor.execute(f"KILL QUERY {int(target)}")
            cursor.close()
            log.info("KILL QUERY inviato alla sessione %s", target)
            return True
        except Exception as exc:
            log.warning("KILL QUERY fallito: %r", exc)
            return False
        finally:
            _close_quietly(conn)


def _close_quietly(conn: Any) -> None:
    try:
        conn.close()
    except Exception:
        _shutdown_quietly(conn)


def _shutdown_quietly(conn: Any) -> None:
    try:
        conn.shutdown()
    except Exception as exc:
        log.debug("Chiusura della connessione ignorata: %r", exc)
