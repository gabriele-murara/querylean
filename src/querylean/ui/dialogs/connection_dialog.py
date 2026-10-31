"""Configuration dialog of the single connection."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from querylean.config.connection_config import ConnectionConfig
from querylean.ui.worker.db_worker import DbWorker


class ConnectionDialog(QDialog):
    """Edits host, port, database, credentials, timeouts and row limit; offers
    "Test connessione" (asynchronous, through the worker) and "Salva
    configurazione"."""

    __OK_COLOR = "#1a7f37"
    __ERROR_COLOR = "#c62828"
    __ROW_LIMIT_STEP = 100

    def __init__(
        self,
        config: ConnectionConfig,
        password: str,
        worker: DbWorker,
        *,
        keyring_available: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurazione connessione")
        self.setMinimumWidth(440)
        self.__worker = worker

        self.__host = QLineEdit(config.host)
        self.__port = ConnectionDialog.__spin(
            1, ConnectionConfig.MAX_PORT, config.port
        )
        self.__database = QLineEdit(config.database)
        self.__username = QLineEdit(config.username)
        self.__password = QLineEdit(password)
        self.__password.setEchoMode(QLineEdit.EchoMode.Password)
        self.__show_password = QCheckBox("Mostra password")
        self.__show_password.toggled.connect(self.__on_toggle_password)

        self.__remember_password = QCheckBox(
            "Salva la password nel portachiavi di sistema"
        )
        self.__remember_password.setChecked(keyring_available)
        self.__remember_password.setEnabled(keyring_available)
        if not keyring_available:
            self.__remember_password.setToolTip(
                "Portachiavi non disponibile: la password resterà in memoria "
                "solo per questa sessione."
            )

        max_timeout = ConnectionConfig.MAX_TIMEOUT_SECONDS
        self.__connect_timeout = ConnectionDialog.__spin(
            1, max_timeout, config.connect_timeout, " s"
        )
        self.__query_timeout = ConnectionDialog.__spin(
            1, max_timeout, config.query_timeout, " s"
        )
        self.__row_limit = ConnectionDialog.__spin(
            1, ConnectionConfig.MAX_ROW_LIMIT, config.row_limit
        )
        self.__row_limit.setSingleStep(ConnectionDialog.__ROW_LIMIT_STEP)

        form = QFormLayout()
        form.addRow("Host *", self.__host)
        form.addRow("Porta *", self.__port)
        form.addRow("Database *", self.__database)
        form.addRow("Username *", self.__username)
        form.addRow("Password *", self.__password)
        form.addRow("", self.__show_password)
        form.addRow("", self.__remember_password)
        form.addRow("Timeout connessione", self.__connect_timeout)
        form.addRow("Timeout query", self.__query_timeout)
        form.addRow("Righe massime", self.__row_limit)

        hint = QLabel(
            "Usa un account MySQL con soli privilegi SELECT: la modalità di "
            "sola lettura è garantita principalmente dai privilegi "
            "dell'account."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(placeholder-text);")

        self.__status = QLabel()
        self.__status.setWordWrap(True)
        self.__status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.__test_button = QPushButton("Test connessione")
        self.__test_button.clicked.connect(self.test_connection)
        buttons = QDialogButtonBox()
        self.__save_button = buttons.addButton(
            "Salva configurazione", QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        bottom = QHBoxLayout()
        bottom.addWidget(self.__test_button)
        bottom.addStretch(1)
        bottom.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(self.__status)
        layout.addLayout(bottom)

        worker.test_finished.connect(self.__on_test_finished)

    # ------------------------------------------------------------------ widgets
    @property
    def host(self) -> QLineEdit:
        """Host field."""
        return self.__host

    @property
    def port(self) -> QSpinBox:
        """Port field."""
        return self.__port

    @property
    def database(self) -> QLineEdit:
        """Database field."""
        return self.__database

    @property
    def username(self) -> QLineEdit:
        """Username field."""
        return self.__username

    @property
    def password(self) -> QLineEdit:
        """Masked password field."""
        return self.__password

    @property
    def show_password(self) -> QCheckBox:
        """Toggle that temporarily reveals the password."""
        return self.__show_password

    @property
    def remember_password(self) -> QCheckBox:
        """Whether the password is stored in the keychain."""
        return self.__remember_password

    @property
    def connect_timeout(self) -> QSpinBox:
        """Connection timeout field (seconds)."""
        return self.__connect_timeout

    @property
    def query_timeout(self) -> QSpinBox:
        """Query timeout field (seconds)."""
        return self.__query_timeout

    @property
    def row_limit(self) -> QSpinBox:
        """Row limit field."""
        return self.__row_limit

    @property
    def status(self) -> QLabel:
        """Validation and test outcome label."""
        return self.__status

    @property
    def test_button(self) -> QPushButton:
        """ "Test connessione" button."""
        return self.__test_button

    @property
    def save_button(self) -> QPushButton:
        """ "Salva configurazione" button."""
        return self.__save_button

    # ------------------------------------------------------------------ values
    def config(self) -> ConnectionConfig:
        """Configuration currently entered in the form."""
        return ConnectionConfig(
            host=self.__host.text(),
            port=self.__port.value(),
            database=self.__database.text(),
            username=self.__username.text(),
            connect_timeout=self.__connect_timeout.value(),
            query_timeout=self.__query_timeout.value(),
            row_limit=self.__row_limit.value(),
        )

    def password_value(self) -> str:
        """Password currently entered."""
        return self.__password.text()

    def missing_fields(self) -> list[str]:
        """Labels of required fields that are empty, password included."""
        missing = self.config().missing_fields()
        if not self.password_value():
            missing.append("Password")
        return missing

    # ------------------------------------------------------------------ actions
    def test_connection(self) -> None:
        """Ask the worker to test the entered parameters."""
        if not self.__check_required():
            return
        self.__test_button.setEnabled(False)
        self.__status.setStyleSheet("")
        self.__status.setText("Test della connessione in corso…")
        self.__worker.test_requested.emit(self.config(), self.password_value())

    def save(self) -> None:
        """Accept the dialog when every required field is filled in."""
        if self.__check_required():
            self.accept()

    def done(self, result: int) -> None:
        """Disconnect from the worker before closing."""
        try:
            self.__worker.test_finished.disconnect(self.__on_test_finished)
        except (RuntimeError, TypeError):
            pass
        super().done(result)

    # ---------------------------------------------------------------- internals
    def __check_required(self) -> bool:
        missing = self.missing_fields()
        if missing:
            self.__set_status(
                False, "Campi obbligatori mancanti: " + ", ".join(missing) + "."
            )
            return False
        return True

    def __on_test_finished(self, ok: bool, message: str) -> None:
        self.__test_button.setEnabled(True)
        self.__set_status(ok, message)

    def __on_toggle_password(self, visible: bool) -> None:
        self.__password.setEchoMode(
            QLineEdit.EchoMode.Normal
            if visible
            else QLineEdit.EchoMode.Password
        )

    def __set_status(self, ok: bool, message: str) -> None:
        color = (
            ConnectionDialog.__OK_COLOR
            if ok
            else ConnectionDialog.__ERROR_COLOR
        )
        self.__status.setStyleSheet(f"color: {color};")
        self.__status.setText(message)

    @staticmethod
    def __spin(low: int, high: int, value: int, suffix: str = "") -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        spin.setSuffix(suffix)
        return spin
