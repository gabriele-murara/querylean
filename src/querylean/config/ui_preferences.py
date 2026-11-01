"""User interface preferences persisted between sessions."""

from __future__ import annotations

from typing import Any


class UiPreferences:
    """Window geometry and splitter states, stored as base64 strings."""

    __FIELDS = ("window_geometry", "splitter_state", "sidebar_state")

    def __init__(
        self,
        window_geometry: str = "",
        splitter_state: str = "",
        sidebar_state: str = "",
    ) -> None:
        self.__window_geometry = window_geometry
        self.__splitter_state = splitter_state
        self.__sidebar_state = sidebar_state

    @property
    def window_geometry(self) -> str:
        """Base64 of ``QWidget.saveGeometry()``."""
        return self.__window_geometry

    @window_geometry.setter
    def window_geometry(self, value: str) -> None:
        self.__window_geometry = str(value)

    @property
    def splitter_state(self) -> str:
        """Base64 of ``QSplitter.saveState()``."""
        return self.__splitter_state

    @splitter_state.setter
    def splitter_state(self, value: str) -> None:
        self.__splitter_state = str(value)

    @property
    def sidebar_state(self) -> str:
        """Base64 of the state of the splitter between the table side bar
        and the rest of the window."""
        return self.__sidebar_state

    @sidebar_state.setter
    def sidebar_state(self, value: str) -> None:
        self.__sidebar_state = str(value)

    def to_dict(self) -> dict[str, Any]:
        """Serializable representation."""
        return {
            "window_geometry": self.__window_geometry,
            "splitter_state": self.__splitter_state,
            "sidebar_state": self.__sidebar_state,
        }

    @staticmethod
    def from_dict(data: object) -> UiPreferences:
        """Build preferences from untrusted data, ignoring non-string values."""
        prefs = UiPreferences()
        if isinstance(data, dict):
            for name in UiPreferences.__FIELDS:
                if isinstance(data.get(name), str):
                    setattr(prefs, name, data[name])
        return prefs

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, UiPreferences)
            and self.to_dict() == other.to_dict()
        )

    def __hash__(self) -> int:
        return hash(tuple(self.to_dict().items()))
