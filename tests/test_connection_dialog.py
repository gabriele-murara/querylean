"""GUI tests of the configuration dialog."""

from mysql.connector import errors as mysql_errors
from PySide6.QtWidgets import QLineEdit

from querylean.config.connection_config import ConnectionConfig
from querylean.ui.dialogs.connection_dialog import ConnectionDialog
from support.main_window_test_base import MainWindowTestBase


class TestConnectionDialog(MainWindowTestBase):
    """Defaults, required fields, password masking and connection test."""

    def test_validates_required_fields(self, qtbot, window):
        dialog = ConnectionDialog(
            ConnectionConfig(), "", window.worker, keyring_available=True
        )
        qtbot.addWidget(dialog)
        assert dialog.host.text() == "localhost" and dialog.port.value() == 3306
        assert dialog.connect_timeout.value() == 5
        assert dialog.password.echoMode() == QLineEdit.EchoMode.Password
        dialog.save()
        assert dialog.result() != ConnectionDialog.DialogCode.Accepted
        for field in ("Database", "Username", "Password"):
            assert field in dialog.status.text()
        dialog.show_password.setChecked(True)
        assert dialog.password.echoMode() == QLineEdit.EchoMode.Normal

    def test_keyring_unavailable_disables_remember(self, qtbot, window):
        dialog = ConnectionDialog(
            ConnectionConfig(), "", window.worker, keyring_available=False
        )
        qtbot.addWidget(dialog)
        assert not dialog.remember_password.isEnabled()
        assert not dialog.remember_password.isChecked()

    def test_connection_test(self, qtbot, window, connector):
        dialog = ConnectionDialog(
            ConnectionConfig(database="app", username="ro"),
            "pw",
            window.worker,
            keyring_available=True,
        )
        qtbot.addWidget(dialog)
        dialog.test_connection()
        qtbot.waitUntil(
            lambda: dialog.test_button.isEnabled(), timeout=self.WAIT_MS
        )
        assert "succeeded" in dialog.status.text()
        connector.error = mysql_errors.ProgrammingError(
            msg="denied", errno=1045
        )
        dialog.test_connection()
        qtbot.waitUntil(
            lambda: dialog.test_button.isEnabled(), timeout=self.WAIT_MS
        )
        assert "Authentication failed" in dialog.status.text()

    def test_caution_list_starts_from_the_accepted_databases(
        self, qtbot, window
    ):
        dialog = ConnectionDialog(
            ConnectionConfig(database="app", username="ro"),
            "pw",
            window.worker,
            keyring_available=True,
        )
        qtbot.addWidget(dialog)
        assert dialog.caution_list.isHidden()
        assert dialog.caution_warning.isHidden()
        assert dialog.config().caution_databases == ()
        edit = ConnectionDialog(
            ConnectionConfig(database="app", caution_databases=["app"]),
            "",
            window.worker,
            keyring_available=True,
        )
        qtbot.addWidget(edit)
        assert not edit.caution_list.isHidden()
        assert not edit.caution_warning.isHidden()
        assert edit.accepted_databases() == ["app"]
        edit.set_accepted("app", False)
        assert edit.config().caution_databases == ()

    def test_all_databases_checkbox(self, qtbot, window):
        dialog = ConnectionDialog(
            ConnectionConfig(host="db", username="ro"),
            "pw",
            window.worker,
            keyring_available=True,
        )
        qtbot.addWidget(dialog)
        assert "Database" in dialog.missing_fields()
        dialog.all_databases.setChecked(True)
        assert dialog.missing_fields() == []
        assert dialog.config().all_databases
        assert dialog.name.placeholderText().endswith("ro@db/*")
        assert dialog.database.placeholderText()

    def test_connection_test_with_write_account(self, qtbot, window, connector):
        connector.configure = lambda conn: setattr(
            conn, "grants", ["GRANT SELECT, INSERT ON `app`.* TO `rw`@`%`"]
        )
        dialog = ConnectionDialog(
            ConnectionConfig(database="app", username="rw"),
            "pw",
            window.worker,
            keyring_available=True,
        )
        qtbot.addWidget(dialog)
        dialog.test_connection()
        qtbot.waitUntil(
            lambda: dialog.test_button.isEnabled(), timeout=self.WAIT_MS
        )
        assert "succeeded" in dialog.status.text()
        assert "app (INSERT)" in dialog.status.text()
        assert "accept" in dialog.status.text()
        assert dialog.caution_databases() == ["app"]
        assert dialog.accepted_databases() == []
        assert not dialog.caution_list.isHidden()
        dialog.set_accepted("app")
        assert dialog.config().caution_databases == ("app",)
        dialog.test_connection()
        qtbot.waitUntil(
            lambda: dialog.test_button.isEnabled(), timeout=self.WAIT_MS
        )
        # The choice survives a new test.
        assert dialog.accepted_databases() == ["app"]
        assert "Caution mode" in dialog.status.text()
        assert "INSERT" in dialog.status.text()

    def test_test_with_all_databases_lists_each_writable_one(
        self, qtbot, window, connector
    ):
        def configure(conn):
            conn.grants = [
                "GRANT SELECT ON *.* TO `rw`@`%`",
                "GRANT INSERT ON `shop`.* TO `rw`@`%`",
                "GRANT DELETE ON `crm`.* TO `rw`@`%`",
            ]
            conn.databases = ["information_schema", "app", "shop", "crm"]

        connector.configure = configure
        dialog = ConnectionDialog(
            ConnectionConfig(username="rw", all_databases=True),
            "pw",
            window.worker,
            keyring_available=True,
        )
        qtbot.addWidget(dialog)
        dialog.test_connection()
        qtbot.waitUntil(
            lambda: dialog.test_button.isEnabled(), timeout=self.WAIT_MS
        )
        assert dialog.caution_databases() == ["shop", "crm"]
        assert dialog.caution_list.item(1).text() == "crm — DELETE"
        dialog.set_accepted("crm")
        assert dialog.config().caution_databases == ("crm",)
