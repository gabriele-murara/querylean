"""Kinds of autocompletion proposals."""

from __future__ import annotations

from enum import Enum


class CompletionKind(Enum):
    """Kind of a proposal, with the label shown when it has no detail."""

    COLUMN = "column"
    KEY_COLUMN = "key column"
    TABLE = "table"
    VIEW = "view"
    CTE = "query"
    ALIAS = "alias"
    KEYWORD = "keyword"
    FUNCTION = "function"
    DATABASE = "database"

    @property
    def label(self) -> str:
        """User-facing description."""
        return self.value

    @property
    def is_column(self) -> bool:
        """True for column proposals."""
        return self in (CompletionKind.COLUMN, CompletionKind.KEY_COLUMN)

    @property
    def is_table(self) -> bool:
        """True for tables, views and common table expressions."""
        return self in (
            CompletionKind.TABLE,
            CompletionKind.VIEW,
            CompletionKind.CTE,
        )
