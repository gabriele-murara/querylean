"""Dialog to create or edit a saved connection."""

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
    """Edits name, host, port, database, credentials, timeouts and row
    limit; offers "Test connection" (asynchronous, through the worker) and
    "Save". The name is optional: when empty the connection is listed as
    ``<user>@<host>/<database>``, shown as placeholder."""

    NEW_TITLE = "New connection"
    EDIT_TITLE = "Edit connection"

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
        title: str = NEW_TITLE,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self.__worker = worker

        self.__name = QLineEdit(config.name)
        self.__host = QLineEdit(config.host)
        self.__port = ConnectionDialog.__spin(
            1, ConnectionConfig.MAX_PORT, config.port
        )
        self.__database = QLineEdit(config.database)
        self.__username = QLineEdit(config.username)
        self.__password = QLineEdit(password)
        self.__password.setEchoMode(QLineEdit.EchoMode.Password)
        self.__show_password = QCheckBox("Show password")
        self.__show_password.toggled.connect(self.__on_toggle_password)

        self.__remember_password = QCheckBox(
            "Save the password in the system keyring"
        )
        self.__remember_password.setChecked(keyring_available)
        self.__remember_password.setEnabled(keyring_available)
        if not keyring_available:
            tip = "Keyring not available: the password will be kept in "
            tip += "memory for this session only."
            self.__remember_password.setToolTip(tip)

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
        form.addRow("Name", self.__name)
        form.addRow("Host *", self.__host)
        form.addRow("Port *", self.__port)
        form.addRow("Database *", self.__database)
        form.addRow("Username *", self.__username)
        form.addRow("Password *", self.__password)
        form.addRow("", self.__show_password)
        form.addRow("", self.__remember_password)
        form.addRow("Connection timeout", self.__connect_timeout)
        form.addRow("Query timeout", self.__query_timeout)
        form.addRow("Maximum rows", self.__row_limit)

        hint_text = "Use a MySQL account with SELECT privileges only: "
        hint_text += "read-only mode is guaranteed mainly by the account "
        hint_text += "privileges."
        hint = QLabel(hint_text)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(placeholder-text);")

        self.__status = QLabel()
        self.__status.setWordWrap(True)
        self.__status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.__test_button = QPushButton("Test connection")
        self.__test_button.clicked.connect(self.test_connection)
        buttons = QDialogButtonBox()
        self.__save_button = buttons.addButton(
            "Save", QDialogButtonBox.ButtonRole.AcceptRole
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
        for field in (self.__host, self.__database, self.__username):
            field.textChanged.connect(self.__update_name_placeholder)
        self.__update_name_placeholder()

    # ------------------------------------------------------------------ widgets
    @property
    def name(self) -> QLineEdit:
        """Optional name field."""
        return self.__name

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
        """ "Test connection" button."""
        return self.__test_button

    @property
    def save_button(self) -> QPushButton:
        """ "Save" button."""
        return self.__save_button

    # ------------------------------------------------------------------ values
    def config(self) -> ConnectionConfig:
        """Configuration currently entered in the form."""
        return ConnectionConfig(
            name=self.__name.text(),
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
        self.__status.setText("Testing the connection…")
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
            msg = "Missing required fields: {}."
            self.__set_status(False, msg.format(", ".join(missing)))
            return False
        return True

    def __update_name_placeholder(self, *_: object) -> None:
        msg = "Optional, default: {}"
        self.__name.setPlaceholderText(msg.format(self.config().default_name()))

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
        self.__status.setStyleSheet("color: {};".format(color))
        self.__status.setText(message)

    @staticmethod
    def __spin(low: int, high: int, value: int, suffix: str = "") -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        spin.setSuffix(suffix)
        return spin
