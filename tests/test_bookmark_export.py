"""Tests of the export file of bookmarked queries."""

import datetime as dt
import json
import stat

import pytest

from querylean.app.app_info import AppInfo
from querylean.bookmarks.bookmark_entry import BookmarkEntry
from querylean.bookmarks.bookmark_export import BookmarkExport
from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_type import PlaceholderType
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.config_error import ConfigError
from querylean.config.connection_config import ConnectionConfig
from querylean.config.connection_profile import ConnectionProfile


class TestBookmarkExport:
    """Structure, grouping, privacy and writing of the export file."""

    WHEN = dt.datetime(2026, 11, 8, 9, 30, tzinfo=dt.UTC)

    @pytest.fixture
    def prod(self) -> ConnectionProfile:
        config = ConnectionConfig(
            name="Prod",
            host="db",
            port=3307,
            database="sales",
            username="report",
            caution_databases=["sales"],
        )
        return ConnectionProfile("a" * 32, config)

    @pytest.fixture
    def everything(self) -> ConnectionProfile:
        config = ConnectionConfig(host="db2", username="ro", all_databases=True)
        return ConnectionProfile("b" * 32, config)

    @pytest.fixture
    def mask(self, prod) -> QueryBookmark:
        placeholder = Placeholder(
            "YEAR",
            PlaceholderType.INTEGER,
            default="2025",
            description="Fiscal year",
        )
        return QueryBookmark(
            "By year",
            "SELECT * FROM orders WHERE y = ${YEAR}",
            QueryBookmark.target_of(prod.config),
            (placeholder,),
            {"YEAR": "2024"},
        )

    @pytest.fixture
    def entries(self, prod, everything, mask) -> list[BookmarkEntry]:
        users = QueryBookmark(
            "Users", "SELECT 1", QueryBookmark.target_of(prod.config)
        )
        dbs = QueryBookmark(
            "Users", "SELECT 2", QueryBookmark.target_of(everything.config)
        )
        return [
            BookmarkEntry(prod, mask),
            BookmarkEntry(everything, dbs),
            BookmarkEntry(prod, users),
        ]

    def test_header(self, entries):
        data = BookmarkExport.payload(entries, exported_at=self.WHEN)
        assert data["format"] == "querylean-bookmarks"
        assert data["format_version"] == 1
        assert data["exported_at"] == "2026-11-08T09:30:00+00:00"
        assert data["exported_by"] == {
            "application": AppInfo.NAME,
            "version": AppInfo.version(),
        }

    def test_only_queries_and_masks(self, entries):
        data = BookmarkExport.payload(entries, exported_at=self.WHEN)
        assert set(data) == {
            "format",
            "format_version",
            "exported_at",
            "exported_by",
            "bookmarks",
        }
        assert data["bookmarks"] == [
            {
                "name": "By year",
                "kind": "mask",
                "sql": "SELECT * FROM orders WHERE y = ${YEAR}",
                "placeholders": [
                    {
                        "name": "YEAR",
                        "type": "integer",
                        "list": False,
                        "default": "2025",
                        "description": "Fiscal year",
                    }
                ],
            },
            {"name": "Users", "kind": "query", "sql": "SELECT 2"},
            {"name": "Users", "kind": "query", "sql": "SELECT 1"},
        ]

    def test_no_connection_data(self, entries):
        data = BookmarkExport.payload(entries, include_last_values=True)
        text = json.dumps(data)
        absent = (
            "a" * 32,
            "b" * 32,
            "Prod",
            "report",
            "db2",
            "3307",
            "sales",
            "target",
            "host",
            "caution",
            "password",
            "timeout",
        )
        for word in absent:
            assert word not in text

    def test_identical_bookmarks_written_once(self, prod, everything):
        def entry(profile):
            target = QueryBookmark.target_of(profile.config)
            return BookmarkEntry(
                profile, QueryBookmark("Users", "SELECT 1", target)
            )

        data = BookmarkExport.payload([entry(prod), entry(everything)])
        assert data["bookmarks"] == [
            {"name": "Users", "kind": "query", "sql": "SELECT 1"}
        ]

    def test_last_values_only_on_request(self, entries):
        without = BookmarkExport.payload(entries)
        assert "last_values" not in without["bookmarks"][0]
        with_values = BookmarkExport.payload(entries, include_last_values=True)
        mask = with_values["bookmarks"][0]
        assert mask["last_values"] == {"YEAR": "2024"}

    def test_bookmarks_can_be_rebuilt_for_an_import(self, entries, mask):
        data = BookmarkExport.payload(entries, include_last_values=True)
        # The import adds the target of the connection chosen locally.
        stored = dict(data["bookmarks"][0], target=mask.target)
        assert QueryBookmark.from_dict(stored) == mask

    def test_empty_export(self):
        assert BookmarkExport.payload([])["bookmarks"] == []

    def test_kind_of(self, entries):
        kinds = [BookmarkExport.kind_of(e) for e in entries]
        assert kinds == ["mask", "query", "query"]

    def test_write_private_file(self, tmp_path, entries):
        path = tmp_path / "out" / "b.json"
        assert BookmarkExport.write(path, entries) == 3
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["format"] == BookmarkExport.FORMAT
        assert len(data["bookmarks"]) == 3

    def test_write_error(self, tmp_path, entries):
        blocker = tmp_path / "file"
        blocker.write_text("x", encoding="utf-8")
        with pytest.raises(ConfigError, match="Cannot write"):
            BookmarkExport.write(blocker / "b.json", entries)
