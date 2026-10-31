"""Finestra principale: barra superiore, editor SQL e pannello dei risultati."""

from __future__ import annotations

import base64
import logging
from enum import Enum

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from querylean import APP_DISPLAY_NAME
from querylean.config.config_manager import AppConfig, ConfigError, ConfigManager
from querylean.config.secret_storage import (
    SecretStorage,
    SecretStorageError,
    account_key,
)
from querylean.database.query_executor import QueryResult
from querylean.ui.connection_dialog import ConnectionDialog
from querylean.ui.db_worker import DbThread
from querylean.ui.results_table import ResultsTable
from querylean.ui.sql_editor import SqlEditor
from querylean.utils.logging_config import redacting_filter

log = logging.getLogger(__name__)

# Margine oltre il timeout della query prima che il watchdog invii KILL QUERY: lascia
# intervenire per primo MAX_EXECUTION_TIME lato server.
WATCHDOG_GRACE_MS = 2000


class ConnState(Enum):
    DISCONNECTED = ("Disconnesso", "#757575")
    CONNECTING = ("Connessione in corso…", "#ef6c00")
    CONNECTED = ("Connesso", "#2e7d32")
    ERROR = ("Errore di connessione", "#c62828")


class MainWindow(QMainWindow):
    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        secrets: SecretStorage | None = None,
        db: DbThread | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.config_manager = config_manager or ConfigManager()
        self.secrets = secrets or SecretStorage()
        self.db = db or DbThread()
        self.worker = self.db.worker
        self.app_config: AppConfig = self.config_manager.load()
        self.password = ""
        self.state = ConnState.DISCONNECTED
        self.running = False
        self._closed = False

        self._build_toolbar()
        self._build_body()
        self._connect_worker()

        self.watchdog = QTimer(self)
        self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(self._on_watchdog)

        self._restore_geometry()
        self._load_password()
        self._set_state(ConnState.DISCONNECTED)
        self._update_actions()

    # ------------------------------------------------------------------ costruzione UI
    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Principale", self)
        toolbar.setObjectName("main-toolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(toolbar)

        self.state_label = QLabel()
        self.state_label.setContentsMargins(6, 0, 12, 0)
        toolbar.addWidget(self.state_label)
        toolbar.addSeparator()

        self.config_action = QAction("Configurazione", self)
        self.config_action.triggered.connect(self.open_configuration)
        self.connect_action = QAction("Connetti", self)
        self.connect_action.triggered.connect(self.toggle_connection)
        self.execute_action = QAction("Esegui", self)
        self.execute_action.setToolTip("Esegui la selezione o l'intera query (Ctrl/Cmd+Invio)")
        self.execute_action.triggered.connect(self.execute_query)
        self.stop_action = QAction("Interrompi", self)
        self.stop_action.triggered.connect(self.stop_query)
        for action in (self.config_action, self.connect_action, self.execute_action,
                       self.stop_action):
            toolbar.addAction(action)

        quit_action = QAction(self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

    def _build_body(self) -> None:
        self.editor = SqlEditor()
        self.editor.execute_requested.connect(self.execute_query)

        self.results = ResultsTable()
        self.rows_label = QLabel()
        self.time_label = QLabel()
        self.limit_label = QLabel()
        self.limit_label.setStyleSheet("color: #ef6c00; font-weight: bold;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminata
        self.progress.setMaximumWidth(120)
        self.progress.setMaximumHeight(14)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.running_label = QLabel()
        self.running_label.setStyleSheet("color: palette(placeholder-text);")
        self.running_label.hide()

        info = QHBoxLayout()
        info.addWidget(self.progress)
        info.addWidget(self.rows_label)
        info.addWidget(self.time_label)
        info.addWidget(self.limit_label)
        info.addStretch(1)

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 4, 0, 0)
        panel_layout.addWidget(self.results, 1)
        panel_layout.addLayout(info)
        panel_layout.addWidget(self.running_label)
        panel_layout.addWidget(self.message_label)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setObjectName("editor-results-splitter")
        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(panel)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setChildrenCollapsible(False)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.splitter)
        self.setCentralWidget(container)
        self.resize(1000, 700)

    def _connect_worker(self) -> None:
        self.worker.connected.connect(self._on_connected)
        self.worker.connect_failed.connect(self._on_connect_failed)
        self.worker.disconnected.connect(self._on_disconnected)
        self.worker.query_finished.connect(self._on_query_finished)
        self.worker.query_failed.connect(self._on_query_failed)

    # ------------------------------------------------------------------ stato
    def _set_state(self, state: ConnState) -> None:
        self.state = state
        text, color = state.value
        self.state_label.setText(f"<b style='color:{color}'>●</b> {text}")
        self._update_actions()

    def _update_actions(self) -> None:
        connected = self.state == ConnState.CONNECTED
        busy = self.state == ConnState.CONNECTING
        self.connect_action.setText("Disconnetti" if connected else "Connetti")
        self.connect_action.setEnabled(not busy and not self.running)
        self.config_action.setEnabled(not busy and not self.running)
        self.execute_action.setEnabled(connected and not self.running)
        self.stop_action.setEnabled(self.running)

    def show_message(self, text: str, *, error: bool = False) -> None:
        self.message_label.setStyleSheet("color: #c62828;" if error else "")
        self.message_label.setText(text)

    # ------------------------------------------------------------------ password
    def _secret_key(self) -> str:
        cfg = self.app_config.connection
        return account_key(cfg.username, cfg.host, cfg.port)

    def _load_password(self) -> None:
        if not self.app_config.connection.username:
            return
        try:
            self.password = self.secrets.get_password(self._secret_key()) or ""
        except SecretStorageError as exc:
            self.show_message(exc.args[0], error=True)
            self.password = ""
        redacting_filter.register_secret(self.password)

    def _ask_password(self) -> bool:
        password, ok = QInputDialog.getText(
            self,
            "Password",
            f"Password per {self.app_config.connection.username}@"
            f"{self.app_config.connection.host}:",
            QLineEdit.EchoMode.Password,
        )
        if ok and password:
            self.password = password
            redacting_filter.register_secret(password)
            return True
        return False

    # ------------------------------------------------------------------ azioni
    def open_configuration(self) -> None:
        dialog = ConnectionDialog(
            self.app_config.connection,
            self.password,
            self.worker,
            keyring_available=self.secrets.is_available(),
            parent=self,
        )
        if dialog.exec() != ConnectionDialog.DialogCode.Accepted:
            return
        old_key = self._secret_key() if self.app_config.connection.username else None
        self.app_config.connection = dialog.config().normalized()
        self.password = dialog.password_value()
        redacting_filter.register_secret(self.password)
        self._save_config()

        if dialog.remember_password.isChecked():
            try:
                new_key = self._secret_key()
                if old_key is not None and old_key != new_key:
                    self.secrets.delete_password(old_key)
                self.secrets.set_password(new_key, self.password)
                self.show_message("Configurazione salvata. Password salvata nel portachiavi.")
            except SecretStorageError as exc:
                self.show_message(
                    f"Configurazione salvata. {exc.args[0]}", error=True
                )
        else:
            self.show_message(
                "Configurazione salvata. La password resterà in memoria solo per questa sessione."
            )
        if self.state == ConnState.CONNECTED:
            self.show_message(
                self.message_label.text() + " Riconnettiti per applicare le modifiche."
            )

    def _save_config(self) -> None:
        try:
            self.config_manager.save(self.app_config)
        except ConfigError as exc:
            QMessageBox.warning(self, "Configurazione", str(exc))

    def toggle_connection(self) -> None:
        if self.state == ConnState.CONNECTED:
            self.worker.disconnect_requested.emit()
            return
        cfg = self.app_config.connection
        if not cfg.is_complete():
            self.show_message("Configurazione incompleta: compila i campi obbligatori.",
                              error=True)
            self.open_configuration()
            cfg = self.app_config.connection
            if not cfg.is_complete():
                return
        if not self.password and not self._ask_password():
            self.show_message("Connessione annullata: password non inserita.", error=True)
            return
        self._set_state(ConnState.CONNECTING)
        self.show_message(f"Connessione a {cfg.host}:{cfg.port}/{cfg.database}…")
        self.worker.connect_requested.emit(cfg, self.password)

    def execute_query(self) -> None:
        if self.running:
            return
        sql = self.editor.query_text()
        if not sql.strip():
            return
        if self.state != ConnState.CONNECTED:
            self.show_message("Non connesso: premi «Connetti» prima di eseguire una query.",
                              error=True)
            return
        cfg = self.app_config.connection
        self.running = True
        self._update_actions()
        self.progress.show()
        self.rows_label.clear()
        self.time_label.clear()
        self.limit_label.clear()
        single_line = " ".join(sql.split())
        elided = single_line if len(single_line) <= 160 else single_line[:157] + "…"
        self.running_label.setText(f"In esecuzione: {elided}")
        self.running_label.show()
        self.show_message("Esecuzione in corso…")
        self.watchdog.start(cfg.query_timeout * 1000 + WATCHDOG_GRACE_MS)
        self.worker.query_requested.emit(sql, cfg.row_limit, cfg.query_timeout)

    def stop_query(self) -> None:
        if self.running:
            self.show_message("Interruzione in corso…")
            self.stop_action.setEnabled(False)
            self.worker.cancel_query("user")

    def _on_watchdog(self) -> None:
        if self.running:
            log.info("Watchdog: query oltre il timeout, invio KILL QUERY")
            self.worker.cancel_query("timeout")

    # ------------------------------------------------------------------ risposte worker
    def _on_connected(self) -> None:
        cfg = self.app_config.connection
        self._set_state(ConnState.CONNECTED)
        self.show_message(f"Connesso a {cfg.host}:{cfg.port}/{cfg.database}.")
        self.editor.setFocus()

    def _on_connect_failed(self, message: str) -> None:
        self._set_state(ConnState.ERROR)
        self.show_message(message, error=True)

    def _on_disconnected(self) -> None:
        if self._closed or self.state == ConnState.ERROR:
            return  # mantiene visibile l'errore che ha causato la disconnessione
        self._set_state(ConnState.DISCONNECTED)
        self.show_message("Disconnesso.")

    def _finish_run(self) -> None:
        self.watchdog.stop()
        self.running = False
        self.progress.hide()
        self.running_label.clear()
        self.running_label.hide()
        self._update_actions()

    def _on_query_finished(self, result: QueryResult) -> None:
        self._finish_run()
        self.results.set_result(result.columns, result.rows)
        self.rows_label.setText(f"{len(result.rows)} righe")
        self.time_label.setText(f"· {result.elapsed * 1000:.0f} ms")
        if result.truncated:
            self.limit_label.setText(
                f"· Risultati limitati alle prime {result.row_limit} righe"
            )
        self.show_message("Query eseguita." if result.columns else
                          "Query eseguita: nessun risultato tabellare.")

    def _on_query_failed(self, message: str, kind: str) -> None:
        self._finish_run()
        self.show_message(message, error=True)
        if kind == "not_connected":
            self._set_state(ConnState.DISCONNECTED)
        elif kind == "connection_lost":
            self._set_state(ConnState.ERROR)
            self.worker.disconnect_requested.emit()

    # ------------------------------------------------------------------ geometria/chiusura
    def _restore_geometry(self) -> None:
        ui = self.app_config.ui
        try:
            if ui.window_geometry:
                self.restoreGeometry(QByteArray(base64.b64decode(ui.window_geometry)))
            if ui.splitter_state:
                self.splitter.restoreState(QByteArray(base64.b64decode(ui.splitter_state)))
        except (ValueError, TypeError):
            log.warning("Geometria della finestra non valida: ignorata")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._closed:
            event.accept()
            return
        self._closed = True
        self.watchdog.stop()
        self.app_config.ui.window_geometry = base64.b64encode(
            bytes(self.saveGeometry().data())
        ).decode("ascii")
        self.app_config.ui.splitter_state = base64.b64encode(
            bytes(self.splitter.saveState().data())
        ).decode("ascii")
        try:
            self.config_manager.save(self.app_config)
        except ConfigError as exc:
            log.warning("Salvataggio della configurazione alla chiusura fallito: %s", exc)
        self.db.shutdown()
        event.accept()
