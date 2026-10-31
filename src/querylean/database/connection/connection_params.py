"""Immutable parameters used to open a connection."""

from __future__ import annotations

from typing import Any

from mysql.connector.constants import ClientFlag

from querylean.config.connection_config import ConnectionConfig


class ConnectionParams:
    """Configuration snapshot plus password, converted into driver arguments.

    The password is masked in ``repr`` so it cannot leak into logs.
    """

    SOCKET_TIMEOUT_GRACE = (
        30  # seconds added to the query timeout for socket I/O
    )

    def __init__(self, config: ConnectionConfig, password: str) -> None:
        self.__config = config.copy()
        self.__password = password

    @property
    def config(self) -> ConnectionConfig:
        """Copy of the connection configuration."""
        return self.__config.copy()

    @property
    def password(self) -> str:
        """Account password."""
        return self.__password

    def to_connect_kwargs(self) -> dict[str, Any]:
        """Arguments for ``mysql.connector.connect``."""
        cfg = self.__config
        socket_timeout = (
            cfg.query_timeout + ConnectionParams.SOCKET_TIMEOUT_GRACE
        )
        return {
            "host": cfg.host,
            "port": cfg.port,
            "database": cfg.database,
            "user": cfg.username,
            "password": self.__password,
            "connection_timeout": cfg.connect_timeout,
            # Last resort if the server stops answering (e.g. network down) and
            # KILL QUERY cannot reach it; normal timeouts are MAX_EXECUTION_TIME
            # and the watchdog.
            "read_timeout": socket_timeout,
            "write_timeout": socket_timeout,
            "autocommit": True,
            "use_pure": True,
            "charset": "utf8mb4",
            # One statement per request: no multi-statements, no LOCAL INFILE.
            "client_flags": [
                -ClientFlag.MULTI_STATEMENTS,
                -ClientFlag.MULTI_RESULTS,
                -ClientFlag.LOCAL_FILES,
            ],
            "allow_local_infile": False,
            "get_warnings": False,
            "raise_on_warnings": False,
        }

    def __repr__(self) -> str:
        return f"ConnectionParams(config={self.__config!r}, password='***')"
