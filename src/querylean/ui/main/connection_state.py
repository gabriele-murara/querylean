"""Connection states shown in the toolbar."""

from __future__ import annotations

from enum import Enum


class ConnectionState(Enum):
    """Connection state with its user-facing label and indicator color."""

    DISCONNECTED = ("Disconnesso", "#757575")
    CONNECTING = ("Connessione in corso…", "#ef6c00")
    CONNECTED = ("Connesso", "#2e7d32")
    ERROR = ("Errore di connessione", "#c62828")

    @property
    def label(self) -> str:
        """User-facing label."""
        return self.value[0]

    @property
    def color(self) -> str:
        """Indicator color."""
        return self.value[1]
