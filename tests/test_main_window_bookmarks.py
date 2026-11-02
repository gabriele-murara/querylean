"""GUI tests of the bookmarked queries."""

from PySide6.QtWidgets import QInputDialog, QMessageBox, QToolBar, QToolButton

from querylean.config.connection_config import ConnectionConfig
from querylean.ui.main.bookmarks_menu import BookmarksMenu
from querylean.ui.main.connection_state import ConnectionState
from querylean.ui.worker.db_worker import DbWorker
from support.main_window_test_base import MainWindowTestBase


class TestMainWindowBookmarks(MainWindowTestBase):
    """Save, run and delete bookmarks; only those of the open connection
    are offered and run."""

    PROD = ConnectionConfig(
        name="Prod", host="db", database="app", username="ro"
    )
    STAGING = ConnectionConfig(
        name="Staging", host="db2", database="app", username="ro"
    )
    SQL = "SELECT id FROM users"

    def wait_state(self, qtbot, window, state) -> None:
        qtbot.waitUntil(lambda: window.state == state, timeout=self.WAIT_MS)

    def open(self, qtbot, window, config):
        """Save ``config`` (if new) and connect to it."""
        profile = next(
            (p for p in window.connections if p.config == config), None
        ) or window.save_connection(config, "pw", remember=False)
        window.connect_to(profile.profile_id)
        self.wait_state(qtbot, window, ConnectionState.CONNECTED)
        qtbot.waitUntil(
            lambda: window.active_connection.profile_id == profile.profile_id
        )
        return profile

    def bookmark(self, window, name="Users", sql=SQL):
        window.editor.setPlainText(sql)
        return window.save_bookmark(name)

    def executed(self, connector) -> list[str]:
        return [sql for conn in connector.connections for sql in conn.executed]

    def test_toolbar_actions(self, qtbot, window):
        toolbar = window.findChild(QToolBar, "main-toolbar")
        button = toolbar.widgetForAction(window.bookmarks_action)
        assert isinstance(button, QToolButton)
        assert (
            button.popupMode() == QToolButton.ToolButtonPopupMode.InstantPopup
        )
        assert window.bookmarks_action.menu() is window.bookmarks_menu
        assert not window.save_query_action.isEnabled()
        assert not window.bookmarks_action.isEnabled()
        self.open(qtbot, window, self.PROD)
        assert window.save_query_action.isEnabled()
        assert window.bookmarks_action.isEnabled()

    def test_save_asks_a_name_and_runs(
        self, qtbot, window, connector, monkeypatch
    ):
        self.open(qtbot, window, self.PROD)
        monkeypatch.setattr(
            QInputDialog, "getText", lambda *a, **k: ("  Active  users ", True)
        )
        window.editor.setPlainText("{}\n".format(self.SQL))
        window.save_query_action.trigger()
        assert window.bookmarks_menu.names() == ["Active users"]
        assert "Active users" in window.message_label.text()
        assert window.bookmarks[0].sql == self.SQL
        assert window.bookmarks[0].target == "ro@db:3306/app"

        window.editor.setPlainText("SELECT 1")
        window.bookmarks_menu.actions()[0].trigger()
        qtbot.waitUntil(lambda: not window.running, timeout=self.WAIT_MS)
        assert window.editor.toPlainText() == self.SQL
        assert self.SQL in self.executed(connector)
        assert "Query executed" in window.message_label.text()
        # The editor change is undoable.
        window.editor.undo()
        assert window.editor.toPlainText() == "SELECT 1"

    def test_cancelled_or_empty_name(self, qtbot, window, monkeypatch):
        self.open(qtbot, window, self.PROD)
        window.editor.setPlainText(self.SQL)
        monkeypatch.setattr(
            QInputDialog, "getText", lambda *a, **k: ("", False)
        )
        assert window.save_bookmark() is None
        assert window.save_bookmark("   ") is None
        assert window.save_bookmark("x" * 101) is None
        assert window.bookmarks == []

    def test_only_read_queries_are_saved(self, qtbot, window):
        self.open(qtbot, window, self.PROD)
        assert self.bookmark(window, "Bad", "DELETE FROM users") is None
        assert "Only read queries" in window.message_label.text()
        assert self.bookmark(window, "Empty", "  ") is None
        assert window.bookmarks == []

    def test_selection_is_saved(self, qtbot, window):
        self.open(qtbot, window, self.PROD)
        window.editor.setPlainText("SELECT 1;\nSELECT 2")
        cursor = window.editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(8, cursor.MoveMode.KeepAnchor)
        window.editor.setTextCursor(cursor)
        assert window.save_bookmark("One").sql == "SELECT 1"

    def test_replace_requires_confirmation(self, qtbot, window, monkeypatch):
        self.open(qtbot, window, self.PROD)
        self.bookmark(window, "Users", "SELECT 1")
        answers = [QMessageBox.StandardButton.No]
        monkeypatch.setattr(
            QMessageBox, "question", lambda *a, **k: answers.pop(0)
        )
        assert self.bookmark(window, "users", "SELECT 2") is None
        answers.append(QMessageBox.StandardButton.Yes)
        saved = self.bookmark(window, "users", "SELECT 2")
        assert (saved.name, saved.sql) == ("Users", "SELECT 2")
        assert [b.sql for b in window.bookmarks] == ["SELECT 2"]

    def test_bookmarks_belong_to_their_connection(
        self, qtbot, window, connector
    ):
        self.open(qtbot, window, self.PROD)
        self.bookmark(window, "Users")
        assert window.bookmarks_menu.names() == ["Users"]

        self.open(qtbot, window, self.STAGING)
        assert window.bookmarks_menu.names() == []
        before = len(self.executed(connector))
        window.run_bookmark("Users")
        assert not window.running
        assert "not available for this connection" in (
            window.message_label.text()
        )
        assert len(self.executed(connector)) == before

        self.open(qtbot, window, self.PROD)
        assert window.bookmarks_menu.names() == ["Users"]

    def test_same_database_in_another_connection(self, qtbot, window):
        prod = self.open(qtbot, window, self.PROD)
        self.bookmark(window, "Users")
        copy = self.PROD.copy()
        copy.name = "Prod copy"
        other = self.open(qtbot, window, copy)
        assert other.profile_id != prod.profile_id
        assert window.bookmarks_menu.names() == []

    def test_edited_connection_hides_old_bookmarks(self, qtbot, window):
        prod = self.open(qtbot, window, self.PROD)
        self.bookmark(window, "Users")
        window.toggle_connection()
        self.wait_state(qtbot, window, ConnectionState.DISCONNECTED)
        assert window.bookmarks == []
        assert not window.bookmarks_action.isEnabled()
        edited = self.PROD.copy()
        edited.database = "other"
        window.save_connection(
            edited, "pw", profile_id=prod.profile_id, remember=False
        )
        window.toggle_connection()
        self.wait_state(qtbot, window, ConnectionState.CONNECTED)
        assert window.session_target == "ro@db:3306/other"
        assert window.bookmarks_menu.names() == []

    def test_worker_refuses_another_target(self, qtbot, window, connector):
        self.open(qtbot, window, self.PROD)
        before = len(self.executed(connector))
        with qtbot.waitSignal(window.worker.query_failed) as failed:
            window.worker.bookmark_requested.emit(
                self.SQL, "ro@db2:3306/app", 100, 30
            )
        assert failed.args == [
            DbWorker.WRONG_TARGET,
            DbWorker.WRONG_TARGET_KIND,
        ]
        assert len(self.executed(connector)) == before

    def test_delete_bookmark(self, qtbot, window, monkeypatch):
        self.open(qtbot, window, self.PROD)
        self.bookmark(window, "Users")
        self.bookmark(window, "Orders", "SELECT * FROM orders")
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **k: QMessageBox.StandardButton.Yes,
        )
        window.bookmarks_menu.delete_menu.actions()[1].trigger()
        assert window.bookmarks_menu.names() == ["Orders"]
        assert "deleted" in window.message_label.text()

    def test_deleting_the_connection_deletes_its_bookmarks(self, qtbot, window):
        prod = self.open(qtbot, window, self.PROD)
        self.bookmark(window, "Users")
        store = window.config_manager.bookmarks
        assert store.path_of(prod.profile_id).exists()
        window.delete_connection(prod.profile_id, confirm=False)
        assert not store.path_of(prod.profile_id).exists()

    def test_not_connected(self, window):
        window.editor.setPlainText(self.SQL)
        assert window.save_bookmark("Users") is None
        window.run_bookmark("Users")
        assert not window.running
        assert window.bookmarks_menu.names() == []
        assert window.bookmarks_menu.actions()[0].text() == (
            BookmarksMenu.EMPTY_TEXT
        )
