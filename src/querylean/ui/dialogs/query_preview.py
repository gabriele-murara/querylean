"""Read-only, monospaced preview of a query in a dialog."""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QPlainTextEdit, QWidget


class QueryPreview(QPlainTextEdit):
    """Shows a query (compiled mask, query with placeholders) that the user
    reads but does not edit; plain text, so nothing is interpreted."""

    DEFAULT_MAX_HEIGHT = 140

    def __init__(
        self,
        max_height: int = DEFAULT_MAX_HEIGHT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.setMaximumHeight(max_height)
