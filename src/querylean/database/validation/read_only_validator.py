"""Fail-closed validator of read-only statements."""

from __future__ import annotations

from querylean.database.validation.keyword_stage import KeywordStage
from querylean.database.validation.lexical_stage import LexicalStage
from querylean.database.validation.syntax_tree_stage import SyntaxTreeStage
from querylean.database.validation.validation_context import ValidationContext
from querylean.database.validation.validation_rejected import ValidationRejected
from querylean.database.validation.validation_result import ValidationResult
from querylean.database.validation.validation_stage import ValidationStage
from querylean.log.log_manager import LogManager


class ReadOnlyValidator:
    """Runs independent stages (lexical, keyword, syntax tree) over a statement.

    Any rejection or unexpected error rejects the query. The accepted
    ``statement`` is the original text without the trailing ``;`` (never
    regenerated SQL). The validator is an additional barrier: the primary
    guarantee is a MySQL account with SELECT-only privileges.
    """

    __log = LogManager.get_logger(__name__)

    def __init__(self, stages: list[ValidationStage] | None = None) -> None:
        self.__stages = (
            list(stages)
            if stages
            else [
                LexicalStage(),
                KeywordStage(),
                SyntaxTreeStage(),
            ]
        )

    @property
    def stages(self) -> list[ValidationStage]:
        """Stages in execution order."""
        return list(self.__stages)

    def validate(self, sql: str) -> ValidationResult:
        """Validate a single read statement. Never raises."""
        context = ValidationContext(sql or "")
        try:
            for stage in self.__stages:
                stage.apply(context)
        except ValidationRejected as rejection:
            return ValidationResult.reject(str(rejection))
        except Exception:
            self.__log.exception("Unexpected error in the validator")
            reason = "The query could not be checked safely, so it was "
            reason += "rejected."
            return ValidationResult.reject(reason)
        return ValidationResult.accept(context.statement)
