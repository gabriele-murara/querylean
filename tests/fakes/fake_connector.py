"""Fake replacement for ``mysql.connector.connect``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fakes.fake_connection import FakeConnection


class FakeConnector:
    """Callable that creates ``FakeConnection`` objects and records them."""

    def __init__(self) -> None:
        self.__connections: list[FakeConnection] = []
        self.__error: BaseException | None = None
        self.__configure: Callable[[FakeConnection], None] | None = None

    @property
    def connections(self) -> list[FakeConnection]:
        """Connections created so far, in order."""
        return self.__connections

    @property
    def error(self) -> BaseException | None:
        """When set, every connection attempt raises it."""
        return self.__error

    @error.setter
    def error(self, value: BaseException | None) -> None:
        self.__error = value

    @property
    def configure(self) -> Callable[[FakeConnection], None] | None:
        """Hook applied to each new connection."""
        return self.__configure

    @configure.setter
    def configure(self, value: Callable[[FakeConnection], None] | None) -> None:
        self.__configure = value

    def __call__(self, **kwargs: Any) -> FakeConnection:
        if self.__error is not None:
            raise self.__error
        conn = FakeConnection(**kwargs)
        if self.__configure is not None:
            self.__configure(conn)
        self.__connections.append(conn)
        return conn
