"""Small badges for the kinds of completion proposals and columns."""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPixmap

from querylean.completion.completion_kind import CompletionKind


class CompletionIcons:
    """Rounded badges with a letter, drawn with QPainter (no assets):
    one color and letter per proposal kind. Icons are cached."""

    SIZE = 32
    __STYLES: ClassVar[dict[CompletionKind, tuple[str, str]]] = {
        CompletionKind.COLUMN: ("#1565c0", "c"),
        CompletionKind.KEY_COLUMN: ("#f9a825", "P"),
        CompletionKind.TABLE: ("#2e7d32", "T"),
        CompletionKind.VIEW: ("#00897b", "V"),
        CompletionKind.CTE: ("#6d4c41", "Q"),
        CompletionKind.ALIAS: ("#546e7a", "a"),
        CompletionKind.KEYWORD: ("#6a1b9a", "k"),
        CompletionKind.FUNCTION: ("#ef6c00", "f"),
        CompletionKind.DATABASE: ("#37474f", "D"),
    }
    __cache: ClassVar[dict[CompletionKind, QIcon]] = {}

    @staticmethod
    def icon(kind: CompletionKind) -> QIcon:
        """Badge of ``kind``."""
        cached = CompletionIcons.__cache.get(kind)
        if cached is None:
            color, letter = CompletionIcons.__STYLES[kind]
            cached = CompletionIcons.__render(color, letter)
            CompletionIcons.__cache[kind] = cached
        return cached

    @staticmethod
    def __render(color: str, letter: str) -> QIcon:
        size = CompletionIcons.SIZE
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(color)))
            painter.drawRoundedRect(QRectF(2, 2, size - 4, size - 4), 7, 7)
            painter.setPen(QColor("white"))
            font = QFont()
            font.setBold(True)
            font.setPixelSize(20)
            painter.setFont(font)
            painter.drawText(
                QRectF(0, 0, size, size),
                int(Qt.AlignmentFlag.AlignCenter),
                letter,
            )
        finally:
            painter.end()
        return QIcon(pixmap)
