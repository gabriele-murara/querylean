"""JSON file with bookmarked queries exported from QueryLean."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from querylean.app.app_info import AppInfo
from querylean.bookmarks.bookmark_entry import BookmarkEntry
from querylean.config.config_error import ConfigError
from querylean.files.private_json_file import PrivateJsonFile
from querylean.log.log_manager import LogManager


class BookmarkExport:
    """Builds and writes the export file of bookmarked queries.

    The file holds only queries and masks, to be shared with other users
    and imported by another QueryLean installation::

        {
          "format": "querylean-bookmarks",
          "format_version": 1,
          "exported_at": "2026-11-08T09:30:00+00:00",
          "exported_by": {"application": "querylean", "version": "…"},
          "bookmarks": [
            {"name": "…", "kind": "query", "sql": "…"},
            {"name": "…", "kind": "mask", "sql": "…",
             "placeholders": [{"name": "…", "type": "…", …}],
             "last_values": {"…": "…"}}
          ]
        }

    Nothing about connections is written (no host, port, user, database,
    target, password or local setting): whoever imports the file chooses
    the connection, with their own credentials, the queries run on.

    A bookmark keeps the keys of the bookmark files
    (``QueryBookmark.to_dict`` without the target); ``kind`` is
    informative only.
    ``last_values`` is written only on request: they may be real data.
    The same bookmark saved for several connections is written once.

    An import must treat the file as untrusted: check ``format`` and
    ``format_version``, rebuild each bookmark with ``QueryBookmark.from_dict``
    (adding the target of the chosen connection) and accept it only if
    ``ReadOnlyValidator`` accepts its query (compiled with the defaults for
    a mask), as when saving.
    """

    FORMAT = "querylean-bookmarks"
    # Increase on incompatible changes; an import refuses newer versions.
    FORMAT_VERSION = 1
    EXTENSION = ".json"
    DEFAULT_FILE_NAME = "querylean-bookmarks.json"
    NAME_FILTER = "QueryLean bookmarks (*.json)"
    QUERY_KIND = "query"
    MASK_KIND = "mask"
    __log = LogManager.get_logger(__name__)

    @staticmethod
    def payload(
        entries: Iterable[BookmarkEntry],
        *,
        include_last_values: bool = False,
        exported_at: dt.datetime | None = None,
    ) -> dict[str, Any]:
        """Content of the export file for ``entries``, in their order;
        identical bookmarks (same name, query and placeholders) are
        written once."""
        when = exported_at or dt.datetime.now(dt.UTC)
        bookmarks: list[dict[str, Any]] = []
        for entry in entries:
            data = BookmarkExport.__bookmark(entry, include_last_values)
            if data not in bookmarks:
                bookmarks.append(data)
        return {
            "format": BookmarkExport.FORMAT,
            "format_version": BookmarkExport.FORMAT_VERSION,
            "exported_at": when.isoformat(timespec="seconds"),
            "exported_by": {
                "application": AppInfo.NAME,
                "version": AppInfo.version(),
            },
            "bookmarks": bookmarks,
        }

    @staticmethod
    def write(
        path: Path,
        entries: Iterable[BookmarkEntry],
        *,
        include_last_values: bool = False,
    ) -> int:
        """Write the export of ``entries`` to ``path`` (atomically, mode
        0600). Returns the number of bookmarks written (identical ones
        count once). Raises ``ConfigError``."""
        payload = BookmarkExport.payload(
            entries, include_last_values=include_last_values
        )
        count = len(payload["bookmarks"])
        try:
            PrivateJsonFile.write(Path(path), payload)
        except OSError as exc:
            BookmarkExport.__log.error(
                "Cannot export bookmarks to {}: {}", path, exc
            )
            msg = "Cannot write {}: {}"
            raise ConfigError(msg.format(path, exc.strerror or exc)) from exc
        BookmarkExport.__log.info("{} bookmarks exported to {}", count, path)
        return count

    @staticmethod
    def kind_of(entry: BookmarkEntry) -> str:
        """``mask`` for a bookmark with placeholders, otherwise ``query``."""
        if entry.bookmark.is_mask:
            return BookmarkExport.MASK_KIND
        return BookmarkExport.QUERY_KIND

    @staticmethod
    def __bookmark(
        entry: BookmarkEntry, include_last_values: bool
    ) -> dict[str, Any]:
        stored = entry.bookmark.to_dict()
        data: dict[str, Any] = {
            "name": stored["name"],
            "kind": BookmarkExport.kind_of(entry),
            "sql": stored["sql"],
        }
        if "placeholders" in stored:
            data["placeholders"] = stored["placeholders"]
        if include_last_values and "last_values" in stored:
            data["last_values"] = stored["last_values"]
        return data
