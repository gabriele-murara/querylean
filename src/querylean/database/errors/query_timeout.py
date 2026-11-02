"""Query exceeded its execution timeout."""

from __future__ import annotations

from querylean.database.errors.database_error import DatabaseError


class QueryTimeout(DatabaseError):
    """The query was stopped because it exceeded the configured timeout."""

    def __init__(self, seconds: int) -> None:
        msg = "Timeout: the query exceeded the {} second limit and was "
        msg += "stopped. You can raise the timeout in the connection "
        msg += "settings."
        super().__init__(msg.format(seconds), kind="timeout")
        self.__seconds = seconds

    @property
    def seconds(self) -> int:
        """Timeout that was exceeded, in seconds."""
        return self.__seconds
