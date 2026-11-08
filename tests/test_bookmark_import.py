"""Tests of the reading of an export file of bookmarked queries."""

import json
import os

import pytest

from querylean.bookmarks.bookmark_entry import BookmarkEntry
from querylean.bookmarks.bookmark_export import BookmarkExport
from querylean.bookmarks.bookmark_import import BookmarkImport
from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_type import PlaceholderType
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.config_error import ConfigError
from querylean.config.connection_config import ConnectionConfig
from querylean.config.connection_profile import ConnectionProfile
from querylean.database.validation.read_only_validator import (
    ReadOnlyValidator,
)


class TestBookmarkImport:
    """Untrusted file: format, version, entries and validator."""

    TARGET = "me@localhost:3306/dev"

    @pytest.fixture
    def validator(self) -> ReadOnlyValidator:
        return ReadOnlyValidator()

    @pytest.fixture
    def mask(self) -> QueryBookmark:
        placeholder = Placeholder(
            "YEAR", PlaceholderType.INTEGER, default="2025"
        )
        return QueryBookmark(
            "By year",
            "SELECT * FROM orders WHERE y = ${YEAR}",
            "ro@db:3306/sales",
            (placeholder,),
            {"YEAR": "2024"},
        )

    def payload(self, *bookmarks, **extra) -> dict:
        data = {
            "format": BookmarkExport.FORMAT,
            "format_version": BookmarkExport.FORMAT_VERSION,
            "bookmarks": list(bookmarks),
        }
        data.update(extra)
        return data

    def write(self, tmp_path, data) -> object:
        path = tmp_path / "in.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_round_trip_of_an_export(self, tmp_path, validator, mask):
        profile = ConnectionProfile(
            "a" * 32, ConnectionConfig(host="db", username="ro")
        )
        users = QueryBookmark("Users", "SELECT * FROM users", mask.target)
        path = tmp_path / "out.json"
        BookmarkExport.write(
            path,
            [BookmarkEntry(profile, mask), BookmarkEntry(profile, users)],
            include_last_values=True,
        )
        source = BookmarkImport.read(path, validator)
        assert source.invalid == 0
        assert all(item.importable for item in source.items)
        assert source.exported_by.startswith("querylean ")
        assert source.exported_at
        saved = [item.for_target(self.TARGET) for item in source.items]
        assert saved == [
            mask.with_target(self.TARGET),
            users.with_target(self.TARGET),
        ]
        bare = source.items[0].for_target(self.TARGET, last_values=False)
        assert bare.last_values == {}

    def test_connection_data_in_the_file_is_ignored(self, validator):
        entry = {
            "name": "Users",
            "kind": "mask",
            "sql": "SELECT 1",
            "target": "root@prod:3306/app",
            "host": "prod",
        }
        source = BookmarkImport.parse(self.payload(entry), validator)
        bookmark = source.items[0].bookmark
        assert bookmark.target == BookmarkImport.NO_TARGET
        assert not bookmark.is_mask

    def test_invalid_entries_are_counted(self, validator):
        entries = (
            {"name": "ok", "sql": "SELECT 1"},
            {"name": "", "sql": "SELECT 1"},
            {"name": "no sql"},
            "text",
            {"name": "m", "sql": "SELECT ${A}", "placeholders": []},
            {"name": "x" * 101, "sql": "SELECT 1"},
        )
        source = BookmarkImport.parse(self.payload(*entries), validator)
        assert [i.bookmark.name for i in source.items] == ["ok"]
        assert source.invalid == 5

    def test_write_queries_are_refused(self, validator):
        entries = (
            {"name": "Drop", "sql": "DROP TABLE users"},
            {"name": "Two", "sql": "SELECT 1; DELETE FROM t"},
            {"name": "Read", "sql": "SELECT 1"},
        )
        source = BookmarkImport.parse(self.payload(*entries), validator)
        assert [i.importable for i in source.items] == [False, False, True]
        assert source.items[0].refusal.startswith("Not a read query: ")
        assert source.items[2].refusal == ""

    def test_masks_are_checked_with_their_defaults(self, validator):
        placeholder = Placeholder("N", PlaceholderType.INTEGER, default="x")
        bad_default = QueryBookmark("Bad", "SELECT ${N}", "t", (placeholder,))
        assert BookmarkImport.refusal(bad_default, validator)
        text = Placeholder("V", default="1")
        hidden = QueryBookmark(
            "Hidden", "DELETE FROM t WHERE a = ${V}", "t", (text,)
        )
        assert BookmarkImport.refusal(hidden, validator).startswith(
            "Not a read query"
        )

    @pytest.mark.parametrize(
        ("data", "message"),
        [
            ([], "not an export"),
            ({"format": "other", "format_version": 1}, "not an export"),
            ({"format": "querylean-bookmarks"}, "version"),
            (
                {"format": "querylean-bookmarks", "format_version": True},
                "version",
            ),
            (
                {"format": "querylean-bookmarks", "format_version": 0},
                "version",
            ),
            ({"format": "querylean-bookmarks", "format_version": 99}, "newer"),
            (
                {
                    "format": "querylean-bookmarks",
                    "format_version": 1,
                    "bookmarks": {},
                },
                "no list",
            ),
        ],
    )
    def test_not_an_export(self, validator, data, message):
        with pytest.raises(ConfigError, match=message):
            BookmarkImport.parse(data, validator)

    def test_too_many_bookmarks(self, validator):
        entries = [{"name": "a", "sql": "SELECT 1"}] * (
            BookmarkImport.MAX_BOOKMARKS + 1
        )
        with pytest.raises(ConfigError, match="more than"):
            BookmarkImport.parse(self.payload(*entries), validator)

    def test_unreadable_files(self, tmp_path, validator, monkeypatch):
        with pytest.raises(ConfigError, match="Cannot read"):
            BookmarkImport.read(tmp_path / "missing.json", validator)
        broken = tmp_path / "broken.json"
        broken.write_text("{", encoding="utf-8")
        with pytest.raises(ConfigError, match="not a valid JSON"):
            BookmarkImport.read(broken, validator)
        deep = tmp_path / "deep.json"
        deep.write_text("[" * 100000, encoding="utf-8")
        with pytest.raises(ConfigError, match="not a valid JSON"):
            BookmarkImport.read(deep, validator)
        monkeypatch.setattr(BookmarkImport, "MAX_FILE_SIZE", 10)
        path = self.write(tmp_path, self.payload())
        with pytest.raises(ConfigError, match="too big"):
            BookmarkImport.read(path, validator)

    def test_producer_text_is_cleaned(self, validator):
        data = self.payload(
            exported_by={"application": "querylean", "version": ["x"]},
            exported_at="2026-11-08\nT09:30",
        )
        source = BookmarkImport.parse(data, validator)
        assert source.exported_by == "querylean"
        assert source.exported_at == "2026-11-08 T09:30"
        assert BookmarkImport.parse(self.payload(), validator).items == ()

    def test_only_regular_files_are_read(self, tmp_path, validator):
        fifo = tmp_path / "pipe.json"
        os.mkfifo(fifo)
        # Opening a FIFO would block until a writer appears.
        with pytest.raises(ConfigError, match="not a regular file"):
            BookmarkImport.read(fifo, validator)
        with pytest.raises(ConfigError, match="not a regular file"):
            BookmarkImport.read(tmp_path, validator)
