"""GUI tests of the main window."""

import threading

from mysql.connector import errors as mysql_errors
from PySide6.QtGui import QTextCursor

from fakes.fake_connector import FakeConnector
from querylean.config.config_manager import ConfigManager
from querylean.database.connection.connection_manager import ConnectionManager
from querylean.security.keyring_secret_store import KeyringSecretStore
from querylean.ui.main.connection_state import ConnectionState
from querylean.ui.main.main_window import MainWindow
from querylean.ui.worker.db_thread import DbThread
from support.main_window_test_base import MainWindowTestBase


class TestMainWindow(MainWindowTestBase):
    """Opening, connection handling, execution, errors, responsiveness and
    closing."""

    def test_opens_disconnected(self, window):
        assert window.isVisible()
        assert window.state == ConnectionState.DISCONNECTED
        assert "Disconnesso" in window.state_label.text()
        assert not window.execute_action.isEnabled()
        assert not window.stop_action.isEnabled()

    def test_toolbar_order_and_icons(self, window):
        texts = [action.text() for action in window.toolbar_actions()]
        assert texts == [
            "Esegui",
            "Interrompi",
            "Esporta",
            "Connetti",
            "Configurazione",
            "Informazioni",
        ]
        for action in window.toolbar_actions():
            assert not action.icon().isNull()

    def test_connect_action_icon_follows_state(self, qtbot, window):
        before = window.connect_action.icon().cacheKey()
        self.connect(qtbot, window)
        assert window.connect_action.icon().cacheKey() != before

    def test_connection_failure_is_shown(self, qtbot, window, connector):
        connector.error = mysql_errors.InterfaceError(
            msg="Can't connect", errno=2003
        )
        self.configure(window)
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.ERROR, timeout=self.WAIT_MS
        )
        assert "Impossibile raggiungere" in window.message_label.text()
        assert not window.execute_action.isEnabled()

    def test_connect_disconnect_reconnect(self, qtbot, window):
        self.connect(qtbot, window)
        assert window.connect_action.text() == "Disconnetti"
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.DISCONNECTED,
            timeout=self.WAIT_MS,
        )
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.CONNECTED,
            timeout=self.WAIT_MS,
        )

    def test_execute_valid_query_shows_results(self, qtbot, window):
        self.connect(qtbot, window)
        self.run(qtbot, window, "SELECT n FROM t")
        assert window.results.results_model.rowCount() == 3
        assert window.rows_label.text() == "3 righe"
        assert "ms" in window.time_label.text()
        assert window.limit_label.text() == ""
        assert window.running_label.isHidden()

    def test_truncation_is_signalled(self, qtbot, window, connector):
        self.connect(qtbot, window)
        window.app_config.connection.row_limit = 100
        connector.connections[0].row_count = 5000
        self.run(qtbot, window, "SELECT n FROM t")
        assert window.results.results_model.rowCount() == 100
        assert "limitati alle prime 100" in window.limit_label.text()

    def test_rejected_query_shows_error(self, qtbot, window):
        self.connect(qtbot, window)
        self.run(qtbot, window, "DROP TABLE users")
        assert "Query non consentita" in window.message_label.text()

    def test_timeout_is_shown(self, qtbot, window, connector):
        self.connect(qtbot, window)
        connector.connections[0].handler = lambda sql: (
            mysql_errors.DatabaseError(
                msg="maximum statement execution time exceeded", errno=3024
            )
        )
        self.run(qtbot, window, "SELECT SLEEP(10)")
        assert "Timeout" in window.message_label.text()

    def test_gui_stays_responsive_and_query_can_be_stopped(
        self, qtbot, window, connector
    ):
        self.connect(qtbot, window)
        conn = connector.connections[0]
        gate = threading.Event()
        conn.block_fetch = gate

        def on_kill():
            conn.killed = True
            gate.set()

        connector.configure = lambda killer: setattr(killer, "on_kill", on_kill)
        window.editor.setPlainText("SELECT n FROM t")
        window.execute_query()
        assert window.running
        assert not window.execute_action.isEnabled()
        assert window.stop_action.isEnabled()
        assert window.progress.isVisible()
        assert "In esecuzione: SELECT n FROM t" in window.running_label.text()
        # The GUI thread keeps processing events while the worker is blocked.
        qtbot.wait(100)
        window.editor.insertPlainText(" ")
        window.stop_query()
        qtbot.waitUntil(lambda: not window.running, timeout=self.WAIT_MS)
        assert "interrotta" in window.message_label.text()
        assert window.execute_action.isEnabled()

    def test_execute_uses_selection(self, qtbot, window):
        self.connect(qtbot, window)
        window.editor.setPlainText("DELETE FROM t\nSELECT n FROM t")
        cursor = window.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Down)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor
        )
        window.editor.setTextCursor(cursor)
        window.execute_query()
        qtbot.waitUntil(lambda: not window.running, timeout=self.WAIT_MS)
        assert window.rows_label.text() == "3 righe"

    def test_empty_editor_does_nothing(self, qtbot, window):
        self.connect(qtbot, window)
        window.editor.setPlainText("   \n ")
        window.execute_query()
        assert not window.running

    def test_close_releases_resources_and_persists_config(
        self, qtbot, window, tmp_path
    ):
        backend = window.secrets.backend
        self.configure(window, password="pw-123")
        window.close()
        assert window.closed
        assert window.db.thread.isFinished()
        data = (tmp_path / "config.json").read_text()
        assert "pw-123" not in data
        assert '"username": "ro"' in data
        # Restart: configuration and password are restored.
        window.secrets.set_password("ro@db:3306", "pw-123")
        restarted = MainWindow(
            ConfigManager(tmp_path / "config.json"),
            KeyringSecretStore(backend),
            DbThread(ConnectionManager(FakeConnector())),
        )
        qtbot.addWidget(restarted)
        assert restarted.app_config.connection.host == "db"
        assert restarted.password == "pw-123"
        restarted.close()

    def test_executed_query_is_reported(self, qtbot, window):
        self.connect(qtbot, window)
        self.run(qtbot, window, "SELECT n\n  FROM t;")
        text = window.message_label.text()
        assert text == "Query eseguita: SELECT n FROM t"
        assert window.message_label.toolTip() == ""

    def test_long_executed_query_is_cut(self, qtbot, window):
        self.connect(qtbot, window)
        columns = ", ".join("c{}".format(i) for i in range(80))
        sql = "SELECT {} FROM t WHERE a < b".format(columns)
        self.run(qtbot, window, sql)
        text = window.message_label.text()
        assert text.startswith("Query eseguita: SELECT c0, c1")
        assert text.endswith("…")
        assert window.message_label.toolTip() == sql

    def test_query_without_result_set_is_reported(
        self, qtbot, window, connector
    ):
        self.connect(qtbot, window)
        connector.connections[0].handler = lambda sql: ([], [])
        self.run(qtbot, window, "SHOW WARNINGS")
        assert window.message_label.text() == (
            "Query eseguita (nessun risultato tabellare): SHOW WARNINGS"
        )

    def test_query_preview(self):
        assert MainWindow.query_preview(" SELECT\n\t1 ") == "SELECT 1"
        preview = MainWindow.query_preview("x" * 500)
        assert preview.endswith("…")
        assert len(preview) == len(MainWindow.query_preview("y" * 900))
