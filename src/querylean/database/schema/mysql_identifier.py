"""Quoting of MySQL identifiers."""

from __future__ import annotations


class MySqlIdentifier:
    """Builds identifiers that are safe to put in a statement."""

    @staticmethod
    def quote(name: str) -> str:
        """``name`` between backticks, with inner backticks doubled: any
        table name (spaces, reserved words, backticks) stays one
        identifier."""
        return "`{}`".format(name.replace("`", "``"))
