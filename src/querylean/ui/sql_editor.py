"""Editor SQL con numeri di riga ed evidenziazione sintattica di base."""

from __future__ import annotations

import re

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)
from PySide6.QtWidgets import QPlainTextEdit, QWidget

SQL_KEYWORDS = (
    "ADD ALL AND ANY AS ASC BETWEEN BINARY BY CASE CAST COLLATE CREATE CROSS CURRENT_DATE "
    "CURRENT_TIME CURRENT_TIMESTAMP DATABASE DATABASES DEFAULT DELETE DESC DESCRIBE DISTINCT "
    "DIV DROP ELSE END ESCAPE EXCEPT EXISTS EXPLAIN FALSE FOR FROM FULL GROUP HAVING IF IN "
    "INDEX INNER INSERT INTERSECT INTERVAL INTO IS JOIN KEY LATERAL LEFT LIKE LIMIT MOD "
    "NATURAL NOT NULL OFFSET ON OR ORDER OUTER OVER PARTITION RECURSIVE REGEXP RIGHT ROLLUP "
    "ROW ROWS SELECT SET SHOW STATUS STRAIGHT_JOIN TABLE TABLES THEN TRUE UNION UNIQUE "
    "UPDATE USING VALUES VARIABLES VIEW WHEN WHERE WINDOW WITH XOR"
).split()


class SqlHighlighter(QSyntaxHighlighter):
    _IN_COMMENT = 1

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._keyword = _fmt("#0033b3", bold=True)
        self._string = _fmt("#067d17")
        self._number = _fmt("#1750eb")
        self._comment = _fmt("#8c8c8c", italic=True)
        self._keyword_re = re.compile(r"\b(?:" + "|".join(SQL_KEYWORDS) + r")\b", re.IGNORECASE)
        self._number_re = re.compile(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b")
        # Stringhe, identificatori quotati e commenti di riga, in ordine di apparizione.
        self._span_re = re.compile(
            r"'(?:\\.|''|[^'\\])*'?|\"(?:\\.|\"\"|[^\"\\])*\"?|`(?:``|[^`])*`?"
            r"|#.*$|--(?:\s.*)?$|/\*"
        )

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (API Qt)
        for match in self._keyword_re.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), self._keyword)
        for match in self._number_re.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), self._number)

        self.setCurrentBlockState(0)
        pos = 0
        if self.previousBlockState() == self._IN_COMMENT:
            pos = self._comment_to_end(text, 0, continuing=True)
        while pos < len(text):
            match = self._span_re.search(text, pos)
            if not match:
                break
            token = match.group()
            if token == "/*":
                pos = self._comment_to_end(text, match.start(), continuing=False)
                continue
            fmt = self._comment if token[0] in "#-" else self._string
            if token[0] == "`":
                fmt = QTextCharFormat()  # identificatori quotati: nessuna evidenziazione
            self.setFormat(match.start(), len(token), fmt)
            pos = match.end()

    def _comment_to_end(self, text: str, start: int, *, continuing: bool) -> int:
        """Colora un commento /* */ da `start`; restituisce la posizione successiva."""
        end = text.find("*/", start if continuing else start + 2)
        if end < 0:
            self.setCurrentBlockState(self._IN_COMMENT)
            self.setFormat(start, len(text) - start, self._comment)
            return len(text)
        self.setFormat(start, end + 2 - start, self._comment)
        return end + 2


def _fmt(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    fmt.setFontItalic(italic)
    return fmt


class _LineNumberArea(QWidget):
    def __init__(self, editor: SqlEditor) -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        self._editor.paint_line_numbers(event)


class SqlEditor(QPlainTextEdit):
    """Editor monospazio. Emette `execute_requested` con Ctrl/Cmd+Invio."""

    execute_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(max(font.pointSize(), 11))
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setPlaceholderText("Scrivi una query SELECT e premi Ctrl+Invio (Cmd+Invio su macOS)")
        self.highlighter = SqlHighlighter(self.document())

        self._line_area = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._update_line_area)
        self._update_margin()

    # -- testo da eseguire -------------------------------------------------------
    def query_text(self) -> str:
        """La selezione, se presente; altrimenti l'intero contenuto."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            # Qt usa U+2029 come separatore di paragrafo nella selezione.
            return cursor.selectedText().replace("\u2029", "\n").replace("\u2028", "\n")
        return self.toPlainText()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        # Su macOS Qt mappa Cmd su ControlModifier.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.execute_requested.emit()
            return
        super().keyPressEvent(event)

    # -- numeri di riga -----------------------------------------------------------
    def line_number_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * max(digits, 2)

    def _update_margin(self, *_: object) -> None:
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_line_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_width(),
                                          cr.height()))

    def paint_line_numbers(self, event: QPaintEvent) -> None:
        painter = QPainter(self._line_area)
        palette = self.palette()
        painter.fillRect(event.rect(), palette.alternateBase())
        painter.setPen(palette.placeholderText().color())
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        height = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(0, top, self._line_area.width() - 6, height,
                                 Qt.AlignmentFlag.AlignRight, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1
        painter.end()
