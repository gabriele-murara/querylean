"""Tests of the bookmark files of the saved connections."""

import json
import stat

import pytest

from querylean.bookmarks.bookmark_store import BookmarkStore
from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_type import PlaceholderType
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.config_error import ConfigError
from querylean.config.connection_store import ConnectionStore


class TestBookmarkStore:
    """Per connection and per target, replacement, damaged files."""

    TARGET = "ro@db:3306/app"
    OTHER_TARGET = "ro@db:3306/other"

    @pytest.fixture
    def store(self, tmp_path) -> BookmarkStore:
        return BookmarkStore(tmp_path / "bookmarks")

    @pytest.fixture
    def profile_id(self) -> str:
        return ConnectionStore.new_id()

    def bookmark(self, name, sql="SELECT 1", target=TARGET) -> QueryBookmark:
        return QueryBookmark(name, sql, target)

    def test_empty_when_missing(self, store, profile_id):
        assert store.load(profile_id, self.TARGET) == []
        assert store.find(profile_id, self.TARGET, "a") is None

    def test_add_and_load_sorted(self, store, profile_id):
        store.add(profile_id, self.bookmark("beta"))
        store.add(profile_id, self.bookmark("Alpha"))
        names = [b.name for b in store.load(profile_id, self.TARGET)]
        assert names == ["Alpha", "beta"]
        path = store.path_of(profile_id)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_same_name_is_replaced(self, store, profile_id):
        store.add(profile_id, self.bookmark("Users", "SELECT 1"))
        store.add(profile_id, self.bookmark("users", "SELECT 2"))
        found = store.load(profile_id, self.TARGET)
        assert [(b.name, b.sql) for b in found] == [("users", "SELECT 2")]

    def test_bookmarks_are_per_connection(self, store, profile_id):
        store.add(profile_id, self.bookmark("Users"))
        other = ConnectionStore.new_id()
        assert store.load(other, self.TARGET) == []
        assert store.find(other, self.TARGET, "Users") is None

    def test_bookmarks_are_per_target(self, store, profile_id):
        store.add(profile_id, self.bookmark("Users"))
        store.add(profile_id, self.bookmark("Users", target=self.OTHER_TARGET))
        assert len(store.load(profile_id, self.TARGET)) == 1
        assert store.find(profile_id, self.OTHER_TARGET, "Users") is not None
        assert store.find(profile_id, "ro@db2:3306/app", "Users") is None

    def test_remove(self, store, profile_id):
        store.add(profile_id, self.bookmark("Users"))
        store.add(profile_id, self.bookmark("Users", target=self.OTHER_TARGET))
        assert store.remove(profile_id, self.TARGET, "USERS")
        assert not store.remove(profile_id, self.TARGET, "Users")
        assert store.load(profile_id, self.TARGET) == []
        assert len(store.load(profile_id, self.OTHER_TARGET)) == 1

    def test_delete_all(self, store, profile_id):
        store.add(profile_id, self.bookmark("Users"))
        store.delete_all(profile_id)
        assert not store.path_of(profile_id).exists()
        store.delete_all(profile_id)  # missing file: no error

    def test_invalid_id_is_refused(self, store):
        with pytest.raises(ValueError):
            store.path_of("../config")

    @pytest.mark.parametrize("content", ["{not json", "[]", '{"bookmarks": 1}'])
    def test_damaged_file_is_not_overwritten(self, store, profile_id, content):
        path = store.path_of(profile_id)
        path.parent.mkdir(parents=True)
        path.write_text(content, encoding="utf-8")
        assert store.load(profile_id, self.TARGET) == []
        with pytest.raises(ConfigError):
            store.add(profile_id, self.bookmark("Users"))
        with pytest.raises(ConfigError):
            store.remove(profile_id, self.TARGET, "Users")
        assert path.read_text(encoding="utf-8") == content

    def test_invalid_entries_are_skipped(self, store, profile_id):
        path = store.path_of(profile_id)
        path.parent.mkdir(parents=True)
        entries = [
            {"name": "ok", "sql": "SELECT 1", "target": self.TARGET},
            {"name": "", "sql": "SELECT 1", "target": self.TARGET},
            "junk",
        ]
        path.write_text(json.dumps({"bookmarks": entries}), encoding="utf-8")
        names = [b.name for b in store.load(profile_id, self.TARGET)]
        assert names == ["ok"]

    def test_masks_are_stored_and_version_1_files_still_read(
        self, store, profile_id
    ):
        path = store.path_of(profile_id)
        path.parent.mkdir(parents=True)
        legacy = {
            "version": 1,
            "bookmarks": [
                {"name": "old", "sql": "SELECT 1", "target": self.TARGET}
            ],
        }
        path.write_text(json.dumps(legacy), encoding="utf-8")
        mask = QueryBookmark(
            "mask",
            "SELECT * FROM t WHERE y = ${Y}",
            self.TARGET,
            (Placeholder("Y", PlaceholderType.INTEGER, default="1"),),
        )
        store.add(profile_id, mask)
        loaded = store.load(profile_id, self.TARGET)
        assert [b.name for b in loaded] == ["mask", "old"]
        assert loaded[0] == mask
        assert json.loads(path.read_text(encoding="utf-8"))["version"] == 2
