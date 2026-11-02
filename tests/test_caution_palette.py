"""Tests of the pink tint used for accounts that are not read-only."""

import pytest
from PySide6.QtGui import QColor, QPalette

from querylean.ui.main.caution_palette import CautionPalette


class TestCautionPalette:
    """Blend of colors and roles set by the tinted palette."""

    @pytest.mark.parametrize(
        ("ratio", "expected"),
        [(0.0, "#000000"), (1.0, "#ffffff"), (0.5, "#808080"), (2, "#ffffff")],
    )
    def test_blend(self, ratio, expected):
        color = CautionPalette.blend(
            QColor("#000000"), QColor("#ffffff"), ratio
        )
        assert color.name() == expected

    @pytest.mark.parametrize("grey", ["#efefef", "#353535"])
    def test_window_turns_pink(self, grey):
        base = QPalette(QColor(grey))
        role = QPalette.ColorRole.Window
        tinted = CautionPalette.tinted(base).color(role)
        assert tinted != base.color(role)
        # More red than green and blue: a pink or rose hue.
        assert tinted.red() > tinted.green()
        assert tinted.red() > tinted.blue()

    def test_only_window_roles_are_set(self):
        palette = CautionPalette.tinted(QPalette(QColor("#efefef")))
        for role in (
            QPalette.ColorRole.Base,
            QPalette.ColorRole.Text,
            QPalette.ColorRole.Button,
        ):
            assert not palette.isBrushSet(QPalette.ColorGroup.Active, role)
        assert palette.isBrushSet(
            QPalette.ColorGroup.Active, QPalette.ColorRole.Window
        )
