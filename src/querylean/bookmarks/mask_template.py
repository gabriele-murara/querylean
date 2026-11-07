"""Text of a mask: a query with ``${NAME}`` placeholders."""

from __future__ import annotations

import re
from collections.abc import Mapping

from querylean.bookmarks.mask_error import MaskError
from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_occurrence import PlaceholderOccurrence
from querylean.bookmarks.placeholder_type import PlaceholderType


class MaskTemplate:
    """Finds the placeholders of a query and compiles it with values.

    Placeholders are recognised outside comments, both in plain SQL
    (``year = ${YEAR}``) and inside string literals (``cli =
    '${DIGITS}'``); one between backticks would name a table or column and
    is refused. Compiling never inserts text as SQL: outside strings a
    value becomes a typed literal (a number, ``TRUE``/``FALSE`` or an
    escaped string), inside a string it becomes escaped string content.
    So the compiled query keeps the structure of the mask whatever the
    values are.
    """

    __PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
    __OPENING = "${"
    __UNQUOTED_VALUE = re.compile(
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)|true|false", re.IGNORECASE
    )
    # Regions of the text: (kind, start, end, quote).
    __STRING = "string"
    __QUOTED_NAME = "quoted_name"
    __COMMENT = "comment"

    def __init__(self, sql: str) -> None:
        self.__sql = sql
        self.__occurrences = MaskTemplate.__parse(sql)

    @property
    def sql(self) -> str:
        """Text of the mask."""
        return self.__sql

    @property
    def occurrences(self) -> tuple[PlaceholderOccurrence, ...]:
        """Every placeholder in the text, in order."""
        return self.__occurrences

    @property
    def names(self) -> tuple[str, ...]:
        """Placeholder names in order of first appearance."""
        names: list[str] = []
        for occurrence in self.__occurrences:
            if occurrence.name not in names:
                names.append(occurrence.name)
        return tuple(names)

    @staticmethod
    def has_placeholders(sql: str) -> bool:
        """True when ``sql`` contains placeholders (also malformed ones,
        which make it a mask that cannot be used yet)."""
        if MaskTemplate.__OPENING not in sql:
            return False
        try:
            return bool(MaskTemplate.__parse(sql))
        except MaskError:
            return True

    def compile(
        self,
        placeholders: Mapping[str, Placeholder],
        values: Mapping[str, str],
    ) -> str:
        """The query with each placeholder replaced by its value. Raises
        ``MaskError`` naming the placeholder with a missing or invalid
        value."""
        parts: list[str] = []
        last = 0
        for occurrence in self.__occurrences:
            placeholder = placeholders.get(occurrence.name)
            if placeholder is None:
                msg = "{} is not defined."
                raise MaskError(msg.format("${{{}}}".format(occurrence.name)))
            try:
                text = MaskTemplate.__value_text(
                    placeholder, values.get(occurrence.name, ""), occurrence
                )
            except MaskError as exc:
                msg = "{}: {}"
                raise MaskError(
                    msg.format(placeholder.token, exc.message)
                ) from None
            parts.append(self.__sql[last : occurrence.start])
            parts.append(text)
            last = occurrence.end
        parts.append(self.__sql[last:])
        return "".join(parts)

    @staticmethod
    def make_placeholder(
        sql: str, start: int, end: int, name: str
    ) -> tuple[str, Placeholder]:
        """Replace the value selected between ``start`` and ``end`` with
        ``${name}``. Returns the new text and the placeholder, whose type
        and default come from the replaced value. Raises ``MaskError`` when
        the selection is not a value (a number, a string, part of a string
        or a comma-separated list of them)."""
        if not Placeholder.is_valid_name(name):
            msg = "“{}” is not a valid name: use letters, digits and _ "
            msg += "(not starting with a digit)."
            raise MaskError(msg.format(name))
        while start < end and sql[start].isspace():
            start += 1
        while end > start and sql[end - 1].isspace():
            end -= 1
        if start >= end:
            raise MaskError("Select the value to turn into a placeholder.")
        token = "${{{}}}".format(name)
        regions = MaskTemplate.__regions(sql)
        for kind, region_start, region_end, quote in regions:
            if (
                kind == MaskTemplate.__STRING
                and region_start < start
                and end < region_end
            ):
                # Part of a string: the placeholder stays inside the quotes.
                example = sql[start:end].replace(quote * 2, quote)
                placeholder = Placeholder(
                    name,
                    PlaceholderType.infer(example, quoted=True),
                    default=example,
                )
                return MaskTemplate.__replaced(sql, start, end, token), (
                    placeholder
                )
            if (
                region_start < end
                and start < region_end
                and not (
                    kind == MaskTemplate.__STRING
                    and start <= region_start
                    and region_end <= end
                )
            ):
                raise MaskError(
                    "Select a whole value, not part of a name or comment."
                )
        if MaskTemplate.__OPENING in sql[start:end]:
            raise MaskError("The selection already contains a placeholder.")
        examples, quoted = MaskTemplate.__literals(sql[start:end])
        kind = PlaceholderType.infer(examples[0], quoted=quoted)
        try:
            for example in examples:
                kind.normalize(example)
        except MaskError:
            kind = PlaceholderType.TEXT
        placeholder = Placeholder(
            name,
            kind,
            default=", ".join(examples),
            is_list=len(examples) > 1,
        )
        return MaskTemplate.__replaced(sql, start, end, token), placeholder

    # ------------------------------------------------------------ internals
    @staticmethod
    def __value_text(
        placeholder: Placeholder, value: str, occurrence: PlaceholderOccurrence
    ) -> str:
        kind = placeholder.kind
        if placeholder.is_list:
            if occurrence.quoted:
                raise MaskError("a list cannot be written inside quotes.")
            separator = "\n" if "\n" in value else ","
            items = [item.strip() for item in value.split(separator)]
            items = [item for item in items if item]
            if not items:
                raise MaskError("at least one value is required.")
            return ", ".join(kind.literal(kind.normalize(i)) for i in items)
        normalized = kind.normalize(value)
        if not occurrence.quoted:
            return kind.literal(normalized)
        quote = occurrence.quote
        return normalized.replace("\\", "\\\\").replace(quote, quote * 2)

    @staticmethod
    def __replaced(sql: str, start: int, end: int, text: str) -> str:
        return "{}{}{}".format(sql[:start], text, sql[end:])

    @staticmethod
    def __literals(text: str) -> tuple[list[str], bool]:
        """Values of a comma-separated list of literals (quotes removed)
        and whether they were quoted. Raises ``MaskError`` when an item is
        not a literal."""
        items: list[str] = []
        current: list[str] = []
        quote = ""
        i = 0
        while i < len(text):
            ch = text[i]
            if quote:
                current.append(ch)
                if ch == "\\" and i + 1 < len(text):
                    current.append(text[i + 1])
                    i += 1
                elif ch == quote:
                    if text[i + 1 : i + 2] == quote:
                        current.append(quote)
                        i += 1
                    else:
                        quote = ""
            elif ch in "'\"":
                quote = ch
                current.append(ch)
            elif ch == ",":
                items.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
            i += 1
        items.append("".join(current).strip())
        values: list[str] = []
        quoted_items = 0
        for item in items:
            if len(item) >= 2 and item[0] in "'\"" and item[-1] == item[0]:
                mark = item[0]
                inner = item[1:-1].replace(mark * 2, mark)
                values.append(inner.replace("\\\\", "\\"))
                quoted_items += 1
            elif MaskTemplate.__UNQUOTED_VALUE.fullmatch(item):
                values.append(item)
            else:
                msg = "Select a value: a number, a quoted string or a "
                msg += "comma-separated list of them (not “{}”)."
                raise MaskError(msg.format(item))
        return values, quoted_items == len(values)

    @staticmethod
    def __parse(sql: str) -> tuple[PlaceholderOccurrence, ...]:
        """Placeholders outside comments; raises ``MaskError`` for
        malformed ones and for those between backticks."""
        regions = MaskTemplate.__regions(sql)
        found: list[PlaceholderOccurrence] = []
        position = 0
        while True:
            i = sql.find(MaskTemplate.__OPENING, position)
            if i < 0:
                break
            region = next((r for r in regions if r[1] <= i < r[2]), None)
            if region is not None and region[0] == MaskTemplate.__COMMENT:
                position = i + 2
                continue
            if region is not None and region[0] == MaskTemplate.__QUOTED_NAME:
                raise MaskError(
                    "A placeholder cannot replace a name between backticks."
                )
            match = MaskTemplate.__PLACEHOLDER.match(sql, i)
            if match is None:
                line = sql.count("\n", 0, i) + 1
                msg = "Invalid placeholder on line {}: write ${{NAME}} "
                msg += "with letters, digits and _."
                raise MaskError(msg.format(line))
            quote = region[3] if region is not None else ""
            found.append(
                PlaceholderOccurrence(
                    match.group(1), match.start(), match.end(), quote
                )
            )
            position = match.end()
        return tuple(found)

    @staticmethod
    def __regions(sql: str) -> list[tuple[str, int, int, str]]:
        """Strings, names between backticks and comments, following MySQL's
        rules; unterminated ones run to the end of the text."""
        regions: list[tuple[str, int, int, str]] = []
        i, n = 0, len(sql)
        while i < n:
            ch = sql[i]
            nxt = sql[i + 1] if i + 1 < n else ""
            if ch == "#" or (
                ch == "-"
                and nxt == "-"
                and (i + 2 >= n or sql[i + 2].isspace())
            ):
                end = sql.find("\n", i)
                end = n if end < 0 else end
                regions.append((MaskTemplate.__COMMENT, i, end, ""))
                i = end
            elif ch == "/" and nxt == "*":
                end = sql.find("*/", i + 2)
                end = n if end < 0 else end + 2
                regions.append((MaskTemplate.__COMMENT, i, end, ""))
                i = end
            elif ch in "'\"`":
                kind = (
                    MaskTemplate.__QUOTED_NAME
                    if ch == "`"
                    else MaskTemplate.__STRING
                )
                j = i + 1
                while j < n:
                    if sql[j] == "\\" and ch != "`":
                        j += 2
                        continue
                    if sql[j] == ch:
                        if sql[j + 1 : j + 2] == ch:
                            j += 2
                            continue
                        break
                    j += 1
                end = min(j + 1, n)
                regions.append((kind, i, end, ch))
                i = end
            else:
                i += 1
        return regions
