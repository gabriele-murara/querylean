"""A placeholder of a mask: name, type, default and description."""

from __future__ import annotations

import re
from typing import Any

from querylean.bookmarks.placeholder_type import PlaceholderType


class Placeholder:
    """Definition of a ``${NAME}`` placeholder.

    ``is_list`` accepts several values (for ``IN (${CODES})``): each one is
    checked and written as a literal of ``kind``, separated by commas.
    ``default`` is the value proposed when the mask is compiled (and the
    one used to check the mask when it is saved).
    """

    NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    MAX_NAME_LENGTH = 64
    MAX_DESCRIPTION_LENGTH = 200
    # Format with the refused name.
    INVALID_NAME = "“{}” is not a valid name: use letters, digits and _ "
    INVALID_NAME += "(not starting with a digit)."

    def __init__(
        self,
        name: str,
        kind: PlaceholderType = PlaceholderType.TEXT,
        *,
        default: str = "",
        description: str = "",
        is_list: bool = False,
    ) -> None:
        self.__name = name
        self.__kind = kind
        self.__default = default
        self.__description = description
        self.__is_list = is_list

    @property
    def name(self) -> str:
        """Name written between ``${`` and ``}``."""
        return self.__name

    @property
    def kind(self) -> PlaceholderType:
        """Type of the value."""
        return self.__kind

    @property
    def default(self) -> str:
        """Value proposed at compilation (may be empty)."""
        return self.__default

    @property
    def description(self) -> str:
        """Help text shown next to the field (may be empty)."""
        return self.__description

    @property
    def is_list(self) -> bool:
        """True when several comma-separated values are accepted."""
        return self.__is_list

    @property
    def token(self) -> str:
        """``${NAME}`` as written in the query."""
        return "${{{}}}".format(self.__name)

    @staticmethod
    def is_valid_name(name: str) -> bool:
        """True for names made of letters, digits and ``_`` that do not
        start with a digit."""
        return (
            bool(Placeholder.NAME_PATTERN.fullmatch(name))
            and len(name) <= Placeholder.MAX_NAME_LENGTH
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializable representation."""
        return {
            "name": self.__name,
            "type": self.__kind.key,
            "list": self.__is_list,
            "default": self.__default,
            "description": self.__description,
        }

    @staticmethod
    def from_dict(data: object) -> Placeholder | None:
        """Placeholder from untrusted data; None when invalid."""
        if not isinstance(data, dict):
            return None
        name = data.get("name")
        kind = PlaceholderType.from_key(data.get("type"))
        default = data.get("default", "")
        description = data.get("description", "")
        is_list = data.get("list", False)
        if (
            not isinstance(name, str)
            or not Placeholder.is_valid_name(name)
            or kind is None
            or not isinstance(default, str)
            or not isinstance(description, str)
            or not isinstance(is_list, bool)
        ):
            return None
        return Placeholder(
            name,
            kind,
            default=default,
            description=description[: Placeholder.MAX_DESCRIPTION_LENGTH],
            is_list=is_list,
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Placeholder) and (
            self.to_dict() == other.to_dict()
        )

    def __hash__(self) -> int:
        return hash(tuple(self.to_dict().items()))

    def __repr__(self) -> str:
        text = "Placeholder({!r}, {}, list={})"
        return text.format(self.__name, self.__kind.name, self.__is_list)
