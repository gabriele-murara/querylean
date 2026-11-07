"""Tests of the bookmarked query value object."""

import pytest

from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_type import PlaceholderType
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.connection_config import ConnectionConfig


class TestQueryBookmark:
    """Target, names and parsing of untrusted data."""

    def test_target_of_a_configuration(self):
        config = ConnectionConfig(
            host="db", port=3307, database="app", username="ro"
        )
        assert QueryBookmark.target_of(config) == "ro@db:3307/app"

    def test_target_ignores_name_and_limits(self):
        base = ConnectionConfig(host="db", database="app", username="ro")
        other = base.copy()
        other.name = "Production"
        other.row_limit = 50
        other.caution_databases = ["app"]
        assert QueryBookmark.target_of(base) == QueryBookmark.target_of(other)

    def test_target_of_all_databases_ignores_the_active_one(self):
        base = ConnectionConfig(host="db", username="ro", all_databases=True)
        other = base.copy()
        other.database = "shop"
        assert QueryBookmark.target_of(base) == "ro@db:3306/*"
        assert QueryBookmark.target_of(base) == QueryBookmark.target_of(other)

    @pytest.mark.parametrize(
        "change",
        [
            {"host": "db2"},
            {"port": 3308},
            {"database": "other"},
            {"username": "rw"},
        ],
    )
    def test_target_changes_with_the_database(self, change):
        base = ConnectionConfig(host="db", database="app", username="ro")
        other = base.copy()
        for name, value in change.items():
            setattr(other, name, value)
        assert QueryBookmark.target_of(base) != QueryBookmark.target_of(other)

    def test_names(self):
        bookmark = QueryBookmark("Daily users", "SELECT 1", "t")
        assert QueryBookmark.clean_name("  Daily \n users ") == "Daily users"
        assert bookmark.same_name(" daily   USERS ")
        assert not bookmark.same_name("Daily")

    def test_roundtrip(self):
        bookmark = QueryBookmark("Users", "SELECT *\nFROM users", "ro@db:1/a")
        assert QueryBookmark.from_dict(bookmark.to_dict()) == bookmark

    @pytest.mark.parametrize(
        "data",
        [
            None,
            [],
            {},
            {"name": "a", "sql": "SELECT 1"},
            {"name": "", "sql": "SELECT 1", "target": "t"},
            {"name": "   ", "sql": "SELECT 1", "target": "t"},
            {"name": "a", "sql": "", "target": "t"},
            {"name": "a", "sql": 1, "target": "t"},
            {"name": "x" * 101, "sql": "SELECT 1", "target": "t"},
        ],
    )
    def test_invalid_data_is_ignored(self, data):
        assert QueryBookmark.from_dict(data) is None

    MASK_SQL = "SELECT * FROM orders WHERE year = ${YEAR} AND c IN (${C})"

    def test_mask_roundtrip(self):
        mask = QueryBookmark(
            "Orders",
            self.MASK_SQL,
            "t",
            (
                Placeholder("YEAR", PlaceholderType.INTEGER, default="2026"),
                Placeholder("C", is_list=True, description="Codes"),
            ),
        )
        assert mask.is_mask
        assert QueryBookmark.from_dict(mask.to_dict()) == mask
        plain = QueryBookmark("Users", "SELECT 1", "t")
        assert not plain.is_mask
        assert "placeholders" not in plain.to_dict()

    @pytest.mark.parametrize(
        "placeholders",
        [
            [],  # placeholders of the text not defined
            [{"name": "YEAR", "type": "integer"}],  # C missing
            [
                {"name": "YEAR", "type": "integer"},
                {"name": "C", "type": "text"},
                {"name": "EXTRA", "type": "text"},
            ],
            [{"name": "YEAR", "type": "nope"}, {"name": "C", "type": "text"}],
            "not a list",
        ],
    )
    def test_inconsistent_masks_are_ignored(self, placeholders):
        data = {
            "name": "Orders",
            "sql": self.MASK_SQL,
            "target": "t",
            "placeholders": placeholders,
        }
        assert QueryBookmark.from_dict(data) is None
