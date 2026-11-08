"""Outcome line of a dialog: green when it can go on, red otherwise."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget


class StatusLabel(QLabel):
    """Word-wrapped plain-text label (the messages may quote names or SQL
    typed by the user or sent by the server: never rendered as HTML).
    ``show_status`` colours it green for success and red for a problem;
    ``show_neutral`` uses the normal text colour. ``HINT_STYLE`` is the
    muted colour of hints, shared by the other widgets."""

    OK_COLOR = "#1a7f37"
    ERROR_COLOR = "#c62828"
    # Muted text of hints and descriptions, also outside the dialogs.
    HINT_STYLE = "color: palette(placeholder-text);"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)

    def show_status(self, ok: bool, message: str) -> None:
        """Show ``message`` in green (``ok``) or red."""
        color = StatusLabel.OK_COLOR if ok else StatusLabel.ERROR_COLOR
        self.setStyleSheet("color: {};".format(color))
        self.setText(message)

    def show_neutral(self, message: str) -> None:
        """Show ``message`` in the normal text colour."""
        self.setStyleSheet("")
        self.setText(message)
