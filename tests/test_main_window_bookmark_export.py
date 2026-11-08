"""GUI tests of the export of bookmarked queries."""

import json
import stat

from PySide6.QtWidgets import QFileDialog, QMessageBox

from querylean.bookmarks.bookmark_export import BookmarkExport
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.connection_config import ConnectionConfig
from querylean.ui.dialogs.export_bookmarks_dialog import (
    ExportBookmarksDialog,
)
from support.main_window_test_base import MainWindowTestBase


class TestMainWindowBookmarkExport(MainWindowTestBase):
    """Bookmarks of every saved connection, without connecting."""

    PROD = ConnectionConfig(
        name="Prod", host="db", database="app", username="ro"
    )
    STAGING = ConnectionConfig(
        name="Staging", host="db2", database="app", username="ro"
    )

    def save(self, window, config, *names):
        """Save ``config`` with a bookmark per name, no session needed."""
        profile = window.save_connection(config, "pw", remember=False)
        target = QueryBookmark.target_of(config)
        for name in names:
            window.config_manager.bookmarks.add(
                profile.profile_id,
                QueryBookmark(name, "SELECT 1", target),
            )
        return profile

    def test_entries_of_every_connection(self, window):
        staging = self.save(window, self.STAGING, "b", "A")
        prod = self.save(window, self.PROD, "z")
        # A bookmark of an older target of the connection is not offered.
        window.config_manager.bookmarks.add(
            prod.profile_id, QueryBookmark("old", "SELECT 1", "x@y:1/z")
        )
        entries = window.bookmark_entries()
        assert [(e.profile.profile_id, e.bookmark.name) for e in entries] == [
            (prod.profile_id, "z"),
            (staging.profile_id, "A"),
            (staging.profile_id, "b"),
        ]

    def test_menus_open_the_export(self, window, monkeypatch):
        calls = []
        monkeypatch.setattr(
            QMessageBox, "warning", lambda *a, **k: calls.append(a[1:])
        )
        assert not window.bookmarks_action.isEnabled()
        export = window.connections_menu.actions()[-1]
        assert not export.isEnabled()
        self.save(window, self.PROD)
        export = window.connections_menu.actions()[-1]
        assert export.isEnabled()
        export.trigger()
        assert calls[0][0] == ExportBookmarksDialog.TITLE
        assert "No bookmarked queries" in calls[0][1]
        window.bookmarks_menu.export_action.trigger()
        assert len(calls) == 2

    def test_export_through_the_dialogs(self, window, tmp_path, monkeypatch):
        self.save(window, self.PROD, "Users", "Orders")
        shown = []

        def choose(dialog):
            shown.append([e.bookmark.name for e in dialog.entries])
            dialog.set_checked(0, False)
            return ExportBookmarksDialog.DialogCode.Accepted

        monkeypatch.setattr(ExportBookmarksDialog, "exec", choose)
        target = tmp_path / "mine"
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            lambda *a, **k: (str(target), BookmarkExport.NAME_FILTER),
        )
        window.export_bookmarks()
        assert shown == [["Orders", "Users"]]
        path = tmp_path / "mine.json"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        data = json.loads(path.read_text(encoding="utf-8"))
        assert [b["name"] for b in data["bookmarks"]] == ["Users"]
        assert "db" not in json.dumps(data)
        text = window.message_label.text()
        assert "Exported 1 bookmarked query to" in text

    def test_cancelled_dialog_writes_nothing(
        self, window, tmp_path, monkeypatch
    ):
        self.save(window, self.PROD, "Users")
        monkeypatch.setattr(
            ExportBookmarksDialog,
            "exec",
            lambda dialog: ExportBookmarksDialog.DialogCode.Rejected,
        )

        def never(*a, **k):
            raise AssertionError("no file dialog expected")

        monkeypatch.setattr(QFileDialog, "getSaveFileName", never)
        window.export_bookmarks()
        assert list(tmp_path.glob("*.json")) == [tmp_path / "config.json"]

    def test_write_error_is_reported(self, window, tmp_path, monkeypatch):
        self.save(window, self.PROD, "Users")
        warnings = []
        monkeypatch.setattr(
            QMessageBox, "warning", lambda *a, **k: warnings.append(a[2])
        )
        blocker = tmp_path / "file"
        blocker.write_text("x", encoding="utf-8")
        entries = window.bookmark_entries()
        assert not window.export_bookmarks_to(blocker / "b.json", entries)
        assert warnings
        assert "Cannot write" in window.message_label.text()
