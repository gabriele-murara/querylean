"""Tests of the dialog that chooses the bookmarks to export."""

import pytest
from PySide6.QtCore import Qt

from querylean.bookmarks.bookmark_entry import BookmarkEntry
from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.connection_config import ConnectionConfig
from querylean.config.connection_profile import ConnectionProfile
from querylean.ui.dialogs.export_bookmarks_dialog import (
    ExportBookmarksDialog,
)
from querylean.ui.safe_text import SafeText


class TestExportBookmarksDialog:
    """Rows, check boxes, filter and the "Export…" button."""

    NAME, TYPE, CONNECTION, TARGET, PLACEHOLDERS, QUERY = range(6)

    @pytest.fixture
    def entries(self) -> list[BookmarkEntry]:
        prod = ConnectionProfile(
            "a" * 32,
            ConnectionConfig(
                name="Prod", host="db", database="app", username="ro"
            ),
        )
        test = ConnectionProfile(
            "b" * 32,
            ConnectionConfig(host="db2", database="app", username="ro"),
        )
        mask = QueryBookmark(
            "Users",
            "SELECT *\nFROM users WHERE id IN (${IDS})",
            "ro@db:3306/app",
            (Placeholder("IDS", default="1", is_list=True),),
        )
        return [
            BookmarkEntry(prod, mask),
            BookmarkEntry(
                test, QueryBookmark("Users", "SELECT <b>1</b>", "t2")
            ),
        ]

    @pytest.fixture
    def dialog(self, qtbot, entries) -> ExportBookmarksDialog:
        widget = ExportBookmarksDialog(entries)
        qtbot.addWidget(widget)
        return widget

    def text(self, dialog, row, column) -> str:
        return dialog.table.item(row, column).text()

    def test_rows_tell_bookmarks_apart(self, dialog):
        table = dialog.table
        assert table.rowCount() == 2
        assert [self.text(dialog, r, self.NAME) for r in (0, 1)] == [
            "Users",
            "Users",
        ]
        assert (
            self.text(dialog, 0, self.TYPE) == ExportBookmarksDialog.MASK_TYPE
        )
        assert self.text(dialog, 1, self.TYPE) == (
            ExportBookmarksDialog.QUERY_TYPE
        )
        assert self.text(dialog, 0, self.CONNECTION) == "Prod"
        assert self.text(dialog, 1, self.CONNECTION) == "ro@db2/app"
        assert self.text(dialog, 0, self.TARGET) == "ro@db:3306/app"
        assert self.text(dialog, 0, self.PLACEHOLDERS) == "${IDS}"
        assert self.text(dialog, 1, self.PLACEHOLDERS) == ""
        query = "SELECT * FROM users WHERE id IN (${IDS})"
        assert self.text(dialog, 0, self.QUERY) == query
        item = table.item(1, self.QUERY)
        assert item.toolTip() == SafeText.tooltip("SELECT <b>1</b>")
        assert not item.flags() & Qt.ItemFlag.ItemIsEditable
        assert not table.item(0, self.NAME).icon().isNull()

    def test_everything_checked_at_first(self, dialog, entries):
        assert dialog.selected() == entries
        assert dialog.export_button.isEnabled()
        assert dialog.status.text() == "2 of 2 bookmarked queries selected."
        assert not dialog.include_last_values()

    def test_unchecking_disables_export(self, dialog, entries):
        dialog.set_checked(0, False)
        assert dialog.selected() == [entries[1]]
        assert dialog.status.text() == "1 of 2 bookmarked queries selected."
        dialog.select_none_button.click()
        assert dialog.selected() == []
        assert not dialog.export_button.isEnabled()
        dialog.accept()
        assert dialog.result() != ExportBookmarksDialog.DialogCode.Accepted
        dialog.select_all_button.click()
        assert dialog.selected() == entries

    def test_filter_and_select_visible_rows(self, dialog, entries):
        dialog.filter_edit.setText("PROD")
        assert not dialog.table.isRowHidden(0)
        assert dialog.table.isRowHidden(1)
        dialog.select_none_button.click()
        # Hidden rows keep their state and are still exported.
        assert dialog.selected() == [entries[1]]
        dialog.filter_edit.setText("db2")
        assert dialog.table.isRowHidden(0)
        dialog.filter_edit.setText("from users")
        assert not dialog.table.isRowHidden(0)
        dialog.filter_edit.clear()
        assert not any(dialog.table.isRowHidden(r) for r in (0, 1))

    def test_last_values_option(self, dialog):
        dialog.last_values_box.setChecked(True)
        assert dialog.include_last_values()

    def test_accept_with_a_selection(self, dialog):
        dialog.accept()
        assert dialog.result() == ExportBookmarksDialog.DialogCode.Accepted
