"""How imported bookmarks join the saved ones of a connection."""

from __future__ import annotations

from collections.abc import Iterable

from querylean.bookmarks.name_conflict import NameConflict
from querylean.bookmarks.query_bookmark import QueryBookmark


class BookmarkImportPlan:
    """Bookmarks of one connection and target after an import.

    Each incoming bookmark (already for the target) is, in order:

    - **unchanged** when a bookmark with the same name (ignoring case),
      query and placeholders is already there: nothing is written;
    - **added** when its name is free;
    - otherwise handled by ``conflict``: renamed to "name (2)", "name (3)",
      … (``RENAME``), saved in place of the other bookmark (``REPLACE``,
      keeping its last values when the imported one has none) or
      **skipped** (``SKIP``). A name taken by a bookmark added by the same
      import is always renamed: both were chosen.
    """

    NEW = "New"
    SAVED = "Already saved"
    NAME_TAKEN = "Name in use"
    # Format with the name and the number.
    __RENAMED = "{} ({})"

    def __init__(
        self,
        existing: Iterable[QueryBookmark],
        incoming: Iterable[QueryBookmark],
        conflict: NameConflict = NameConflict.RENAME,
    ) -> None:
        self.__kept = list(existing)
        self.__added: list[QueryBookmark] = []
        self.__renamed: list[tuple[str, str]] = []
        self.__replaced = 0
        self.__unchanged = 0
        self.__skipped = 0
        for bookmark in incoming:
            self.__place(bookmark, conflict)

    @property
    def bookmarks(self) -> list[QueryBookmark]:
        """Every bookmark of the target after the import."""
        return self.__kept + self.__added

    @property
    def added(self) -> tuple[QueryBookmark, ...]:
        """Imported bookmarks (new, renamed or replacing), with their
        final names."""
        return tuple(self.__added)

    @property
    def renamed(self) -> tuple[tuple[str, str], ...]:
        """``(name in the file, name saved)`` of the renamed bookmarks."""
        return tuple(self.__renamed)

    @property
    def replaced(self) -> int:
        """Saved bookmarks replaced by an imported one."""
        return self.__replaced

    @property
    def unchanged(self) -> int:
        """Imported bookmarks that were already saved."""
        return self.__unchanged

    @property
    def skipped(self) -> int:
        """Imported bookmarks left out because their name was taken."""
        return self.__skipped

    @property
    def changed(self) -> bool:
        """True when the saved bookmarks must be written."""
        return bool(self.__added)

    @staticmethod
    def status(
        existing: Iterable[QueryBookmark], bookmark: QueryBookmark
    ) -> str:
        """``NEW``, ``SAVED`` or ``NAME_TAKEN`` for ``bookmark`` against the
        saved bookmarks ``existing``."""
        for other in existing:
            if other.same_name(bookmark.name):
                if other.same_query(bookmark):
                    return BookmarkImportPlan.SAVED
                return BookmarkImportPlan.NAME_TAKEN
        return BookmarkImportPlan.NEW

    @staticmethod
    def free_name(name: str, taken: Iterable[str]) -> str:
        """``name``, or "name (N)" with the lowest N from 2 not in
        ``taken`` (ignoring case), cut to ``QueryBookmark.MAX_NAME_LENGTH``.
        """
        used = {other.casefold() for other in taken}
        if name.casefold() not in used:
            return name
        number = 2
        while True:
            suffix = BookmarkImportPlan.__RENAMED.format("", number)
            base = name[: QueryBookmark.MAX_NAME_LENGTH - len(suffix)]
            candidate = BookmarkImportPlan.__RENAMED.format(
                base.rstrip(), number
            )
            if candidate.casefold() not in used:
                return candidate
            number += 1

    def __place(self, bookmark: QueryBookmark, conflict: NameConflict) -> None:
        saved = self.__find(self.__kept, bookmark.name)
        added = self.__find(self.__added, bookmark.name)
        other = saved if saved is not None else added
        if other is None:
            self.__added.append(bookmark)
        elif other.same_query(bookmark):
            self.__unchanged += 1
        elif added is not None or conflict == NameConflict.RENAME:
            self.__rename(bookmark)
        elif conflict == NameConflict.REPLACE and saved is not None:
            self.__kept.remove(saved)
            if not bookmark.last_values:
                bookmark = bookmark.with_last_values(saved.last_values)
            self.__added.append(bookmark)
            self.__replaced += 1
        else:
            self.__skipped += 1

    def __rename(self, bookmark: QueryBookmark) -> None:
        taken = [b.name for b in self.bookmarks]
        name = BookmarkImportPlan.free_name(bookmark.name, taken)
        self.__renamed.append((bookmark.name, name))
        self.__added.append(bookmark.with_name(name))

    @staticmethod
    def __find(
        bookmarks: list[QueryBookmark], name: str
    ) -> QueryBookmark | None:
        for bookmark in bookmarks:
            if bookmark.same_name(name):
                return bookmark
        return None
