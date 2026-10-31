import datetime as dt
import threading
from decimal import Decimal

import pytest
from mysql.connector import errors as mysql_errors
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QTextCursor

from fakes import FakeConnector
from querylean.config.config_manager import ConfigManager, ConnectionConfig
from querylean.config.secret_storage import SecretStorage
from querylean.database.connection_manager import ConnectionManager
from querylean.ui.connection_dialog import ConnectionDialog
from querylean.ui.db_worker import DbThread
from querylean.ui.main_window import ConnState, MainWindow
from test_secret_storage import MemoryKeyring


@pytest.fixture
def connector():
    return FakeConnector()


@pytest.fixture
def window(qtbot, tmp_path, connector):
    config_manager = ConfigManager(tmp_path / "config.json")
    win = MainWindow(config_manager, SecretStorage(MemoryKeyring()),
                     DbThread(ConnectionManager(connector)))
    qtbot.addWidget(win)
    win.show()
    yield win
    if not win._closed:
        win.close()


def configure(window, password="pw"):
    window.app_config.connection = ConnectionConfig(host="db", database="app", username="ro")
    window.password = password


def connect(qtbot, window):
    configure(window)
    window.toggle_connection()
    qtbot.waitUntil(lambda: window.state == ConnState.CONNECTED, timeout=3000)


def run(qtbot, window, sql):
    window.editor.setPlainText(sql)
    window.execute_query()
    qtbot.waitUntil(lambda: not window.running, timeout=5000)


def test_main_window_opens_disconnected(window):
    assert window.isVisible()
    assert window.state == ConnState.DISCONNECTED
    assert "Disconnesso" in window.state_label.text()
    assert not window.execute_action.isEnabled()
    assert not window.stop_action.isEnabled()


def test_connection_dialog_validates_required_fields(qtbot, window):
    dialog = ConnectionDialog(ConnectionConfig(), "", window.worker, keyring_available=True)
    qtbot.addWidget(dialog)
    assert dialog.host.text() == "localhost" and dialog.port.value() == 3306
    assert dialog.connect_timeout.value() == 5
    assert dialog.password.echoMode() == dialog.password.EchoMode.Password
    dialog._on_save()
    assert dialog.result() != ConnectionDialog.DialogCode.Accepted
    for field in ("Database", "Username", "Password"):
        assert field in dialog.status.text()
    dialog.show_password.setChecked(True)
    assert dialog.password.echoMode() == dialog.password.EchoMode.Normal


def test_connection_dialog_test_button(qtbot, window, connector):
    dialog = ConnectionDialog(ConnectionConfig(database="app", username="ro"), "pw",
                              window.worker, keyring_available=True)
    qtbot.addWidget(dialog)
    dialog._on_test()
    qtbot.waitUntil(lambda: dialog.test_button.isEnabled(), timeout=3000)
    assert "riuscita" in dialog.status.text()
    connector.error = mysql_errors.ProgrammingError(msg="denied", errno=1045)
    dialog._on_test()
    qtbot.waitUntil(lambda: dialog.test_button.isEnabled(), timeout=3000)
    assert "Autenticazione fallita" in dialog.status.text()


def test_connection_failure_is_shown(qtbot, window, connector):
    connector.error = mysql_errors.InterfaceError(msg="Can't connect", errno=2003)
    configure(window)
    window.toggle_connection()
    qtbot.waitUntil(lambda: window.state == ConnState.ERROR, timeout=3000)
    assert "Impossibile raggiungere" in window.message_label.text()
    assert not window.execute_action.isEnabled()


def test_connect_disconnect_reconnect(qtbot, window):
    connect(qtbot, window)
    assert window.connect_action.text() == "Disconnetti"
    window.toggle_connection()
    qtbot.waitUntil(lambda: window.state == ConnState.DISCONNECTED, timeout=3000)
    window.toggle_connection()
    qtbot.waitUntil(lambda: window.state == ConnState.CONNECTED, timeout=3000)


def test_execute_valid_query_shows_results(qtbot, window, connector):
    connect(qtbot, window)
    run(qtbot, window, "SELECT n FROM t")
    assert window.results.results_model.rowCount() == 3
    assert window.rows_label.text() == "3 righe"
    assert "ms" in window.time_label.text()
    assert window.limit_label.text() == ""


def test_truncation_is_signalled(qtbot, window, connector):
    connect(qtbot, window)
    window.app_config.connection.row_limit = 100
    connector.connections[0].row_count = 5000
    run(qtbot, window, "SELECT n FROM t")
    assert window.results.results_model.rowCount() == 100
    assert "limitati alle prime 100" in window.limit_label.text()


def test_rejected_query_shows_error(qtbot, window):
    connect(qtbot, window)
    run(qtbot, window, "DROP TABLE users")
    assert "Query non consentita" in window.message_label.text()


def test_timeout_is_shown(qtbot, window, connector):
    connect(qtbot, window)
    connector.connections[0].handler = lambda sql: mysql_errors.DatabaseError(
        msg="maximum statement execution time exceeded", errno=3024)
    run(qtbot, window, "SELECT SLEEP(10)")
    assert "Timeout" in window.message_label.text()


def test_gui_stays_responsive_and_query_can_be_stopped(qtbot, window, connector):
    connect(qtbot, window)
    conn = connector.connections[0]
    gate = threading.Event()
    conn.block_fetch = gate

    def on_kill_connection(c):
        original = c.cursor

        def cursor():
            cur = original()
            real_execute = cur.execute

            def execute(sql):
                real_execute(sql)
                if sql.startswith("KILL QUERY"):
                    conn.killed = True
                    gate.set()
            cur.execute = execute
            return cur
        c.cursor = cursor
    connector.configure = on_kill_connection

    window.editor.setPlainText("SELECT n FROM t")
    window.execute_query()
    assert window.running
    assert not window.execute_action.isEnabled()
    assert window.stop_action.isEnabled()
    assert window.progress.isVisible()
    assert "In esecuzione: SELECT n FROM t" in window.running_label.text()
    # Il thread GUI elabora eventi mentre la query è bloccata nel worker.
    qtbot.wait(100)
    window.editor.insertPlainText(" ")
    window.stop_query()
    qtbot.waitUntil(lambda: not window.running, timeout=5000)
    assert "interrotta" in window.message_label.text()
    assert window.execute_action.isEnabled()


def test_execute_uses_selection(qtbot, window, connector):
    connect(qtbot, window)
    window.editor.setPlainText("DELETE FROM t\nSELECT n FROM t")
    cursor = window.editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.Down)
    cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
    window.editor.setTextCursor(cursor)
    assert window.editor.query_text() == "SELECT n FROM t"
    window.execute_query()
    qtbot.waitUntil(lambda: not window.running, timeout=5000)
    assert window.rows_label.text() == "3 righe"


def test_empty_editor_does_nothing(qtbot, window):
    connect(qtbot, window)
    window.editor.setPlainText("   \n ")
    window.execute_query()
    assert not window.running


def test_ctrl_enter_triggers_execution(qtbot, window):
    with qtbot.waitSignal(window.editor.execute_requested, timeout=1000):
        qtbot.keyClick(window.editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)


def test_results_null_vs_empty_and_copy(qtbot, window):
    table = window.results
    table.set_result(
        ["id", "name", "note", "when", "amount"],
        [(1, None, "", dt.date(2024, 1, 2), Decimal("1.50")),
         (2, "a\tb", "x\ny", None, None)],
    )
    model = table.results_model
    assert model.data(model.index(0, 1)) == "NULL"
    assert model.data(model.index(0, 2)) == ""
    assert model.data(model.index(0, 1), Qt.ItemDataRole.FontRole).italic()
    assert not (model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable)

    table.selectAll()
    text = table.copy_selection(headers=True)
    assert text == "id\tname\tnote\twhen\tamount\n1\t\t\t2024-01-02\t1.50\n2\ta b\tx y\t\t"
    assert QGuiApplication.clipboard().text() == text

    table.clearSelection()
    table.selectionModel().select(model.index(1, 0),
                                  table.selectionModel().SelectionFlag.Select)
    assert table.copy_selection() == "2"
    assert table.copy_selection(whole_rows=True) == "2\ta b\tx y\t\t"


def test_config_and_password_persist(qtbot, window, tmp_path):
    keyring_backend = window.secrets.backend
    configure(window, password="pw-123")
    window.close()
    data = (tmp_path / "config.json").read_text()
    assert "pw-123" not in data
    assert '"username": "ro"' in data
    assert window.db.thread.isFinished()
    # riavvio: configurazione e password vengono ripristinate
    window.secrets.set_password("ro@db:3306", "pw-123")
    win2 = MainWindow(ConfigManager(tmp_path / "config.json"), SecretStorage(keyring_backend),
                      DbThread(ConnectionManager(FakeConnector())))
    qtbot.addWidget(win2)
    assert win2.app_config.connection.host == "db"
    assert win2.password == "pw-123"
    win2.close()
