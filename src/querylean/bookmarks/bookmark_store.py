"""Bookmarked queries, one JSON file per saved connection."""

from __future__ import annotations

import json
from pathlib import Path

from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.config_error import ConfigError
from querylean.config.connection_store import ConnectionStore
from querylean.files.private_json_file import PrivateJsonFile
from querylean.log.log_manager import LogManager


class BookmarkStore:
    """Directory with one ``<connection id>.json`` file (mode 0600) per
    saved connection, holding its bookmarked queries.

    Each bookmark also records its target (``QueryBookmark.target``):
    reading returns only the bookmarks of the requested target, so after a
    connection is edited to point elsewhere its old bookmarks are no longer
    offered. A damaged file is never overwritten: reading it yields no
    bookmarks, changing it raises ``ConfigError``.
    """

    SUFFIX = ".json"
    # Format with the name of the other bookmark.
    NAME_TAKEN = "Another bookmarked query is named “{}”."
    # 2: masks (bookmarks with placeholders); version 1 files are read
    # unchanged.
    __FORMAT_VERSION = 2
    __log = LogManager.get_logger(__name__)

    def __init__(self, directory: Path) -> None:
        self.__directory = Path(directory)

    @property
    def directory(self) -> Path:
        """Folder holding the bookmark files."""
        return self.__directory

    def path_of(self, profile_id: str) -> Path:
        """Bookmark file of the connection ``profile_id``."""
        ConnectionStore.check_id(profile_id)
        return self.__directory / "{}{}".format(
            profile_id, BookmarkStore.SUFFIX
        )

    def load(self, profile_id: str, target: str) -> list[QueryBookmark]:
        """Bookmarks of ``profile_id`` saved for ``target``, sorted by name
        (case insensitive). An unreadable file yields an empty list."""
        try:
            bookmarks = self.__read(profile_id)
        except ConfigError as exc:
            self.__log.warning("{}", exc)
            return []
        found = [b for b in bookmarks if b.target == target]
        found.sort(key=lambda b: b.name.casefold())
        return found

    def find(
        self, profile_id: str, target: str, name: str
    ) -> QueryBookmark | None:
        """Bookmark ``name`` of ``profile_id`` for ``target``, if any."""
        for bookmark in self.load(profile_id, target):
            if bookmark.same_name(name):
                return bookmark
        return None

    def add(self, profile_id: str, bookmark: QueryBookmark) -> None:
        """Save ``bookmark``, replacing the one with the same name and
        target. Raises ``ConfigError``."""
        bookmarks = [
            b
            for b in self.__read(profile_id)
            if not (b.target == bookmark.target and b.same_name(bookmark.name))
        ]
        bookmarks.append(bookmark)
        self.__write(profile_id, bookmarks)
        self.__log.info("Bookmark saved for connection {}", profile_id)

    def remember_values(
        self,
        profile_id: str,
        target: str,
        name: str,
        values: dict[str, str],
    ) -> QueryBookmark | None:
        """Store ``values`` as the last ones of the mask ``name`` for
        ``target``. Returns the updated mask, None when it does not exist.
        Raises ``ConfigError``."""
        bookmarks = self.__read(profile_id)
        for index, bookmark in enumerate(bookmarks):
            if bookmark.target == target and bookmark.same_name(name):
                updated = bookmark.with_last_values(values)
                bookmarks[index] = updated
                self.__write(profile_id, bookmarks)
                return updated
        return None

    def rename(
        self, profile_id: str, target: str, name: str, new_name: str
    ) -> QueryBookmark | None:
        """Give the bookmark ``name`` for ``target`` the name ``new_name``
        (a change of case only is allowed). Returns the renamed bookmark,
        None when it does not exist. Raises ``ConfigError``, also when
        another bookmark already has ``new_name``."""
        new_name = QueryBookmark.clean_name(new_name)
        if not new_name or len(new_name) > QueryBookmark.MAX_NAME_LENGTH:
            raise ConfigError("Invalid bookmark name.")
        bookmarks = self.__read(profile_id)
        found = None
        for index, bookmark in enumerate(bookmarks):
            if bookmark.target != target:
                continue
            if bookmark.same_name(name):
                found = index
            elif bookmark.same_name(new_name):
                raise ConfigError(
                    BookmarkStore.NAME_TAKEN.format(bookmark.name)
                )
        if found is None:
            return None
        renamed = bookmarks[found].with_name(new_name)
        bookmarks[found] = renamed
        self.__write(profile_id, bookmarks)
        self.__log.info("Bookmark renamed for connection {}", profile_id)
        return renamed

    def remove(self, profile_id: str, target: str, name: str) -> bool:
        """Delete the bookmark ``name`` for ``target``. Returns False when it
        does not exist. Raises ``ConfigError``."""
        bookmarks = self.__read(profile_id)
        kept = [
            b
            for b in bookmarks
            if not (b.target == target and b.same_name(name))
        ]
        if len(kept) == len(bookmarks):
            return False
        self.__write(profile_id, kept)
        self.__log.info("Bookmark deleted for connection {}", profile_id)
        return True

    def delete_all(self, profile_id: str) -> None:
        """Remove the bookmark file of ``profile_id``. Raises
        ``ConfigError``."""
        path = self.path_of(profile_id)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            self.__log.error("Cannot delete bookmarks {}: {}", path, exc)
            msg = "Cannot delete the bookmarks in {}: {}"
            raise ConfigError(msg.format(path, exc.strerror or exc)) from exc

    def __read(self, profile_id: str) -> list[QueryBookmark]:
        """Every bookmark in the file of ``profile_id`` (none when it does
        not exist). Raises ``ConfigError`` when it cannot be read."""
        path = self.path_of(profile_id)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            msg = "Unreadable bookmarks in {}: {}"
            raise ConfigError(msg.format(path, exc)) from exc
        entries = data.get("bookmarks") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            raise ConfigError("Invalid bookmark file {}".format(path))
        bookmarks = []
        for entry in entries:
            bookmark = QueryBookmark.from_dict(entry)
            if bookmark is None:
                self.__log.warning("Skipping an invalid bookmark in {}", path)
            else:
                bookmarks.append(bookmark)
        return bookmarks

    def __write(self, profile_id: str, bookmarks: list[QueryBookmark]) -> None:
        path = self.path_of(profile_id)
        payload = {
            "version": BookmarkStore.__FORMAT_VERSION,
            "bookmarks": [b.to_dict() for b in bookmarks],
        }
        try:
            PrivateJsonFile.write(path, payload)
        except OSError as exc:
            self.__log.error("Cannot save bookmarks {}: {}", path, exc)
            msg = "Cannot save the bookmarks in {}: {}"
            raise ConfigError(msg.format(path, exc.strerror or exc)) from exc
