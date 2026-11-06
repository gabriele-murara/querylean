"""Tests of MySQL string literal quoting."""

import pytest

from querylean.database.schema.mysql_literal import MySqlLiteral
from querylean.database.validation.read_only_validator import (
    ReadOnlyValidator,
)


class TestMySqlLiteral:
    """Quotes and backslashes are escaped; the result stays one string."""

    @pytest.mark.parametrize(
        ("value", "quoted"),
        [
            ("app", "'app'"),
            ("it's", "'it''s'"),
            ("a\\b", "'a\\\\b'"),
            ("\\'", "'\\\\'''"),
            ("", "''"),
        ],
    )
    def test_quote(self, value, quoted):
        assert MySqlLiteral.quote(value) == quoted

    @pytest.mark.parametrize("value", ["x' OR '1'='1", "a\\' ; DROP", "\\"])
    def test_injection_stays_inside_the_string(self, value):
        sql = "SELECT 1 FROM t WHERE c = {}".format(MySqlLiteral.quote(value))
        assert ReadOnlyValidator().validate(sql).ok
