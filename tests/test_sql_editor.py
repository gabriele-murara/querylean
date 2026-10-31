"""GUI tests of the SQL editor."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor

from querylean.ui.editor.sql_editor import SqlEditor


class TestSqlEditor:
    """Selection rules and execution shortcut."""

    def test_query_text_uses_selection_when_present(self, qtbot):
        editor = SqlEditor()
        qtbot.addWidget(editor)
        editor.setPlainText("DELETE FROM t\nSELECT n FROM t")
        assert editor.query_text() == "DELETE FROM t\nSELECT n FROM t"
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Down)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        assert editor.query_text() == "SELECT n FROM t"

    def test_ctrl_enter_requests_execution(self, qtbot):
        editor = SqlEditor()
        qtbot.addWidget(editor)
        with qtbot.waitSignal(editor.execute_requested, timeout=1000):
            qtbot.keyClick(editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
