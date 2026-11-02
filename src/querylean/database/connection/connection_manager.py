"""Lifecycle of the application's single MySQL connection."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import mysql.connector

from querylean.config.connection_config import ConnectionConfig
from querylean.database.connection.connection_params import ConnectionParams
from querylean.database.errors.database_error import DatabaseError
from querylean.database.errors.error_translator import ErrorTranslator
from querylean.log.log_manager import LogManager


class ConnectionManager:
    """Opens, keeps and closes the connection.

    Not thread safe: it must be used by a single thread, except for
    ``kill_running_query`` which opens its own short-lived connection.
    """

    # Align the server lexer with the validator (backslash escapes in
    # strings).
    __SQL_MODE = "SET SESSION sql_mode = REPLACE(@@SESSION.sql_mode, "
    __SQL_MODE += "'NO_BACKSLASH_ESCAPES', '')"
    # Fixed internal statements run when every session is opened.
    __SESSION_SETUP = (
        # Server-side barrier on top of the account privileges.
        "SET SESSION TRANSACTION READ ONLY",
        __SQL_MODE,
    )
    # User-facing message shown when a query is requested without a session.
    NOT_CONNECTED = "Not connected: press “Connect” before running a "
    NOT_CONNECTED += "query."
    __log = LogManager.get_logger(__name__)

    def __init__(self, connector: Callable[..., Any] | None = None) -> None:
        self.__connector = connector or mysql.connector.connect
        self.__conn: Any = None
        self.__params: ConnectionParams | None = None
        self.__connection_id: int | None = None
        self.__lock = threading.Lock()  # guards __params and __connection_id

    # --------------------------------------------------------------- properties
    @property
    def connection_id(self) -> int | None:
        """Server id of the current session, if any."""
        with self.__lock:
            return self.__connection_id

    @property
    def is_connected(self) -> bool:
        """True after a successful ``connect`` and until ``disconnect``."""
        return self.__params is not None

    # ---------------------------------------------------------------- lifecycle
    def connect(self, config: ConnectionConfig, password: str) -> None:
        """Open a new session, closing any previous one. Raises
        ``DatabaseError``."""
        self.disconnect()
        params = ConnectionParams(config, password)
        conn = self.__open(params)
        with self.__lock:
            self.__conn = conn
            self.__params = params
            self.__connection_id = getattr(conn, "connection_id", None)
        self.__log.info("Connected (session id {})", self.__connection_id)

    def test_connection(self, config: ConnectionConfig, password: str) -> str:
        """Check reachability and credentials. Returns the server version."""
        conn = self.__open(ConnectionParams(config, password))
        try:
            version = (
                conn.get_server_info()
                if hasattr(conn, "get_server_info")
                else ""
            )
            return str(version or "")
        finally:
            ConnectionManager.__close_quietly(conn)

    def disconnect(self) -> None:
        """Close the session and forget the parameters."""
        with self.__lock:
            conn, self.__conn = self.__conn, None
            self.__params = None
            self.__connection_id = None
        if conn is not None:
            ConnectionManager.__close_quietly(conn)
            self.__log.info("Disconnected")

    def abort_session(self) -> None:
        """Drop the current session abruptly (e.g. with unread results) while
        keeping the parameters: the next ``ensure_connected`` opens a fresh
        session."""
        with self.__lock:
            conn, self.__conn = self.__conn, None
            self.__connection_id = None
        if conn is not None:
            ConnectionManager.__shutdown_quietly(conn)

    def ensure_connected(self) -> Any:
        """Return a live connection, reopening the session if it was dropped."""
        if self.__params is None:
            raise DatabaseError(
                ConnectionManager.NOT_CONNECTED, kind="not_connected"
            )
        if self.__conn is not None:
            try:
                if self.__conn.is_connected():
                    return self.__conn
            except Exception:
                pass
            ConnectionManager.__shutdown_quietly(self.__conn)
            self.__conn = None
        conn = self.__open(self.__params)
        with self.__lock:
            self.__conn = conn
            self.__connection_id = getattr(conn, "connection_id", None)
        self.__log.info("Session reopened (id {})", self.__connection_id)
        return conn

    def kill_running_query(self) -> bool:
        """Send ``KILL QUERY`` for the current session from a separate
        connection. Safe to call from a thread other than the one running the
        query."""
        with self.__lock:
            params, target = self.__params, self.__connection_id
        if params is None or target is None:
            return False
        try:
            conn = self.__connector(**params.to_connect_kwargs())
        except Exception as exc:
            self.__log.warning("Connection for KILL QUERY failed: {!r}", exc)
            return False
        try:
            cursor = conn.cursor()
            cursor.execute("KILL QUERY {}".format(int(target)))
            cursor.close()
            self.__log.info("KILL QUERY sent to session {}", target)
            return True
        except Exception as exc:
            self.__log.warning("KILL QUERY failed: {!r}", exc)
            return False
        finally:
            ConnectionManager.__close_quietly(conn)

    # ---------------------------------------------------------------- internals
    def __open(self, params: ConnectionParams) -> Any:
        LogManager.register_secret(params.password)
        cfg = params.config
        self.__log.info(
            "Connecting to {}:{}/{} as {}",
            cfg.host,
            cfg.port,
            cfg.database,
            cfg.username,
        )
        try:
            conn = self.__connector(**params.to_connect_kwargs())
        except Exception as exc:
            self.__log.warning("Connection failed: {!r}", exc)
            raise ErrorTranslator.translate_connect_error(
                exc, cfg.connect_timeout
            ) from None
        try:
            cursor = conn.cursor()
            try:
                for statement in ConnectionManager.__SESSION_SETUP:
                    cursor.execute(statement)
            finally:
                cursor.close()
        except Exception as exc:
            self.__log.warning("Session initialisation failed: {!r}", exc)
            ConnectionManager.__close_quietly(conn)
            msg = "Connection opened, but the session could not be made "
            msg += "read-only. See the log for details."
            raise DatabaseError(msg) from None
        return conn

    @staticmethod
    def __close_quietly(conn: Any) -> None:
        try:
            conn.close()
        except Exception:
            ConnectionManager.__shutdown_quietly(conn)

    @staticmethod
    def __shutdown_quietly(conn: Any) -> None:
        try:
            conn.shutdown()
        except Exception as exc:
            ConnectionManager.__log.debug(
                "Ignoring error while closing the connection: {!r}", exc
            )
