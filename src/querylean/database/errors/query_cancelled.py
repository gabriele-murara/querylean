"""Query interrupted by the user."""

from __future__ import annotations

from querylean.database.errors.database_error import DatabaseError


class QueryCancelled(DatabaseError):
    """The running query was interrupted on user request."""

    def __init__(
        self, message: str = "Esecuzione interrotta dall'utente."
    ) -> None:
        super().__init__(message, kind="cancelled")
