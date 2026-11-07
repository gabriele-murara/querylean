"""GUI tests of placeholders in the SQL editor."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog, QMessageBox

from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_type import PlaceholderType
from querylean.completion.completion_engine import CompletionEngine
from querylean.completion.schema_model import SchemaModel
from querylean.database.schema.column_info import ColumnInfo
from querylean.database.schema.table_info import TableInfo
from querylean.ui.dialogs.make_placeholders_dialog import (
    MakePlaceholdersDialog,
)
from querylean.ui.editor.sql_editor import SqlEditor
from querylean.ui.editor.sql_highlighter import SqlHighlighter


class TestSqlEditorPlaceholders:
    """Make placeholder, suggested names, highlighting, no completion."""

    SQL = "SELECT * FROM calls WHERE cli = '3391234567' AND year = 2026"

    @pytest.fixture
    def editor(self, qtbot) -> SqlEditor:
        editor = SqlEditor()
        qtbot.addWidget(editor)
        editor.show()
        return editor

    @staticmethod
    def select(editor, text, value):
        editor.setPlainText(text)
        start = text.index(value)
        cursor = editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(start + len(value), cursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)

    def test_make_placeholder_with_suggested_name(self, editor, monkeypatch):
        self.select(editor, self.SQL, "3391234567")
        asked = []

        def get_text(parent, title, label, text=""):
            asked.append(text)
            return text, True

        monkeypatch.setattr(QInputDialog, "getText", get_text)
        placeholder = editor.make_placeholder()
        assert asked == ["CLI"]
        assert placeholder.name == "CLI"
        assert editor.toPlainText().endswith("cli = '${CLI}' AND year = 2026")
        # The cursor is after the placeholder.
        position = editor.textCursor().position()
        assert editor.toPlainText()[:position].endswith("${CLI}")
        # One undo restores the value.
        editor.undo()
        assert editor.toPlainText() == self.SQL

    def test_typed_placeholder_is_remembered(self, editor):
        self.select(editor, self.SQL, "2026")
        placeholder = editor.make_placeholder("YEAR")
        assert placeholder.kind is PlaceholderType.INTEGER
        assert editor.placeholders() == {"YEAR": placeholder}
        # Gone from the text: forgotten.
        editor.setPlainText("SELECT 1")
        assert editor.placeholders() == {}

    def test_shortcut_and_context_menu(self, qtbot, editor, monkeypatch):
        action = editor.make_placeholder_action
        assert (
            action.shortcut().toString() == SqlEditor.MAKE_PLACEHOLDER_SHORTCUT
        )
        assert action in editor.actions()
        self.select(editor, self.SQL, "2026")
        monkeypatch.setattr(
            QInputDialog, "getText", lambda *a, **k: ("Y", True)
        )
        editor.setFocus()
        qtbot.waitUntil(editor.hasFocus)
        qtbot.keyClick(
            editor,
            Qt.Key.Key_P,
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier,
        )
        assert "${Y}" in editor.toPlainText()

    def test_invalid_selection_is_explained(self, editor, monkeypatch):
        warnings = []
        monkeypatch.setattr(
            QMessageBox, "warning", lambda *a: warnings.append(a[2])
        )
        self.select(editor, self.SQL, "calls")
        assert editor.make_placeholder("X") is None
        self.select(editor, self.SQL, "2026")
        assert editor.make_placeholder("1X") is None
        assert len(warnings) == 2
        assert editor.toPlainText() == self.SQL

    def test_cancelled_name_changes_nothing(self, editor, monkeypatch):
        self.select(editor, self.SQL, "2026")
        monkeypatch.setattr(
            QInputDialog, "getText", lambda *a, **k: ("", False)
        )
        assert editor.make_placeholder() is None
        assert editor.toPlainText() == self.SQL

    def test_remembered_definitions(self, editor):
        editor.setPlainText("SELECT ${A}")
        known = Placeholder("A", PlaceholderType.DATE, default="2026-01-01")
        editor.remember_placeholders((known,))
        assert editor.placeholders() == {"A": known}

    def test_placeholders_are_highlighted(self, qtbot, editor):
        editor.setPlainText("SELECT '${A}', ${B} -- ${C}")
        qtbot.wait(10)
        block = editor.document().firstBlock()
        formats = block.layout().formats()

        def color_at(position):
            for item in formats:
                if item.start <= position < item.start + item.length:
                    return item.format.foreground().color().name()
            return None

        text = block.text()
        placeholder = SqlHighlighter.PLACEHOLDER_COLOR
        assert color_at(text.index("${A}")) == placeholder
        assert color_at(text.index("${B}")) == placeholder
        assert color_at(text.index("${C}")) != placeholder  # comment

    def test_no_completion_inside_a_placeholder(self, qtbot, editor):
        schema = SchemaModel()
        schema.set_tables([TableInfo("t")])
        schema.set_columns("t", (ColumnInfo("year"),))
        editor.completion_engine = CompletionEngine(schema)
        editor.setPlainText("SELECT * FROM t WHERE year = ${YE")
        editor.moveCursor(editor.textCursor().MoveOperation.End)
        result = editor.complete()
        assert result.items == ()

    def test_without_selection_every_value_is_offered(
        self, qtbot, editor, monkeypatch
    ):
        sql = "SELECT * FROM calls WHERE cli = '3391234567' "
        sql += "AND code IN (12, 15) LIMIT 10"
        editor.setPlainText(sql)
        opened = []

        def choose(dialog):
            opened.append(dialog)
            assert dialog.table.rowCount() == 3
            # Compared values are checked, LIMIT is not.
            assert [dialog.use_box(r).isChecked() for r in range(3)] == [
                True,
                True,
                False,
            ]
            dialog.name_edit(1).setText("CODES")
            return MakePlaceholdersDialog.DialogCode.Accepted

        monkeypatch.setattr(MakePlaceholdersDialog, "exec", choose)
        editor.setFocus()
        qtbot.waitUntil(editor.hasFocus)
        qtbot.keyClick(
            editor,
            Qt.Key.Key_P,
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier,
        )
        assert len(opened) == 1
        expected = "SELECT * FROM calls WHERE cli = ${CLI} "
        expected += "AND code IN (${CODES}) LIMIT 10"
        assert editor.toPlainText() == expected
        made = editor.placeholders()
        assert made["CODES"].is_list
        assert made["CODES"].kind is PlaceholderType.INTEGER
        assert made["CLI"].default == "3391234567"
        # One undo restores every value.
        editor.undo()
        assert editor.toPlainText() == sql

    def test_cancelled_dialog_changes_nothing(self, editor, monkeypatch):
        editor.setPlainText(self.SQL)
        monkeypatch.setattr(
            MakePlaceholdersDialog,
            "exec",
            lambda d: MakePlaceholdersDialog.DialogCode.Rejected,
        )
        assert editor.make_placeholder() is None
        assert editor.toPlainText() == self.SQL

    def test_query_without_values_is_explained(self, editor, monkeypatch):
        warnings = []
        monkeypatch.setattr(
            QMessageBox, "warning", lambda *a: warnings.append(a[2])
        )
        editor.setPlainText("SELECT a FROM t -- 2026")
        assert editor.make_placeholders() == ()
        assert len(warnings) == 1 and "no values" in warnings[0]
