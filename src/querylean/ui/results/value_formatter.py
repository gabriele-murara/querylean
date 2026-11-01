"""Text representation of values returned by the driver."""

from __future__ import annotations

import datetime as dt
import decimal
from typing import Any


class ValueFormatter:
    """Formats cell values for display and for tab-separated copying."""

    NULL_TEXT = "NULL"
    MAX_BINARY_PREVIEW = 64

    @staticmethod
    def format_value(value: Any) -> str:
        """Display text of a non-NULL value."""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, bytes | bytearray):
            return ValueFormatter.__format_bytes(bytes(value))
        if isinstance(value, dt.datetime):
            return value.isoformat(sep=" ")
        if isinstance(value, dt.date | dt.time):
            return value.isoformat()
        if isinstance(value, dt.timedelta):  # TIME columns
            return ValueFormatter.__format_timedelta(value)
        if isinstance(value, decimal.Decimal):
            return format(value, "f")
        if isinstance(value, set):
            return ",".join(sorted(str(v) for v in value))
        return str(value)

    @staticmethod
    def copy_text(value: Any) -> str:
        """Value for TSV copy: NULL becomes an empty cell, tabs and newlines
        become spaces so that rows and columns stay aligned."""
        if value is None:
            return ""
        text = ValueFormatter.format_value(value)
        for separator in ("\r\n", "\t", "\n", "\r"):
            text = text.replace(separator, " ")
        return text

    @staticmethod
    def __format_bytes(data: bytes) -> str:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            preview = data[: ValueFormatter.MAX_BINARY_PREVIEW].hex()
            suffix = (
                "…" if len(data) > ValueFormatter.MAX_BINARY_PREVIEW else ""
            )
            return "0x{}{}".format(preview, suffix)

    @staticmethod
    def __format_timedelta(value: dt.timedelta) -> str:
        total = int(value.total_seconds())
        sign = "-" if total < 0 else ""
        total = abs(total)
        hours, rest = divmod(total, 3600)
        minutes, seconds = divmod(rest, 60)
        return "{}{:02d}:{:02d}:{:02d}".format(sign, hours, minutes, seconds)
