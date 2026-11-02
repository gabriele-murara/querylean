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

    def test_caution_mode_checkbox(self, qtbot, window):
        dialog = ConnectionDialog(
            ConnectionConfig(database="app", username="ro"),
            "pw",
            window.worker,
            keyring_available=True,
        )
        qtbot.addWidget(dialog)
        assert not dialog.caution_mode.isChecked()
        assert dialog.caution_warning.isHidden()
        assert dialog.config().caution_mode is False
        dialog.caution_mode.setChecked(True)
        assert not dialog.caution_warning.isHidden()
        assert dialog.config().caution_mode is True
        edit = ConnectionDialog(
            ConnectionConfig(caution_mode=True),
            "",
            window.worker,
            keyring_available=True,
        )
        qtbot.addWidget(edit)
        assert edit.caution_mode.isChecked()
        assert not edit.caution_warning.isHidden()

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
        assert "Caution mode" in dialog.status.text()
        assert "INSERT" in dialog.status.text()
        dialog.caution_mode.setChecked(True)
        dialog.test_connection()
        qtbot.waitUntil(
            lambda: dialog.test_button.isEnabled(), timeout=self.WAIT_MS
        )
        assert "succeeded" in dialog.status.text()
        assert "INSERT" in dialog.status.text()
