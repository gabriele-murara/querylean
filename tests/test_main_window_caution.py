"""GUI tests of connections with an account that is not read-only."""

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from querylean.config.connection_config import ConnectionConfig
from querylean.ui.main.caution_palette import CautionPalette
from querylean.ui.main.connection_state import ConnectionState
from querylean.ui.main.connections_menu import ConnectionsMenu
from querylean.ui.main.main_window import MainWindow
from support.main_window_test_base import MainWindowTestBase


class TestMainWindowCaution(MainWindowTestBase):
    """Refusal without caution mode, warning state with it, pink window,
    menu marker."""

    WRITE_GRANTS = ["GRANT SELECT, UPDATE ON `app`.* TO `rw`@`%`"]

    def write_account(self, connector) -> None:
        connector.configure = lambda conn: setattr(
            conn, "grants", self.WRITE_GRANTS
        )

    @staticmethod
    def window_color(widget):
        return widget.palette().color(QPalette.ColorRole.Window)

    @staticmethod
    def default_color(widget):
        palette = QApplication.palette(widget)
        return palette.color(QPalette.ColorRole.Window)

    def save(self, window, *, caution: bool):
        return window.save_connection(
            ConnectionConfig(
                host="db",
                database="app",
                username="rw",
                caution_databases=["app"] if caution else [],
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
        assert "Connection refused" in text and "app (UPDATE)" in text
        assert "caution mode" in text
        assert not window.caution_active
        assert self.window_color(window) == self.default_color(window)

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
        # The grey parts turn pink; editor and results keep their colors.
        pink = CautionPalette.tinted(QApplication.palette(window))
        assert self.window_color(window) == pink.color(
            QPalette.ColorRole.Window
        )
        assert self.window_color(window) != self.default_color(window)
        assert self.window_color(window.sidebar) == self.window_color(window)
        base = QPalette.ColorRole.Base
        assert window.editor.palette().color(base) == QApplication.palette(
            window.editor
        ).color(base)
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
        assert self.window_color(window) == self.default_color(window)

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
        assert self.window_color(window) == self.default_color(window)

    def test_menu_marks_caution_connections(self, window):
        profile = self.save(window, caution=True)
        titles = [a.text() for a in window.connections_menu.actions()]
        expected = ConnectionsMenu.CAUTION_TITLE.format(profile.display_name)
        assert expected in titles

    def test_caution_label_names_the_databases(self, qtbot, window, connector):
        def configure(conn):
            conn.grants = [
                "GRANT SELECT ON *.* TO `rw`@`%`",
                "GRANT INSERT ON `shop`.* TO `rw`@`%`",
            ]
            conn.databases = ["app", "shop"]

        connector.configure = configure
        window.save_connection(
            ConnectionConfig(
                host="db",
                username="rw",
                all_databases=True,
                caution_databases=["shop"],
            ),
            "pw",
            remember=False,
        )
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.CONNECTED,
            timeout=self.WAIT_MS,
        )
        assert window.caution_active
        assert window.account_check.write_databases == ("shop",)
        label = window.state_label.text()
        assert "{} (shop)".format(MainWindow.CAUTION_LABEL) in label
        assert "shop (INSERT)" in window.message_label.text()

    def test_no_dialog_on_connection(self, qtbot, window, connector):
        self.write_account(connector)
        self.save(window, caution=True)
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.CONNECTED,
            timeout=self.WAIT_MS,
        )
        assert window.caution_active
        assert window.read_only_notice is None

    def test_write_query_shows_the_dialog(self, qtbot, window, connector):
        self.write_account(connector)
        self.save(window, caution=True)
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.CONNECTED,
            timeout=self.WAIT_MS,
        )
        self.run(qtbot, window, "UPDATE t SET a = 1")
        notice = window.read_only_notice
        assert notice is not None
        qtbot.waitUntil(notice.isVisible, timeout=self.WAIT_MS)
        assert notice.windowTitle() == MainWindow.READ_ONLY_NOTICE_TITLE
        assert "only read queries" in notice.text()
        assert "read operations only" in notice.informativeText()
        assert "app (UPDATE)" in notice.informativeText()
        # The error stays below the results too.
        assert "read operations only" in window.message_label.text()
        notice.accept()
        # A read query does not show it.
        self.run(qtbot, window, "SELECT n FROM t")
        assert not notice.isVisible()

    def test_read_only_account_also_gets_the_dialog(self, qtbot, window):
        self.save(window, caution=False)
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.CONNECTED,
            timeout=self.WAIT_MS,
        )
        assert window.read_only_notice is None
        self.run(qtbot, window, "DELETE FROM t")
        notice = window.read_only_notice
        assert notice is not None and notice.isVisible()
        # No account warning without caution mode.
        assert "could change data" not in notice.informativeText()
        notice.accept()
