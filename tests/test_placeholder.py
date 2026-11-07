"""Tests of placeholder definitions."""

import pytest

from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_type import PlaceholderType


class TestPlaceholder:
    """Names, token, serialization of untrusted data."""

    @pytest.mark.parametrize(
        ("name", "valid"),
        [
            ("YEAR", True),
            ("import_date_time", True),
            ("_X1", True),
            ("1X", False),
            ("A-B", False),
            ("A B", False),
            ("", False),
            ("X" * 65, False),
        ],
    )
    def test_names(self, name, valid):
        assert Placeholder.is_valid_name(name) is valid

    def test_roundtrip_and_token(self):
        placeholder = Placeholder(
            "CODES",
            PlaceholderType.INTEGER,
            default="1, 2",
            description="Codici",
            is_list=True,
        )
        assert placeholder.token == "${CODES}"
        assert Placeholder.from_dict(placeholder.to_dict()) == placeholder

    @pytest.mark.parametrize(
        "data",
        [
            None,
            {"name": "1X", "type": "text"},
            {"name": "X", "type": "nope"},
            {"name": "X", "type": "text", "list": "yes"},
            {"name": "X", "type": "text", "default": 3},
            {"type": "text"},
        ],
    )
    def test_invalid_data(self, data):
        assert Placeholder.from_dict(data) is None
