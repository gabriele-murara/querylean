"""Tests of the text of driver values."""

from querylean.database.execution.driver_value import DriverValue


class TestDriverValue:
    """Bytes are decoded, None handled, spaces kept."""

    def test_text(self):
        assert DriverValue.text("app") == "app"
        assert DriverValue.text(b"caf\xc3\xa9") == "café"
        assert DriverValue.text(bytearray(b"x")) == "x"
        assert DriverValue.text(b"\xff") == "�"
        assert DriverValue.text(None) == ""
        assert DriverValue.text(3) == "3"
        assert DriverValue.text(" app ") == " app "

    def test_optional_text(self):
        assert DriverValue.optional_text(None) is None
        assert DriverValue.optional_text(b"") == ""
