"""Proposals for one cursor position."""

from __future__ import annotations

from querylean.completion.completion_item import CompletionItem
from querylean.completion.statement_context import StatementContext


class CompletionResult:
    """Ranked proposals, the range they replace and the tables whose
    columns were needed but are not loaded yet."""

    def __init__(
        self,
        context: StatementContext,
        items: tuple[CompletionItem, ...] = (),
        missing_tables: tuple[str, ...] = (),
    ) -> None:
        self.__context = context
        self.__items = tuple(items)
        self.__missing_tables = tuple(missing_tables)

    @property
    def context(self) -> StatementContext:
        """Analysis of the cursor position."""
        return self.__context

    @property
    def items(self) -> tuple[CompletionItem, ...]:
        """Proposals, best first."""
        return self.__items

    @property
    def start(self) -> int:
        """Start of the replaced text."""
        return self.__context.start

    @property
    def end(self) -> int:
        """End of the replaced text."""
        return self.__context.end

    @property
    def prefix(self) -> str:
        """Typed part of the word."""
        return self.__context.prefix

    @property
    def missing_tables(self) -> tuple[str, ...]:
        """Tables whose columns should be loaded to complete better."""
        return self.__missing_tables

    def __repr__(self) -> str:
        text = "CompletionResult({!r}, {} items, missing={!r})"
        return text.format(
            self.__context, len(self.__items), self.__missing_tables
        )
