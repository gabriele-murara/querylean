"""GUI tests of connections with an account that is not read-only."""

from querylean.config.connection_config import ConnectionConfig
from querylean.ui.main.connection_state import ConnectionState
from querylean.ui.main.connections_menu import ConnectionsMenu
from querylean.ui.main.main_window import MainWindow
from support.main_window_test_base import MainWindowTestBase


class TestMainWindowCaution(MainWindowTestBase):
    """Refusal without caution mode, warning state with it, menu marker."""

    WRITE_GRANTS = ["GRANT SELECT, UPDATE ON `app`.* TO `rw`@`%`"]

    def write_account(self, connector) -> None:
        connector.configure = lambda conn: setattr(
            conn, "grants", self.WRITE_GRANTS
        )

    def save(self, window, *, caution: bool):
        return window.save_connection(
            ConnectionConfig(
                host="db", database="app", username="rw", caution_mode=caution
            ),
            "pw",
            remember=False,
        )

    def test_write_account_is_refused(self, qtbot, window, connector):
        self.write_account(connector)
        self.save(window, caution=False)
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.ERROR,
            timeout=self.WAIT_MS,
        )
        text = window.message_label.text()
        assert "Connection refused" in text and "UPDATE" in text
        assert "Caution mode" in text
        assert not window.caution_active

    def test_caution_mode_connects_with_warning(self, qtbot, window, connector):
        self.write_account(connector)
        self.save(window, caution=True)
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.CONNECTED,
            timeout=self.WAIT_MS,
        )
        assert window.caution_active
        assert MainWindow.CAUTION_LABEL in window.state_label.text()
        assert "Caution mode" in window.message_label.text()
        # Writes stay forbidden.
        self.run(qtbot, window, "UPDATE t SET a = 1")
        assert "read operations only" in window.message_label.text()
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.DISCONNECTED,
            timeout=self.WAIT_MS,
        )
        assert not window.caution_active
        assert MainWindow.CAUTION_LABEL not in window.state_label.text()

    def test_read_only_account_in_caution_mode_has_no_warning(
        self, qtbot, window
    ):
        self.save(window, caution=True)
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.CONNECTED,
            timeout=self.WAIT_MS,
        )
        assert not window.caution_active
        assert MainWindow.CAUTION_LABEL not in window.state_label.text()

    def test_menu_marks_caution_connections(self, window):
        profile = self.save(window, caution=True)
        titles = [a.text() for a in window.connections_menu.actions()]
        expected = ConnectionsMenu.CAUTION_TITLE.format(profile.display_name)
        assert expected in titles
