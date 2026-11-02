"""Outcome of the privilege check of an account."""

from __future__ import annotations


class AccountPrivileges:
    """Whether an account is provably read-only.

    ``write_privileges`` lists the privileges beyond reading that were found
    (e.g. ``INSERT``, ``ALL PRIVILEGES``). ``verified`` is false when the
    grants could not be read or contain entries that cannot be checked
    (roles, unknown lines): such an account is never considered read-only.
    """

    def __init__(
        self, write_privileges: tuple[str, ...] = (), verified: bool = True
    ) -> None:
        self.__write_privileges = tuple(write_privileges)
        self.__verified = verified

    @property
    def write_privileges(self) -> tuple[str, ...]:
        """Privileges beyond reading, in the order found, without repeats."""
        return self.__write_privileges

    @property
    def verified(self) -> bool:
        """True when every grant was recognised."""
        return self.__verified

    @property
    def read_only(self) -> bool:
        """True only for a verified account without write privileges."""
        return self.__verified and not self.__write_privileges

    def describe(self) -> str:
        """User-facing description of why the account is not read-only
        (empty when it is)."""
        if self.read_only:
            return ""
        if self.__write_privileges:
            msg = "the account has privileges beyond reading ({})"
            return msg.format(", ".join(self.__write_privileges))
        return "the privileges of the account could not be verified"

    @staticmethod
    def unverified() -> AccountPrivileges:
        """Result for grants that could not be read or recognised."""
        return AccountPrivileges(verified=False)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, AccountPrivileges)
            and self.__write_privileges == other.write_privileges
            and self.__verified == other.verified
        )

    def __hash__(self) -> int:
        return hash((self.__write_privileges, self.__verified))

    def __repr__(self) -> str:
        text = "AccountPrivileges(write_privileges={!r}, verified={!r})"
        return text.format(self.__write_privileges, self.__verified)
