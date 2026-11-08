"""Stage 1: MySQL-aware lexical analysis."""

from __future__ import annotations

from querylean.database.validation.mysql_lexer import MySqlLexer
from querylean.database.validation.validation_context import ValidationContext
from querylean.database.validation.validation_rejected import ValidationRejected
from querylean.database.validation.validation_stage import ValidationStage


class LexicalStage(ValidationStage):
    """Splits the text into significant tokens and isolates the single
    statement."""

    __EMPTY = "The query is empty."

    def apply(self, context: ValidationContext) -> None:
        if not context.sql.strip():
            raise ValidationRejected(LexicalStage.__EMPTY)
        lexed = MySqlLexer.tokenize(context.sql)
        if not lexed.statement or not lexed.tokens:
            raise ValidationRejected(LexicalStage.__EMPTY)
        context.tokens = lexed.tokens
        context.statement = lexed.statement
