"""Plain-text SQL editor with line numbers, syntax highlighting and
autocompletion."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QFontDatabase,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextCursor,
)
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from querylean.completion.completion_engine import CompletionEngine
from querylean.completion.completion_item import CompletionItem
from querylean.completion.completion_result import CompletionResult
from querylean.completion.sql_scanner import SqlScanner
from querylean.completion.statement_analyzer import StatementAnalyzer
from querylean.completion.statement_context import StatementContext
from querylean.ui.editor.line_number_area import LineNumberArea
from querylean.ui.editor.sql_completer import SqlCompleter
from querylean.ui.editor.sql_highlighter import SqlHighlighter


class SqlEditor(QPlainTextEdit):
    """Monospaced editor. Emits ``execute_requested`` on Ctrl/Cmd+Enter.

    Autocompletion (with a ``CompletionEngine``): Ctrl+Space opens the
    proposals (a single proposal is inserted at once); while typing they
    open by themselves after a dot or after the first letters of a name.
    Enter or Tab accepts, Esc closes, the arrows move in the list. When a
    proposal needs columns that are not loaded yet, ``columns_needed`` is
    emitted and ``refresh_completion`` updates the list once they arrive.
    """

    execute_requested = Signal()
    columns_needed = Signal(str)  # table name

    PLACEHOLDER = "Write a SELECT query: Ctrl+Space completes, Ctrl+Enter "
    PLACEHOLDER += "runs (Cmd+Enter on macOS)"
    # Delay before the proposals open by themselves while typing.
    AUTO_DELAY_MS = 80
    __MIN_FONT_SIZE = 11
    __TAB_WIDTH = 4
    # Letters to type before proposals open by themselves: names (columns,
    # tables) need one, keywords two.
    __NAME_CONTEXTS = (
        StatementContext.EXPRESSION,
        StatementContext.QUALIFIED,
        StatementContext.TABLE_NAME,
        StatementContext.SUBQUERY,
    )
    __KEYWORD_MIN = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(max(font.pointSize(), SqlEditor.__MIN_FONT_SIZE))
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * SqlEditor.__TAB_WIDTH
        )
        self.setPlaceholderText(SqlEditor.PLACEHOLDER)
        self.__highlighter = SqlHighlighter(self.document())
        self.__line_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.__update_margin)
        self.updateRequest.connect(self.__update_line_area)
        self.__update_margin()

        self.__engine: CompletionEngine | None = None
        self.__auto_completion = True
        # The open list was asked with Ctrl+Space (it then stays open with
        # an empty word and inserts a single proposal at once).
        self.__manual = False
        # A Ctrl+Space request is waiting for columns being loaded.
        self.__awaiting_columns = False
        self.__completer = SqlCompleter(self)
        self.__completer.item_chosen.connect(self.apply_completion)
        self.__auto_timer = QTimer(self)
        self.__auto_timer.setSingleShot(True)
        self.__auto_timer.setInterval(SqlEditor.AUTO_DELAY_MS)
        self.__auto_timer.timeout.connect(self.__auto_complete)

    @property
    def completion_engine(self) -> CompletionEngine | None:
        """Engine of the proposals (None disables the completion)."""
        return self.__engine

    @completion_engine.setter
    def completion_engine(self, value: CompletionEngine | None) -> None:
        self.__engine = value
        if value is None:
            self.hide_completion()

    @property
    def auto_completion(self) -> bool:
        """True when proposals open by themselves while typing."""
        return self.__auto_completion

    @auto_completion.setter
    def auto_completion(self, value: bool) -> None:
        self.__auto_completion = value
        if not value:
            self.__auto_timer.stop()

    @property
    def completer(self) -> SqlCompleter:
        """Popup list of the proposals."""
        return self.__completer

    def complete(self, *, manual: bool = True) -> CompletionResult | None:
        """Compute the proposals at the cursor and show them. With
        ``manual`` (Ctrl+Space) a single proposal is inserted directly and
        an empty word is accepted. Returns the result (None without
        engine)."""
        self.__auto_timer.stop()
        result = self.__result()
        if result is None:
            return None
        self.__request_columns(result)
        self.__awaiting_columns = manual and bool(result.missing_tables)
        items = result.items
        if not items:
            self.__completer.hide_popup()
            return result
        if manual and len(items) == 1 and not result.missing_tables:
            self.apply_completion(items[0])
            return result
        self.__manual = manual
        self.__show(result)
        return result

    def refresh_completion(self) -> None:
        """Recompute the open list (e.g. after columns were loaded); a
        Ctrl+Space request still waiting for columns is answered now."""
        if self.__completer.visible:
            self.__update_open_list()
        elif self.__awaiting_columns and self.hasFocus():
            self.complete(manual=True)

    def hide_completion(self) -> None:
        """Close the proposals."""
        self.__auto_timer.stop()
        self.__awaiting_columns = False
        self.__completer.hide_popup()

    def apply_completion(self, item: CompletionItem) -> None:
        """Replace the word at the cursor with ``item`` (one undoable
        edit)."""
        self.hide_completion()
        cursor = self.textCursor()
        context = StatementAnalyzer.analyze(
            self.toPlainText(), cursor.position()
        )
        cursor.beginEditBlock()
        cursor.setPosition(context.start)
        cursor.setPosition(context.end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(item.insert_text)
        if item.caret_back:
            cursor.movePosition(
                QTextCursor.MoveOperation.Left,
                QTextCursor.MoveMode.MoveAnchor,
                item.caret_back,
            )
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def insert_text(self, text: str) -> None:
        """Insert ``text`` at the cursor (replacing the selection)."""
        self.hide_completion()
        self.textCursor().insertText(text)
        self.setFocus()

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

    def replace_query(self, text: str) -> None:
        """Replace the whole content with ``text`` as one edit, so that
        Ctrl/Cmd+Z restores the previous query; the cursor goes to the
        end."""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(text)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        # On macOS Qt maps Cmd to ControlModifier.
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.hide_completion()
            self.execute_requested.emit()
            return
        if SqlEditor.is_completion_shortcut(event):
            event.accept()
            self.complete(manual=True)
            return
        was_open = self.__completer.visible
        if was_open:
            if key == Qt.Key.Key_Escape:
                event.accept()
                self.hide_completion()
                return
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                item = self.__completer.current_item()
                if item is not None:
                    event.accept()
                    self.apply_completion(item)
                    return
                self.hide_completion()
            elif key == Qt.Key.Key_Backtab:
                self.hide_completion()
        super().keyPressEvent(event)
        text = event.text()
        if was_open:
            if text and not (
                SqlScanner.is_identifier_char(text) or text in ".`"
            ):
                self.hide_completion()
            elif key not in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                self.__update_open_list()
        elif self.__auto_completion and text and self.__engine is not None:
            if text == "." or SqlScanner.is_identifier_char(text):
                self.__auto_timer.start()
            else:
                self.__auto_timer.stop()

    @staticmethod
    def is_completion_shortcut(event: QKeyEvent) -> bool:
        """Ctrl+Space; on macOS the physical Control key (Qt reports it as
        Meta, since Cmd is mapped to Control)."""
        if event.key() != Qt.Key.Key_Space:
            return False
        modifiers = event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
        return modifiers in (
            Qt.KeyboardModifier.ControlModifier,
            Qt.KeyboardModifier.MetaModifier,
        )

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self.__auto_timer.stop()
        super().focusOutEvent(event)

    # ----------------------------------------------------------- completion
    def __result(self) -> CompletionResult | None:
        if self.__engine is None:
            return None
        return self.__engine.complete(
            self.toPlainText(), self.textCursor().position()
        )

    def __request_columns(self, result: CompletionResult) -> None:
        for table in result.missing_tables:
            self.columns_needed.emit(table)

    def __auto_complete(self) -> None:
        """Open the proposals while typing, when they are useful."""
        if not self.hasFocus() or self.__completer.visible:
            return
        result = self.__result()
        if result is None:
            return
        self.__request_columns(result)
        context = result.context
        cursor = self.textCursor().position()
        after_dot = cursor > 0 and self.toPlainText()[cursor - 1] == "."
        if after_dot:
            wanted = context.kind == StatementContext.QUALIFIED
        elif context.kind in SqlEditor.__NAME_CONTEXTS:
            wanted = len(context.prefix) >= 1
        else:
            wanted = len(context.prefix) >= SqlEditor.__KEYWORD_MIN
        if not wanted or not SqlEditor.__worth_showing(result):
            return
        self.__manual = False
        self.__show(result)

    def __update_open_list(self) -> None:
        """Recompute the open list after the text or cursor changed."""
        result = self.__result()
        if result is None:
            self.hide_completion()
            return
        self.__request_columns(result)
        context = result.context
        keep = bool(result.items) and (
            self.__manual
            or context.kind == StatementContext.QUALIFIED
            or bool(context.prefix)
        )
        if not keep or (
            not self.__manual and not SqlEditor.__worth_showing(result)
        ):
            self.hide_completion()
            return
        self.__show(result)

    @staticmethod
    def __worth_showing(result: CompletionResult) -> bool:
        """False without proposals or when the word is already complete
        (the best proposal is exactly what was typed)."""
        if not result.items:
            return False
        prefix = result.prefix.casefold()
        return not (prefix and result.items[0].label.casefold() == prefix)

    def __show(self, result: CompletionResult) -> None:
        cursor = QTextCursor(self.document())
        cursor.setPosition(result.start)
        rect = self.cursorRect(cursor)
        rect.translate(self.viewport().geometry().topLeft())
        self.__completer.show_items(result.items, rect)

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
