"""GUI tests of the import of bookmarked queries."""

import json

from PySide6.QtWidgets import QFileDialog, QMessageBox

from querylean.bookmarks.bookmark_export import BookmarkExport
from querylean.bookmarks.name_conflict import NameConflict
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.connection_config import ConnectionConfig
from querylean.ui.dialogs.import_bookmarks_dialog import (
    ImportBookmarksDialog,
)
from support.main_window_test_base import MainWindowTestBase


class TestMainWindowBookmarkImport(MainWindowTestBase):
    """File → dialog → bookmarks of the chosen connection."""

    PROD = ConnectionConfig(
        name="Prod", host="db", database="app", username="ro"
    )
    DEV = ConnectionConfig(
        name="Dev", host="localhost", database="dev", username="me"
    )

    def write(self, tmp_path, *bookmarks):
        path = tmp_path / "shared.json"
        data = {
            "format": BookmarkExport.FORMAT,
            "format_version": BookmarkExport.FORMAT_VERSION,
            "bookmarks": list(bookmarks),
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def warnings(self, monkeypatch) -> list:
        found = []
        monkeypatch.setattr(
            QMessageBox, "warning", lambda *a, **k: found.append(a[1:])
        )
        return found

    def test_import_through_the_dialogs(self, window, tmp_path, monkeypatch):
        window.save_connection(self.PROD, "pw", remember=False)
        dev = window.save_connection(self.DEV, "pw", remember=False)
        target = QueryBookmark.target_of(self.DEV)
        window.config_manager.bookmarks.add(
            dev.profile_id, QueryBookmark("Users", "SELECT 0", target)
        )
        path = self.write(
            tmp_path,
            {"name": "Users", "sql": "SELECT 1"},
            {"name": "Orders", "sql": "SELECT 2"},
            {"name": "Drop", "sql": "DROP TABLE t"},
        )
        monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            lambda *a, **k: (str(path), BookmarkExport.NAME_FILTER),
        )
        shown = []

        def choose(dialog):
            shown.append(dialog.profile().profile_id)
            return ImportBookmarksDialog.DialogCode.Accepted

        monkeypatch.setattr(ImportBookmarksDialog, "exec", choose)
        window.connections_menu.actions()[-1].trigger()
        # The active connection (the last saved) is proposed.
        assert shown == [dev.profile_id]
        saved = window.config_manager.bookmarks.load(dev.profile_id, target)
        assert [(b.name, b.sql) for b in saved] == [
            ("Orders", "SELECT 2"),
            ("Users", "SELECT 0"),
            ("Users (2)", "SELECT 1"),
        ]
        text = window.message_label.text()
        assert text == "Imported 2 bookmarked queries into “Dev” (1 renamed)."
        assert "Users → Users (2)" in window.message_label.toolTip()

    def test_refused_bookmarks_are_never_saved(self, window):
        profile = window.save_connection(self.PROD, "pw", remember=False)
        bookmarks = [
            QueryBookmark("Drop", "DROP TABLE t", "-"),
            QueryBookmark("Ok", "SELECT 1", "-"),
        ]
        plan = window.import_bookmarks_into(
            profile.profile_id, bookmarks, NameConflict.SKIP
        )
        assert [b.name for b in plan.added] == ["Ok"]
        assert window.message_label.text() == (
            "Imported 1 bookmarked query into “Prod”."
        )

    def test_session_menu_is_reloaded(self, qtbot, window):
        self.connect(qtbot, window)
        profile = window.active_connection
        window.import_bookmarks_into(
            profile.profile_id, [QueryBookmark("Users", "SELECT 1", "-")]
        )
        assert window.bookmarks_menu.names() == ["Users"]

    def test_without_connections(self, window, monkeypatch):
        warnings = self.warnings(monkeypatch)

        def never(*a, **k):
            raise AssertionError("no file dialog expected")

        monkeypatch.setattr(QFileDialog, "getOpenFileName", never)
        window.bookmarks_menu.import_action.trigger()
        assert warnings[0][0] == ImportBookmarksDialog.TITLE
        assert "Save a connection" in warnings[0][1]

    def test_bad_files_are_reported(self, window, tmp_path, monkeypatch):
        window.save_connection(self.PROD, "pw", remember=False)
        warnings = self.warnings(monkeypatch)
        broken = tmp_path / "broken.json"
        broken.write_text("{", encoding="utf-8")
        assert window.import_bookmarks_from(broken) is None
        assert "not a valid JSON" in window.message_label.text()
        empty = self.write(tmp_path, {"name": ""})
        assert window.import_bookmarks_from(empty) is None
        assert "no valid bookmarked queries" in warnings[-1][1]
        assert len(warnings) == 2

    def test_cancelled_dialog_imports_nothing(
        self, window, tmp_path, monkeypatch
    ):
        profile = window.save_connection(self.PROD, "pw", remember=False)
        path = self.write(tmp_path, {"name": "A", "sql": "SELECT 1"})
        monkeypatch.setattr(
            ImportBookmarksDialog,
            "exec",
            lambda dialog: ImportBookmarksDialog.DialogCode.Rejected,
        )
        assert window.import_bookmarks_from(path) is None
        target = QueryBookmark.target_of(self.PROD)
        bookmarks = window.config_manager.bookmarks
        assert bookmarks.load(profile.profile_id, target) == []
