"""Whole application configuration."""

from __future__ import annotations

from querylean.config.connection_config import ConnectionConfig
from querylean.config.ui_preferences import UiPreferences


class AppConfig:
    """Connection settings plus UI preferences."""

    def __init__(
        self,
        connection: ConnectionConfig | None = None,
        ui: UiPreferences | None = None,
    ) -> None:
        self.__connection = connection or ConnectionConfig()
        self.__ui = ui or UiPreferences()

    @property
    def connection(self) -> ConnectionConfig:
        """Connection settings."""
        return self.__connection

    @connection.setter
    def connection(self, value: ConnectionConfig) -> None:
        self.__connection = value

    @property
    def ui(self) -> UiPreferences:
        """User interface preferences."""
        return self.__ui

    @ui.setter
    def ui(self, value: UiPreferences) -> None:
        self.__ui = value
