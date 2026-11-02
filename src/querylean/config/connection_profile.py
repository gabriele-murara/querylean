"""A saved connection."""

from __future__ import annotations

from querylean.config.connection_config import ConnectionConfig


class ConnectionProfile:
    """Saved connection: a stable identifier (also its file name) plus the
    connection settings. The password is never part of it."""

    def __init__(self, profile_id: str, config: ConnectionConfig) -> None:
        self.__profile_id = profile_id
        self.__config = config

    @property
    def profile_id(self) -> str:
        """Stable identifier (32 hex characters)."""
        return self.__profile_id

    @property
    def config(self) -> ConnectionConfig:
        """Connection settings."""
        return self.__config

    @config.setter
    def config(self, value: ConnectionConfig) -> None:
        self.__config = value

    @property
    def display_name(self) -> str:
        """Name shown in the connection list."""
        return self.__config.display_name()

    def __repr__(self) -> str:
        text = "ConnectionProfile({!r}, {!r})"
        return text.format(self.__profile_id, self.__config)
