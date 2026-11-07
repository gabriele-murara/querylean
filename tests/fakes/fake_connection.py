"""Fake driver connection."""

from __future__ import annotations

import itertools
import threading
from collections.abc import Callable
from typing import Any

from mysql.connector import errors as mysql_errors

from fakes.fake_cursor import FakeCursor


class FakeConnection:
    """In-memory connection whose behaviour is controlled by the test.

    The session checks of ``ConnectionManager`` are answered from
    ``session_variables``, ``grants`` and ``databases`` (a read-only session
    and account by default), without reaching ``handler``.
    """

    READ_ONLY_GRANTS = (
        "GRANT USAGE ON *.* TO `ro`@`%`",
        "GRANT SELECT ON `app`.* TO `ro`@`%`",
    )
    DATABASES = ("information_schema", "app")
    __ids = itertools.count(100)

    def __init__(self, **kwargs: Any) -> None:
        self.__kwargs = kwargs
        self.__connection_id = next(FakeConnection.__ids)
        self.__executed: list[str] = []
        self.__handler: Callable[[str], Any] | None = None
        self.__on_kill: Callable[[], None] | None = None
        self.__row_count = 3
        self.__fetched = 0
        self.__unread_result = False
        self.__open = True
        self.__closed_by: str | None = None
        self.__block_fetch: threading.Event | None = None
        self.__killed = False
        self.__session_variables: dict[str, Any] = {
            "transaction_read_only": 1,
            "tx_read_only": 1,
            "sql_mode": "ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES",
        }
        self.__grants: Any = list(FakeConnection.READ_ONLY_GRANTS)
        self.__databases: Any = list(FakeConnection.DATABASES)
        self.__init_db: list[str] = []

    @property
    def kwargs(self) -> dict[str, Any]:
        """Arguments received by the connector."""
        return self.__kwargs

    @property
    def connection_id(self) -> int:
        """Fake server session id."""
        return self.__connection_id

    @property
    def executed(self) -> list[str]:
        """Statements executed on this connection."""
        return self.__executed

    @property
    def handler(self) -> Callable[[str], Any] | None:
        """Returns ``(columns, rows)`` or an exception for each statement."""
        return self.__handler

    @handler.setter
    def handler(self, value: Callable[[str], Any] | None) -> None:
        self.__handler = value

    @property
    def on_kill(self) -> Callable[[], None] | None:
        """Called when this connection executes KILL QUERY."""
        return self.__on_kill

    @on_kill.setter
    def on_kill(self, value: Callable[[], None] | None) -> None:
        self.__on_kill = value

    @property
    def row_count(self) -> int:
        """Rows returned by the default handler."""
        return self.__row_count

    @row_count.setter
    def row_count(self, value: int) -> None:
        self.__row_count = value

    @property
    def fetched(self) -> int:
        """Rows fetched so far."""
        return self.__fetched

    @fetched.setter
    def fetched(self, value: int) -> None:
        self.__fetched = value

    @property
    def unread_result(self) -> bool:
        """True while a result set is not fully read."""
        return self.__unread_result

    @unread_result.setter
    def unread_result(self, value: bool) -> None:
        self.__unread_result = value

    @property
    def closed_by(self) -> str | None:
        """``"close"`` or ``"shutdown"`` once closed."""
        return self.__closed_by

    @property
    def block_fetch(self) -> threading.Event | None:
        """When set, ``fetchmany`` waits on this event."""
        return self.__block_fetch

    @block_fetch.setter
    def block_fetch(self, value: threading.Event | None) -> None:
        self.__block_fetch = value

    @property
    def killed(self) -> bool:
        """When true, a blocked fetch fails as interrupted."""
        return self.__killed

    @killed.setter
    def killed(self, value: bool) -> None:
        self.__killed = value

    @property
    def session_variables(self) -> dict[str, Any]:
        """Values (or exceptions) of ``SELECT @@SESSION.<name>``; a missing
        name fails like an unknown system variable."""
        return self.__session_variables

    @session_variables.setter
    def session_variables(self, value: dict[str, Any]) -> None:
        self.__session_variables = dict(value)

    @property
    def grants(self) -> Any:
        """Lines returned by ``SHOW GRANTS``, or an exception."""
        return self.__grants

    @grants.setter
    def grants(self, value: Any) -> None:
        self.__grants = value

    @property
    def databases(self) -> Any:
        """Names returned by ``SHOW DATABASES``, or an exception."""
        return self.__databases

    @databases.setter
    def databases(self, value: Any) -> None:
        self.__databases = value

    @property
    def init_db(self) -> list[str]:
        """Databases chosen with ``cmd_init_db``, in order."""
        return self.__init_db

    def cmd_init_db(self, database: str) -> None:
        """Change the default database like ``COM_INIT_DB``."""
        if isinstance(self.__databases, list) and (
            database not in self.__databases
        ):
            raise mysql_errors.ProgrammingError(
                msg="Unknown database '{}'".format(database), errno=1049
            )
        self.__init_db.append(database)

    def cursor(self) -> FakeCursor:
        """New cursor on this connection."""
        return FakeCursor(self)

    def is_connected(self) -> bool:
        """True until closed."""
        return self.__open

    def get_server_info(self) -> str:
        """Fake server version."""
        return "8.0.36"

    def close(self) -> None:
        """Graceful close; fails with pending results like the real driver."""
        if self.__unread_result:
            raise mysql_errors.InternalError("Unread result found")
        self.__open = False
        self.__closed_by = "close"

    def shutdown(self) -> None:
        """Abrupt close."""
        self.__open = False
        self.__closed_by = "shutdown"
