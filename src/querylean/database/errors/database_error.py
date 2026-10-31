"""Base user-facing database error."""

from __future__ import annotations


class DatabaseError(Exception):
    """Error that can be shown to the user.

    ``message`` never contains sensitive data; ``kind`` classifies the error for the UI
    (e.g. ``auth``, ``timeout``, ``rejected``, ``connection_lost``).
    """

    def __init__(self, message: str, *, kind: str = "generic") -> None:
        super().__init__(message)
        self.__message = message
        self.__kind = kind

    @property
    def message(self) -> str:
        """User-facing message."""
        return self.__message

    @property
    def kind(self) -> str:
        """Error category."""
        return self.__kind
