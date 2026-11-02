"""A column of a table (or view) of the current database."""

from __future__ import annotations


class ColumnInfo:
    """Immutable description of a column, as reported by the server."""

    PRIMARY_KEY = "PRI"
    UNIQUE_KEY = "UNI"
    INDEX_KEY = "MUL"

    def __init__(
        self,
        name: str,
        data_type: str = "",
        *,
        nullable: bool = True,
        key: str = "",
        default: str | None = None,
        extra: str = "",
        comment: str = "",
    ) -> None:
        self.__name = name
        self.__data_type = data_type
        self.__nullable = nullable
        self.__key = key.upper()
        self.__default = default
        self.__extra = extra
        self.__comment = comment

    @property
    def name(self) -> str:
        """Column name as returned by the server."""
        return self.__name

    @property
    def data_type(self) -> str:
        """Full column type, e.g. ``varchar(64)`` or ``int unsigned``."""
        return self.__data_type

    @property
    def nullable(self) -> bool:
        """True when the column accepts NULL."""
        return self.__nullable

    @property
    def key(self) -> str:
        """``PRI``, ``UNI``, ``MUL`` or empty."""
        return self.__key

    @property
    def default(self) -> str | None:
        """Default value as text (None when there is none)."""
        return self.__default

    @property
    def extra(self) -> str:
        """Extra information, e.g. ``auto_increment``."""
        return self.__extra

    @property
    def comment(self) -> str:
        """Column comment."""
        return self.__comment

    @property
    def is_primary(self) -> bool:
        """True for a column of the primary key."""
        return self.__key == ColumnInfo.PRIMARY_KEY

    def key_label(self) -> str:
        """User-facing name of the key, empty when there is none."""
        return {
            ColumnInfo.PRIMARY_KEY: "primary key",
            ColumnInfo.UNIQUE_KEY: "unique",
            ColumnInfo.INDEX_KEY: "indexed",
        }.get(self.__key, "")

    def describe(self) -> str:
        """Multi-line description (type, NULL, key, default, extra,
        comment) for tooltips."""
        lines = [self.__name, self.__data_type or "unknown type"]
        lines.append("NULL" if self.__nullable else "NOT NULL")
        if self.key_label():
            lines.append(self.key_label())
        if self.__default is not None:
            lines.append("default: {}".format(self.__default))
        if self.__extra:
            lines.append(self.__extra)
        if self.__comment:
            lines.append("“{}”".format(self.__comment))
        return "\n".join(lines)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ColumnInfo) and self.__fields() == (
            other.name,
            other.data_type,
            other.nullable,
            other.key,
            other.default,
            other.extra,
            other.comment,
        )

    def __hash__(self) -> int:
        return hash(self.__fields())

    def __repr__(self) -> str:
        text = "ColumnInfo({!r}, {!r}, key={!r})"
        return text.format(self.__name, self.__data_type, self.__key)

    def __fields(self) -> tuple[object, ...]:
        return (
            self.__name,
            self.__data_type,
            self.__nullable,
            self.__key,
            self.__default,
            self.__extra,
            self.__comment,
        )
