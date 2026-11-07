"""A named query saved for one connection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from querylean.bookmarks.mask_error import MaskError
from querylean.bookmarks.mask_template import MaskTemplate
from querylean.bookmarks.placeholder import Placeholder
from querylean.config.connection_config import ConnectionConfig


class QueryBookmark:
    """Query saved with a name for a target database.

    ``target`` identifies the database and account the query was saved for
    (``user@host:port/database``, ``/*`` with all the databases, see
    ``target_of``): a bookmark is offered
    and executed only on a session with the same target.

    A bookmark with ``placeholders`` is a **mask**: its query contains
    ``${NAME}`` placeholders (see ``MaskTemplate``), each defined by one
    ``Placeholder``, and must be compiled with values before running.
    ``last_values`` keeps the values it was last run with (by placeholder
    name), proposed again the next time.
    """

    MAX_NAME_LENGTH = 100
    MAX_VALUE_LENGTH = 10000

    def __init__(
        self,
        name: str,
        sql: str,
        target: str,
        placeholders: tuple[Placeholder, ...] = (),
        last_values: Mapping[str, str] | None = None,
    ) -> None:
        self.__name = name
        self.__sql = sql
        self.__target = target
        self.__placeholders = tuple(placeholders)
        self.__last_values = QueryBookmark.__clean_values(
            self.__placeholders, last_values or {}
        )

    @property
    def name(self) -> str:
        """Name chosen by the user."""
        return self.__name

    @property
    def sql(self) -> str:
        """Text of the query."""
        return self.__sql

    @property
    def target(self) -> str:
        """``user@host:port/database`` the query was saved for."""
        return self.__target

    @property
    def placeholders(self) -> tuple[Placeholder, ...]:
        """Placeholders of a mask, in order (empty for a plain query)."""
        return self.__placeholders

    @property
    def last_values(self) -> dict[str, str]:
        """Values of the last run of a mask, by placeholder name (only
        for placeholders of the mask; empty when never run)."""
        return dict(self.__last_values)

    def with_last_values(self, values: Mapping[str, str]) -> QueryBookmark:
        """The same bookmark remembering ``values`` as the last ones."""
        return QueryBookmark(
            self.__name,
            self.__sql,
            self.__target,
            self.__placeholders,
            values,
        )

    def with_name(self, name: str) -> QueryBookmark:
        """The same bookmark (and last values) with another name."""
        return QueryBookmark(
            name,
            self.__sql,
            self.__target,
            self.__placeholders,
            self.__last_values,
        )

    @property
    def is_mask(self) -> bool:
        """True when the query has placeholders to fill in."""
        return bool(self.__placeholders)

    @staticmethod
    def target_of(config: ConnectionConfig) -> str:
        """Target of the sessions opened with ``config``."""
        return "{}@{}:{}/{}".format(
            config.username, config.host, config.port, config.scope_label()
        )

    @staticmethod
    def clean_name(name: str) -> str:
        """``name`` on one line, without surrounding spaces."""
        return " ".join(str(name).split())

    def same_name(self, name: str) -> bool:
        """True when ``name`` matches this name, ignoring case."""
        return (
            self.__name.casefold() == QueryBookmark.clean_name(name).casefold()
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializable representation."""
        data: dict[str, Any] = {
            "name": self.__name,
            "sql": self.__sql,
            "target": self.__target,
        }
        if self.__placeholders:
            data["placeholders"] = [p.to_dict() for p in self.__placeholders]
        if self.__last_values:
            data["last_values"] = dict(self.__last_values)
        return data

    @staticmethod
    def from_dict(data: object) -> QueryBookmark | None:
        """Bookmark from untrusted data; None when a field is missing, empty
        or of the wrong type."""
        if not isinstance(data, dict):
            return None
        values = [data.get(key) for key in ("name", "sql", "target")]
        if not all(isinstance(value, str) and value for value in values):
            return None
        name = QueryBookmark.clean_name(values[0])
        if not name or len(name) > QueryBookmark.MAX_NAME_LENGTH:
            return None
        placeholders = QueryBookmark.__placeholders_of(
            values[1], data.get("placeholders", [])
        )
        if placeholders is None:
            return None
        last_values = data.get("last_values", {})
        if not isinstance(last_values, dict):
            # Only a convenience: a damaged entry is forgotten.
            last_values = {}
        return QueryBookmark(
            name, values[1], values[2], placeholders, last_values
        )

    @staticmethod
    def __clean_values(
        placeholders: tuple[Placeholder, ...], values: Mapping[object, object]
    ) -> dict[str, str]:
        """Text values of ``values`` that belong to a placeholder, in the
        order of the placeholders; others (and too long ones) dropped."""
        clean = {}
        for placeholder in placeholders:
            value = values.get(placeholder.name)
            if (
                isinstance(value, str)
                and len(value) <= QueryBookmark.MAX_VALUE_LENGTH
            ):
                clean[placeholder.name] = value
        return clean

    @staticmethod
    def __placeholders_of(
        sql: str, data: object
    ) -> tuple[Placeholder, ...] | None:
        """Placeholders stored with ``sql``: exactly one valid definition
        for each placeholder of the text, otherwise None."""
        if not isinstance(data, list):
            return None
        placeholders = [Placeholder.from_dict(item) for item in data]
        if any(p is None for p in placeholders):
            return None
        try:
            names = MaskTemplate(sql).names
        except MaskError:
            return None
        defined = [p.name for p in placeholders if p is not None]
        if sorted(defined) != sorted(names):
            return None
        return tuple(p for p in placeholders if p is not None)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, QueryBookmark)
            and self.to_dict() == other.to_dict()
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.__name,
                self.__sql,
                self.__target,
                self.__placeholders,
                tuple(self.__last_values.items()),
            )
        )

    def __repr__(self) -> str:
        text = "QueryBookmark(name={!r}, target={!r})"
        return text.format(self.__name, self.__target)
