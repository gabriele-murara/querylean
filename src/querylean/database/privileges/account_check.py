"""Write access of an account to the databases of a connection."""

from __future__ import annotations

from collections.abc import Iterable

from querylean.database.privileges.account_privileges import AccountPrivileges


class AccountCheck:
    """Which databases of a connection the account can change, and which of
    them the user accepted in caution mode.

    Built at every connection and test: the connection is refused while
    ``refused`` is not empty.
    """

    # Read-only by design: no privilege can change it.
    ALWAYS_READ_ONLY = frozenset({"information_schema"})

    def __init__(
        self,
        privileges: AccountPrivileges,
        databases: Iterable[str],
        accepted: Iterable[str] = (),
    ) -> None:
        self.__privileges = privileges
        self.__databases = tuple(databases)
        accepted_names = set(accepted)
        self.__writable = tuple(
            (database, privileges.describe_database(database))
            for database in self.__databases
            if database.casefold() not in AccountCheck.ALWAYS_READ_ONLY
            and privileges.writable(database)
        )
        self.__refused = tuple(
            database
            for database, _ in self.__writable
            if database not in accepted_names
        )

    @property
    def privileges(self) -> AccountPrivileges:
        """Privileges of the account."""
        return self.__privileges

    @property
    def databases(self) -> tuple[str, ...]:
        """Databases of the connection that were checked."""
        return self.__databases

    @property
    def write_databases(self) -> tuple[str, ...]:
        """Databases the account can change, in order."""
        return tuple(database for database, _ in self.__writable)

    @property
    def refused(self) -> tuple[str, ...]:
        """Writable databases not accepted in caution mode."""
        return self.__refused

    @property
    def caution(self) -> bool:
        """True when the session can change at least one database."""
        return bool(self.__writable)

    def reason(self, database: str) -> str:
        """Privileges that make ``database`` writable (user-facing)."""
        for name, reason in self.__writable:
            if name == database:
                return reason
        return ""

    def describe(self, databases: Iterable[str] | None = None) -> str:
        """``db (INSERT, UPDATE); other (ALL PRIVILEGES)`` for
        ``databases`` (default: every writable one)."""
        names = self.write_databases if databases is None else databases
        return "; ".join(
            "{} ({})".format(name, self.reason(name)) for name in names
        )

    def __repr__(self) -> str:
        text = "AccountCheck(write={!r}, refused={!r})"
        return text.format(self.write_databases, self.__refused)
