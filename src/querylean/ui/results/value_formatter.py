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
        """Display text of a non-NULL value (long binary values are cut to a
        preview)."""
        return ValueFormatter.__text(value, full=False)

    @staticmethod
    def full_text(value: Any) -> str:
        """Lossless text of a non-NULL value, used by the exports: binary
        values are written in full, TIME values keep their microseconds."""
        return ValueFormatter.__text(value, full=True)

    @staticmethod
    def __text(value: Any, *, full: bool) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, bytes | bytearray):
            return ValueFormatter.__format_bytes(bytes(value), full=full)
        if isinstance(value, dt.datetime):
            return value.isoformat(sep=" ")
        if isinstance(value, dt.date | dt.time):
            return value.isoformat()
        if isinstance(value, dt.timedelta):  # TIME columns
            return ValueFormatter.__format_timedelta(value, full=full)
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
    def __format_bytes(data: bytes, *, full: bool) -> str:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            limit = ValueFormatter.MAX_BINARY_PREVIEW
            if full or len(data) <= limit:
                return "0x{}".format(data.hex())
            return "0x{}…".format(data[:limit].hex())

    @staticmethod
    def __format_timedelta(value: dt.timedelta, *, full: bool) -> str:
        sign = "-" if value < dt.timedelta(0) else ""
        micros = abs(value) // dt.timedelta(microseconds=1)
        total, micros = divmod(micros, 1_000_000)
        hours, rest = divmod(total, 3600)
        minutes, seconds = divmod(rest, 60)
        text = "{}{:02d}:{:02d}:{:02d}".format(sign, hours, minutes, seconds)
        if full and micros:
            text = "{}.{:06d}".format(text, micros)
        return text
