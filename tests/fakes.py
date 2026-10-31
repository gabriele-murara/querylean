"""Doppioni del driver MySQL per i test unitari."""

from __future__ import annotations

import threading

from mysql.connector import errors as mysql_errors


class FakeCursor:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn
        self.description = None
        self._rows: list[tuple] = []
        self._pos = 0

    def execute(self, sql: str) -> None:
        self.conn.executed.append(sql)
        if sql.startswith(("SET ", "KILL ")):
            self.description = None
            return
        handler = self.conn.handler
        if handler is not None:
            outcome = handler(sql)
            if isinstance(outcome, BaseException):
                raise outcome
            columns, rows = outcome
        else:
            columns, rows = ["n"], [(i,) for i in range(self.conn.row_count)]
        self.description = [(c,) for c in columns] if columns else None
        self._rows = rows
        self._pos = 0
        self.conn.unread_result = bool(rows)

    def fetchmany(self, size: int = 1) -> list[tuple]:
        if self.conn.block_fetch is not None:
            self.conn.block_fetch.wait(5)
            if self.conn.killed:
                raise mysql_errors.DatabaseError(msg="Query execution was interrupted",
                                                 errno=1317)
        batch = self._rows[self._pos : self._pos + size]
        self._pos += len(batch)
        self.conn.fetched += len(batch)
        if self._pos >= len(self._rows):
            self.conn.unread_result = False
        return batch

    def close(self) -> None:
        if self.conn.unread_result:
            raise mysql_errors.InternalError("Unread result found")


class FakeConnection:
    _ids = iter(range(100, 10_000))

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.connection_id = next(self._ids)
        self.executed: list[str] = []
        self.handler = None
        self.row_count = 3
        self.fetched = 0
        self.unread_result = False
        self.open = True
        self.closed_by = None
        self.block_fetch: threading.Event | None = None
        self.killed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def is_connected(self) -> bool:
        return self.open

    def get_server_info(self) -> str:
        return "8.0.36"

    def close(self) -> None:
        if self.unread_result:
            raise mysql_errors.InternalError("Unread result found")
        self.open = False
        self.closed_by = "close"

    def shutdown(self) -> None:
        self.open = False
        self.closed_by = "shutdown"


class FakeConnector:
    """Sostituisce mysql.connector.connect; registra le connessioni aperte."""

    def __init__(self) -> None:
        self.connections: list[FakeConnection] = []
        self.error: BaseException | None = None
        self.configure = None  # callable(conn) applicato alle connessioni create

    def __call__(self, **kwargs) -> FakeConnection:
        if self.error is not None:
            raise self.error
        conn = FakeConnection(**kwargs)
        if self.configure:
            self.configure(conn)
        self.connections.append(conn)
        return conn
