"""Plain-text SQL editor with line numbers and syntax highlighting."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import (
    QFontDatabase,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
)
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from querylean.ui.editor.line_number_area import LineNumberArea
from querylean.ui.editor.sql_highlighter import SqlHighlighter


class SqlEditor(QPlainTextEdit):
    """Monospaced editor. Emits ``execute_requested`` on Ctrl/Cmd+Enter."""

    execute_requested = Signal()

    __MIN_FONT_SIZE = 11
    __TAB_WIDTH = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(max(font.pointSize(), SqlEditor.__MIN_FONT_SIZE))
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * SqlEditor.__TAB_WIDTH
        )
        self.setPlaceholderText(
            "Scrivi una query SELECT e premi Ctrl+Invio (Cmd+Invio su macOS)"
        )
        self.__highlighter = SqlHighlighter(self.document())
        self.__line_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.__update_margin)
        self.updateRequest.connect(self.__update_line_area)
        self.__update_margin()

    @property
    def highlighter(self) -> SqlHighlighter:
        """Syntax highlighter attached to the document."""
        return self.__highlighter

    def query_text(self) -> str:
        """The selection if present, otherwise the whole content."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            # Qt uses U+2029 (and U+2028) as paragraph separators in selections.
            return (
                cursor.selectedText()
                .replace("\u2029", "\n")
                .replace("\u2028", "\n")
            )
        return self.toPlainText()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        # On macOS Qt maps Cmd to ControlModifier.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.execute_requested.emit()
            return
        super().keyPressEvent(event)

    def line_number_width(self) -> int:
        """Width of the line number gutter."""
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * max(digits, 2)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.__line_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_width(), cr.height())
        )

    def paint_line_numbers(self, event: QPaintEvent) -> None:
        """Paint the visible line numbers into the gutter."""
        painter = QPainter(self.__line_area)
        palette = self.palette()
        painter.fillRect(event.rect(), palette.alternateBase())
        painter.setPen(palette.placeholderText().color())
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(
            self.blockBoundingGeometry(block)
            .translated(self.contentOffset())
            .top()
        )
        bottom = top + round(self.blockBoundingRect(block).height())
        height = self.fontMetrics().height()
        width = self.__line_area.width() - 6
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    width,
                    height,
                    Qt.AlignmentFlag.AlignRight,
                    str(number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1
        painter.end()

    def __update_margin(self, *_: object) -> None:
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def __update_line_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.__line_area.scroll(0, dy)
        else:
            self.__line_area.update(
                0, rect.y(), self.__line_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self.__update_margin()
