"""Builds and ranks the autocompletion proposals."""

from __future__ import annotations

import re

from querylean.completion.completion_item import CompletionItem
from querylean.completion.completion_kind import CompletionKind
from querylean.completion.completion_result import CompletionResult
from querylean.completion.schema_model import SchemaModel
from querylean.completion.sql_vocabulary import SqlVocabulary
from querylean.completion.statement_analyzer import StatementAnalyzer
from querylean.completion.statement_context import StatementContext
from querylean.completion.table_reference import TableReference
from querylean.database.schema.column_info import ColumnInfo


class CompletionEngine:
    """Proposals for a cursor position, from the statement context and the
    schema of the connected database.

    Matching ignores case: names that start with the typed text come
    first, then names with a word (after ``_``) that starts with it, then,
    for tables and columns, names that contain it. Within the same match
    quality the order depends on the context (columns of the tables in
    the statement before keywords in a WHERE, tables after FROM…).
    """

    MAX_ITEMS = 300
    # Shortest typed text that also matches inside names.
    MIN_CONTAINS = 2
    # Keywords that are values or end an expression: no space after them.
    __NO_SPACE = frozenset(
        {
            "NULL",
            "TRUE",
            "FALSE",
            "CURRENT_DATE",
            "CURRENT_TIME",
            "CURRENT_TIMESTAMP",
            "END",
            "ASC",
            "DESC",
            "IS NULL",
            "IS NOT NULL",
            "WITH ROLLUP",
        }
    )
    __WORD_BREAK = re.compile(r"[_\s]+")

    def __init__(self, schema: SchemaModel) -> None:
        self.__schema = schema

    @property
    def schema(self) -> SchemaModel:
        """Tables and columns used for the proposals."""
        return self.__schema

    def complete(self, text: str, position: int) -> CompletionResult:
        """Ranked proposals for the cursor at ``position`` in ``text``."""
        context = StatementAnalyzer.analyze(text, position)
        missing: list[str] = []
        groups = self.__candidates(context, missing)
        items = CompletionEngine.__rank(context.prefix, groups)
        return CompletionResult(context, items, tuple(missing))

    # ------------------------------------------------------------ candidates
    def __candidates(
        self, context: StatementContext, missing: list[str]
    ) -> list[tuple[int, list[CompletionItem]]]:
        """Proposals grouped by priority (lower first)."""
        kind = context.kind
        typed = bool(context.prefix)
        if kind == StatementContext.NONE:
            return []
        if kind == StatementContext.STATEMENT_START:
            return [
                (0, self.__keywords(context, SqlVocabulary.STATEMENT_KEYWORDS))
            ]
        if kind == StatementContext.SHOW:
            return [
                (
                    0,
                    self.__keywords(
                        context, SqlVocabulary.SHOW_KEYWORDS, checked=False
                    ),
                )
            ]
        if kind == StatementContext.TABLE_NAME:
            return [(0, self.__tables(context))]
        if kind == StatementContext.AFTER_TABLE:
            return [
                (
                    0,
                    self.__keywords(
                        context, SqlVocabulary.AFTER_TABLE_KEYWORDS
                    ),
                )
            ]
        if kind == StatementContext.QUALIFIED:
            return [(0, self.__qualified(context, missing))]
        in_scope = self.__scope_columns(context, missing)
        names = self.__scope_names(context)
        groups: list[tuple[int, list[CompletionItem]]] = []
        if kind == StatementContext.AFTER_OPERAND:
            groups.append(
                (
                    0,
                    self.__keywords(
                        context, SqlVocabulary.AFTER_OPERAND_KEYWORDS
                    ),
                )
            )
            if typed:
                groups += [(1, in_scope), (2, names)]
            return groups
        if kind == StatementContext.SUBQUERY:
            groups.append(
                (0, self.__keywords(context, SqlVocabulary.SELECT_KEYWORDS))
            )
        groups += [(1, in_scope), (2, names)]
        no_scope = not any(r.table for r in context.references)
        if no_scope and len(context.prefix) >= CompletionEngine.MIN_CONTAINS:
            groups.append((3, self.__all_columns(context)))
        if typed or no_scope:
            groups.append((4, self.__functions(context)))
            groups.append(
                (
                    4,
                    self.__keywords(context, SqlVocabulary.EXPRESSION_KEYWORDS),
                )
            )
        if typed:
            groups.append((5, self.__tables(context)))
        return groups

    def __qualified(
        self, context: StatementContext, missing: list[str]
    ) -> list[CompletionItem]:
        """Columns of the table (or alias) before the dot, or the tables
        of the database before the dot."""
        qualifier = context.qualifier
        database = self.__schema.database.casefold()
        name = qualifier[-1]
        if len(qualifier) >= 2 and qualifier[-2].casefold() != database:
            return []
        if context.expects_table:
            if name.casefold() == database:
                return self.__tables(context, ctes=False)
            return []
        table: str | None = None
        for reference in context.references:
            if reference.matches(name):
                if reference.table is None:
                    return []  # derived table: columns unknown
                table = reference.table
                break
        if table is None:
            if any(cte.casefold() == name.casefold() for cte in context.ctes):
                return []
            if self.__schema.table(name) is not None:
                table = name
            elif len(qualifier) == 1 and name.casefold() == database:
                return self.__tables(context, ctes=False)
            else:
                return []
        columns = self.__columns(table, missing)
        return [
            self.__column_item(context, column, table, None)
            for column in columns
        ]

    def __scope_columns(
        self, context: StatementContext, missing: list[str]
    ) -> list[CompletionItem]:
        """Columns of the tables of the statement. A name found in more
        than one table is inserted qualified (``alias.column``)."""
        database = self.__schema.database.casefold()
        scope: list[tuple[TableReference, tuple[ColumnInfo, ...]]] = []
        for reference in context.references:
            if reference.table is None:
                continue
            if reference.schema and reference.schema.casefold() != database:
                continue
            scope.append((reference, self.__columns(reference.table, missing)))
        counts: dict[str, int] = {}
        for _, columns in scope:
            for column in columns:
                key = column.name.casefold()
                counts[key] = counts.get(key, 0) + 1
        items = []
        for reference, columns in scope:
            for column in columns:
                ambiguous = counts[column.name.casefold()] > 1
                items.append(
                    self.__column_item(
                        context,
                        column,
                        reference.table or "",
                        reference.visible_name if ambiguous else None,
                    )
                )
        return items

    def __scope_names(self, context: StatementContext) -> list[CompletionItem]:
        """Aliases and table names of the statement (to qualify
        columns)."""
        items = []
        for reference in context.references:
            if reference.alias:
                detail = "alias of {}".format(reference.table or "a subquery")
                items.append(
                    CompletionItem(
                        reference.alias,
                        CompletionKind.ALIAS,
                        detail=detail,
                        insert_text=self.__name(context, reference.alias),
                    )
                )
            elif reference.table:
                items.append(
                    CompletionItem(
                        reference.table,
                        CompletionKind.TABLE,
                        detail="table in the query",
                        insert_text=self.__name(context, reference.table),
                    )
                )
        return items

    def __all_columns(self, context: StatementContext) -> list[CompletionItem]:
        """Columns of every loaded table, one proposal per name."""
        seen: dict[str, list[str]] = {}
        first: dict[str, tuple[ColumnInfo, str]] = {}
        for table in self.__schema.tables:
            for column in self.__schema.columns_of(table.name) or ():
                key = column.name.casefold()
                seen.setdefault(key, []).append(table.name)
                first.setdefault(key, (column, table.name))
        items = []
        for key, (column, table) in first.items():
            tables = seen[key]
            item = self.__column_item(context, column, table, None)
            if len(tables) > 1:
                detail = "{} · {} tables".format(column.data_type, len(tables))
                item = CompletionItem(
                    item.label,
                    item.kind,
                    detail=detail,
                    insert_text=item.insert_text,
                    tooltip=item.tooltip,
                )
            items.append(item)
        return items

    def __tables(
        self, context: StatementContext, *, ctes: bool = True
    ) -> list[CompletionItem]:
        """Tables, views and (with ``ctes``) WITH queries."""
        items = []
        if ctes:
            for cte in context.ctes:
                items.append(
                    CompletionItem(
                        cte,
                        CompletionKind.CTE,
                        detail="WITH query",
                        insert_text=self.__name(context, cte),
                    )
                )
        for table in self.__schema.tables:
            kind = (
                CompletionKind.VIEW if table.is_view else CompletionKind.TABLE
            )
            items.append(
                CompletionItem(
                    table.name,
                    kind,
                    detail=kind.label,
                    insert_text=self.__name(context, table.name),
                )
            )
        return items

    def __columns(
        self, table: str, missing: list[str]
    ) -> tuple[ColumnInfo, ...]:
        """Columns of ``table``; a listed table whose columns are not loaded
        is added to ``missing``."""
        columns = self.__schema.columns_of(table)
        if columns is None:
            listed = self.__schema.table(table)
            if listed is not None and listed.name not in missing:
                missing.append(listed.name)
            return ()
        return columns

    def __column_item(
        self,
        context: StatementContext,
        column: ColumnInfo,
        table: str,
        qualifier: str | None,
    ) -> CompletionItem:
        insert = self.__name(context, column.name)
        if qualifier:
            insert = "{}.{}".format(SqlVocabulary.identifier(qualifier), insert)
        kind = (
            CompletionKind.KEY_COLUMN
            if column.is_primary
            else CompletionKind.COLUMN
        )
        detail = column.data_type or kind.label
        if table:
            detail = "{} · {}".format(detail, table)
        return CompletionItem(
            column.name,
            kind,
            detail=detail,
            insert_text=insert,
            tooltip="{}\ntable: {}".format(column.describe(), table),
        )

    @staticmethod
    def __name(context: StatementContext, name: str) -> str:
        """Identifier to insert; inside a quoted word it stays quoted."""
        if context.quoted:
            return "`{}`".format(name.replace("`", "``"))
        return SqlVocabulary.identifier(name)

    def __keywords(
        self,
        context: StatementContext,
        phrases: tuple[str, ...],
        *,
        checked: bool = True,
    ) -> list[CompletionItem]:
        """Keyword phrases written in the case of the typed text."""
        if context.quoted:
            return []
        items = []
        for phrase in phrases:
            if checked and not SqlVocabulary.allowed(phrase):
                continue
            text = CompletionEngine.__cased(context.prefix, phrase)
            if phrase not in CompletionEngine.__NO_SPACE:
                text = "{} ".format(text)
            items.append(
                CompletionItem(
                    phrase,
                    CompletionKind.KEYWORD,
                    detail=CompletionKind.KEYWORD.label,
                    insert_text=text,
                )
            )
        return items

    def __functions(self, context: StatementContext) -> list[CompletionItem]:
        """Functions, inserted with their parentheses."""
        if context.quoted:
            return []
        items = []
        for name in SqlVocabulary.functions():
            no_arguments = name in SqlVocabulary.NO_ARGUMENT_FUNCTIONS
            items.append(
                CompletionItem(
                    name,
                    CompletionKind.FUNCTION,
                    detail="{}()".format(name.lower()),
                    insert_text="{}()".format(
                        CompletionEngine.__cased(context.prefix, name)
                    ),
                    caret_back=0 if no_arguments else 1,
                )
            )
        return items

    @staticmethod
    def __cased(prefix: str, phrase: str) -> str:
        """``phrase`` in lower case when the typed text is all lower case,
        otherwise in upper case."""
        if prefix and prefix == prefix.lower() and prefix != prefix.upper():
            return phrase.lower()
        return phrase.upper()

    # --------------------------------------------------------------- ranking
    @staticmethod
    def __rank(
        prefix: str, groups: list[tuple[int, list[CompletionItem]]]
    ) -> tuple[CompletionItem, ...]:
        """Matching proposals, best first, without duplicates."""
        wanted = prefix.casefold()
        scored = []
        seen: set[tuple[str, CompletionKind, str]] = set()
        sequence = 0
        for priority, items in groups:
            for item in items:
                key = (item.label.casefold(), item.kind, item.insert_text)
                if key in seen:
                    continue
                tier = CompletionEngine.__match(item, wanted)
                if tier is None:
                    continue
                seen.add(key)
                label = item.label.casefold()
                if wanted:
                    order = (tier, priority, label != wanted, label, sequence)
                else:
                    order = (0, priority, False, "", sequence)
                scored.append((order, item))
                sequence += 1
        scored.sort(key=lambda pair: pair[0])
        return tuple(item for _, item in scored[: CompletionEngine.MAX_ITEMS])

    @staticmethod
    def __match(item: CompletionItem, wanted: str) -> int | None:
        """0: starts with ``wanted``; 1: a word of it does; 2: contains it
        (tables and columns only); None: no match."""
        if not wanted:
            return 0
        label = item.label.casefold()
        if label.startswith(wanted):
            return 0
        words = CompletionEngine.__WORD_BREAK.split(label)
        if any(word.startswith(wanted) for word in words[1:]):
            return 1
        if (
            (item.kind.is_column or item.kind.is_table)
            and len(wanted) >= CompletionEngine.MIN_CONTAINS
            and wanted in label
        ):
            return 2
        return None
