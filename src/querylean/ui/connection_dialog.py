"""Finestra di configurazione dell'unica connessione."""

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

from querylean.config.config_manager import (
    MAX_ROW_LIMIT,
    MAX_TIMEOUT_SECONDS,
    ConnectionConfig,
)
from querylean.ui.db_worker import DbWorker


class ConnectionDialog(QDialog):
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
        self._worker = worker

        self.host = QLineEdit(config.host)
        self.port = _spin(1, 65535, config.port)
        self.database = QLineEdit(config.database)
        self.username = QLineEdit(config.username)
        self.password = QLineEdit(password)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_password = QCheckBox("Mostra password")
        self.show_password.toggled.connect(self._on_toggle_password)

        self.remember_password = QCheckBox("Salva la password nel portachiavi di sistema")
        self.remember_password.setChecked(keyring_available)
        self.remember_password.setEnabled(keyring_available)
        if not keyring_available:
            self.remember_password.setToolTip(
                "Portachiavi non disponibile: la password resterà in memoria solo per questa "
                "sessione."
            )

        self.connect_timeout = _spin(1, MAX_TIMEOUT_SECONDS, config.connect_timeout, " s")
        self.query_timeout = _spin(1, MAX_TIMEOUT_SECONDS, config.query_timeout, " s")
        self.row_limit = _spin(1, MAX_ROW_LIMIT, config.row_limit)
        self.row_limit.setSingleStep(100)

        form = QFormLayout()
        form.addRow("Host *", self.host)
        form.addRow("Porta *", self.port)
        form.addRow("Database *", self.database)
        form.addRow("Username *", self.username)
        form.addRow("Password *", self.password)
        form.addRow("", self.show_password)
        form.addRow("", self.remember_password)
        form.addRow("Timeout connessione", self.connect_timeout)
        form.addRow("Timeout query", self.query_timeout)
        form.addRow("Righe massime", self.row_limit)

        hint = QLabel(
            "Usa un account MySQL con soli privilegi SELECT: la modalità di sola lettura è "
            "garantita principalmente dai privilegi dell'account."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(placeholder-text);")

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.test_button = QPushButton("Test connessione")
        self.test_button.clicked.connect(self._on_test)
        buttons = QDialogButtonBox()
        self.save_button = buttons.addButton("Salva configurazione",
                                             QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        bottom = QHBoxLayout()
        bottom.addWidget(self.test_button)
        bottom.addStretch(1)
        bottom.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(self.status)
        layout.addLayout(bottom)

        worker.test_finished.connect(self._on_test_finished)

    # -- valori ---------------------------------------------------------------------
    def config(self) -> ConnectionConfig:
        return ConnectionConfig(
            host=self.host.text().strip(),
            port=self.port.value(),
            database=self.database.text().strip(),
            username=self.username.text().strip(),
            connect_timeout=self.connect_timeout.value(),
            query_timeout=self.query_timeout.value(),
            row_limit=self.row_limit.value(),
        )

    def password_value(self) -> str:
        return self.password.text()

    def missing_fields(self) -> list[str]:
        missing = self.config().missing_fields()
        if not self.password_value():
            missing.append("Password")
        return missing

    # -- azioni ---------------------------------------------------------------------
    def _check_required(self) -> bool:
        missing = self.missing_fields()
        if missing:
            self._set_status(False, "Campi obbligatori mancanti: " + ", ".join(missing) + ".")
            return False
        return True

    def _on_test(self) -> None:
        if not self._check_required():
            return
        self.test_button.setEnabled(False)
        self.status.setStyleSheet("")
        self.status.setText("Test della connessione in corso…")
        self._worker.test_requested.emit(self.config(), self.password_value())

    def _on_test_finished(self, ok: bool, message: str) -> None:
        self.test_button.setEnabled(True)
        self._set_status(ok, message)

    def _on_save(self) -> None:
        if self._check_required():
            self.accept()

    def _on_toggle_password(self, visible: bool) -> None:
        self.password.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )

    def _set_status(self, ok: bool, message: str) -> None:
        self.status.setStyleSheet(f"color: {'#1a7f37' if ok else '#c62828'};")
        self.status.setText(message)

    def done(self, result: int) -> None:  # disconnette il segnale del worker
        try:
            self._worker.test_finished.disconnect(self._on_test_finished)
        except (RuntimeError, TypeError):
            pass
        super().done(result)


def _spin(low: int, high: int, value: int, suffix: str = "") -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(low, high)
    spin.setValue(value)
    spin.setSuffix(suffix)
    return spin
