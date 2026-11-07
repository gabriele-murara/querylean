"""Tests of the types of mask placeholder values."""

import pytest

from querylean.bookmarks.mask_error import MaskError
from querylean.bookmarks.placeholder_type import PlaceholderType


class TestPlaceholderType:
    """Validation, canonical form, literals and type inference."""

    @pytest.mark.parametrize(
        ("kind", "value", "normalized", "literal"),
        [
            (PlaceholderType.INTEGER, " 2026 ", "2026", "2026"),
            (PlaceholderType.INTEGER, "-007", "-7", "-7"),
            (PlaceholderType.DECIMAL, "12.50", "12.50", "12.50"),
            (PlaceholderType.DECIMAL, ".5", ".5", ".5"),
            (PlaceholderType.TEXT, " a'b\\c ", " a'b\\c ", "' a''b\\\\c '"),
            (PlaceholderType.DATE, "2026-02-28", "2026-02-28", "'2026-02-28'"),
            (PlaceholderType.TIME, "10:05", "10:05:00", "'10:05:00'"),
            (
                PlaceholderType.DATETIME,
                "2026-11-03T10:00",
                "2026-11-03 10:00:00",
                "'2026-11-03 10:00:00'",
            ),
            (PlaceholderType.BOOLEAN, "Yes", "true", "TRUE"),
            (PlaceholderType.BOOLEAN, "0", "false", "FALSE"),
        ],
    )
    def test_valid_values(self, kind, value, normalized, literal):
        assert kind.normalize(value) == normalized
        assert kind.literal(kind.normalize(value)) == literal

    @pytest.mark.parametrize(
        ("kind", "value"),
        [
            (PlaceholderType.INTEGER, "2026 OR 1=1"),
            (PlaceholderType.INTEGER, "1.5"),
            (PlaceholderType.INTEGER, "0x10"),
            (PlaceholderType.DECIMAL, "1e9"),
            (PlaceholderType.DECIMAL, "1,5"),
            (PlaceholderType.DATE, "2026-02-30"),
            (PlaceholderType.DATE, "03/11/2026"),
            (PlaceholderType.TIME, "25:00"),
            (PlaceholderType.DATETIME, "2026-11-03"),
            (PlaceholderType.BOOLEAN, "maybe"),
            (PlaceholderType.TEXT, ""),
            (PlaceholderType.INTEGER, "   "),
        ],
    )
    def test_invalid_values(self, kind, value):
        with pytest.raises(MaskError):
            kind.normalize(value)

    def test_text_with_nul_is_refused(self):
        with pytest.raises(MaskError):
            PlaceholderType.TEXT.normalize("a{}b".format(chr(0)))

    @pytest.mark.parametrize(
        ("example", "quoted", "kind"),
        [
            ("2026", False, PlaceholderType.INTEGER),
            ("2026", True, PlaceholderType.TEXT),
            ("12.5", False, PlaceholderType.DECIMAL),
            ("2026-11-03", True, PlaceholderType.DATE),
            ("2026-11-03 10:00:00", True, PlaceholderType.DATETIME),
            ("10:00", True, PlaceholderType.TIME),
            ("TRUE", False, PlaceholderType.BOOLEAN),
            ("2026-13-45", True, PlaceholderType.TEXT),
            ("abc", False, PlaceholderType.TEXT),
        ],
    )
    def test_infer(self, example, quoted, kind):
        assert PlaceholderType.infer(example, quoted=quoted) is kind

    def test_keys(self):
        for kind in PlaceholderType:
            assert PlaceholderType.from_key(kind.key) is kind
        assert PlaceholderType.from_key("nope") is None
        assert len(list(PlaceholderType)) == 7
