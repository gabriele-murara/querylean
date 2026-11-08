"""Tests of the dialog that chooses the bookmarks to import."""

import pytest

from querylean.bookmarks.bookmark_export import BookmarkExport
from querylean.bookmarks.bookmark_import import BookmarkImport
from querylean.bookmarks.bookmark_import_plan import BookmarkImportPlan
from querylean.bookmarks.name_conflict import NameConflict
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.connection_config import ConnectionConfig
from querylean.config.connection_profile import ConnectionProfile
from querylean.database.validation.read_only_validator import (
    ReadOnlyValidator,
)
from querylean.ui.dialogs.bookmark_table import BookmarkTable
from querylean.ui.dialogs.import_bookmarks_dialog import (
    ImportBookmarksDialog,
)
from querylean.ui.safe_text import SafeText


class TestImportBookmarksDialog:
    """Rows, refused queries, statuses per connection and choices."""

    NAME, TYPE, STATUS, PLACEHOLDERS, QUERY = range(5)

    @pytest.fixture
    def profiles(self) -> list[ConnectionProfile]:
        return [
            ConnectionProfile(
                "a" * 32,
                ConnectionConfig(
                    name="Prod", host="db", database="app", username="ro"
                ),
            ),
            ConnectionProfile(
                "b" * 32,
                ConnectionConfig(
                    host="localhost", database="dev", username="me"
                ),
            ),
        ]

    @pytest.fixture
    def source(self) -> BookmarkImport:
        data = {
            "format": BookmarkExport.FORMAT,
            "format_version": 1,
            "exported_at": "2026-11-08T09:30:00+00:00",
            "exported_by": {"application": "querylean", "version": "9"},
            "bookmarks": [
                {"name": "Users", "sql": "SELECT '<b>1</b>'"},
                {
                    "name": "By id",
                    "sql": "SELECT * FROM t WHERE id IN (${IDS})",
                    "placeholders": [
                        {
                            "name": "IDS",
                            "type": "integer",
                            "list": True,
                            "default": "1",
                        }
                    ],
                    "last_values": {"IDS": "4, 5"},
                },
                {"name": "Drop", "sql": "DROP TABLE t"},
                {"name": ""},
            ],
        }
        return BookmarkImport.parse(data, ReadOnlyValidator())

    @pytest.fixture
    def saved(self, profiles) -> dict:
        target = QueryBookmark.target_of(profiles[1].config)
        return {
            profiles[1].profile_id: [
                QueryBookmark("users", "SELECT '<b>1</b>'", target),
                QueryBookmark("By ID", "SELECT 2", target),
            ]
        }

    @pytest.fixture
    def dialog(self, qtbot, source, profiles, saved) -> ImportBookmarksDialog:
        widget = ImportBookmarksDialog(
            source,
            profiles,
            saved,
            profile_id=profiles[1].profile_id,
            file_name="shared.json",
        )
        qtbot.addWidget(widget)
        return widget

    def text(self, dialog, row, column) -> str:
        return dialog.table.item(row, column).text()

    def test_rows(self, dialog):
        assert dialog.table.rowCount() == 3
        assert self.text(dialog, 0, self.NAME) == "Users"
        assert self.text(dialog, 1, self.TYPE) == BookmarkTable.MASK_TYPE
        assert self.text(dialog, 1, self.PLACEHOLDERS) == "${IDS}"
        item = dialog.table.item(0, self.QUERY)
        assert item.toolTip() == SafeText.tooltip("SELECT '<b>1</b>'")
        origin = dialog.origin_label.text()
        assert "shared.json" in origin
        assert "querylean 9" in origin
        assert "1 invalid entries" in origin

    def test_refused_query_cannot_be_checked(self, dialog):
        assert not dialog.table.is_checkable(2)
        dialog.table.set_checked(2, True)
        assert not dialog.table.is_checked(2)
        assert dialog.status_text(2) == ImportBookmarksDialog.REFUSED
        tip = dialog.table.item(2, self.STATUS).toolTip()
        assert "Not a read query" in tip
        assert dialog.status.text() == (
            "2 of 3 bookmarked queries selected. 1 refused: not read queries."
        )

    def test_statuses_follow_the_connection(self, dialog, profiles):
        assert dialog.profile() is profiles[1]
        assert dialog.status_text(0) == BookmarkImportPlan.SAVED
        assert dialog.status_text(1) == BookmarkImportPlan.NAME_TAKEN
        assert dialog.target_label.text() == "Saved for me@localhost:3306/dev"
        dialog.connection_box.setCurrentIndex(0)
        assert dialog.status_text(0) == BookmarkImportPlan.NEW
        assert dialog.status_text(1) == BookmarkImportPlan.NEW
        assert "ro@db:3306/app" in dialog.target_label.text()

    def test_selected_for_the_chosen_target(self, dialog, profiles):
        dialog.connection_box.setCurrentIndex(0)
        selected = dialog.selected()
        assert [b.name for b in selected] == ["Users", "By id"]
        assert {b.target for b in selected} == {"ro@db:3306/app"}
        assert selected[1].last_values == {"IDS": "4, 5"}
        assert dialog.last_values_box.isEnabled()
        dialog.last_values_box.setChecked(False)
        assert dialog.selected()[1].last_values == {}

    def test_conflict_choice(self, dialog):
        assert dialog.conflict() == NameConflict.RENAME
        dialog.set_conflict(NameConflict.SKIP)
        assert dialog.conflict() == NameConflict.SKIP

    def test_filter_and_selection(self, dialog):
        dialog.filter_edit.setText("where id")
        assert dialog.table.isRowHidden(0)
        assert not dialog.table.isRowHidden(1)
        dialog.select_none_button.click()
        assert [b.name for b in dialog.selected()] == ["Users"]
        dialog.filter_edit.clear()
        dialog.select_none_button.click()
        assert not dialog.import_button.isEnabled()
        dialog.accept()
        assert dialog.result() != ImportBookmarksDialog.DialogCode.Accepted
        dialog.select_all_button.click()
        assert len(dialog.selected()) == 2
        dialog.accept()
        assert dialog.result() == ImportBookmarksDialog.DialogCode.Accepted

    def test_without_last_values(self, qtbot, profiles):
        data = {
            "format": BookmarkExport.FORMAT,
            "format_version": 1,
            "bookmarks": [{"name": "A", "sql": "SELECT 1"}],
        }
        source = BookmarkImport.parse(data, ReadOnlyValidator())
        dialog = ImportBookmarksDialog(source, profiles, {})
        qtbot.addWidget(dialog)
        assert dialog.profile() is profiles[0]
        assert not dialog.last_values_box.isEnabled()
        assert not dialog.last_values_box.isChecked()
        assert dialog.origin_label.text() == ""
