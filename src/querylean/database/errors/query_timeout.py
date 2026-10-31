"""Query exceeded its execution timeout."""

from __future__ import annotations

from querylean.database.errors.database_error import DatabaseError


class QueryTimeout(DatabaseError):
    """The query was stopped because it exceeded the configured timeout."""

    def __init__(self, seconds: int) -> None:
        super().__init__(
            f"Timeout: la query ha superato il limite di {seconds} secondi ed è stata "
            "interrotta. Puoi aumentare il timeout nella configurazione.",
            kind="timeout",
        )
        self.__seconds = seconds

    @property
    def seconds(self) -> int:
        """Timeout that was exceeded, in seconds."""
        return self.__seconds
