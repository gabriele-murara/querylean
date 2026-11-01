"""Query exceeded its execution timeout."""

from __future__ import annotations

from querylean.database.errors.database_error import DatabaseError


class QueryTimeout(DatabaseError):
    """The query was stopped because it exceeded the configured timeout."""

    def __init__(self, seconds: int) -> None:
        msg = "Timeout: la query ha superato il limite di {} secondi ed è "
        msg += "stata interrotta. Puoi aumentare il timeout nella "
        msg += "configurazione."
        super().__init__(msg.format(seconds), kind="timeout")
        self.__seconds = seconds

    @property
    def seconds(self) -> int:
        """Timeout that was exceeded, in seconds."""
        return self.__seconds
