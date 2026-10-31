"""Tests of logging configuration and secret redaction."""

import logging
import logging.handlers

from querylean.log.app_logger import AppLogger
from querylean.log.log_manager import LogManager
from querylean.log.secret_redactor import SecretRedactor


class TestLogManager:
    """Logger tree, redaction filter and rotating file output."""

    def test_loggers_belong_to_application_tree(self):
        assert LogManager.get_logger("querylean.x").name == "querylean.x"
        assert LogManager.get_logger("other").name == "querylean.other"
        assert isinstance(LogManager.get_logger("x"), AppLogger)

    def test_redacts_registered_secret_and_password_pairs(self):
        redactor = SecretRedactor()
        redactor.register_secret("Sup3r!")
        record = logging.LogRecord(
            "x", logging.INFO, __file__, 1, "connect pwd=%s password: other", ("Sup3r!",), None
        )
        redactor.filter(record)
        assert "Sup3r!" not in record.getMessage()
        assert "other" not in record.getMessage()

    def test_log_file_is_rotating_and_redacted(self, tmp_path):
        LogManager.register_secret("TopSecret42")
        log_file = LogManager.configure(tmp_path)
        LogManager.get_logger("test").warning("attempt with TopSecret42")
        handlers = logging.getLogger("querylean").handlers
        assert any(isinstance(h, logging.handlers.RotatingFileHandler) for h in handlers)
        for handler in handlers:
            handler.flush()
        content = log_file.read_text()
        assert "attempt with ***" in content
        assert "TopSecret42" not in content
        assert "test_log_manager" in content or "querylean.test" in content
