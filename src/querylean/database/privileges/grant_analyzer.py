"""Fail-closed analysis of the lines returned by ``SHOW GRANTS``."""

from __future__ import annotations

from collections.abc import Iterable

from querylean.database.privileges.account_privileges import AccountPrivileges


class GrantAnalyzer:
    """Finds the privileges beyond reading in ``SHOW GRANTS`` output.

    Only ``GRANT <privileges> ON <object> TO …`` lines are recognised. Role
    grants (``GRANT `role` TO …``) and any other line make the result
    unverified, because the privileges they carry cannot be checked here.
    ``REVOKE`` lines (partial revokes) only remove privileges and are
    ignored.
    """

    # Privileges that only read data or metadata. Everything else, including
    # EXECUTE, PROCESS, PROXY, GRANT OPTION and dynamic privileges, is
    # treated as a privilege beyond reading.
    READ_PRIVILEGES = frozenset(
        {"USAGE", "SELECT", "SHOW VIEW", "SHOW DATABASES"}
    )
    GRANT_OPTION = "GRANT OPTION"
    __GRANT = "GRANT "
    __REVOKE = "REVOKE "
    __ON = " ON "
    __WITH_GRANT_OPTION = "WITH GRANT OPTION"
    __QUOTES = "`'\""

    @staticmethod
    def analyze(lines: Iterable[str]) -> AccountPrivileges:
        """Privileges granted by ``lines`` (one ``SHOW GRANTS`` row each)."""
        found: list[str] = []
        verified = True
        for line in lines:
            text = " ".join(str(line).split())
            upper = text.upper()
            if not upper or upper.startswith(GrantAnalyzer.__REVOKE):
                continue
            privileges = GrantAnalyzer.__privileges_of(text)
            if privileges is None:
                verified = False
                continue
            if GrantAnalyzer.__WITH_GRANT_OPTION in upper:
                privileges.append(GrantAnalyzer.GRANT_OPTION)
            for privilege in privileges:
                if (
                    privilege not in GrantAnalyzer.READ_PRIVILEGES
                    and privilege not in found
                ):
                    found.append(privilege)
        return AccountPrivileges(tuple(found), verified)

    @staticmethod
    def __privileges_of(text: str) -> list[str] | None:
        """Upper-case privilege names of a ``GRANT … ON …`` line, without
        column lists; ``None`` when the line has another form."""
        if not text.upper().startswith(GrantAnalyzer.__GRANT):
            return None
        start = len(GrantAnalyzer.__GRANT)
        parts: list[str] = []
        current: list[str] = []
        depth = 0
        quote = ""
        i = start
        while i < len(text):
            ch = text[i]
            if quote:
                if ch == quote:
                    quote = ""
            elif ch in GrantAnalyzer.__QUOTES:
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0 and ch == ",":
                parts.append("".join(current))
                current = []
                i += 1
                continue
            elif depth == 0 and GrantAnalyzer.__on_at(text, i):
                parts.append("".join(current))
                names = [GrantAnalyzer.__name_of(part) for part in parts]
                if not all(names):
                    return None
                return names
            if depth == 0 and not quote and ch not in "()":
                current.append(ch)
            i += 1
        return None

    @staticmethod
    def __on_at(text: str, i: int) -> bool:
        """True when the `` ON `` keyword starts at ``i``."""
        end = i + len(GrantAnalyzer.__ON)
        return text[i:end].upper() == GrantAnalyzer.__ON

    @staticmethod
    def __name_of(part: str) -> str:
        """Privilege name without spaces at the ends, in upper case. Column
        lists were already dropped while scanning."""
        return " ".join(part.split()).upper()
