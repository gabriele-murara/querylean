"""Pink tint of the window background for accounts that are not read-only."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette


class CautionPalette:
    """Builds the palette that tints the "grey" parts of the main window
    (toolbar, side bar background, status bar, margins) pink.

    The tint is a blend of the current window color with a rose hue, so it
    stays a soft pink on light themes and a dark rose on dark themes.
    Only the window background roles are set: editor, tables and text keep
    their colors."""

    TINT_COLOR = "#e91e63"
    # Share of the tint in the blend (0 = no tint, 1 = pure tint).
    TINT_RATIO = 0.2
    ROLES = (QPalette.ColorRole.Window,)

    @staticmethod
    def blend(base: QColor, tint: QColor, ratio: float) -> QColor:
        """``base`` moved towards ``tint`` by ``ratio`` (0–1)."""
        ratio = min(max(ratio, 0.0), 1.0)
        return QColor(
            round(base.red() + (tint.red() - base.red()) * ratio),
            round(base.green() + (tint.green() - base.green()) * ratio),
            round(base.blue() + (tint.blue() - base.blue()) * ratio),
        )

    @staticmethod
    def tinted(base: QPalette) -> QPalette:
        """Palette that sets only the window roles of ``base``, tinted, in
        every color group; the other roles stay inherited."""
        tint = QColor(CautionPalette.TINT_COLOR)
        palette = QPalette()
        for role in CautionPalette.ROLES:
            for group in (
                QPalette.ColorGroup.Active,
                QPalette.ColorGroup.Inactive,
                QPalette.ColorGroup.Disabled,
            ):
                color = CautionPalette.blend(
                    base.color(group, role), tint, CautionPalette.TINT_RATIO
                )
                palette.setColor(group, role, color)
        return palette
