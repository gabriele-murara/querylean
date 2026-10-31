"""Lexer that follows MySQL's rules for strings and comments."""

from __future__ import annotations

from querylean.database.validation.lexed_statement import LexedStatement
from querylean.database.validation.sql_token import SqlToken
from querylean.database.validation.validation_rejected import ValidationRejected


class MySqlLexer:
    """Scans SQL text the way the MySQL server does.

    It rejects constructs that the server would execute but a generic parser would
    ignore (executable comments ``/*! */``, optimizer hints ``/*+ */``, ``--`` not
    followed by whitespace), multiple statements, ``:=`` assignments and unterminated
    strings or comments.
    """

    __MULTIPLE_STATEMENTS = (
        "Sono presenti più istruzioni SQL: questa versione ne esegue una sola per volta."
    )

    @staticmethod
    def tokenize(sql: str) -> LexedStatement:
        """Return the significant tokens and the single statement text.

        Raises ``ValidationRejected``.
        """
        tokens: list[SqlToken] = []
        i, n = 0, len(sql)
        statement_end: int | None = None

        while i < n:
            ch = sql[i]
            nxt = sql[i + 1] if i + 1 < n else ""

            if (
                statement_end is not None
                and not ch.isspace()
                and not MySqlLexer.__starts_comment(sql, i)
            ):
                raise ValidationRejected(MySqlLexer.__MULTIPLE_STATEMENTS)

            if ch.isspace():
                i += 1
            elif ch == "#":
                i = MySqlLexer.__skip_line(sql, i)
            elif ch == "-" and nxt == "-":
                after = sql[i + 2] if i + 2 < n else ""
                if after == "" or after.isspace() or ord(after) < 32:
                    i = MySqlLexer.__skip_line(sql, i)
                else:
                    raise ValidationRejected(
                        "Sequenza «--» ambigua: in MySQL è un commento solo se seguita da uno "
                        "spazio. Aggiungi uno spazio o riformula l'espressione."
                    )
            elif ch == "/" and nxt == "*":
                marker = sql[i + 2] if i + 2 < n else ""
                if marker in ("!", "+"):
                    raise ValidationRejected(
                        "I commenti eseguibili MySQL (/*! … */) e gli hint dell'ottimizzatore "
                        "(/*+ … */) non sono consentiti."
                    )
                end = sql.find("*/", i + 2)
                if end < 0:
                    raise ValidationRejected("Commento /* … */ non chiuso.")
                i = end + 2
            elif ch in ("'", '"'):
                end = MySqlLexer.__scan_quoted(sql, i, ch, backslash=True)
                tokens.append(SqlToken(SqlToken.STRING, sql[i:end], i))
                i = end
            elif ch == "`":
                end = MySqlLexer.__scan_quoted(sql, i, ch, backslash=False)
                tokens.append(SqlToken(SqlToken.QUOTED_IDENTIFIER, sql[i:end], i))
                i = end
            elif ch == ";":
                statement_end = i
                i += 1
            elif ch == ":" and nxt == "=":
                raise ValidationRejected("L'assegnazione di variabili (:=) non è consentita.")
            elif MySqlLexer.__is_word_char(ch) and not ch.isdigit():
                j = i + 1
                while j < n and MySqlLexer.__is_word_char(sql[j]):
                    j += 1
                tokens.append(SqlToken(SqlToken.WORD, sql[i:j], i))
                i = j
            elif ch.isdigit():
                j = i + 1
                while j < n and (sql[j].isalnum() or sql[j] in "._"):
                    j += 1
                tokens.append(SqlToken(SqlToken.NUMBER, sql[i:j], i))
                i = j
            else:
                tokens.append(SqlToken(SqlToken.SYMBOL, ch, i))
                i += 1

        statement = sql[:statement_end] if statement_end is not None else sql
        return LexedStatement(tokens, statement.strip())

    @staticmethod
    def __is_word_char(ch: str) -> bool:
        return ch.isalnum() or ch in "_$" or ord(ch) > 127

    @staticmethod
    def __starts_comment(sql: str, i: int) -> bool:
        if sql[i] == "#":
            return True
        two = sql[i : i + 2]
        if two == "/*":
            return True
        if two == "--":
            after = sql[i + 2] if i + 2 < len(sql) else ""
            return after == "" or after.isspace()
        return False

    @staticmethod
    def __skip_line(sql: str, i: int) -> int:
        end = sql.find("\n", i)
        return len(sql) if end < 0 else end + 1

    @staticmethod
    def __scan_quoted(sql: str, start: int, quote: str, *, backslash: bool) -> int:
        """Index just after the closing quote."""
        i, n = start + 1, len(sql)
        while i < n:
            ch = sql[i]
            if backslash and ch == "\\":
                i += 2
                continue
            if ch == quote:
                if i + 1 < n and sql[i + 1] == quote:  # doubled quote
                    i += 2
                    continue
                return i + 1
            i += 1
        raise ValidationRejected("Stringa o identificatore tra virgolette non chiuso.")
