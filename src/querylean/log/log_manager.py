"""Central logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_dir

from querylean.app.app_info import AppInfo
from querylean.log.app_logger import AppLogger
from querylean.log.secret_redactor import SecretRedactor


class LogManager:
    """Configures handlers for the application logger tree and hands out
    loggers."""

    __MAX_BYTES = 1_000_000
    __BACKUP_COUNT = 3
    __FORMAT = "{asctime} {levelname} {name} [{threadName}] {message}"
    __HANDLER_MARK = "_querylean_handler"
    __redactor = SecretRedactor()

    @staticmethod
    def get_logger(name: str) -> AppLogger:
        """Return a logger inside the application tree (``querylean.*``)."""
        root = AppInfo.NAME
        if name != root and not name.startswith("{}.".format(root)):
            name = "{}.{}".format(root, name)
        return AppLogger(name)

    @staticmethod
    def redactor() -> SecretRedactor:
        """Shared filter that masks secrets in every handler."""
        return LogManager.__redactor

    @staticmethod
    def register_secret(secret: str | None) -> None:
        """Ensure ``secret`` never appears in log output."""
        LogManager.__redactor.register_secret(secret)

    @staticmethod
    def default_log_dir() -> Path:
        """Platform specific log directory."""
        return Path(user_log_dir(AppInfo.NAME, appauthor=False))

    @staticmethod
    def configure(
        log_dir: Path | None = None,
        level: int = logging.INFO,
        *,
        console: bool = False,
    ) -> Path:
        """Attach a size-limited rotating file handler (and optionally a console
        handler) to the application logger. Returns the log file path."""
        log_dir = log_dir or LogManager.default_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "{}.log".format(AppInfo.NAME)

        app_logger = logging.getLogger(AppInfo.NAME)
        app_logger.setLevel(level)
        for existing in list(app_logger.handlers):
            if getattr(existing, LogManager.__HANDLER_MARK, False):
                app_logger.removeHandler(existing)
                existing.close()

        handlers: list[logging.Handler] = [
            RotatingFileHandler(
                log_file,
                maxBytes=LogManager.__MAX_BYTES,
                backupCount=LogManager.__BACKUP_COUNT,
                encoding="utf-8",
            )
        ]
        if console:
            handlers.append(logging.StreamHandler())
        for handler in handlers:
            handler.setFormatter(
                logging.Formatter(LogManager.__FORMAT, style="{")
            )
            handler.addFilter(LogManager.__redactor)
            setattr(handler, LogManager.__HANDLER_MARK, True)
            app_logger.addHandler(handler)
        return log_file
