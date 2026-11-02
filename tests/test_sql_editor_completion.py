"""GUI tests of the autocompletion inside the SQL editor."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from querylean.completion.completion_engine import CompletionEngine
from querylean.completion.schema_model import SchemaModel
from querylean.database.schema.column_info import ColumnInfo
from querylean.database.schema.table_info import TableInfo
from querylean.ui.editor.sql_editor import SqlEditor


class TestSqlEditorCompletion:
    """Ctrl+Space, automatic opening, keys, insertion, lazy columns."""

    @pytest.fixture
    def schema(self) -> SchemaModel:
        schema = SchemaModel()
        schema.database = "app"
        schema.set_tables(
            [TableInfo("users"), TableInfo("orders"), TableInfo("invoices")]
        )
        schema.set_all_columns(
            {
                "users": (
                    ColumnInfo("id", "int", key="PRI"),
                    ColumnInfo("name", "varchar(64)"),
                    ColumnInfo("email", "varchar(255)"),
                ),
                "orders": (ColumnInfo("id", "int"), ColumnInfo("total")),
            }
        )
        return schema

    @pytest.fixture
    def editor(self, qtbot, schema) -> SqlEditor:
        editor = SqlEditor()
        qtbot.addWidget(editor)
        editor.completion_engine = CompletionEngine(schema)
        editor.resize(600, 300)
        editor.show()
        editor.setFocus()
        qtbot.waitUntil(editor.hasFocus)
        return editor

    @staticmethod
    def type_text(qtbot, editor, text) -> None:
        qtbot.keyClicks(editor, text)

    @staticmethod
    def ctrl_space(qtbot, editor) -> None:
        qtbot.keyClick(
            editor, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier
        )

    @staticmethod
    def wait_open(qtbot, editor) -> None:
        qtbot.waitUntil(lambda: editor.completer.visible, timeout=2000)

    @staticmethod
    def labels(editor) -> list[str]:
        return [item.label for item in editor.completer.items]

    def test_shortcut(self):
        for modifier in (
            Qt.KeyboardModifier.ControlModifier,
            Qt.KeyboardModifier.MetaModifier,
        ):
            event = QKeyEvent(
                QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, modifier, " "
            )
            assert SqlEditor.is_completion_shortcut(event)
        for key, modifier in (
            (Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier),
            (
                Qt.Key.Key_Space,
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.ShiftModifier,
            ),
            (Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier),
        ):
            event = QKeyEvent(QKeyEvent.Type.KeyPress, key, modifier, "")
            assert not SqlEditor.is_completion_shortcut(event)

    def test_ctrl_space_opens_and_enter_accepts(self, qtbot, editor):
        editor.setPlainText("SELECT  FROM users u")
        cursor = editor.textCursor()
        cursor.setPosition(7)
        editor.setTextCursor(cursor)
        self.ctrl_space(qtbot, editor)
        self.wait_open(qtbot, editor)
        assert self.labels(editor)[:3] == ["id", "name", "email"]
        qtbot.keyClick(editor.completer.popup(), Qt.Key.Key_Down)
        qtbot.keyClick(editor, Qt.Key.Key_Return)
        assert editor.toPlainText() == "SELECT name FROM users u"
        assert not editor.completer.visible
        # One undo restores the text before the completion.
        editor.undo()
        assert editor.toPlainText() == "SELECT  FROM users u"

    def test_single_proposal_is_inserted_at_once(self, qtbot, editor):
        editor.setPlainText("SELECT * FROM users WHERE ema")
        editor.moveCursor(editor.textCursor().MoveOperation.End)
        self.ctrl_space(qtbot, editor)
        assert editor.toPlainText() == "SELECT * FROM users WHERE email"
        assert not editor.completer.visible

    def test_opens_while_typing_and_filters(self, qtbot, editor):
        self.type_text(qtbot, editor, "SELECT * FROM ord")
        self.wait_open(qtbot, editor)
        assert self.labels(editor) == ["orders"]
        qtbot.keyClick(editor, Qt.Key.Key_Tab)
        assert editor.toPlainText() == "SELECT * FROM orders"

    def test_opens_after_a_dot(self, qtbot, editor):
        self.type_text(qtbot, editor, "SELECT * FROM users u WHERE u.")
        self.wait_open(qtbot, editor)
        assert self.labels(editor) == ["id", "name", "email"]
        self.type_text(qtbot, editor, "e")
        assert self.labels(editor) == ["email"]
        qtbot.keyClick(editor, Qt.Key.Key_Return)
        assert editor.toPlainText().endswith("u.email")

    def test_typing_a_separator_closes_the_list(self, qtbot, editor):
        self.type_text(qtbot, editor, "SELECT * FROM users WHERE na")
        self.wait_open(qtbot, editor)
        self.type_text(qtbot, editor, " ")
        assert not editor.completer.visible
        assert editor.toPlainText().endswith("na ")

    def test_escape_closes(self, qtbot, editor):
        self.type_text(qtbot, editor, "SELECT * FROM us")
        self.wait_open(qtbot, editor)
        qtbot.keyClick(editor, Qt.Key.Key_Escape)
        assert not editor.completer.visible
        assert editor.toPlainText() == "SELECT * FROM us"

    def test_complete_word_does_not_open(self, qtbot, editor):
        self.type_text(qtbot, editor, "SELECT * FROM users")
        qtbot.wait(SqlEditor.AUTO_DELAY_MS * 3)
        assert not editor.completer.visible
        # Enter goes to the next line.
        qtbot.keyClick(editor, Qt.Key.Key_Return)
        assert editor.toPlainText() == "SELECT * FROM users\n"

    def test_no_automatic_opening_in_strings(self, qtbot, editor):
        self.type_text(qtbot, editor, "SELECT * FROM users WHERE name = 'na")
        qtbot.wait(SqlEditor.AUTO_DELAY_MS * 3)
        assert not editor.completer.visible

    def test_automatic_opening_can_be_disabled(self, qtbot, editor):
        editor.auto_completion = False
        self.type_text(qtbot, editor, "SELECT * FROM ord")
        qtbot.wait(SqlEditor.AUTO_DELAY_MS * 3)
        assert not editor.completer.visible
        self.ctrl_space(qtbot, editor)
        assert editor.toPlainText() == "SELECT * FROM orders"

    def test_ctrl_enter_still_runs(self, qtbot, editor):
        self.type_text(qtbot, editor, "SELECT * FROM us")
        self.wait_open(qtbot, editor)
        with qtbot.waitSignal(editor.execute_requested):
            qtbot.keyClick(
                editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier
            )
        assert not editor.completer.visible
        assert editor.toPlainText() == "SELECT * FROM us"

    def test_function_puts_the_cursor_inside(self, qtbot, editor):
        editor.setPlainText("SELECT COU FROM users")
        cursor = editor.textCursor()
        cursor.setPosition(10)
        editor.setTextCursor(cursor)
        self.ctrl_space(qtbot, editor)
        self.wait_open(qtbot, editor)
        qtbot.keyClick(editor, Qt.Key.Key_Return)
        assert editor.toPlainText() == "SELECT COUNT() FROM users"
        assert editor.textCursor().position() == len("SELECT COUNT(")

    def test_word_after_the_cursor_is_replaced(self, qtbot, editor):
        editor.setPlainText("SELECT * FROM users WHERE emxyz")
        cursor = editor.textCursor()
        cursor.setPosition(len("SELECT * FROM users WHERE em"))
        editor.setTextCursor(cursor)
        self.ctrl_space(qtbot, editor)
        assert editor.toPlainText() == "SELECT * FROM users WHERE email"

    def test_missing_columns_are_requested_then_shown(
        self, qtbot, editor, schema
    ):
        editor.setPlainText("SELECT i. FROM invoices i")
        cursor = editor.textCursor()
        cursor.setPosition(9)
        editor.setTextCursor(cursor)
        with qtbot.waitSignal(editor.columns_needed) as blocker:
            self.ctrl_space(qtbot, editor)
        assert blocker.args == ["invoices"]
        assert not editor.completer.visible
        schema.set_columns(
            "invoices", (ColumnInfo("number"), ColumnInfo("issued"))
        )
        editor.refresh_completion()
        self.wait_open(qtbot, editor)
        assert self.labels(editor) == ["number", "issued"]

    def test_mouse_choice(self, qtbot, editor):
        self.type_text(qtbot, editor, "SELECT * FROM users WHERE na")
        self.wait_open(qtbot, editor)
        editor.completer.item_chosen.emit(editor.completer.items[0])
        assert editor.toPlainText() == "SELECT * FROM users WHERE name"

    def test_without_engine_nothing_happens(self, qtbot, editor):
        editor.completion_engine = None
        self.type_text(qtbot, editor, "SELECT * FROM us")
        self.ctrl_space(qtbot, editor)
        assert not editor.completer.visible
        assert editor.toPlainText() == "SELECT * FROM us"

    def test_insert_text(self, qtbot, editor):
        editor.setPlainText("SELECT  FROM t")
        cursor = editor.textCursor()
        cursor.setPosition(7)
        editor.setTextCursor(cursor)
        editor.insert_text("`my col`")
        assert editor.toPlainText() == "SELECT `my col` FROM t"
