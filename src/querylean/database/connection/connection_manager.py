"""Lifecycle of the application's single MySQL connection."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import mysql.connector

from querylean.app.app_info import AppInfo
from querylean.config.connection_config import ConnectionConfig
from querylean.database.connection.connection_params import ConnectionParams
from querylean.database.errors.database_error import DatabaseError
from querylean.database.errors.error_translator import ErrorTranslator
from querylean.database.privileges.account_privileges import AccountPrivileges
from querylean.database.privileges.grant_analyzer import GrantAnalyzer
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
    # Read back the transaction access mode: the first variable exists in
    # MySQL 5.7.20+ and MariaDB 11.1+, the second in older servers.
    __READ_ONLY_CHECKS = (
        "SELECT @@SESSION.transaction_read_only",
        "SELECT @@SESSION.tx_read_only",
    )
    GRANTS_STATEMENT = "SHOW GRANTS"
    # Error kind of a refused account with privileges beyond reading.
    WRITE_ACCOUNT_KIND = "write_account"
    __SETUP_FAILED = "Connection opened, but the session could not be made "
    __SETUP_FAILED += "read-only. See the log for details."
    __NOT_CONFIRMED = "Connection opened, but the server did not confirm "
    __NOT_CONFIRMED += "that the session is read-only, so it was closed. "
    __NOT_CONFIRMED += "See the log for details."
    __WRITE_ACCOUNT = "Connection refused: {}. {} accepts only accounts "
    __WRITE_ACCOUNT += "with read privileges (SELECT). To use this account "
    __WRITE_ACCOUNT += "anyway, enable “Caution mode” in the connection "
    __WRITE_ACCOUNT += "(Connections → Edit…)."
    # User-facing message shown when a query is requested without a session.
    NOT_CONNECTED = "Not connected: press “Connect” before running a "
    NOT_CONNECTED += "query."
    __log = LogManager.get_logger(__name__)

    def __init__(self, connector: Callable[..., Any] | None = None) -> None:
        self.__connector = connector or mysql.connector.connect
        self.__conn: Any = None
        self.__params: ConnectionParams | None = None
        self.__connection_id: int | None = None
        self.__account_privileges: AccountPrivileges | None = None
        self.__lock = threading.Lock()  # guards __params and __connection_id

    # --------------------------------------------------------------- properties
    @property
    def connection_id(self) -> int | None:
        """Server id of the current session, if any."""
        with self.__lock:
            return self.__connection_id

    @property
    def account_privileges(self) -> AccountPrivileges | None:
        """Privileges of the account of the current session, if any."""
        return self.__account_privileges

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
        conn, privileges = self.__open(params)
        self.__account_privileges = privileges
        with self.__lock:
            self.__conn = conn
            self.__params = params
            self.__connection_id = getattr(conn, "connection_id", None)
        self.__log.info("Connected (session id {})", self.__connection_id)

    def test_connection(
        self, config: ConnectionConfig, password: str
    ) -> tuple[str, AccountPrivileges]:
        """Check reachability, credentials, the read-only session and the
        account privileges, like ``connect``. Returns the server version and
        the privileges."""
        conn, privileges = self.__open(ConnectionParams(config, password))
        try:
            version = (
                conn.get_server_info()
                if hasattr(conn, "get_server_info")
                else ""
            )
            return str(version or ""), privileges
        finally:
            ConnectionManager.__close_quietly(conn)

    def disconnect(self) -> None:
        """Close the session and forget the parameters."""
        with self.__lock:
            conn, self.__conn = self.__conn, None
            self.__params = None
            self.__connection_id = None
        self.__account_privileges = None
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
        conn, privileges = self.__open(self.__params)
        self.__account_privileges = privileges
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
    def __open(self, params: ConnectionParams) -> tuple[Any, AccountPrivileges]:
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
            ConnectionManager.__prepare_session(conn)
            privileges = ConnectionManager.__check_account(conn, cfg)
        except BaseException:
            ConnectionManager.__close_quietly(conn)
            raise
        return conn, privileges

    @staticmethod
    def __prepare_session(conn: Any) -> None:
        """Make the session read-only and check that the server agrees."""
        try:
            cursor = conn.cursor()
            try:
                for statement in ConnectionManager.__SESSION_SETUP:
                    cursor.execute(statement)
            finally:
                cursor.close()
        except Exception as exc:
            ConnectionManager.__log.warning(
                "Session initialisation failed: {!r}", exc
            )
            raise DatabaseError(ConnectionManager.__SETUP_FAILED) from None
        value = None
        for statement in ConnectionManager.__READ_ONLY_CHECKS:
            try:
                rows = ConnectionManager.__fetch(conn, statement)
            except Exception as exc:
                ConnectionManager.__log.info(
                    "Read-only check {} failed: {!r}", statement, exc
                )
                continue
            value = rows[0][0] if rows and rows[0] else None
            break
        if ConnectionManager.__text(value) != "1":
            ConnectionManager.__log.warning(
                "The server did not confirm a read-only session (value {!r})",
                value,
            )
            raise DatabaseError(ConnectionManager.__NOT_CONFIRMED) from None

    @staticmethod
    def __check_account(
        conn: Any, config: ConnectionConfig
    ) -> AccountPrivileges:
        """Read the account grants; refuse an account that is not provably
        read-only unless the connection is in caution mode."""
        try:
            rows = ConnectionManager.__fetch(
                conn, ConnectionManager.GRANTS_STATEMENT
            )
            lines = [ConnectionManager.__text(row[0]) for row in rows if row]
            privileges = GrantAnalyzer.analyze(lines)
        except Exception as exc:
            ConnectionManager.__log.warning(
                "Could not read the account grants: {!r}", exc
            )
            privileges = AccountPrivileges.unverified()
        if privileges.read_only:
            ConnectionManager.__log.info("Account privileges: read-only")
            return privileges
        # Only privilege names are logged: grant lines can contain password
        # hashes (MariaDB).
        ConnectionManager.__log.warning(
            "Account not read-only: write privileges {}, verified {}",
            list(privileges.write_privileges),
            privileges.verified,
        )
        if config.caution_mode:
            ConnectionManager.__log.warning(
                "Caution mode: account with privileges beyond reading allowed"
            )
            return privileges
        msg = ConnectionManager.__WRITE_ACCOUNT.format(
            privileges.describe(), AppInfo.DISPLAY_NAME
        )
        raise DatabaseError(msg, kind=ConnectionManager.WRITE_ACCOUNT_KIND)

    @staticmethod
    def __fetch(conn: Any, statement: str) -> list[Any]:
        """Run a fixed internal statement and return all its rows."""
        cursor = conn.cursor()
        try:
            cursor.execute(statement)
            return list(cursor.fetchall())
        finally:
            cursor.close()

    @staticmethod
    def __text(value: object) -> str:
        """Driver value as text (some servers return bytes)."""
        if isinstance(value, (bytes, bytearray)):
            return bytes(value).decode("utf-8", errors="replace").strip()
        return "" if value is None else str(value).strip()

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
