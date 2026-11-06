"""Quoting of MySQL string literals."""

from __future__ import annotations


class MySqlLiteral:
    """Builds string literals that are safe to put in a statement.

    Sessions run without ``NO_BACKSLASH_ESCAPES`` (see ``ConnectionManager``),
    so backslashes are escaped as well as quotes.
    """

    @staticmethod
    def quote(value: str) -> str:
        """``value`` between single quotes, with ``\\`` and ``'``
        escaped."""
        escaped = value.replace("\\", "\\\\").replace("'", "''")
        return "'{}'".format(escaped)
