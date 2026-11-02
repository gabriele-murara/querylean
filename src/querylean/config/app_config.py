"""Whole application configuration."""

from __future__ import annotations

from querylean.config.ui_preferences import UiPreferences


class AppConfig:
    """Active connection identifier plus UI preferences. The connections
    themselves live in ``ConnectionStore``."""

    def __init__(
        self, active_connection: str = "", ui: UiPreferences | None = None
    ) -> None:
        self.__active_connection = active_connection
        self.__ui = ui or UiPreferences()

    @property
    def active_connection(self) -> str:
        """Identifier of the connection in use ("" when none)."""
        return self.__active_connection

    @active_connection.setter
    def active_connection(self, value: str) -> None:
        self.__active_connection = str(value)

    @property
    def ui(self) -> UiPreferences:
        """User interface preferences."""
        return self.__ui

    @ui.setter
    def ui(self, value: UiPreferences) -> None:
        self.__ui = value
