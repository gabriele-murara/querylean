"""Application entry point."""

from __future__ import annotations

import sys
from types import TracebackType

from PySide6.QtWidgets import QApplication

from querylean.app.app_info import AppInfo
from querylean.app.smoke_test import SmokeTest
from querylean.log.log_manager import LogManager
from querylean.ui.main.main_window import MainWindow


class Application:
    """Configures logging and Qt, then runs the main window or smoke test."""

    SMOKE_TEST_FLAG = "--smoke-test"
    __log = LogManager.get_logger(__name__)

    @staticmethod
    def run(argv: list[str] | None = None) -> int:
        """Start the application and return its exit code."""
        argv = list(sys.argv if argv is None else argv)
        smoke_test = Application.SMOKE_TEST_FLAG in argv
        log_file = LogManager.configure(console=smoke_test)
        sys.excepthook = Application.handle_uncaught_exception
        Application.__log.info(
            "Starting %s %s (log: %s)", AppInfo.NAME, AppInfo.VERSION, log_file
        )

        app = QApplication(argv)
        app.setApplicationName(AppInfo.NAME)
        app.setApplicationDisplayName(AppInfo.DISPLAY_NAME)
        app.setApplicationVersion(AppInfo.VERSION)

        if smoke_test:
            return SmokeTest(app).run()

        window = MainWindow()
        window.show()
        code = app.exec()
        Application.__log.info("Application closed (exit code %s)", code)
        return code

    @staticmethod
    def handle_uncaught_exception(
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
    ) -> None:
        """Log uncaught exceptions; stack traces are never shown to the user."""
        Application.__log.critical(
            "Uncaught exception", exc_info=(exc_type, exc, tb)
        )
