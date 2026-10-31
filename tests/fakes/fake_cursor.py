"""Fake driver cursor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mysql.connector import errors as mysql_errors

if TYPE_CHECKING:
    from fakes.fake_connection import FakeConnection


class FakeCursor:
    """Records executed statements; serves rows from its ``FakeConnection``."""

    def __init__(self, conn: FakeConnection) -> None:
        self.__conn = conn
        self.__description: list[tuple[str]] | None = None
        self.__rows: list[tuple] = []
        self.__pos = 0

    @property
    def description(self) -> list[tuple[str]] | None:
        """Column descriptions of the last result set."""
        return self.__description

    def execute(self, sql: str) -> None:
        """Run ``sql`` through the connection handler or the default result."""
        conn = self.__conn
        conn.executed.append(sql)
        if sql.startswith(("SET ", "KILL ")):
            self.__description = None
            if sql.startswith("KILL ") and conn.on_kill is not None:
                conn.on_kill()
            return
        if conn.handler is not None:
            outcome = conn.handler(sql)
            if isinstance(outcome, BaseException):
                raise outcome
            columns, rows = outcome
        else:
            columns, rows = ["n"], [(i,) for i in range(conn.row_count)]
        self.__description = [(c,) for c in columns] if columns else None
        self.__rows = rows
        self.__pos = 0
        conn.unread_result = bool(rows)

    def fetchmany(self, size: int = 1) -> list[tuple]:
        """Return up to ``size`` rows; may block on the connection gate."""
        conn = self.__conn
        if conn.block_fetch is not None:
            conn.block_fetch.wait(5)
            if conn.killed:
                raise mysql_errors.DatabaseError(
                    msg="Query execution was interrupted", errno=1317
                )
        batch = self.__rows[self.__pos : self.__pos + size]
        self.__pos += len(batch)
        conn.fetched += len(batch)
        if self.__pos >= len(self.__rows):
            conn.unread_result = False
        return batch

    def close(self) -> None:
        """Fail like the real driver when results are still pending."""
        if self.__conn.unread_result:
            raise mysql_errors.InternalError("Unread result found")
