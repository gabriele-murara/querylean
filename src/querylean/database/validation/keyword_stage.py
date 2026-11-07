"""Stage 2: checks on significant words."""

from __future__ import annotations

from querylean.database.validation.read_only_rules import ReadOnlyRules
from querylean.database.validation.sql_token import SqlToken
from querylean.database.validation.validation_context import ValidationContext
from querylean.database.validation.validation_rejected import ValidationRejected
from querylean.database.validation.validation_stage import ValidationStage


class KeywordStage(ValidationStage):
    """Accepts only allowed first words and rejects forbidden words and
    side-effect functions found outside strings and comments.

    Forbidden words are rejected also when qualified (``t.update``) or
    written as quoted identifiers (`` `delete` ``)."""

    def apply(self, context: ValidationContext) -> None:
        tokens = context.tokens
        words = [t for t in tokens if t.is_word()]
        if not words or (
            not tokens[0].is_word() and not tokens[0].is_symbol("(")
        ):
            raise ValidationRejected(ReadOnlyRules.NOT_ALLOWED)

        first = words[0].text.upper()
        if first not in ReadOnlyRules.ALLOWED_FIRST_WORDS:
            raise ValidationRejected(ReadOnlyRules.NOT_ALLOWED)
        is_show = first == ReadOnlyRules.SHOW_FIRST_WORD

        for index, token in enumerate(tokens):
            name = KeywordStage.__name_of(token)
            if name is None:
                continue
            previous = tokens[index - 1] if index > 0 else None
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            qualified = previous is not None and previous.is_symbol(".")
            call = following is not None and following.is_symbol("(")

            if name in ReadOnlyRules.FORBIDDEN_WORDS:
                plain = token.is_word() and not qualified
                show_create = (
                    is_show
                    and plain
                    and name == ReadOnlyRules.SHOW_CREATE_EXCEPTION
                    and index == 1
                )
                function = (
                    plain
                    and call
                    and name in ReadOnlyRules.FUNCTION_NAME_EXCEPTIONS
                )
                if not show_create and not function:
                    msg = "{} Keyword not allowed: {}."
                    msg = msg.format(ReadOnlyRules.NOT_ALLOWED, name)
                    raise ValidationRejected(msg)
            if name in ReadOnlyRules.FORBIDDEN_FUNCTIONS and call:
                raise ValidationRejected(
                    ReadOnlyRules.FUNCTION_NOT_ALLOWED.format(name)
                )
        context.first_word = first

    @staticmethod
    def __name_of(token: SqlToken) -> str | None:
        """Upper-case name of a word or quoted identifier, else ``None``."""
        if token.is_word():
            return token.text.upper()
        if token.kind == SqlToken.QUOTED_IDENTIFIER:
            return token.text[1:-1].replace("``", "`").upper()
        return None
