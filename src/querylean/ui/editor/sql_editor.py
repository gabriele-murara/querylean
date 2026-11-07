"""Plain-text SQL editor with line numbers, syntax highlighting and
autocompletion."""

from __future__ import annotations

import html
import re

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QContextMenuEvent,
    QFontDatabase,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextCursor,
)
from PySide6.QtWidgets import QInputDialog, QMessageBox, QPlainTextEdit, QWidget

from querylean.bookmarks.mask_error import MaskError
from querylean.bookmarks.mask_template import MaskTemplate
from querylean.bookmarks.placeholder import Placeholder
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
    proposal needs columns (or tables) that are not loaded yet,
    ``columns_needed`` (or ``tables_needed``) is emitted and
    ``refresh_completion`` updates the list once they arrive.
    """

    execute_requested = Signal()
    columns_needed = Signal(str, str)  # database, table
    tables_needed = Signal(str)  # database

    PLACEHOLDER = "Write a SELECT query: Ctrl+Space completes, Ctrl+Enter "
    PLACEHOLDER += "runs (Cmd+Enter on macOS)"
    MAKE_PLACEHOLDER_TEXT = "Make placeholder…"
    MAKE_PLACEHOLDER_SHORTCUT = "Ctrl+Shift+P"
    DEFAULT_PLACEHOLDER_NAME = "VALUE"
    # Column compared with the selected value: suggests the placeholder
    # name (``cli = '…'`` → ``CLI``).
    __COLUMN_PATTERN = r"([A-Za-z_][A-Za-z0-9_]*)`?\s*"
    __COLUMN_PATTERN += r"(?:=|<>|!=|<=|>=|<|>|\bLIKE|\bIN\s*\(|\bBETWEEN)"
    __COLUMN_PATTERN += r"\s*['\"]?\s*$"
    __COMPARED_COLUMN = re.compile(__COLUMN_PATTERN, re.IGNORECASE)
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

        # Placeholders made from a selected value: type and example value
        # are kept for the "Save mask" dialog.
        self.__placeholders: dict[str, Placeholder] = {}
        self.__make_placeholder_action = QAction(
            SqlEditor.MAKE_PLACEHOLDER_TEXT, self
        )
        self.__make_placeholder_action.setShortcut(
            QKeySequence(SqlEditor.MAKE_PLACEHOLDER_SHORTCUT)
        )
        self.__make_placeholder_action.setShortcutContext(
            Qt.ShortcutContext.WidgetShortcut
        )
        self.__make_placeholder_action.triggered.connect(
            lambda: self.make_placeholder()
        )
        self.addAction(self.__make_placeholder_action)

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
        waiting = result.missing_tables or result.missing_databases
        self.__awaiting_columns = manual and bool(waiting)
        items = result.items
        if not items:
            self.__completer.hide_popup()
            return result
        if manual and len(items) == 1 and not waiting:
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
        # "db." continues with the tables of that database.
        if item.insert_text.endswith(".") and self.__auto_completion:
            self.__auto_timer.start()

    @property
    def make_placeholder_action(self) -> QAction:
        """ "Make placeholder…" action (Ctrl+Shift+P)."""
        return self.__make_placeholder_action

    def placeholders(self) -> dict[str, Placeholder]:
        """Placeholders made in this editor that are still in the text,
        by name (type and example value for the "Save mask" dialog)."""
        try:
            names = MaskTemplate(self.toPlainText()).names
        except MaskError:
            return {}
        return {
            name: self.__placeholders[name]
            for name in names
            if name in self.__placeholders
        }

    def remember_placeholders(
        self, placeholders: tuple[Placeholder, ...]
    ) -> None:
        """Keep the definitions of ``placeholders`` (e.g. of a mask loaded
        from the bookmarks) for the next "Save mask" dialog."""
        for placeholder in placeholders:
            self.__placeholders[placeholder.name] = placeholder

    def make_placeholder(self, name: str | None = None) -> Placeholder | None:
        """Turn the selected value into a ``${NAME}`` placeholder (one
        undoable edit). Without ``name`` the user is asked for one,
        suggested from the column compared with the value. The type and
        the example come from the replaced value. Returns None when
        cancelled or when the selection is not a value (the reason is
        shown)."""
        cursor = self.textCursor()
        if not cursor.hasSelection():
            self.__warn("Select the value to turn into a placeholder.")
            return None
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        text = self.toPlainText()
        if name is None:
            name, ok = QInputDialog.getText(
                self,
                SqlEditor.MAKE_PLACEHOLDER_TEXT,
                "Placeholder name (letters, digits and _):",
                text=SqlEditor.__suggested_name(text[:start]),
            )
            if not ok:
                return None
        try:
            new_text, placeholder = MaskTemplate.make_placeholder(
                text, start, end, name.strip()
            )
        except MaskError as exc:
            self.__warn(exc.message)
            return None
        known = self.__placeholders.get(placeholder.name)
        if known is None or not known.default:
            self.__placeholders[placeholder.name] = placeholder
        tail = len(text) - end
        self.replace_query(new_text)
        cursor = self.textCursor()
        cursor.setPosition(len(new_text) - tail)
        self.setTextCursor(cursor)
        return placeholder

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        self.__make_placeholder_action.setEnabled(
            self.textCursor().hasSelection()
        )
        menu.addAction(self.__make_placeholder_action)
        menu.exec(event.globalPos())
        self.__make_placeholder_action.setEnabled(True)

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

    @staticmethod
    def __suggested_name(before: str) -> str:
        match = SqlEditor.__COMPARED_COLUMN.search(before)
        if match is None:
            return SqlEditor.DEFAULT_PLACEHOLDER_NAME
        return match.group(1).upper()

    def __warn(self, message: str) -> None:
        QMessageBox.warning(
            self, SqlEditor.MAKE_PLACEHOLDER_TEXT, html.escape(message)
        )

    def __request_columns(self, result: CompletionResult) -> None:
        for database, table in result.missing_tables:
            self.columns_needed.emit(database, table)
        for database in result.missing_databases:
            self.tables_needed.emit(database)

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
