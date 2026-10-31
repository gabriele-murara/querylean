"""Logger used across the application."""

from __future__ import annotations

import logging


class AppLogger:
    """Thin wrapper around :class:`logging.Logger`.

    The API mirrors py-nano-logger (``debug``/``info``/``warning``/``error``/
    ``critical``) and adds ``exception``. Records are attributed to the caller
    (``stacklevel=2``). Handlers are configured once by ``LogManager``.
    """

    def __init__(self, name: str) -> None:
        self.__name = name
        self.__logger = logging.getLogger(name)

    @property
    def name(self) -> str:
        """Fully qualified logger name."""
        return self.__name

    @property
    def logger(self) -> logging.Logger:
        """Underlying standard library logger."""
        return self.__logger

    def debug(self, msg: str, *args: object) -> None:
        """Log a DEBUG message."""
        self.__logger.debug(msg, *args, stacklevel=2)

    def info(self, msg: str, *args: object) -> None:
        """Log an INFO message."""
        self.__logger.info(msg, *args, stacklevel=2)

    def warning(self, msg: str, *args: object) -> None:
        """Log a WARNING message."""
        self.__logger.warning(msg, *args, stacklevel=2)

    def error(self, msg: str, *args: object) -> None:
        """Log an ERROR message."""
        self.__logger.error(msg, *args, stacklevel=2)

    def critical(self, msg: str, *args: object, exc_info: object = None) -> None:
        """Log a CRITICAL message, optionally with exception information."""
        self.__logger.critical(msg, *args, exc_info=exc_info, stacklevel=2)

    def exception(self, msg: str, *args: object) -> None:
        """Log an ERROR message with the traceback of the exception being handled."""
        self.__logger.error(msg, *args, exc_info=True, stacklevel=2)
