"""Where the cursor is, for the autocompletion."""

from __future__ import annotations

from querylean.completion.table_reference import TableReference


class StatementContext:
    """Result of ``StatementAnalyzer.analyze``: the word being completed,
    what is expected there and the tables in scope.

    ``kind`` is one of the constants below. ``start``/``end`` delimit the
    text that a proposal replaces (the whole word around the cursor,
    backticks included when ``quoted``).
    """

    NONE = "none"  # no proposals (strings, comments, numbers, LIMIT …)
    STATEMENT_START = "statement_start"
    TABLE_NAME = "table_name"
    AFTER_TABLE = "after_table"
    EXPRESSION = "expression"
    AFTER_OPERAND = "after_operand"
    SUBQUERY = "subquery"  # just after "(": SELECT or an expression
    SHOW = "show"
    QUALIFIED = "qualified"  # after "name."

    def __init__(
        self,
        kind: str,
        *,
        prefix: str = "",
        start: int = 0,
        end: int = 0,
        quoted: bool = False,
        qualifier: tuple[str, ...] = (),
        references: tuple[TableReference, ...] = (),
        ctes: tuple[str, ...] = (),
        expects_table: bool = False,
    ) -> None:
        self.__kind = kind
        self.__prefix = prefix
        self.__start = start
        self.__end = end
        self.__quoted = quoted
        self.__qualifier = qualifier
        self.__references = references
        self.__ctes = ctes
        self.__expects_table = expects_table

    @property
    def kind(self) -> str:
        """What is expected at the cursor."""
        return self.__kind

    @property
    def prefix(self) -> str:
        """Part of the word before the cursor (without backtick)."""
        return self.__prefix

    @property
    def start(self) -> int:
        """Start of the text replaced by a proposal."""
        return self.__start

    @property
    def end(self) -> int:
        """End of the text replaced by a proposal."""
        return self.__end

    @property
    def quoted(self) -> bool:
        """True when the word starts with a backtick."""
        return self.__quoted

    @property
    def qualifier(self) -> tuple[str, ...]:
        """Names before the dot(s): ``("u",)`` for ``u.na``."""
        return self.__qualifier

    @property
    def references(self) -> tuple[TableReference, ...]:
        """Tables of the FROM/JOIN clauses of the statement."""
        return self.__references

    @property
    def ctes(self) -> tuple[str, ...]:
        """Names of the common table expressions (``WITH name AS``)."""
        return self.__ctes

    @property
    def expects_table(self) -> bool:
        """For ``QUALIFIED``: the qualifier is followed by a table name
        (``FROM db.``), not a column."""
        return self.__expects_table

    def __repr__(self) -> str:
        text = "StatementContext({}, prefix={!r}, qualifier={!r})"
        return text.format(self.__kind, self.__prefix, self.__qualifier)
