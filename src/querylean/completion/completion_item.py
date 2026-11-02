"""One autocompletion proposal."""

from __future__ import annotations

from querylean.completion.completion_kind import CompletionKind


class CompletionItem:
    """Proposal shown in the list: ``label`` and ``detail`` are displayed,
    ``insert_text`` replaces the word; the cursor ends ``caret_back``
    characters before the end of it (1 to land inside ``()``)."""

    def __init__(
        self,
        label: str,
        kind: CompletionKind,
        *,
        detail: str = "",
        insert_text: str | None = None,
        caret_back: int = 0,
        tooltip: str = "",
    ) -> None:
        self.__label = label
        self.__kind = kind
        self.__detail = detail
        self.__insert_text = label if insert_text is None else insert_text
        self.__caret_back = caret_back
        self.__tooltip = tooltip

    @property
    def label(self) -> str:
        """Text shown in the list."""
        return self.__label

    @property
    def kind(self) -> CompletionKind:
        """Kind of proposal."""
        return self.__kind

    @property
    def detail(self) -> str:
        """Secondary text (type, table…), shown on the right."""
        return self.__detail

    @property
    def insert_text(self) -> str:
        """Text written in the editor."""
        return self.__insert_text

    @property
    def caret_back(self) -> int:
        """Characters between the cursor and the end of the insertion."""
        return self.__caret_back

    @property
    def tooltip(self) -> str:
        """Longer description (column definition), may be empty."""
        return self.__tooltip

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CompletionItem) and (
            self.__label,
            self.__kind,
            self.__detail,
            self.__insert_text,
        ) == (other.label, other.kind, other.detail, other.insert_text)

    def __hash__(self) -> int:
        return hash((self.__label, self.__kind, self.__insert_text))

    def __repr__(self) -> str:
        text = "CompletionItem({!r}, {}, insert={!r})"
        return text.format(self.__label, self.__kind.name, self.__insert_text)
