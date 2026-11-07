"""Types of the values that fill a mask placeholder."""

from __future__ import annotations

import datetime as dt
import re
from enum import Enum

from querylean.bookmarks.mask_error import MaskError
from querylean.database.schema.mysql_literal import MySqlLiteral


class PlaceholderType(Enum):
    """Primitive SQL types of a placeholder value.

    ``normalize`` checks a value typed by the user and returns it in a
    canonical form; ``literal`` turns a normalised value into the SQL
    literal written in place of a placeholder outside quotes: numbers and
    booleans as they are, everything else as an escaped string literal.
    A value therefore never becomes SQL syntax.
    """

    INTEGER = ("integer", "Integer")
    DECIMAL = ("decimal", "Decimal")
    TEXT = ("text", "Text")
    DATE = ("date", "Date")
    TIME = ("time", "Time")
    DATETIME = ("datetime", "Date-time")
    BOOLEAN = ("boolean", "Boolean")

    __INTEGER = re.compile(r"[+-]?\d+")
    __DECIMAL = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")
    __DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
    __TIME = re.compile(r"\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?")
    __DATETIME = re.compile(
        r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?"
    )
    __TRUE = frozenset({"true", "1", "yes"})
    __FALSE = frozenset({"false", "0", "no"})

    @property
    def key(self) -> str:
        """Stable identifier stored in the bookmark files."""
        return self.value[0]

    @property
    def label(self) -> str:
        """User-facing name."""
        return self.value[1]

    @staticmethod
    def from_key(key: object) -> PlaceholderType | None:
        """Type with the stored ``key``, if any."""
        for kind in PlaceholderType:
            if kind.key == key:
                return kind
        return None

    def normalize(self, value: str) -> str:
        """``value`` checked for this type, in canonical form. Raises
        ``MaskError`` with a user-facing message."""
        text = value if self is PlaceholderType.TEXT else value.strip()
        if not text:
            raise MaskError("A value is required.")
        try:
            return self.__normalize(text)
        except ValueError:
            msg = "“{}” is not a valid {} value."
            raise MaskError(msg.format(value, self.label.lower())) from None

    def literal(self, normalized: str) -> str:
        """SQL literal of a value already normalised by ``normalize``."""
        if self in (PlaceholderType.INTEGER, PlaceholderType.DECIMAL):
            return normalized
        if self is PlaceholderType.BOOLEAN:
            return normalized.upper()
        return MySqlLiteral.quote(normalized)

    @staticmethod
    def infer(example: str, *, quoted: bool) -> PlaceholderType:
        """Most likely type of ``example``; inside quotes only text, date
        and time types are proposed."""
        text = example.strip()
        candidates = (
            (PlaceholderType.__DATETIME, PlaceholderType.DATETIME),
            (PlaceholderType.__DATE, PlaceholderType.DATE),
            (PlaceholderType.__TIME, PlaceholderType.TIME),
        )
        if not quoted:
            candidates += (
                (PlaceholderType.__INTEGER, PlaceholderType.INTEGER),
                (PlaceholderType.__DECIMAL, PlaceholderType.DECIMAL),
            )
        for pattern, kind in candidates:
            if pattern.fullmatch(text):
                try:
                    kind.normalize(text)
                except MaskError:
                    continue
                return kind
        if not quoted and text.lower() in ("true", "false"):
            return PlaceholderType.BOOLEAN
        return PlaceholderType.TEXT

    def __normalize(self, text: str) -> str:
        """Canonical text; raises ``ValueError`` when invalid."""
        if self is PlaceholderType.TEXT:
            if "\x00" in text:
                raise ValueError(text)
            return text
        if self is PlaceholderType.INTEGER:
            if not PlaceholderType.__INTEGER.fullmatch(text):
                raise ValueError(text)
            return str(int(text))
        if self is PlaceholderType.DECIMAL:
            if not PlaceholderType.__DECIMAL.fullmatch(text):
                raise ValueError(text)
            return text
        if self is PlaceholderType.DATE:
            if not PlaceholderType.__DATE.fullmatch(text):
                raise ValueError(text)
            return dt.date.fromisoformat(text).isoformat()
        if self is PlaceholderType.TIME:
            if not PlaceholderType.__TIME.fullmatch(text):
                raise ValueError(text)
            return dt.time.fromisoformat(text).isoformat()
        if self is PlaceholderType.DATETIME:
            if not PlaceholderType.__DATETIME.fullmatch(text):
                raise ValueError(text)
            moment = dt.datetime.fromisoformat(text.replace("T", " "))
            return moment.isoformat(sep=" ")
        lowered = text.lower()
        if lowered in PlaceholderType.__TRUE:
            return "true"
        if lowered in PlaceholderType.__FALSE:
            return "false"
        raise ValueError(text)
