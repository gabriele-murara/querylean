"""GUI tests of masks: bookmarked queries with placeholders."""

from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_type import PlaceholderType
from querylean.ui.dialogs.save_mask_dialog import SaveMaskDialog
from querylean.ui.main.bookmarks_menu import BookmarksMenu
from support.main_window_test_base import MainWindowTestBase


class TestMainWindowMasks(MainWindowTestBase):
    """Save through the dialog, refusal to run, loading from the menu."""

    MASK = "SELECT * FROM orders WHERE year = ${YEAR} AND code IN (${CODES})"
    PLACEHOLDERS = (
        Placeholder("YEAR", PlaceholderType.INTEGER, default="2026"),
        Placeholder("CODES", PlaceholderType.TEXT, default="A", is_list=True),
    )

    def executed(self, connector):
        return [s for conn in connector.connections for s in conn.executed]

    def test_mask_with_placeholders_is_saved(self, qtbot, window):
        self.connect(qtbot, window)
        window.editor.setPlainText(self.MASK)
        mask = window.save_bookmark("Orders", placeholders=self.PLACEHOLDERS)
        assert mask is not None and mask.is_mask
        assert mask.placeholders == self.PLACEHOLDERS
        assert "Mask saved" in window.message_label.text()
        assert window.bookmarks_menu.names() == ["Orders"]
        entry = window.bookmarks_menu.actions()[0]
        assert entry.text() == BookmarksMenu.MASK_LABEL.format("Orders")
        assert not entry.icon().isNull()
        assert "${YEAR}" in entry.toolTip()

    def test_save_query_opens_the_mask_dialog(self, qtbot, window, monkeypatch):
        self.connect(qtbot, window)
        window.editor.setPlainText(
            "SELECT * FROM orders WHERE year = 2026 AND code = 'A1'"
        )
        cursor = window.editor.textCursor()
        start = window.editor.toPlainText().index("2026")
        cursor.setPosition(start)
        cursor.setPosition(start + 4, cursor.MoveMode.KeepAnchor)
        window.editor.setTextCursor(cursor)
        window.editor.make_placeholder("YEAR")
        opened = []

        def fake_exec(dialog):
            opened.append(dialog)
            # Type and example come from the replaced value.
            assert dialog.default_edit("YEAR").text() == "2026"
            dialog.name_edit.setText("By year")
            return SaveMaskDialog.DialogCode.Accepted

        monkeypatch.setattr(SaveMaskDialog, "exec", fake_exec)
        window.save_query_action.trigger()
        assert len(opened) == 1
        saved = window.bookmarks[0]
        assert saved.name == "By year"
        assert saved.placeholders[0].kind is PlaceholderType.INTEGER

    def test_cancelled_dialog_saves_nothing(self, qtbot, window, monkeypatch):
        self.connect(qtbot, window)
        window.editor.setPlainText(self.MASK)
        monkeypatch.setattr(
            SaveMaskDialog, "exec", lambda d: SaveMaskDialog.DialogCode.Rejected
        )
        assert window.save_bookmark() is None
        assert window.bookmarks == []

    def test_invalid_masks_are_not_saved(self, qtbot, window, monkeypatch):
        self.connect(qtbot, window)
        window.editor.setPlainText("SELECT `${COL}` FROM t")
        assert window.save_bookmark("Bad", placeholders=()) is None
        assert "backticks" in window.message_label.text()
        window.editor.setPlainText("DELETE FROM t WHERE y = ${Y}")
        bad = (Placeholder("Y", PlaceholderType.INTEGER, default="1"),)
        assert window.save_bookmark("Bad", placeholders=bad) is None
        assert "Only read queries" in window.message_label.text()
        window.editor.setPlainText("SELECT ${Y}")
        no_default = (Placeholder("Y", PlaceholderType.INTEGER),)
        assert window.save_bookmark("Bad", placeholders=no_default) is None
        assert window.bookmarks == []

    def test_mask_is_not_run(self, qtbot, window, connector):
        self.connect(qtbot, window)
        before = len(self.executed(connector))
        window.editor.setPlainText(self.MASK)
        window.execute_query()
        assert not window.running
        text = window.message_label.text()
        assert "placeholders (${YEAR}, ${CODES})" in text
        assert len(self.executed(connector)) == before

    def test_mask_from_the_menu_is_loaded_not_run(
        self, qtbot, window, connector
    ):
        self.connect(qtbot, window)
        window.editor.setPlainText(self.MASK)
        window.save_bookmark("Orders", placeholders=self.PLACEHOLDERS)
        window.editor.setPlainText("SELECT 1")
        before = len(self.executed(connector))
        window.bookmarks_menu.actions()[0].trigger()
        assert window.editor.toPlainText() == self.MASK
        assert not window.running
        assert len(self.executed(connector)) == before
        assert "Mask “Orders” loaded" in window.message_label.text()
        # Saving it again keeps types, defaults and descriptions.
        assert window.editor.placeholders()["CODES"].is_list
