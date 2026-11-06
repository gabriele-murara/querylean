"""Privileges beyond reading granted on one object."""

from __future__ import annotations

import re


class GrantScope:
    """Write privileges of one ``GRANT`` line and the databases they cover.

    ``database`` is None for global grants (``*.*``) and for objects that
    are not in a database (``PROXY``): they cover every database.
    Otherwise it is the database name as written in the grant, where, as
    in MySQL, ``%`` and ``_`` are wildcards unless escaped with ``\\``.
    Matching ignores case, so it never covers fewer databases than the
    server does.
    """

    def __init__(
        self, database: str | None, privileges: tuple[str, ...]
    ) -> None:
        self.__database = database
        self.__privileges = tuple(privileges)
        self.__pattern = (
            None if database is None else GrantScope.__regex(database)
        )

    @property
    def database(self) -> str | None:
        """Database (pattern) of the grant; None for every database."""
        return self.__database

    @property
    def privileges(self) -> tuple[str, ...]:
        """Privileges beyond reading."""
        return self.__privileges

    def covers(self, database: str) -> bool:
        """True when the grant applies to ``database``."""
        if self.__pattern is None:
            return True
        return self.__pattern.fullmatch(database) is not None

    @staticmethod
    def __regex(pattern: str) -> re.Pattern[str]:
        parts: list[str] = []
        i = 0
        while i < len(pattern):
            ch = pattern[i]
            if ch == "\\" and i + 1 < len(pattern):
                parts.append(re.escape(pattern[i + 1]))
                i += 2
                continue
            if ch == "%":
                parts.append(".*")
            elif ch == "_":
                parts.append(".")
            else:
                parts.append(re.escape(ch))
            i += 1
        return re.compile("".join(parts), re.IGNORECASE | re.DOTALL)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, GrantScope) and (
            self.__database,
            self.__privileges,
        ) == (other.database, other.privileges)

    def __hash__(self) -> int:
        return hash((self.__database, self.__privileges))

    def __repr__(self) -> str:
        text = "GrantScope({!r}, {!r})"
        return text.format(self.__database, self.__privileges)
