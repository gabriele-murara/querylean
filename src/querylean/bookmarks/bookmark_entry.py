"""A bookmarked query together with the saved connection it belongs to."""

from __future__ import annotations

from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.connection_profile import ConnectionProfile


class BookmarkEntry:
    """One bookmark of one saved connection, as listed for an export.

    Names are unique only within a connection and its target, so the
    connection is what tells two bookmarks with the same name apart.
    """

    def __init__(
        self, profile: ConnectionProfile, bookmark: QueryBookmark
    ) -> None:
        self.__profile = profile
        self.__bookmark = bookmark

    @property
    def profile(self) -> ConnectionProfile:
        """Saved connection of the bookmark."""
        return self.__profile

    @property
    def bookmark(self) -> QueryBookmark:
        """The bookmarked query (or mask)."""
        return self.__bookmark

    @property
    def sort_key(self) -> tuple[str, str]:
        """Connection name, then bookmark name, ignoring case."""
        return (
            self.__profile.display_name.casefold(),
            self.__bookmark.name.casefold(),
        )

    def __repr__(self) -> str:
        text = "BookmarkEntry({!r}, {!r})"
        return text.format(self.__profile.profile_id, self.__bookmark.name)
