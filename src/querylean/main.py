"""Punto di ingresso dell'applicazione."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from querylean import APP_DISPLAY_NAME, APP_NAME, __version__
from querylean.utils.logging_config import setup_logging

log = logging.getLogger(__name__)


def _excepthook(exc_type, exc, tb) -> None:
    # Le eccezioni non gestite vanno nel log, mai mostrate come stack trace all'utente.
    log.critical("Eccezione non gestita", exc_info=(exc_type, exc, tb))


def _smoke_test(app: QApplication) -> int:
    """Verifica che il pacchetto contenga tutti i moduli necessari (usato dalla CI)."""
    import importlib
    import tempfile
    from pathlib import Path

    from PySide6.QtCore import QTimer

    from querylean.config.config_manager import ConfigManager
    from querylean.config.secret_storage import SecretStorage
    from querylean.database.readonly_validator import validate
    from querylean.ui.main_window import MainWindow

    importlib.import_module("mysql.connector.plugins.caching_sha2_password")
    importlib.import_module("mysql.connector.plugins.mysql_native_password")
    assert validate("SELECT 1").ok and not validate("DROP TABLE x").ok
    print("keyring disponibile:", SecretStorage().is_available())
    with tempfile.TemporaryDirectory() as tmp:
        window = MainWindow(ConfigManager(Path(tmp) / "config.json"))
        window.show()
        QTimer.singleShot(500, window.close)
        code = app.exec()
    print("smoke test OK")
    return code


def main() -> int:
    log_file = setup_logging()
    sys.excepthook = _excepthook
    log.info("Avvio %s %s (log: %s)", APP_NAME, __version__, log_file)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setApplicationVersion(__version__)

    if "--smoke-test" in sys.argv:
        return _smoke_test(app)

    from querylean.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    code = app.exec()
    log.info("Chiusura applicazione (codice %s)", code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
