"""Abstract validation stage."""

from __future__ import annotations

from abc import ABC, abstractmethod

from querylean.database.validation.validation_context import ValidationContext


class ValidationStage(ABC):
    """One independent check of the read-only validator pipeline.

    Stages run in order on a shared ``ValidationContext``; a stage rejects the query by
    raising ``ValidationRejected`` with a user-facing message.
    """

    @property
    def name(self) -> str:
        """Stage name, used in log messages."""
        return type(self).__name__

    @abstractmethod
    def apply(self, context: ValidationContext) -> None:
        """Check ``context`` and enrich it for the next stages."""
