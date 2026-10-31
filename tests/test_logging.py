import logging

from querylean.utils.logging_config import RedactingFilter, setup_logging


def test_redacts_registered_secret_and_password_pairs():
    flt = RedactingFilter()
    flt.register_secret("Sup3r!")
    record = logging.LogRecord("x", logging.INFO, __file__, 1,
                               "connect pwd=%s password: other", ("Sup3r!",), None)
    flt.filter(record)
    assert "Sup3r!" not in record.getMessage()
    assert "other" not in record.getMessage()


def test_log_file_is_rotating_and_redacted(tmp_path):
    from querylean.utils.logging_config import redacting_filter

    redacting_filter.register_secret("TopSecret42")
    log_file = setup_logging(tmp_path)
    logging.getLogger("test").warning("tentativo con TopSecret42")
    for handler in logging.getLogger().handlers:
        handler.flush()
    content = log_file.read_text()
    assert "tentativo con ***" in content
    assert "TopSecret42" not in content
