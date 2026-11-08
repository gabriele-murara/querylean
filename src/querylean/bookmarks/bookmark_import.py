"""Export file of bookmarked queries read for an import."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from querylean.bookmarks.bookmark_export import BookmarkExport
from querylean.bookmarks.imported_bookmark import ImportedBookmark
from querylean.bookmarks.mask_error import MaskError
from querylean.bookmarks.mask_template import MaskTemplate
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.config_error import ConfigError
from querylean.database.validation.read_only_validator import (
    ReadOnlyValidator,
)
from querylean.log.log_manager import LogManager


class BookmarkImport:
    """Content of a file written by ``BookmarkExport``, checked.

    The file comes from someone else and is untrusted: ``format`` must be
    ``BookmarkExport.FORMAT`` and ``format_version`` a version this
    installation knows (newer ones are refused); each bookmark is rebuilt
    with ``QueryBookmark.from_dict`` from its known keys only (``kind`` and
    unknown keys are ignored, a ``target`` in the file never used), and
    invalid ones are counted in ``invalid`` and left out. A bookmark whose
    query (compiled with the defaults for a mask) is refused by
    ``ReadOnlyValidator`` is listed with the reason and never imported.
    """

    # Bigger files are refused without being parsed.
    MAX_FILE_SIZE = 5 * 1024 * 1024
    MAX_BOOKMARKS = 10000
    # Target of the bookmarks until a connection is chosen.
    NO_TARGET = "-"
    NOT_READ = "Not a read query: {}"
    __KEYS = ("name", "sql", "placeholders", "last_values")
    __log = LogManager.get_logger(__name__)

    def __init__(
        self,
        items: tuple[ImportedBookmark, ...],
        *,
        invalid: int = 0,
        exported_at: str = "",
        exported_by: str = "",
    ) -> None:
        self.__items = tuple(items)
        self.__invalid = invalid
        self.__exported_at = exported_at
        self.__exported_by = exported_by

    @property
    def items(self) -> tuple[ImportedBookmark, ...]:
        """Valid bookmarks of the file, in file order."""
        return self.__items

    @property
    def invalid(self) -> int:
        """Entries of the file left out because they are not valid."""
        return self.__invalid

    @property
    def exported_at(self) -> str:
        """Export time as written in the file (may be empty)."""
        return self.__exported_at

    @property
    def exported_by(self) -> str:
        """Application and version that wrote the file (may be empty)."""
        return self.__exported_by

    @staticmethod
    def read(path: Path, validator: ReadOnlyValidator) -> BookmarkImport:
        """Read and check the export file ``path``. Raises ``ConfigError``
        when it cannot be read or is not an export of bookmarks."""
        path = Path(path)
        try:
            with path.open("rb") as stream:
                raw = stream.read(BookmarkImport.MAX_FILE_SIZE + 1)
        except OSError as exc:
            BookmarkImport.__log.error("Cannot read {}: {}", path, exc)
            msg = "Cannot read {}: {}"
            raise ConfigError(msg.format(path, exc.strerror or exc)) from exc
        if len(raw) > BookmarkImport.MAX_FILE_SIZE:
            msg = "{} is too big for a file of bookmarked queries."
            raise ConfigError(msg.format(path))
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, RecursionError) as exc:
            BookmarkImport.__log.warning("Unreadable import {}: {}", path, exc)
            msg = "{} is not a valid JSON file."
            raise ConfigError(msg.format(path)) from exc
        result = BookmarkImport.parse(data, validator)
        BookmarkImport.__log.info(
            "{} bookmarks read from {} ({} invalid)",
            len(result.items),
            path,
            result.invalid,
        )
        return result

    @staticmethod
    def parse(data: object, validator: ReadOnlyValidator) -> BookmarkImport:
        """Check the decoded content of an export file. Raises
        ``ConfigError`` when it is not an export of bookmarks."""
        if (
            not isinstance(data, dict)
            or data.get("format") != BookmarkExport.FORMAT
        ):
            raise ConfigError("The file is not an export of bookmarks.")
        version = data.get("format_version")
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version < 1
        ):
            raise ConfigError("The version of the file is not valid.")
        if version > BookmarkExport.FORMAT_VERSION:
            msg = "The file was written by a newer version of QueryLean: "
            msg += "update QueryLean to import it."
            raise ConfigError(msg)
        entries = data.get("bookmarks")
        if not isinstance(entries, list):
            raise ConfigError("The file has no list of bookmarks.")
        if len(entries) > BookmarkImport.MAX_BOOKMARKS:
            msg = "The file has more than {} bookmarks."
            raise ConfigError(msg.format(BookmarkImport.MAX_BOOKMARKS))
        items = []
        for entry in entries:
            bookmark = BookmarkImport.__bookmark(entry)
            if bookmark is not None:
                items.append(
                    ImportedBookmark(
                        bookmark, BookmarkImport.refusal(bookmark, validator)
                    )
                )
        return BookmarkImport(
            tuple(items),
            invalid=len(entries) - len(items),
            exported_at=BookmarkImport.__text(data.get("exported_at")),
            exported_by=BookmarkImport.__producer(data.get("exported_by")),
        )

    @staticmethod
    def refusal(bookmark: QueryBookmark, validator: ReadOnlyValidator) -> str:
        """Why ``bookmark`` cannot be saved, as when it is saved from the
        editor: its query (a mask compiled with its defaults) must be
        accepted by ``validator``. Empty when it can."""
        sql = bookmark.sql
        if bookmark.is_mask:
            placeholders = {p.name: p for p in bookmark.placeholders}
            defaults = {p.name: p.default for p in bookmark.placeholders}
            try:
                sql = MaskTemplate(sql).compile(placeholders, defaults)
            except MaskError as exc:
                return exc.message
        # Fail closed: the validator never raises, it rejects.
        validation = validator.validate(sql)
        if validation.ok:
            return ""
        return BookmarkImport.NOT_READ.format(validation.reason)

    @staticmethod
    def __bookmark(entry: object) -> QueryBookmark | None:
        """Bookmark of the file from its known keys; None when invalid."""
        if not isinstance(entry, dict):
            return None
        data: dict[str, Any] = {
            key: entry[key] for key in BookmarkImport.__KEYS if key in entry
        }
        data["target"] = BookmarkImport.NO_TARGET
        return QueryBookmark.from_dict(data)

    @staticmethod
    def __producer(data: object) -> str:
        """``application version`` from ``exported_by``."""
        if not isinstance(data, dict):
            return ""
        parts = [
            BookmarkImport.__text(data.get(key))
            for key in ("application", "version")
        ]
        return " ".join(part for part in parts if part)

    @staticmethod
    def __text(value: object) -> str:
        """``value`` when it is a short text, otherwise empty."""
        if isinstance(value, str) and len(value) <= 100:
            return " ".join(value.split())
        return ""
