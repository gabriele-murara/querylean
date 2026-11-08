"""Tests of how imported bookmarks join the saved ones."""

from querylean.bookmarks.bookmark_import_plan import BookmarkImportPlan
from querylean.bookmarks.name_conflict import NameConflict
from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.query_bookmark import QueryBookmark


class TestBookmarkImportPlan:
    """New, already saved, renamed, replaced and skipped bookmarks."""

    TARGET = "ro@db:3306/app"

    def bookmark(self, name, sql="SELECT 1") -> QueryBookmark:
        return QueryBookmark(name, sql, self.TARGET)

    def names(self, plan) -> list[str]:
        return [b.name for b in plan.bookmarks]

    def test_free_names_are_added(self):
        plan = BookmarkImportPlan(
            [self.bookmark("A")], [self.bookmark("B")], NameConflict.SKIP
        )
        assert self.names(plan) == ["A", "B"]
        assert plan.changed

    def test_identical_bookmarks_are_unchanged(self):
        plan = BookmarkImportPlan(
            [self.bookmark("Users")], [self.bookmark("users")]
        )
        assert plan.unchanged == 1
        assert not plan.changed
        assert self.names(plan) == ["Users"]

    def test_rename(self):
        existing = [self.bookmark("Users"), self.bookmark("Users (2)")]
        plan = BookmarkImportPlan(
            existing, [self.bookmark("users", "SELECT 2")]
        )
        assert plan.renamed == (("users", "users (3)"),)
        assert plan.added[0].sql == "SELECT 2"

    def test_replace_keeps_the_last_values(self):
        placeholder = Placeholder("V", default="1")
        saved = QueryBookmark(
            "Mask", "SELECT ${V}", self.TARGET, (placeholder,), {"V": "7"}
        )
        new = QueryBookmark(
            "mask", "SELECT ${V} + 1", self.TARGET, (placeholder,)
        )
        plan = BookmarkImportPlan(
            [saved, self.bookmark("B")], [new], NameConflict.REPLACE
        )
        assert plan.replaced == 1
        assert self.names(plan) == ["B", "mask"]
        assert plan.added[0].last_values == {"V": "7"}

    def test_skip(self):
        plan = BookmarkImportPlan(
            [self.bookmark("A")],
            [self.bookmark("a", "SELECT 2")],
            NameConflict.SKIP,
        )
        assert plan.skipped == 1
        assert not plan.changed

    def test_same_names_in_one_import_are_renamed(self):
        incoming = [
            self.bookmark("Users", "SELECT 1"),
            self.bookmark("Users", "SELECT 2"),
            self.bookmark("Users", "SELECT 1"),
        ]
        for conflict in NameConflict:
            plan = BookmarkImportPlan([], incoming, conflict)
            assert self.names(plan) == ["Users", "Users (2)"]
            assert plan.unchanged == 1

    def test_free_name_fits_the_limit(self):
        long = "x" * QueryBookmark.MAX_NAME_LENGTH
        name = BookmarkImportPlan.free_name(long, [long])
        assert len(name) == QueryBookmark.MAX_NAME_LENGTH
        assert name.endswith("x (2)")
        assert BookmarkImportPlan.free_name("A", ["b"]) == "A"

    def test_status(self):
        saved = [self.bookmark("Users")]
        status = BookmarkImportPlan.status
        assert status(saved, self.bookmark("USERS")) == BookmarkImportPlan.SAVED
        assert status(saved, self.bookmark("users", "SELECT 2")) == (
            BookmarkImportPlan.NAME_TAKEN
        )
        assert status(saved, self.bookmark("New")) == BookmarkImportPlan.NEW
        assert NameConflict.RENAME.label
