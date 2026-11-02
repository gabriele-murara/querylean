"""Connection states shown in the toolbar."""

from __future__ import annotations

from enum import Enum


class ConnectionState(Enum):
    """Connection state with its user-facing label and indicator color."""

    DISCONNECTED = ("Disconnected", "#757575")
    CONNECTING = ("Connecting…", "#ef6c00")
    CONNECTED = ("Connected", "#2e7d32")
    ERROR = ("Connection error", "#c62828")

    @property
    def label(self) -> str:
        """User-facing label."""
        return self.value[0]

    @property
    def color(self) -> str:
        """Indicator color."""
        return self.value[1]
