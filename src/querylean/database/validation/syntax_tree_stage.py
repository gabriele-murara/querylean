"""Stage 3: structural checks on the sqlglot syntax tree."""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from querylean.database.validation.read_only_rules import ReadOnlyRules
from querylean.database.validation.validation_context import ValidationContext
from querylean.database.validation.validation_rejected import ValidationRejected
from querylean.database.validation.validation_stage import ValidationStage
from querylean.log.log_manager import LogManager


class SyntaxTreeStage(ValidationStage):
    """Parses the statement with the MySQL dialect: it must be exactly one
    statement of an allowed type, without write nodes, ``INTO``, locks or
    side-effect functions."""

    __log = LogManager.get_logger(__name__)

    def apply(self, context: ValidationContext) -> None:
        root = self.__parse(context.statement)
        SyntaxTreeStage.__check_root(root, context.first_word)
        SyntaxTreeStage.__check_nodes(root)
        context.syntax_tree = root

    def __parse(self, statement: str) -> exp.Expression:
        try:
            expressions = sqlglot.parse(statement, read="mysql")
        except SqlglotError as exc:
            self.__log.info("SQL parsing failed: {}", exc)
            msg = "The query could not be parsed safely: check the "
            msg += "syntax. Queries that are not recognised are rejected."
            raise ValidationRejected(msg) from None
        expressions = [e for e in expressions if e is not None]
        if len(expressions) != 1:
            raise ValidationRejected(ReadOnlyRules.MULTIPLE_STATEMENTS)
        return expressions[0]

    @staticmethod
    def __check_root(root: exp.Expression, first_word: str) -> None:
        if first_word == ReadOnlyRules.SHOW_FIRST_WORD:
            if not isinstance(root, exp.Show):
                msg = "{} Unrecognised form of SHOW."
                raise ValidationRejected(msg.format(ReadOnlyRules.NOT_ALLOWED))
        elif first_word in ReadOnlyRules.DESCRIBE_FIRST_WORDS:
            if not isinstance(root, exp.Describe):
                msg = "{} Unrecognised form of {}."
                msg = msg.format(ReadOnlyRules.NOT_ALLOWED, first_word)
                raise ValidationRejected(msg)
            if not isinstance(
                root.this, (exp.Table, *ReadOnlyRules.SELECT_ROOTS)
            ):
                msg = "{} {} is allowed only on tables or SELECT."
                msg = msg.format(ReadOnlyRules.NOT_ALLOWED, first_word)
                raise ValidationRejected(msg)
        elif first_word in ReadOnlyRules.SELECT_FIRST_WORDS:
            if not isinstance(root, ReadOnlyRules.SELECT_ROOTS):
                raise ValidationRejected(ReadOnlyRules.NOT_ALLOWED)
        else:
            raise ValidationRejected(ReadOnlyRules.NOT_ALLOWED)

    @staticmethod
    def __check_nodes(root: exp.Expression) -> None:
        for node in root.walk():
            if isinstance(node, ReadOnlyRules.FORBIDDEN_NODES):
                msg = "{} Construct not allowed: {}."
                msg = msg.format(ReadOnlyRules.NOT_ALLOWED, type(node).__name__)
                raise ValidationRejected(msg)
            if isinstance(node, exp.Select) and (
                node.args.get("locks") or node.args.get("into")
            ):
                msg = "{} SELECT … INTO and locking reads are not allowed."
                raise ValidationRejected(msg.format(ReadOnlyRules.NOT_ALLOWED))
            if isinstance(node, exp.Func):
                name = (
                    node.name
                    if isinstance(node, exp.Anonymous)
                    else node.sql_name()
                ).upper()
                if name in ReadOnlyRules.FORBIDDEN_FUNCTIONS:
                    raise ValidationRejected(
                        ReadOnlyRules.FUNCTION_NOT_ALLOWED.format(name)
                    )
