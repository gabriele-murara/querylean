"""Logging filter that masks secrets."""

from __future__ import annotations

import logging
import re
import threading


class SecretRedactor(logging.Filter):
    """Masks registered secrets and ``password=...`` pairs in log records."""

    __PASSWORD_PAIR = re.compile(r"(?i)(password|passwd|pwd)(\s*[=:]\s*)(\S+)")
    __MASK = "***"

    def __init__(self) -> None:
        super().__init__()
        self.__secrets: set[str] = set()
        self.__lock = threading.Lock()

    @property
    def secret_count(self) -> int:
        """Number of secrets currently registered."""
        with self.__lock:
            return len(self.__secrets)

    def register_secret(self, secret: str | None) -> None:
        """Add a secret that must never appear in log output."""
        if secret:
            with self.__lock:
                self.__secrets.add(secret)

    def redact(self, text: str) -> str:
        """Return ``text`` with every known secret masked."""
        with self.__lock:
            secrets = sorted(self.__secrets, key=len, reverse=True)
        for secret in secrets:
            text = text.replace(secret, SecretRedactor.__MASK)
        return SecretRedactor.__PASSWORD_PAIR.sub(
            rf"\1\2{SecretRedactor.__MASK}", text
        )

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the formatted message and any traceback text of ``record``."""
        message = record.getMessage()
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(
                record.exc_info
            )
        record.msg = self.redact(message)
        record.args = None
        if record.exc_text:
            record.exc_text = self.redact(record.exc_text)
        return True
