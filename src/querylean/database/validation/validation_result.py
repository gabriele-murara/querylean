"""Outcome of a validation."""

from __future__ import annotations


class ValidationResult:
    """Immutable validation outcome.

    When ``ok`` is true, ``statement`` is the original text to send to the
    server (without the trailing semicolon); otherwise ``reason`` is a
    user-facing message.
    """

    def __init__(self, ok: bool, statement: str = "", reason: str = "") -> None:
        self.__ok = ok
        self.__statement = statement
        self.__reason = reason

    @property
    def ok(self) -> bool:
        """True when the statement may be executed."""
        return self.__ok

    @property
    def statement(self) -> str:
        """Statement to execute (empty when rejected)."""
        return self.__statement

    @property
    def reason(self) -> str:
        """User-facing rejection reason (empty when accepted)."""
        return self.__reason

    @staticmethod
    def accept(statement: str) -> ValidationResult:
        """Successful result for ``statement``."""
        return ValidationResult(True, statement, "")

    @staticmethod
    def reject(reason: str) -> ValidationResult:
        """Failed result with a user-facing ``reason``."""
        return ValidationResult(False, "", reason)

    def __repr__(self) -> str:
        text = "ValidationResult(ok={}, reason={!r})"
        return text.format(self.__ok, self.__reason)
