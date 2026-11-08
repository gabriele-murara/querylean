"""GUI tests of the saved connections and the "Connections" menu."""

from PySide6.QtWidgets import QToolBar, QToolButton

from querylean.config.connection_config import ConnectionConfig
from querylean.ui.dialogs.connection_dialog import ConnectionDialog
from querylean.ui.main.connection_state import ConnectionState
from querylean.ui.main.connections_menu import ConnectionsMenu
from support.main_window_test_base import MainWindowTestBase


class TestMainWindowConnections(MainWindowTestBase):
    """Menu, create/edit through the dialog, switch, delete, passwords."""

    PROD = ConnectionConfig(
        name="Produzione", host="db", database="app", username="ro"
    )
    TEST = ConnectionConfig(host="db2", database="test", username="ro")

    @staticmethod
    def fill_dialog(monkeypatch, **fields) -> list[ConnectionDialog]:
        """Make ``ConnectionDialog.exec`` fill ``fields`` and press
        "Save" (or cancel with ``cancel=True``)."""
        opened = []
        cancel = fields.pop("cancel", False)
        remember = fields.pop("remember", False)

        def fake_exec(dialog):
            opened.append(dialog)
            for name, value in fields.items():
                getattr(dialog, name).setText(value)
            dialog.remember_password.setChecked(remember)
            if cancel:
                dialog.reject()
            else:
                dialog.save()
            return dialog.result()

        monkeypatch.setattr(ConnectionDialog, "exec", fake_exec)
        return opened

    def wait_state(self, qtbot, window, state) -> None:
        qtbot.waitUntil(lambda: window.state == state, timeout=self.WAIT_MS)

    EMPTY_MENU = ["New connection…", "", "Export bookmarked queries…"]

    def menu_texts(self, window) -> list[str]:
        return [a.text() for a in window.connections_menu.actions()]

    def test_toolbar_button_opens_the_menu(self, window):
        assert window.connections_action.text() == "Connections"
        toolbar = window.findChild(QToolBar, "main-toolbar")
        button = toolbar.widgetForAction(window.connections_action)
        assert isinstance(button, QToolButton)
        assert (
            button.popupMode() == QToolButton.ToolButtonPopupMode.InstantPopup
        )
        assert self.menu_texts(window) == self.EMPTY_MENU

    def test_menu_lists_saved_connections(self, window):
        prod = window.save_connection(self.PROD, "pw", remember=False)
        test = window.save_connection(self.TEST, "pw", remember=False)
        assert self.menu_texts(window) == [
            ConnectionsMenu.NEW_TEXT,
            "",
            "Produzione",
            "ro@db2/test",
            "",
            ConnectionsMenu.EXPORT_BOOKMARKS_TEXT,
        ]
        # When not connected, the connection just saved becomes active.
        assert window.active_connection.profile_id == test.profile_id
        menu = window.connections_menu
        assert menu.submenu(test.profile_id).menuAction().isChecked()
        assert not menu.submenu(prod.profile_id).menuAction().isChecked()
        entries = [a.text() for a in menu.submenu(test.profile_id).actions()]
        assert entries == [
            ConnectionsMenu.CONNECT_TEXT,
            ConnectionsMenu.EDIT_TEXT,
            "",
            ConnectionsMenu.DELETE_TEXT,
        ]

    def test_new_connection_through_the_dialog(self, window, monkeypatch):
        opened = self.fill_dialog(
            monkeypatch,
            name="Prod",
            database="app",
            username="ro",
            password="pw",
        )
        profile = window.new_connection()
        assert opened[0].windowTitle() == ConnectionDialog.NEW_TITLE
        assert opened[0].save_button.text() == "Save"
        assert profile.display_name == "Prod"
        assert window.active_connection.profile_id == profile.profile_id
        assert window.password == "pw"
        assert "“Prod” saved" in window.message_label.text()

    def test_cancelled_dialog_saves_nothing(self, window, monkeypatch):
        self.fill_dialog(monkeypatch, database="app", cancel=True)
        assert window.new_connection() is None
        assert window.connections == []

    def test_connect_without_connections_asks_for_one(
        self, qtbot, window, monkeypatch
    ):
        self.fill_dialog(
            monkeypatch, database="app", username="ro", password="pw"
        )
        window.toggle_connection()
        self.wait_state(qtbot, window, ConnectionState.CONNECTED)
        assert window.active_connection.display_name == "ro@localhost/app"
        assert "ro@localhost/app" in window.state_label.text()

    def test_edit_keeps_identifier_and_asks_to_reconnect(
        self, qtbot, window, monkeypatch
    ):
        self.connect(qtbot, window)
        profile = window.active_connection
        opened = self.fill_dialog(monkeypatch, name="Nuovo nome")
        edited = window.edit_connection(profile.profile_id)
        assert opened[0].windowTitle() == ConnectionDialog.EDIT_TITLE
        # The stored session password is offered again.
        assert opened[0].password.text() == "pw"
        assert edited.profile_id == profile.profile_id
        assert [p.display_name for p in window.connections] == ["Nuovo nome"]
        assert "Reconnect to apply" in window.message_label.text()

    def test_connect_to_switches_connection(self, qtbot, window, connector):
        prod = window.save_connection(self.PROD, "pw", remember=False)
        test = window.save_connection(self.TEST, "pw2", remember=False)
        window.connect_to(prod.profile_id)
        self.wait_state(qtbot, window, ConnectionState.CONNECTED)
        menu = window.connections_menu
        connect_prod = menu.submenu(prod.profile_id).actions()[0]
        assert not connect_prod.isEnabled()
        menu.submenu(test.profile_id).actions()[0].trigger()
        qtbot.waitUntil(
            lambda: (
                window.state == ConnectionState.CONNECTED
                and len(connector.connections) == 2
            ),
            timeout=self.WAIT_MS,
        )
        assert window.active_connection.profile_id == test.profile_id
        assert connector.connections[1].kwargs["host"] == "db2"
        assert connector.connections[1].kwargs["password"] == "pw2"
        assert "ro@db2/test" in window.state_label.text()
        assert "Connected to db2" in window.message_label.text()

    def test_delete_connection(self, qtbot, window):
        prod = window.save_connection(self.PROD, "pw", remember=False)
        test = window.save_connection(self.TEST, "pw", remember=False)
        window.connect_to(prod.profile_id)
        self.wait_state(qtbot, window, ConnectionState.CONNECTED)
        assert window.delete_connection(prod.profile_id, confirm=False)
        self.wait_state(qtbot, window, ConnectionState.DISCONNECTED)
        assert [p.profile_id for p in window.connections] == [test.profile_id]
        assert window.active_connection.profile_id == test.profile_id
        path = window.config_manager.connections.path_of(prod.profile_id)
        assert not path.exists()
        assert window.delete_connection(test.profile_id, confirm=False)
        assert window.active_connection is None
        assert self.menu_texts(window) == self.EMPTY_MENU

    def test_password_is_shared_by_account_and_removed_with_it(self, window):
        backend = window.secrets.backend
        first = window.save_connection(self.PROD, "pw", remember=True)
        same_account = ConnectionConfig(
            host="db", database="other", username="ro"
        )
        second = window.save_connection(same_account, "pw", remember=True)
        assert backend.get_password("querylean", "ro@db:3306") == "pw"
        window.delete_connection(first.profile_id, confirm=False)
        # Still used by the other connection to the same account.
        assert backend.get_password("querylean", "ro@db:3306") == "pw"
        window.delete_connection(second.profile_id, confirm=False)
        assert backend.get_password("querylean", "ro@db:3306") is None

    def test_name_placeholder_follows_the_fields(self, qtbot, window):
        dialog = ConnectionDialog(
            ConnectionConfig(), "", window.worker, keyring_available=True
        )
        qtbot.addWidget(dialog)
        dialog.username.setText("ro")
        dialog.database.setText("app")
        assert "ro@localhost/app" in dialog.name.placeholderText()
        dialog.name.setText("Prod")
        assert dialog.config().name == "Prod"
        assert dialog.config().display_name() == "Prod"
