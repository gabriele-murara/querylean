"""Logging locale con rotazione e redazione dei segreti."""

from __future__ import annotations

import logging
import re
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_dir

from querylean import APP_NAME

MAX_LOG_BYTES = 1_000_000
LOG_BACKUPS = 3

_PASSWORD_KV = re.compile(r"(?i)(password|passwd|pwd)(\s*[=:]\s*)(\S+)")


class RedactingFilter(logging.Filter):
    """Maschera i segreti noti e i pattern `password=...` nei record di log."""

    def __init__(self) -> None:
        super().__init__()
        self._secrets: set[str] = set()
        self._lock = threading.Lock()

    def register_secret(self, secret: str | None) -> None:
        if secret:
            with self._lock:
                self._secrets.add(secret)

    def redact(self, text: str) -> str:
        with self._lock:
            secrets = sorted(self._secrets, key=len, reverse=True)
        for secret in secrets:
            text = text.replace(secret, "***")
        return _PASSWORD_KV.sub(r"\1\2***", text)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        record.msg = self.redact(message)
        record.args = None
        if record.exc_text:
            record.exc_text = self.redact(record.exc_text)
        return True


redacting_filter = RedactingFilter()


def default_log_dir() -> Path:
    return Path(user_log_dir(APP_NAME, appauthor=False))


def setup_logging(log_dir: Path | None = None, level: int = logging.INFO) -> Path:
    """Configura il logger radice con un file ruotato. Restituisce il percorso del log."""
    log_dir = log_dir or default_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{APP_NAME}.log"

    handler = RotatingFileHandler(
        log_file, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s")
    )
    handler.addFilter(redacting_filter)

    root = logging.getLogger()
    root.setLevel(level)
    for existing in list(root.handlers):
        if getattr(existing, "_querylean", False):
            root.removeHandler(existing)
            existing.close()
    handler._querylean = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    return log_file
