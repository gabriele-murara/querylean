"""A table named in the FROM/JOIN clauses of a statement."""

from __future__ import annotations


class TableReference:
    """Table (or derived table) referenced by a statement, with its alias.

    ``table`` is None for a derived table (``(SELECT …) AS alias``), whose
    columns are not known.
    """

    def __init__(
        self,
        table: str | None,
        alias: str | None = None,
        schema: str | None = None,
    ) -> None:
        self.__table = table
        self.__alias = alias
        self.__schema = schema

    @property
    def table(self) -> str | None:
        """Table name (None for a derived table)."""
        return self.__table

    @property
    def alias(self) -> str | None:
        """Alias, if any."""
        return self.__alias

    @property
    def schema(self) -> str | None:
        """Database qualifier (``db.table``), if any."""
        return self.__schema

    @property
    def visible_name(self) -> str:
        """Name used to qualify its columns: the alias, else the table."""
        return self.__alias or self.__table or ""

    def matches(self, name: str) -> bool:
        """True when ``name`` is its alias or, without alias, its table
        (case insensitive)."""
        wanted = name.casefold()
        if self.__alias:
            return self.__alias.casefold() == wanted
        return bool(self.__table) and self.__table.casefold() == wanted

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TableReference) and (
            self.__table,
            self.__alias,
            self.__schema,
        ) == (other.table, other.alias, other.schema)

    def __hash__(self) -> int:
        return hash((self.__table, self.__alias, self.__schema))

    def __repr__(self) -> str:
        text = "TableReference({!r}, alias={!r}, schema={!r})"
        return text.format(self.__table, self.__alias, self.__schema)
