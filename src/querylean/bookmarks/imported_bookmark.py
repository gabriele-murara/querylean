"""A bookmark read from an export file, with the outcome of its check."""

from __future__ import annotations

from querylean.bookmarks.query_bookmark import QueryBookmark


class ImportedBookmark:
    """Bookmark of an export file, not yet saved for a connection.

    ``bookmark`` has no real target (``BookmarkImport.NO_TARGET``):
    ``for_target`` gives the bookmark to save for the chosen connection.
    ``refusal`` is the reason it cannot be imported (its query, compiled
    with the defaults for a mask, is not a read query); empty when it can.
    """

    def __init__(self, bookmark: QueryBookmark, refusal: str = "") -> None:
        self.__bookmark = bookmark
        self.__refusal = refusal

    @property
    def bookmark(self) -> QueryBookmark:
        """The bookmark as read from the file."""
        return self.__bookmark

    @property
    def refusal(self) -> str:
        """Why it cannot be imported; empty when it can."""
        return self.__refusal

    @property
    def importable(self) -> bool:
        """True when the query was accepted by the validator."""
        return not self.__refusal

    def for_target(
        self, target: str, *, last_values: bool = True
    ) -> QueryBookmark:
        """The bookmark saved for ``target``, without its last values
        unless ``last_values``."""
        bookmark = self.__bookmark.with_target(target)
        if not last_values:
            bookmark = bookmark.with_last_values({})
        return bookmark

    def __repr__(self) -> str:
        text = "ImportedBookmark({!r}, importable={})"
        return text.format(self.__bookmark.name, self.importable)
