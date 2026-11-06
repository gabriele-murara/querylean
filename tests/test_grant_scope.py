"""Tests of the databases covered by one grant."""

import pytest

from querylean.database.privileges.grant_scope import GrantScope


class TestGrantScope:
    """Global grants, exact names, MySQL wildcards and escapes."""

    def test_global_covers_everything(self):
        scope = GrantScope(None, ("INSERT",))
        assert scope.covers("app") and scope.covers("anything")

    @pytest.mark.parametrize(
        ("pattern", "database", "covered"),
        [
            ("app", "app", True),
            ("app", "APP", True),  # never fewer databases than the server
            ("app", "app2", False),
            ("app%", "app2", True),
            ("app%", "ap", False),
            ("a_p", "axp", True),
            ("a\\_p", "a_p", True),
            ("a\\_p", "axp", False),
            ("a\\%", "a%", True),
            ("a\\%", "ab", False),
            ("my.db", "my.db", True),
            ("my.db", "myxdb", False),
            # Grant lines are whitespace-normalised: names must still match.
            ("a b", "a  b", True),
            ("a b", "a\tb", True),
            (" x", "  x", True),
            ("app ", "app ", True),
        ],
    )
    def test_patterns(self, pattern, database, covered):
        assert GrantScope(pattern, ("UPDATE",)).covers(database) is covered

    def test_value_object(self):
        assert GrantScope("a", ("X",)) == GrantScope("a", ("X",))
        assert GrantScope("a", ("X",)) != GrantScope("b", ("X",))
        assert len({GrantScope("a", ("X",)), GrantScope("a", ("X",))}) == 1
