"""Invalid mask or placeholder value."""

from __future__ import annotations


class MaskError(Exception):
    """A mask cannot be parsed or compiled; the message is user facing."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.__message = message

    @property
    def message(self) -> str:
        """User-facing description of the problem."""
        return self.__message
