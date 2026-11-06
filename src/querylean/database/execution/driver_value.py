"""Text of the values returned by the MySQL driver."""

from __future__ import annotations

from typing import Any


class DriverValue:
    """Converts driver values to text: some servers return names and
    metadata as bytes, decoded as UTF-8 (invalid bytes are replaced)."""

    @staticmethod
    def text(value: Any) -> str:
        """``value`` as text; ``None`` becomes an empty string."""
        if value is None:
            return ""
        if isinstance(value, bytes | bytearray):
            return bytes(value).decode("utf-8", errors="replace")
        return str(value)

    @staticmethod
    def optional_text(value: Any) -> str | None:
        """``value`` as text, keeping ``None``."""
        return None if value is None else DriverValue.text(value)
