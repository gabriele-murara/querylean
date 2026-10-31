"""Main window: toolbar, SQL editor and result panel."""

from __future__ import annotations

import base64

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

from querylean.app.app_info import AppInfo
from querylean.config.app_config import AppConfig
from querylean.config.config_error import ConfigError
from querylean.config.config_manager import ConfigManager
from querylean.database.execution.query_executor import QueryExecutor
from querylean.database.execution.query_result import QueryResult
from querylean.log.log_manager import LogManager
from querylean.security.keyring_secret_store import KeyringSecretStore
from querylean.security.secret_storage_error import SecretStorageError
from querylean.security.secret_store import SecretStore
from querylean.ui.dialogs.connection_dialog import ConnectionDialog
from querylean.ui.editor.sql_editor import SqlEditor
from querylean.ui.main.connection_state import ConnectionState
from querylean.ui.results.results_table import ResultsTable
from querylean.ui.worker.db_thread import DbThread
from querylean.ui.worker.db_worker import DbWorker


class MainWindow(QMainWindow):
    """Toolbar (state, configuration, connect, run, stop), editor and result panel
    separated by a resizable splitter."""

    # Delay after the query timeout before the watchdog sends KILL QUERY: lets the
    # server-side MAX_EXECUTION_TIME act first.
    WATCHDOG_GRACE_MS = 2000
    __MAX_RUNNING_PREVIEW = 160
    __ERROR_STYLE = "color: #c62828;"
    __log = LogManager.get_logger(__name__)

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        secrets: SecretStore | None = None,
        db: DbThread | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(AppInfo.DISPLAY_NAME)
        self.__config_manager = config_manager or ConfigManager()
        self.__secrets = secrets or KeyringSecretStore()
        self.__db = db or DbThread()
        self.__app_config: AppConfig = self.__config_manager.load()
        self.__password = ""
        self.__state = ConnectionState.DISCONNECTED
        self.__running = False
        self.__closed = False

        self.__build_toolbar()
        self.__build_body()
        self.__connect_worker()

        self.__watchdog = QTimer(self)
        self.__watchdog.setSingleShot(True)
        self.__watchdog.timeout.connect(self.__on_watchdog)

        self.__restore_geometry()
        self.__load_password()
        self.__set_state(ConnectionState.DISCONNECTED)

    # ------------------------------------------------------------------ properties
    @property
    def config_manager(self) -> ConfigManager:
        """Configuration persistence."""
        return self.__config_manager

    @property
    def secrets(self) -> SecretStore:
        """Password storage."""
        return self.__secrets

    @property
    def db(self) -> DbThread:
        """Database thread."""
        return self.__db

    @property
    def worker(self) -> DbWorker:
        """Database worker."""
        return self.__db.worker

    @property
    def app_config(self) -> AppConfig:
        """Current configuration."""
        return self.__app_config

    @app_config.setter
    def app_config(self, value: AppConfig) -> None:
        self.__app_config = value

    @property
    def password(self) -> str:
        """Password kept in memory for the session."""
        return self.__password

    @password.setter
    def password(self, value: str) -> None:
        self.__password = value
        LogManager.register_secret(value)

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self.__state

    @property
    def running(self) -> bool:
        """True while a query is executing."""
        return self.__running

    @property
    def closed(self) -> bool:
        """True once the window has been closed and resources released."""
        return self.__closed

    @property
    def editor(self) -> SqlEditor:
        """SQL editor."""
        return self.__editor

    @property
    def results(self) -> ResultsTable:
        """Result table."""
        return self.__results

    @property
    def splitter(self) -> QSplitter:
        """Splitter between editor and result panel."""
        return self.__splitter

    @property
    def state_label(self) -> QLabel:
        """Connection state indicator."""
        return self.__state_label

    @property
    def rows_label(self) -> QLabel:
        """Number of loaded rows."""
        return self.__rows_label

    @property
    def time_label(self) -> QLabel:
        """Execution time."""
        return self.__time_label

    @property
    def limit_label(self) -> QLabel:
        """Truncation notice."""
        return self.__limit_label

    @property
    def message_label(self) -> QLabel:
        """Status and error messages."""
        return self.__message_label

    @property
    def running_label(self) -> QLabel:
        """Query currently running."""
        return self.__running_label

    @property
    def progress(self) -> QProgressBar:
        """Activity indicator."""
        return self.__progress

    @property
    def config_action(self) -> QAction:
        """"Configurazione" action."""
        return self.__config_action

    @property
    def connect_action(self) -> QAction:
        """"Connetti"/"Disconnetti" action."""
        return self.__connect_action

    @property
    def execute_action(self) -> QAction:
        """"Esegui" action."""
        return self.__execute_action

    @property
    def stop_action(self) -> QAction:
        """"Interrompi" action."""
        return self.__stop_action

    # ------------------------------------------------------------------ actions
    def show_message(self, text: str, *, error: bool = False) -> None:
        """Show a status (or error) message in the result panel."""
        self.__message_label.setStyleSheet(MainWindow.__ERROR_STYLE if error else "")
        self.__message_label.setText(text)

    def open_configuration(self) -> None:
        """Open the configuration dialog and persist the accepted values."""
        dialog = ConnectionDialog(
            self.__app_config.connection,
            self.__password,
            self.worker,
            keyring_available=self.__secrets.is_available(),
            parent=self,
        )
        if dialog.exec() != ConnectionDialog.DialogCode.Accepted:
            return
        old_key = self.__secret_key() if self.__app_config.connection.username else None
        self.__app_config.connection = dialog.config()
        self.password = dialog.password_value()
        self.__save_config()

        if dialog.remember_password.isChecked():
            try:
                new_key = self.__secret_key()
                if old_key is not None and old_key != new_key:
                    self.__secrets.delete_password(old_key)
                self.__secrets.set_password(new_key, self.__password)
                self.show_message("Configurazione salvata. Password salvata nel portachiavi.")
            except SecretStorageError as exc:
                self.show_message(f"Configurazione salvata. {exc}", error=True)
        else:
            self.show_message(
                "Configurazione salvata. La password resterà in memoria solo per questa sessione."
            )
        if self.__state == ConnectionState.CONNECTED:
            self.show_message(
                self.__message_label.text() + " Riconnettiti per applicare le modifiche."
            )

    def toggle_connection(self) -> None:
        """Connect, or disconnect when already connected."""
        if self.__state == ConnectionState.CONNECTED:
            self.worker.disconnect_requested.emit()
            return
        cfg = self.__app_config.connection
        if not cfg.is_complete():
            self.show_message(
                "Configurazione incompleta: compila i campi obbligatori.", error=True
            )
            self.open_configuration()
            cfg = self.__app_config.connection
            if not cfg.is_complete():
                return
        if not self.__password and not self.__ask_password():
            self.show_message("Connessione annullata: password non inserita.", error=True)
            return
        self.__set_state(ConnectionState.CONNECTING)
        self.show_message(f"Connessione a {cfg.host}:{cfg.port}/{cfg.database}…")
        self.worker.connect_requested.emit(cfg.copy(), self.__password)

    def execute_query(self) -> None:
        """Run the selection, or the whole editor content when nothing is selected."""
        if self.__running:
            return
        sql = self.__editor.query_text()
        if not sql.strip():
            return
        if self.__state != ConnectionState.CONNECTED:
            self.show_message(
                "Non connesso: premi «Connetti» prima di eseguire una query.", error=True
            )
            return
        cfg = self.__app_config.connection
        self.__running = True
        self.__update_actions()
        self.__progress.show()
        self.__rows_label.clear()
        self.__time_label.clear()
        self.__limit_label.clear()
        single_line = " ".join(sql.split())
        limit = MainWindow.__MAX_RUNNING_PREVIEW
        preview = single_line if len(single_line) <= limit else single_line[: limit - 3] + "…"
        self.__running_label.setText(f"In esecuzione: {preview}")
        self.__running_label.show()
        self.show_message("Esecuzione in corso…")
        self.__watchdog.start(cfg.query_timeout * 1000 + MainWindow.WATCHDOG_GRACE_MS)
        self.worker.query_requested.emit(sql, cfg.row_limit, cfg.query_timeout)

    def stop_query(self) -> None:
        """Interrupt the running query."""
        if self.__running:
            self.show_message("Interruzione in corso…")
            self.__stop_action.setEnabled(False)
            self.worker.cancel_query(QueryExecutor.CANCEL_BY_USER)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Save window geometry and configuration, then release database resources."""
        if self.__closed:
            event.accept()
            return
        self.__closed = True
        self.__watchdog.stop()
        ui = self.__app_config.ui
        ui.window_geometry = MainWindow.__encode(self.saveGeometry())
        ui.splitter_state = MainWindow.__encode(self.__splitter.saveState())
        try:
            self.__config_manager.save(self.__app_config)
        except ConfigError as exc:
            self.__log.warning("Saving the configuration on close failed: %s", exc)
        self.__db.shutdown()
        event.accept()

    # ------------------------------------------------------------------ UI construction
    def __build_toolbar(self) -> None:
        toolbar = QToolBar("Principale", self)
        toolbar.setObjectName("main-toolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(toolbar)

        self.__state_label = QLabel()
        self.__state_label.setContentsMargins(6, 0, 12, 0)
        toolbar.addWidget(self.__state_label)
        toolbar.addSeparator()

        self.__config_action = QAction("Configurazione", self)
        self.__config_action.triggered.connect(self.open_configuration)
        self.__connect_action = QAction("Connetti", self)
        self.__connect_action.triggered.connect(self.toggle_connection)
        self.__execute_action = QAction("Esegui", self)
        self.__execute_action.setToolTip(
            "Esegui la selezione o l'intera query (Ctrl/Cmd+Invio)"
        )
        self.__execute_action.triggered.connect(self.execute_query)
        self.__stop_action = QAction("Interrompi", self)
        self.__stop_action.triggered.connect(self.stop_query)
        for action in (
            self.__config_action,
            self.__connect_action,
            self.__execute_action,
            self.__stop_action,
        ):
            toolbar.addAction(action)

        quit_action = QAction(self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

    def __build_body(self) -> None:
        self.__editor = SqlEditor()
        self.__editor.execute_requested.connect(self.execute_query)

        self.__results = ResultsTable()
        self.__rows_label = QLabel()
        self.__time_label = QLabel()
        self.__limit_label = QLabel()
        self.__limit_label.setStyleSheet("color: #ef6c00; font-weight: bold;")
        self.__progress = QProgressBar()
        self.__progress.setRange(0, 0)  # indeterminate
        self.__progress.setMaximumWidth(120)
        self.__progress.setMaximumHeight(14)
        self.__progress.setTextVisible(False)
        self.__progress.hide()
        self.__message_label = QLabel()
        self.__message_label.setWordWrap(True)
        self.__message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.__running_label = QLabel()
        self.__running_label.setStyleSheet("color: palette(placeholder-text);")
        self.__running_label.hide()

        info = QHBoxLayout()
        info.addWidget(self.__progress)
        info.addWidget(self.__rows_label)
        info.addWidget(self.__time_label)
        info.addWidget(self.__limit_label)
        info.addStretch(1)

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 4, 0, 0)
        panel_layout.addWidget(self.__results, 1)
        panel_layout.addLayout(info)
        panel_layout.addWidget(self.__running_label)
        panel_layout.addWidget(self.__message_label)

        self.__splitter = QSplitter(Qt.Orientation.Vertical)
        self.__splitter.setObjectName("editor-results-splitter")
        self.__splitter.addWidget(self.__editor)
        self.__splitter.addWidget(panel)
        self.__splitter.setStretchFactor(0, 2)
        self.__splitter.setStretchFactor(1, 3)
        self.__splitter.setChildrenCollapsible(False)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.__splitter)
        self.setCentralWidget(container)
        self.resize(1000, 700)

    def __connect_worker(self) -> None:
        worker = self.worker
        worker.connected.connect(self.__on_connected)
        worker.connect_failed.connect(self.__on_connect_failed)
        worker.disconnected.connect(self.__on_disconnected)
        worker.query_finished.connect(self.__on_query_finished)
        worker.query_failed.connect(self.__on_query_failed)

    # ------------------------------------------------------------------ state
    def __set_state(self, state: ConnectionState) -> None:
        self.__state = state
        self.__state_label.setText(f"<b style='color:{state.color}'>●</b> {state.label}")
        self.__update_actions()

    def __update_actions(self) -> None:
        connected = self.__state == ConnectionState.CONNECTED
        busy = self.__state == ConnectionState.CONNECTING
        self.__connect_action.setText("Disconnetti" if connected else "Connetti")
        self.__connect_action.setEnabled(not busy and not self.__running)
        self.__config_action.setEnabled(not busy and not self.__running)
        self.__execute_action.setEnabled(connected and not self.__running)
        self.__stop_action.setEnabled(self.__running)

    # ------------------------------------------------------------------ password
    def __secret_key(self) -> str:
        cfg = self.__app_config.connection
        return SecretStore.account_key(cfg.username, cfg.host, cfg.port)

    def __load_password(self) -> None:
        if not self.__app_config.connection.username:
            return
        try:
            self.password = self.__secrets.get_password(self.__secret_key()) or ""
        except SecretStorageError as exc:
            self.show_message(str(exc), error=True)
            self.password = ""

    def __ask_password(self) -> bool:
        cfg = self.__app_config.connection
        password, ok = QInputDialog.getText(
            self,
            "Password",
            f"Password per {cfg.username}@{cfg.host}:",
            QLineEdit.EchoMode.Password,
        )
        if ok and password:
            self.password = password
            return True
        return False

    def __save_config(self) -> None:
        try:
            self.__config_manager.save(self.__app_config)
        except ConfigError as exc:
            QMessageBox.warning(self, "Configurazione", str(exc))

    # ------------------------------------------------------------------ worker responses
    def __on_watchdog(self) -> None:
        if self.__running:
            self.__log.info("Watchdog: query exceeded its timeout, sending KILL QUERY")
            self.worker.cancel_query(QueryExecutor.CANCEL_BY_TIMEOUT)

    def __on_connected(self) -> None:
        cfg = self.__app_config.connection
        self.__set_state(ConnectionState.CONNECTED)
        self.show_message(f"Connesso a {cfg.host}:{cfg.port}/{cfg.database}.")
        self.__editor.setFocus()

    def __on_connect_failed(self, message: str) -> None:
        self.__set_state(ConnectionState.ERROR)
        self.show_message(message, error=True)

    def __on_disconnected(self) -> None:
        if self.__closed or self.__state == ConnectionState.ERROR:
            return  # keep showing the error that caused the disconnection
        self.__set_state(ConnectionState.DISCONNECTED)
        self.show_message("Disconnesso.")

    def __finish_run(self) -> None:
        self.__watchdog.stop()
        self.__running = False
        self.__progress.hide()
        self.__running_label.clear()
        self.__running_label.hide()
        self.__update_actions()

    def __on_query_finished(self, result: QueryResult) -> None:
        self.__finish_run()
        self.__results.set_result(result.columns, result.rows)
        self.__rows_label.setText(f"{len(result.rows)} righe")
        self.__time_label.setText(f"· {result.elapsed * 1000:.0f} ms")
        if result.truncated:
            self.__limit_label.setText(
                f"· Risultati limitati alle prime {result.row_limit} righe"
            )
        self.show_message(
            "Query eseguita."
            if result.columns
            else "Query eseguita: nessun risultato tabellare."
        )

    def __on_query_failed(self, message: str, kind: str) -> None:
        self.__finish_run()
        self.show_message(message, error=True)
        if kind == "not_connected":
            self.__set_state(ConnectionState.DISCONNECTED)
        elif kind == "connection_lost":
            self.__set_state(ConnectionState.ERROR)
            self.worker.disconnect_requested.emit()

    # ------------------------------------------------------------------ geometry
    def __restore_geometry(self) -> None:
        ui = self.__app_config.ui
        try:
            if ui.window_geometry:
                self.restoreGeometry(QByteArray(base64.b64decode(ui.window_geometry)))
            if ui.splitter_state:
                self.__splitter.restoreState(QByteArray(base64.b64decode(ui.splitter_state)))
        except (ValueError, TypeError):
            self.__log.warning("Invalid window geometry: ignored")

    @staticmethod
    def __encode(data: QByteArray) -> str:
        return base64.b64encode(bytes(data.data())).decode("ascii")
