"""Logger used across the application."""

from __future__ import annotations

import logging


class AppLogger:
    """Thin wrapper around :class:`logging.Logger`.

    The API mirrors py-nano-logger (``debug``/``info``/``warning``/``error``/
    ``critical``) and adds ``exception``. Messages use ``str.format``
    placeholders (``log.info("Connected to {}", host)``): the text is formatted
    only when the level is enabled, and the record reaches the handlers
    already formatted, without ``%`` arguments. Records are attributed to the
    caller (``stacklevel=3``). Handlers are configured once by ``LogManager``.
    """

    # Caller -> public method -> __log -> Logger.log.
    __STACKLEVEL = 3

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
        self.__log(logging.DEBUG, msg, args)

    def info(self, msg: str, *args: object) -> None:
        """Log an INFO message."""
        self.__log(logging.INFO, msg, args)

    def warning(self, msg: str, *args: object) -> None:
        """Log a WARNING message."""
        self.__log(logging.WARNING, msg, args)

    def error(self, msg: str, *args: object) -> None:
        """Log an ERROR message."""
        self.__log(logging.ERROR, msg, args)

    def critical(
        self, msg: str, *args: object, exc_info: object = None
    ) -> None:
        """Log a CRITICAL message, optionally with exception information."""
        self.__log(logging.CRITICAL, msg, args, exc_info)

    def exception(self, msg: str, *args: object) -> None:
        """Log an ERROR message with the traceback of the exception being
        handled."""
        self.__log(logging.ERROR, msg, args, True)

    def __log(
        self,
        level: int,
        msg: str,
        args: tuple[object, ...],
        exc_info: object = None,
    ) -> None:
        if not self.__logger.isEnabledFor(level):
            return
        text = msg.format(*args) if args else msg
        self.__logger.log(
            level,
            text,
            exc_info=exc_info,
            stacklevel=AppLogger.__STACKLEVEL,
        )
