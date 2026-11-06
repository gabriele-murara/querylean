"""Outcome of the privilege check of an account."""

from __future__ import annotations

from collections.abc import Iterable

from querylean.database.privileges.grant_scope import GrantScope


class AccountPrivileges:
    """Privileges beyond reading of an account, by database.

    ``scopes`` lists the write privileges of each grant with the databases
    it covers; ``write_privileges`` without ``scopes`` means global
    privileges. ``verified`` is false when the grants could not be read or
    contain entries that cannot be checked (roles, unknown lines): then
    every database counts as writable.
    """

    UNVERIFIED = "the privileges of the account could not be verified"

    def __init__(
        self,
        write_privileges: tuple[str, ...] = (),
        verified: bool = True,
        scopes: tuple[GrantScope, ...] | None = None,
    ) -> None:
        if scopes is None:
            scopes = (
                (GrantScope(None, tuple(write_privileges)),)
                if write_privileges
                else ()
            )
        self.__scopes = tuple(scopes)
        self.__verified = verified

    @property
    def scopes(self) -> tuple[GrantScope, ...]:
        """Write privileges per grant."""
        return self.__scopes

    @property
    def write_privileges(self) -> tuple[str, ...]:
        """Privileges beyond reading, in the order found, without repeats."""
        return AccountPrivileges.__unique(self.__scopes)

    @property
    def verified(self) -> bool:
        """True when every grant was recognised."""
        return self.__verified

    @property
    def read_only(self) -> bool:
        """True only for a verified account without write privileges."""
        return self.__verified and not self.__scopes

    def privileges_on(self, database: str) -> tuple[str, ...]:
        """Privileges beyond reading that apply to ``database``."""
        return AccountPrivileges.__unique(
            s for s in self.__scopes if s.covers(database)
        )

    def writable(self, database: str) -> bool:
        """True when the account may change ``database`` (always when the
        grants could not be verified)."""
        return not self.__verified or bool(self.privileges_on(database))

    def describe(self) -> str:
        """User-facing description of why the account is not read-only
        (empty when it is)."""
        if self.read_only:
            return ""
        if not self.__verified:
            return AccountPrivileges.UNVERIFIED
        msg = "the account has privileges beyond reading ({})"
        return msg.format(", ".join(self.write_privileges))

    def describe_database(self, database: str) -> str:
        """Privileges that make ``database`` writable, for the user (empty
        when it is not)."""
        if not self.__verified:
            return AccountPrivileges.UNVERIFIED
        return ", ".join(self.privileges_on(database))

    @staticmethod
    def unverified() -> AccountPrivileges:
        """Result for grants that could not be read or recognised."""
        return AccountPrivileges(verified=False)

    @staticmethod
    def __unique(scopes: Iterable[GrantScope]) -> tuple[str, ...]:
        found: list[str] = []
        for scope in scopes:
            for privilege in scope.privileges:
                if privilege not in found:
                    found.append(privilege)
        return tuple(found)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, AccountPrivileges)
            and self.__scopes == other.scopes
            and self.__verified == other.verified
        )

    def __hash__(self) -> int:
        return hash((self.__scopes, self.__verified))

    def __repr__(self) -> str:
        text = "AccountPrivileges(scopes={!r}, verified={!r})"
        return text.format(self.__scopes, self.__verified)
