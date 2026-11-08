"""Tests of the bookmark files of the saved connections."""

import json
import stat

import pytest

from querylean.bookmarks.bookmark_store import BookmarkStore
from querylean.bookmarks.name_conflict import NameConflict
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

    def test_last_values_are_remembered(self, store, profile_id):
        mask = QueryBookmark(
            "Mask",
            "SELECT * FROM t WHERE y = ${Y}",
            self.TARGET,
            (Placeholder("Y", PlaceholderType.INTEGER, default="1"),),
        )
        store.add(profile_id, mask)
        store.add(profile_id, self.bookmark("plain"))
        updated = store.remember_values(
            profile_id, self.TARGET, "mask", {"Y": "7"}
        )
        assert updated is not None and updated.last_values == {"Y": "7"}
        loaded = store.find(profile_id, self.TARGET, "Mask")
        assert loaded.last_values == {"Y": "7"}
        assert store.find(profile_id, self.TARGET, "plain") is not None
        assert (
            store.remember_values(profile_id, self.OTHER_TARGET, "Mask", {})
            is None
        )

    def test_rename(self, store, profile_id):
        mask = QueryBookmark(
            "Mask",
            "SELECT * FROM t WHERE y = ${Y}",
            self.TARGET,
            (Placeholder("Y", PlaceholderType.INTEGER, default="1"),),
            {"Y": "7"},
        )
        store.add(profile_id, mask)
        store.add(profile_id, self.bookmark("Other"))
        store.add(profile_id, self.bookmark("Taken", target=self.OTHER_TARGET))
        renamed = store.rename(profile_id, self.TARGET, "mask", " New  name ")
        assert renamed.name == "New name"
        assert renamed.last_values == {"Y": "7"}
        names = [b.name for b in store.load(profile_id, self.TARGET)]
        assert names == ["New name", "Other"]
        # Only the bookmarks of the same target count.
        assert store.rename(profile_id, self.TARGET, "New name", "Taken")
        with pytest.raises(ConfigError):
            store.rename(profile_id, self.TARGET, "Taken", "other")
        with pytest.raises(ConfigError):
            store.rename(profile_id, self.TARGET, "Taken", "  ")
        assert store.rename(profile_id, self.TARGET, "missing", "X") is None
        # A change of case only is allowed.
        assert store.rename(profile_id, self.TARGET, "taken", "TAKEN")

    def test_import_bookmarks(self, store, profile_id):
        store.add(profile_id, self.bookmark("Users"))
        store.add(profile_id, self.bookmark("Users", target=self.OTHER_TARGET))
        incoming = [
            self.bookmark("users", "SELECT 2", target="-"),
            self.bookmark("Orders", target="-"),
        ]
        plan = store.import_bookmarks(
            profile_id, self.TARGET, incoming, NameConflict.REPLACE
        )
        assert plan.replaced == 1
        found = store.load(profile_id, self.TARGET)
        assert [(b.name, b.sql, b.target) for b in found] == [
            ("Orders", "SELECT 1", self.TARGET),
            ("users", "SELECT 2", self.TARGET),
        ]
        assert len(store.load(profile_id, self.OTHER_TARGET)) == 1

    def test_import_without_changes_does_not_write(self, store, profile_id):
        store.add(profile_id, self.bookmark("Users"))
        path = store.path_of(profile_id)
        before = path.stat().st_mtime_ns
        plan = store.import_bookmarks(
            profile_id, self.TARGET, [self.bookmark("Users")]
        )
        assert plan.unchanged == 1
        assert path.stat().st_mtime_ns == before

    def test_import_into_a_damaged_file_fails(self, store, profile_id):
        path = store.path_of(profile_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{", encoding="utf-8")
        with pytest.raises(ConfigError):
            store.import_bookmarks(
                profile_id, self.TARGET, [self.bookmark("A")]
            )
        assert path.read_text(encoding="utf-8") == "{"
