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
from querylean.database.execution.driver_value import DriverValue
from querylean.database.privileges.account_check import AccountCheck
from querylean.database.privileges.account_privileges import AccountPrivileges
from querylean.database.privileges.grant_analyzer import GrantAnalyzer
from querylean.log.log_manager import LogManager


class ConnectionManager:
    """Opens, keeps and closes the connection.

    Not thread safe: it must be used by a single thread, except for
    ``kill_running_query`` which opens its own short-lived connection.
    """

    # Align the server lexer with the validator: backslash escapes in
    # strings, and "…" as a string, never an identifier (with ANSI_QUOTES
    # a backslash would not escape and text the validator reads as one
    # string could hide SQL). ANSI is removed too, since it implies
    # ANSI_QUOTES.
    __SQL_MODE = "SET SESSION sql_mode = REPLACE(REPLACE(REPLACE("
    __SQL_MODE += "@@SESSION.sql_mode, 'NO_BACKSLASH_ESCAPES', ''), "
    __SQL_MODE += "'ANSI_QUOTES', ''), 'ANSI', '')"
    __SQL_MODE_CHECK = "SELECT @@SESSION.sql_mode"
    # Modes the validator cannot follow: a session keeping one is closed.
    LEXER_MODES = frozenset({"NO_BACKSLASH_ESCAPES", "ANSI_QUOTES"})
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
    DATABASES_STATEMENT = "SHOW DATABASES"
    # Error kind of a refused account with privileges beyond reading.
    WRITE_ACCOUNT_KIND = "write_account"
    __SETUP_FAILED = "Connection opened, but the session could not be made "
    __SETUP_FAILED += "read-only. See the log for details."
    __NOT_CONFIRMED = "Connection opened, but the server did not confirm "
    __NOT_CONFIRMED += "that the session is read-only, so it was closed. "
    __NOT_CONFIRMED += "See the log for details."
    __LEXER_MISMATCH = "Connection opened, but the server keeps an "
    __LEXER_MISMATCH += "sql_mode that changes how quotes are read "
    __LEXER_MISMATCH += "(ANSI_QUOTES or NO_BACKSLASH_ESCAPES), so it was "
    __LEXER_MISMATCH += "closed. See the log for details."
    __WRITE_ACCOUNT = "Connection refused: the account can change data in "
    __WRITE_ACCOUNT += "{}. {} uses such databases only in caution mode: "
    __WRITE_ACCOUNT += "open Connections → Edit…, press “Test connection” "
    __WRITE_ACCOUNT += "and accept them."
    __DATABASES_FAILED = "Connection opened, but the list of databases "
    __DATABASES_FAILED += "could not be read, so their privileges cannot be "
    __DATABASES_FAILED += "checked. See the log for details."
    # User-facing message shown when a query is requested without a session.
    NOT_CONNECTED = "Not connected: press “Connect” before running a "
    NOT_CONNECTED += "query."
    __log = LogManager.get_logger(__name__)

    def __init__(self, connector: Callable[..., Any] | None = None) -> None:
        self.__connector = connector or mysql.connector.connect
        self.__conn: Any = None
        self.__params: ConnectionParams | None = None
        self.__connection_id: int | None = None
        self.__account_check: AccountCheck | None = None
        self.__lock = threading.Lock()  # guards __params and __connection_id

    # --------------------------------------------------------------- properties
    @property
    def connection_id(self) -> int | None:
        """Server id of the current session, if any."""
        with self.__lock:
            return self.__connection_id

    @property
    def account_check(self) -> AccountCheck | None:
        """Write access of the account to the databases of the current
        session, if any."""
        return self.__account_check

    @property
    def account_privileges(self) -> AccountPrivileges | None:
        """Privileges of the account of the current session, if any."""
        check = self.__account_check
        return None if check is None else check.privileges

    @property
    def active_database(self) -> str:
        """Default database of the current session (empty when none)."""
        with self.__lock:
            params = self.__params
        return "" if params is None else params.config.database

    @property
    def config(self) -> ConnectionConfig | None:
        """Copy of the settings of the current session (None when
        disconnected)."""
        with self.__lock:
            params = self.__params
        return None if params is None else params.config.copy()

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
        conn, check = self.__open(params, enforce=True)
        self.__account_check = check
        with self.__lock:
            self.__conn = conn
            self.__params = params
            self.__connection_id = getattr(conn, "connection_id", None)
        self.__log.info("Connected (session id {})", self.__connection_id)

    def test_connection(
        self, config: ConnectionConfig, password: str
    ) -> tuple[str, AccountCheck]:
        """Check reachability, credentials, the read-only session and the
        privileges like ``connect``, without refusing writable databases
        that are not accepted yet. Returns the server version and the check
        (with the databases to accept)."""
        conn, check = self.__open(
            ConnectionParams(config, password), enforce=False
        )
        try:
            version = ConnectionManager.__server_version(conn)
            return str(version or ""), check
        finally:
            ConnectionManager.__close_quietly(conn)

    def disconnect(self) -> None:
        """Close the session and forget the parameters."""
        with self.__lock:
            conn, self.__conn = self.__conn, None
            self.__params = None
            self.__connection_id = None
        self.__account_check = None
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
        conn, check = self.__open(self.__params, enforce=True)
        self.__account_check = check
        with self.__lock:
            self.__conn = conn
            self.__connection_id = getattr(conn, "connection_id", None)
        self.__log.info("Session reopened (id {})", self.__connection_id)
        return conn

    def use_database(self, database: str) -> None:
        """Make ``database`` the default database of the session (protocol
        command ``COM_INIT_DB``, not SQL); reconnections keep it. Raises
        ``DatabaseError``."""
        conn = self.ensure_connected()
        try:
            conn.cmd_init_db(database)
        except Exception as exc:
            self.__log.warning("Changing the database failed: {!r}", exc)
            raise ErrorTranslator.translate_query_error(exc) from None
        with self.__lock:
            if self.__params is not None:
                self.__params = self.__params.with_database(database)
        self.__log.info("Active database changed")

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
    def __open(
        self, params: ConnectionParams, *, enforce: bool
    ) -> tuple[Any, AccountCheck]:
        LogManager.register_secret(params.password)
        cfg = params.config
        self.__log.info(
            "Connecting to {}:{}/{} as {}",
            cfg.host,
            cfg.port,
            cfg.scope_label(),
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
            check = ConnectionManager.__check_account(conn, cfg, enforce)
        except BaseException:
            ConnectionManager.__close_quietly(conn)
            raise
        return conn, check

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
        if DriverValue.text(value).strip() != "1":
            ConnectionManager.__log.warning(
                "The server did not confirm a read-only session (value {!r})",
                value,
            )
            raise DatabaseError(ConnectionManager.__NOT_CONFIRMED) from None
        ConnectionManager.__check_sql_mode(conn)

    @staticmethod
    def __check_sql_mode(conn: Any) -> None:
        """Read back the session sql_mode: quoting must follow the rules of
        the validator (fail-closed when it cannot be read)."""
        try:
            rows = ConnectionManager.__fetch(
                conn, ConnectionManager.__SQL_MODE_CHECK
            )
            value = rows[0][0] if rows and rows[0] else None
            # NULL (or no row) cannot be verified.
            mode = None if value is None else DriverValue.text(value)
        except Exception as exc:
            ConnectionManager.__log.warning(
                "Could not read the session sql_mode: {!r}", exc
            )
            mode = None
        modes = (
            {item.strip().upper() for item in mode.split(",")}
            if mode is not None
            else None
        )
        if modes is None or modes & ConnectionManager.LEXER_MODES:
            ConnectionManager.__log.warning(
                "Session sql_mode not usable by the validator: {!r}", mode
            )
            raise DatabaseError(ConnectionManager.__LEXER_MISMATCH) from None

    @staticmethod
    def __check_account(
        conn: Any, config: ConnectionConfig, enforce: bool
    ) -> AccountCheck:
        """Read the account grants and find the databases of the connection
        it can change; with ``enforce``, refuse those not accepted in
        caution mode."""
        try:
            rows = ConnectionManager.__fetch(
                conn, ConnectionManager.GRANTS_STATEMENT
            )
            lines = [DriverValue.text(row[0]) for row in rows if row]
            privileges = GrantAnalyzer.analyze(lines)
        except Exception as exc:
            ConnectionManager.__log.warning(
                "Could not read the account grants: {!r}", exc
            )
            privileges = AccountPrivileges.unverified()
        databases = (
            ConnectionManager.__databases(conn)
            if config.all_databases
            else [config.database]
        )
        check = AccountCheck(privileges, databases, config.caution_databases)
        if not check.caution:
            ConnectionManager.__log.info(
                "Account privileges: read-only on the {} database(s)",
                len(databases),
            )
            return check
        # Only privilege names are logged: grant lines can contain password
        # hashes (MariaDB).
        ConnectionManager.__log.warning(
            "Writable databases: {} of {}; write privileges {}, verified {}",
            len(check.write_databases),
            len(databases),
            list(privileges.write_privileges),
            privileges.verified,
        )
        if not check.refused:
            ConnectionManager.__log.warning(
                "Caution mode: every writable database was accepted"
            )
            return check
        if not enforce:
            return check
        msg = ConnectionManager.__WRITE_ACCOUNT.format(
            check.describe(check.refused), AppInfo.DISPLAY_NAME
        )
        raise DatabaseError(msg, kind=ConnectionManager.WRITE_ACCOUNT_KIND)

    @staticmethod
    def __databases(conn: Any) -> list[str]:
        """Databases the account can access (``SHOW DATABASES``)."""
        try:
            rows = ConnectionManager.__fetch(
                conn, ConnectionManager.DATABASES_STATEMENT
            )
        except Exception as exc:
            ConnectionManager.__log.warning(
                "Could not list the databases: {!r}", exc
            )
            raise DatabaseError(ConnectionManager.__DATABASES_FAILED) from None
        # Names exactly as the server returns them (no stripping): grants
        # are matched against them.
        return [DriverValue.text(row[0]) for row in rows if row]

    @staticmethod
    def __server_version(conn: Any) -> str:
        """Server version: the ``server_info`` property (the
        ``get_server_info()`` method is deprecated in mysql-connector)."""
        version = getattr(conn, "server_info", None)
        if version is None and hasattr(conn, "get_server_info"):
            version = conn.get_server_info()
        return DriverValue.text(version)

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
