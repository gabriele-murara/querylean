"""Fail-closed analysis of the lines returned by ``SHOW GRANTS``."""

from __future__ import annotations

from collections.abc import Iterable

from querylean.database.privileges.account_privileges import AccountPrivileges
from querylean.database.privileges.grant_scope import GrantScope


class GrantAnalyzer:
    """Finds the privileges beyond reading in ``SHOW GRANTS`` output and
    the databases they apply to.

    Only ``GRANT <privileges> ON <object> TO …`` lines are recognised. Role
    grants (``GRANT `role` TO …``) and any other line make the result
    unverified, because the privileges they carry cannot be checked here.
    ``REVOKE`` lines (partial revokes) only remove privileges and are
    ignored. Objects that cannot be tied to one database count as global.
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
    __OBJECT_TYPES = ("PROCEDURE ", "FUNCTION ", "TABLE ")

    @staticmethod
    def analyze(lines: Iterable[str]) -> AccountPrivileges:
        """Privileges granted by ``lines`` (one ``SHOW GRANTS`` row each)."""
        scopes: list[GrantScope] = []
        verified = True
        for line in lines:
            text = " ".join(str(line).split())
            upper = text.upper()
            if not upper or upper.startswith(GrantAnalyzer.__REVOKE):
                continue
            parsed = GrantAnalyzer.__privileges_of(text)
            if parsed is None:
                verified = False
                continue
            privileges, target = parsed
            if GrantAnalyzer.__WITH_GRANT_OPTION in upper:
                privileges.append(GrantAnalyzer.GRANT_OPTION)
            writes: list[str] = []
            for privilege in privileges:
                if (
                    privilege not in GrantAnalyzer.READ_PRIVILEGES
                    and privilege not in writes
                ):
                    writes.append(privilege)
            if writes:
                database = GrantAnalyzer.__database_of(target)
                scopes.append(GrantScope(database, tuple(writes)))
        return AccountPrivileges(verified=verified, scopes=tuple(scopes))

    @staticmethod
    def __privileges_of(text: str) -> tuple[list[str], str] | None:
        """Upper-case privilege names of a ``GRANT … ON …`` line, without
        column lists, and the text after ``ON``; ``None`` when the line has
        another form."""
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
                return names, text[i + len(GrantAnalyzer.__ON) :]
            if depth == 0 and not quote and ch not in "()":
                current.append(ch)
            i += 1
        return None

    @staticmethod
    def __database_of(target: str) -> str | None:
        """Database of the object after ``ON`` (``db.*``, ``db.table``,
        ``PROCEDURE db.name``…); None for ``*.*`` and objects outside a
        database."""
        text = target.lstrip()
        for kind in GrantAnalyzer.__OBJECT_TYPES:
            if text.upper().startswith(kind):
                text = text[len(kind) :].lstrip()
                break
        if not text or text[0] in "*'\"":
            return None
        if text[0] == "`":
            name: list[str] = []
            i = 1
            while i < len(text):
                if text[i] == "`":
                    if text[i + 1 : i + 2] == "`":
                        name.append("`")
                        i += 2
                        continue
                    break
                name.append(text[i])
                i += 1
            rest = text[i + 1 :]
            database = "".join(name)
        else:
            end = len(text)
            for stop in (".", " "):
                found = text.find(stop)
                if 0 <= found < end:
                    end = found
            database, rest = text[:end], text[end:]
        # A name not followed by "." is not a database (e.g. a PROXY user).
        if not rest.startswith(".") or not database:
            return None
        return database

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
