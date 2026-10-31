"""Stage 2: checks on significant words."""

from __future__ import annotations

from querylean.database.validation.read_only_rules import ReadOnlyRules
from querylean.database.validation.validation_context import ValidationContext
from querylean.database.validation.validation_rejected import ValidationRejected
from querylean.database.validation.validation_stage import ValidationStage


class KeywordStage(ValidationStage):
    """Accepts only allowed first words and rejects forbidden reserved words and
    side-effect functions found outside strings and comments."""

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
            if not token.is_word():
                continue
            upper = token.text.upper()
            previous = tokens[index - 1] if index > 0 else None
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            qualified = previous is not None and previous.is_symbol(".")

            if upper in ReadOnlyRules.FORBIDDEN_WORDS and not qualified:
                show_create = (
                    is_show
                    and upper == ReadOnlyRules.SHOW_CREATE_EXCEPTION
                    and index == 1
                )
                if not show_create:
                    raise ValidationRejected(
                        f"{ReadOnlyRules.NOT_ALLOWED} Parola chiave non "
                        f"ammessa: {upper}."
                    )
            if (
                upper in ReadOnlyRules.FORBIDDEN_FUNCTIONS
                and following is not None
                and following.is_symbol("(")
            ):
                raise ValidationRejected(
                    f"La funzione {upper}() non è consentita in modalità sola "
                    "lettura."
                )
        context.first_word = first
