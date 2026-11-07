"""Analysis of the statement around the cursor."""

from __future__ import annotations

from querylean.completion.scan_token import ScanToken
from querylean.completion.sql_scanner import SqlScanner
from querylean.completion.sql_vocabulary import SqlVocabulary
from querylean.completion.statement_context import StatementContext
from querylean.completion.table_reference import TableReference


class StatementAnalyzer:
    """Finds the word under the cursor, what is expected there (a table, a
    column, a keyword…) and the tables of the statement with their
    aliases.

    Only the statement that contains the cursor is considered (statements
    are separated by ``;``); tables are collected from the whole
    statement, also after the cursor, so ``SELECT | FROM users u`` knows
    the columns of ``users``. The analysis never fails: incomplete or
    wrong SQL yields a best-effort context.
    """

    __TABLE_CLAUSES = ("FROM", "JOIN", "STRAIGHT_JOIN")
    __EXPRESSION_CLAUSES = (
        "SELECT",
        "WHERE",
        "ON",
        "HAVING",
        "BY",
        "WHEN",
        "THEN",
        "ELSE",
        "CASE",
        "SET",
        "DISTINCT",
    )
    __SET_OPERATIONS = ("UNION", "EXCEPT", "INTERSECT")
    __NO_PROPOSALS = ("LIMIT", "OFFSET")
    __DESCRIBE = ("DESC", "DESCRIBE")
    # Words after which an expression starts.
    __EXPRESSION_WORDS = frozenset(
        {
            "SELECT",
            "WHERE",
            "ON",
            "HAVING",
            "BY",
            "AND",
            "OR",
            "XOR",
            "NOT",
            "IN",
            "LIKE",
            "RLIKE",
            "REGEXP",
            "BETWEEN",
            "IS",
            "WHEN",
            "THEN",
            "ELSE",
            "CASE",
            "DISTINCT",
            "ALL",
            "ANY",
            "SOME",
            "EXISTS",
            "INTERVAL",
            "DIV",
            "MOD",
            "ESCAPE",
            "SET",
        }
    )
    __OPERATORS = frozenset(
        {
            ",",
            "(",
            "=",
            "<",
            ">",
            "<=",
            ">=",
            "<>",
            "!=",
            "<=>",
            "+",
            "-",
            "*",
            "/",
            "%",
            "||",
            "&&",
            "|",
            "&",
            "^",
            "~",
            "!",
        }
    )
    # Words before "(" that open a subquery or a list, not a function call.
    __PAREN_KEYWORDS = frozenset(
        {
            "IN",
            "EXISTS",
            "FROM",
            "JOIN",
            "AS",
            "ANY",
            "ALL",
            "SOME",
            "UNION",
            "EXCEPT",
            "INTERSECT",
            "SELECT",
            "WHERE",
            "ON",
            "AND",
            "OR",
            "NOT",
            "HAVING",
            "BY",
            "LATERAL",
            "WHEN",
            "THEN",
            "ELSE",
        }
    )
    __SHOW_TABLE_WORDS = frozenset(
        {"COLUMNS", "FIELDS", "INDEX", "INDEXES", "KEYS"}
    )

    @staticmethod
    def analyze(text: str, position: int) -> StatementContext:
        """Context of the cursor at ``position`` in ``text``."""
        position = min(max(position, 0), len(text))
        tokens = SqlScanner.scan(text)
        word: ScanToken | None = None
        quoted = False
        for token in tokens:
            if StatementAnalyzer.__silences(token, position):
                return StatementContext(
                    StatementContext.NONE, start=position, end=position
                )
            if token.kind == ScanToken.QUOTED and (
                token.start < position < token.end
                or (position == token.end and not token.closed)
            ):
                word, quoted = token, True
        if word is not None:
            start, end = word.start, word.end
            prefix = text[word.start + 1 : position].replace("``", "`")
        else:
            start = position
            while start > 0 and SqlScanner.is_identifier_char(text[start - 1]):
                start -= 1
            end = position
            while end < len(text) and SqlScanner.is_identifier_char(text[end]):
                end += 1
            prefix = text[start:position]
            word = next((t for t in tokens if t.start == start), None)
            if prefix[:1].isdigit() or text[:start].endswith("${"):
                # Numbers and placeholder names (``${NAME}``) are not
                # completed.
                return StatementContext(
                    StatementContext.NONE, start=position, end=position
                )

        statement = StatementAnalyzer.__statement(tokens, start, end)
        others = [t for t in statement if t is not word]
        before = [t for t in others if t.end <= start]
        qualifier, head = StatementAnalyzer.__qualifier(before, start)
        references = StatementAnalyzer.__references(others)
        ctes = StatementAnalyzer.__ctes(others)
        kind = StatementAnalyzer.__clause(head)
        expects_table = False
        if qualifier:
            expects_table = kind == StatementContext.TABLE_NAME
            kind = StatementContext.QUALIFIED
        return StatementContext(
            kind,
            prefix=prefix,
            start=start,
            end=end,
            quoted=quoted,
            qualifier=qualifier,
            references=references,
            ctes=ctes,
            expects_table=expects_table,
        )

    # --------------------------------------------------------------- cursor
    @staticmethod
    def __silences(token: ScanToken, position: int) -> bool:
        """True when the cursor is inside (or at the end of) a string,
        comment, number or variable."""
        if token.kind in (ScanToken.STRING, ScanToken.COMMENT):
            return token.start < position < token.end or (
                position == token.end and not token.closed
            )
        if token.kind in (ScanToken.NUMBER, ScanToken.VARIABLE):
            return token.start < position <= token.end
        return False

    @staticmethod
    def __statement(
        tokens: list[ScanToken], start: int, end: int
    ) -> list[ScanToken]:
        """Significant tokens of the statement around ``start``–``end``."""
        first, last = 0, None
        for token in tokens:
            if token.is_symbol(";"):
                if token.end <= start:
                    first = token.end
                elif token.start >= end and last is None:
                    last = token.start
        return [
            t
            for t in tokens
            if t.kind != ScanToken.COMMENT
            and t.start >= first
            and (last is None or t.end <= last)
            and not t.is_symbol(";")
        ]

    @staticmethod
    def __qualifier(
        before: list[ScanToken], start: int
    ) -> tuple[tuple[str, ...], list[ScanToken]]:
        """Names before the word joined by dots (``db.t.``) and the tokens
        that precede them."""
        names: list[str] = []
        expected = start
        k = len(before) - 1
        while (
            k >= 1
            and before[k].is_symbol(".")
            and before[k].end == expected
            and before[k - 1].is_identifier
            and before[k - 1].end == before[k].start
        ):
            names.insert(0, before[k - 1].name)
            expected = before[k - 1].start
            k -= 2
        return tuple(names), before[: k + 1]

    # --------------------------------------------------------------- clause
    @staticmethod
    def __clause(head: list[ScanToken]) -> str:
        """What is expected after the tokens ``head``."""
        if not head:
            return StatementContext.STATEMENT_START
        last = head[-1]
        if last.is_word("AS"):
            return StatementContext.NONE  # an alias is being written
        depth = 0
        for idx in range(len(head) - 1, -1, -1):
            token = head[idx]
            if token.is_symbol(")"):
                depth += 1
                continue
            if token.is_symbol("("):
                if depth:
                    depth -= 1
                    continue
                prev = head[idx - 1] if idx > 0 else None
                if (
                    prev is not None
                    and prev.is_identifier
                    and prev.upper not in StatementAnalyzer.__PAREN_KEYWORDS
                ):
                    continue  # function call: keep looking for the clause
                if idx == len(head) - 1:
                    return StatementContext.SUBQUERY
                return StatementAnalyzer.__operand_or_expression(head)
            if depth or token.kind != ScanToken.WORD:
                continue
            kind = StatementAnalyzer.__keyword_clause(head, idx)
            if kind is not None:
                return kind
        return StatementContext.NONE

    @staticmethod
    def __keyword_clause(head: list[ScanToken], idx: int) -> str | None:
        """Context opened by the keyword ``head[idx]``; None when the word
        does not start a clause."""
        token = head[idx]
        word = token.upper
        is_last = idx == len(head) - 1
        if word in StatementAnalyzer.__DESCRIBE or word == "EXPLAIN":
            if idx != 0:
                return None  # ORDER BY … DESC
            if not is_last:
                return StatementContext.NONE
            if word == "EXPLAIN":
                return StatementContext.STATEMENT_START
            return StatementContext.TABLE_NAME
        if word == "SHOW":
            return StatementAnalyzer.__show(head[idx + 1 :])
        if word in StatementAnalyzer.__TABLE_CLAUSES:
            segment = head[idx + 1 :]
            if word == "FROM":
                commas = [
                    i
                    for i, t in enumerate(segment)
                    if t.is_symbol(",")
                    and StatementAnalyzer.__depth(segment[:i]) == 0
                ]
                if commas:
                    segment = segment[commas[-1] + 1 :]
            if not segment:
                return StatementContext.TABLE_NAME
            return StatementContext.AFTER_TABLE
        if word in StatementAnalyzer.__EXPRESSION_CLAUSES:
            return StatementAnalyzer.__operand_or_expression(head)
        if word in StatementAnalyzer.__NO_PROPOSALS:
            return StatementContext.NONE
        if word in StatementAnalyzer.__SET_OPERATIONS:
            if is_last or (idx == len(head) - 2 and head[-1].is_word("ALL")):
                return StatementContext.STATEMENT_START
            return None
        if word == "WITH":
            if head[-1].is_symbol(")"):
                return StatementContext.STATEMENT_START
            return StatementContext.NONE
        return None

    @staticmethod
    def __show(words: list[ScanToken]) -> str:
        """Context inside a ``SHOW`` statement."""
        upper = [t.upper for t in words]
        if not upper:
            return StatementContext.SHOW
        if upper[-1] in ("FROM", "IN") and any(
            w in StatementAnalyzer.__SHOW_TABLE_WORDS for w in upper
        ):
            return StatementContext.TABLE_NAME
        if upper[-2:] in (["CREATE", "TABLE"], ["CREATE", "VIEW"]):
            return StatementContext.TABLE_NAME
        if len(upper) == 1 and upper[0] in ("FULL", "CREATE", "TABLE"):
            return StatementContext.SHOW
        return StatementContext.NONE

    @staticmethod
    def __operand_or_expression(head: list[ScanToken]) -> str:
        """``EXPRESSION`` when an operand is expected after ``head``,
        ``AFTER_OPERAND`` when one has just been written."""
        last = head[-1]
        if last.kind == ScanToken.SYMBOL:
            if last.text == "*" and (
                len(head) == 1
                or head[-2].is_word("SELECT", "DISTINCT")
                or head[-2].is_symbol(",")
                or head[-2].is_symbol(".")
                or head[-2].is_symbol("(")
            ):
                return StatementContext.AFTER_OPERAND
            if last.text in StatementAnalyzer.__OPERATORS:
                return StatementContext.EXPRESSION
            return StatementContext.AFTER_OPERAND
        if (
            last.kind == ScanToken.WORD
            and last.upper in StatementAnalyzer.__EXPRESSION_WORDS
        ):
            return StatementContext.EXPRESSION
        return StatementContext.AFTER_OPERAND

    @staticmethod
    def __depth(tokens: list[ScanToken]) -> int:
        depth = 0
        for token in tokens:
            if token.is_symbol("("):
                depth += 1
            elif token.is_symbol(")"):
                depth = max(depth - 1, 0)
        return depth

    # ----------------------------------------------------------- references
    @staticmethod
    def __references(tokens: list[ScanToken]) -> tuple[TableReference, ...]:
        """Tables of every FROM/JOIN of the statement, in order."""
        found: list[TableReference] = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token.is_word(*StatementAnalyzer.__TABLE_CLAUSES):
                i = StatementAnalyzer.__table_list(
                    tokens, i + 1, found, comma=token.is_word("FROM")
                )
                continue
            i += 1
        unique: list[TableReference] = []
        for reference in found:
            if reference not in unique:
                unique.append(reference)
        return tuple(unique)

    @staticmethod
    def __table_list(
        tokens: list[ScanToken],
        j: int,
        found: list[TableReference],
        *,
        comma: bool,
    ) -> int:
        """Read ``table [AS] alias[, …]`` from ``j``; returns the index of
        the first token not read."""
        n = len(tokens)
        while j < n:
            token = tokens[j]
            if token.is_symbol("("):
                # Derived table: record its alias, then let the caller read
                # the subquery itself.
                after = StatementAnalyzer.__skip_group(tokens, j)
                alias, _ = StatementAnalyzer.__alias(tokens, after)
                if alias:
                    found.append(TableReference(None, alias))
                return j + 1
            if not StatementAnalyzer.__is_name(token):
                return j
            parts = [token.name]
            j += 1
            while (
                j + 1 < n
                and tokens[j].is_symbol(".")
                and tokens[j + 1].is_identifier
            ):
                parts.append(tokens[j + 1].name)
                j += 2
            if (
                j + 1 < n
                and tokens[j].is_word("PARTITION")
                and tokens[j + 1].is_symbol("(")
            ):
                j = StatementAnalyzer.__skip_group(tokens, j + 1)
            alias, j = StatementAnalyzer.__alias(tokens, j)
            schema = parts[-2] if len(parts) > 1 else None
            found.append(TableReference(parts[-1], alias, schema))
            if comma and j < n and tokens[j].is_symbol(","):
                j += 1
                continue
            return j
        return j

    @staticmethod
    def __alias(tokens: list[ScanToken], j: int) -> tuple[str | None, int]:
        """Optional ``[AS] alias`` at ``j``."""
        n = len(tokens)
        if j < n and tokens[j].is_word("AS"):
            if j + 1 < n and tokens[j + 1].is_identifier:
                return tokens[j + 1].name, j + 2
            return None, j + 1
        if j < n and StatementAnalyzer.__is_name(tokens[j]):
            return tokens[j].name, j + 1
        return None, j

    @staticmethod
    def __is_name(token: ScanToken) -> bool:
        """True for an identifier that is not a reserved word."""
        if token.kind == ScanToken.QUOTED:
            return True
        return token.kind == ScanToken.WORD and not SqlVocabulary.is_reserved(
            token.text
        )

    @staticmethod
    def __skip_group(tokens: list[ScanToken], j: int) -> int:
        """Index after the ``)`` matching the ``(`` at ``j``."""
        depth = 0
        while j < len(tokens):
            if tokens[j].is_symbol("("):
                depth += 1
            elif tokens[j].is_symbol(")"):
                depth -= 1
                if depth == 0:
                    return j + 1
            j += 1
        return j

    @staticmethod
    def __ctes(tokens: list[ScanToken]) -> tuple[str, ...]:
        """Names of the common table expressions of ``WITH`` clauses."""
        names: list[str] = []
        n = len(tokens)
        for i, token in enumerate(tokens):
            if not token.is_word("WITH"):
                continue
            j = i + 1
            if j < n and tokens[j].is_word("RECURSIVE"):
                j += 1
            while j < n and tokens[j].is_identifier:
                name = tokens[j].name
                j += 1
                if j < n and tokens[j].is_symbol("("):
                    j = StatementAnalyzer.__skip_group(tokens, j)
                if j >= n or not tokens[j].is_word("AS"):
                    break
                names.append(name)
                j += 1
                if j < n and tokens[j].is_symbol("("):
                    j = StatementAnalyzer.__skip_group(tokens, j)
                if j < n and tokens[j].is_symbol(","):
                    j += 1
                    continue
                break
        return tuple(names)
