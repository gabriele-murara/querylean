"""Packaging smoke test."""

from __future__ import annotations

import importlib
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from querylean.app.app_info import AppInfo
from querylean.app.version_file import VersionFile
from querylean.config.config_manager import ConfigManager
from querylean.database.validation.read_only_validator import ReadOnlyValidator
from querylean.log.log_manager import LogManager
from querylean.security.keyring_secret_store import KeyringSecretStore
from querylean.ui.main.main_window import MainWindow


class SmokeTest:
    """Checks that a packaged build contains every runtime module (CI)."""

    __DRIVER_PLUGINS = (
        "mysql.connector.plugins.caching_sha2_password",
        "mysql.connector.plugins.mysql_native_password",
    )
    __WINDOW_LIFETIME_MS = 500
    __log = LogManager.get_logger(__name__)

    def __init__(self, app: QApplication) -> None:
        self.__app = app

    @property
    def app(self) -> QApplication:
        """Running Qt application."""
        return self.__app

    def run(self) -> int:
        """Run the checks and briefly show the main window. Returns the exit
        code."""
        try:
            for module in SmokeTest.__DRIVER_PLUGINS:
                importlib.import_module(module)
            if AppInfo.version() == VersionFile.UNKNOWN:
                self.__log.error(
                    "Smoke test: %s not found or invalid at %s",
                    VersionFile.FILE_NAME,
                    VersionFile.path(),
                )
                return 1
            self.__log.info("Smoke test: version %s", AppInfo.version())
            validator = ReadOnlyValidator()
            if (
                not validator.validate("SELECT 1").ok
                or validator.validate("DROP TABLE x").ok
            ):
                self.__log.error(
                    "Smoke test: the validator is not behaving as expected"
                )
                return 1
            self.__log.info(
                "Smoke test: keychain available = %s",
                KeyringSecretStore().is_available(),
            )
            with tempfile.TemporaryDirectory() as tmp:
                window = MainWindow(ConfigManager(Path(tmp) / "config.json"))
                window.show()
                QTimer.singleShot(SmokeTest.__WINDOW_LIFETIME_MS, window.close)
                code = self.__app.exec()
        except Exception:
            self.__log.exception("Smoke test failed")
            return 1
        self.__log.info("Smoke test OK")
        return code
