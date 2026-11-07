"""Tests of mask parsing, compilation and placeholder creation."""

import pytest

from querylean.bookmarks.mask_error import MaskError
from querylean.bookmarks.mask_template import MaskTemplate
from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_type import PlaceholderType
from querylean.completion.sql_scanner import SqlScanner
from querylean.database.validation.read_only_validator import (
    ReadOnlyValidator,
)


class TestMaskTemplate:
    """Placeholders in and out of strings, typed values, injections."""

    SQL = "SELECT * FROM calls WHERE cli = '${DIGITS}' "
    SQL += "AND at >= '${WHEN}' AND code IN (${CODES}) "
    SQL += "AND year = ${YEAR} AND note = ${NOTE} -- ${IGNORED}"
    PLACEHOLDERS = {
        "DIGITS": Placeholder("DIGITS"),
        "WHEN": Placeholder("WHEN", PlaceholderType.DATETIME),
        "CODES": Placeholder("CODES", PlaceholderType.INTEGER, is_list=True),
        "YEAR": Placeholder("YEAR", PlaceholderType.INTEGER),
        "NOTE": Placeholder("NOTE"),
    }
    BENIGN = {
        "DIGITS": "339",
        "WHEN": "2026-11-03 10:00",
        "CODES": "1, 2",
        "YEAR": "2026",
        "NOTE": "ok",
    }

    def compile(self, **values):
        return MaskTemplate(self.SQL).compile(
            self.PLACEHOLDERS, {**self.BENIGN, **values}
        )

    @staticmethod
    def shape(sql):
        """Kinds of the tokens: the structure of a query."""
        return [t.kind for t in SqlScanner.scan(sql)]

    def test_parse(self):
        template = MaskTemplate(self.SQL)
        assert template.names == ("DIGITS", "WHEN", "CODES", "YEAR", "NOTE")
        assert [o.quote for o in template.occurrences] == ["'", "'", "", "", ""]

    def test_compile(self):
        expected = "SELECT * FROM calls WHERE cli = '339' AND at >= "
        expected += "'2026-11-03 10:00:00' AND code IN (1, 2) AND year = 2026 "
        expected += "AND note = 'ok' -- ${IGNORED}"
        assert self.compile() == expected

    def test_same_name_twice_takes_one_value(self):
        template = MaskTemplate("SELECT ${A} + ${A}")
        assert template.names == ("A",)
        compiled = template.compile(
            {"A": Placeholder("A", PlaceholderType.INTEGER)}, {"A": "2"}
        )
        assert compiled == "SELECT 2 + 2"

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("DIGITS", "x' OR 'a'='a"),
            ("DIGITS", "x\\' OR 1=1 -- "),
            ("DIGITS", "'; DROP TABLE calls; --"),
            ("NOTE", "x' UNION SELECT password FROM users -- "),
            ("NOTE", "\\"),
            ("CODES", "1, 2"),
        ],
    )
    def test_values_never_change_the_structure(self, name, value):
        compiled = self.compile(**{name: value})
        assert self.shape(compiled) == self.shape(self.compile())
        assert ReadOnlyValidator().validate(compiled).ok

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("YEAR", "2026 OR 1=1"),
            ("YEAR", "2026; DROP TABLE x"),
            ("CODES", "1, 2) OR (1=1"),
            ("WHEN", "2026-11-03' OR '1'='1"),
            ("YEAR", ""),
            ("CODES", " , "),
        ],
    )
    def test_invalid_values_are_refused(self, name, value):
        with pytest.raises(MaskError) as info:
            self.compile(**{name: value})
        assert "${{{}}}".format(name) in info.value.message

    def test_list_values_one_per_line(self):
        template = MaskTemplate("SELECT * FROM t WHERE c IN (${C})")
        placeholders = {"C": Placeholder("C", is_list=True)}
        compiled = template.compile(placeholders, {"C": "a, b\nc"})
        assert compiled.endswith("IN ('a, b', 'c')")

    def test_list_inside_quotes_is_refused(self):
        template = MaskTemplate("SELECT * FROM t WHERE c = '${C}'")
        with pytest.raises(MaskError):
            template.compile(
                {"C": Placeholder("C", is_list=True)}, {"C": "a, b"}
            )

    def test_undefined_placeholder(self):
        with pytest.raises(MaskError):
            MaskTemplate("SELECT ${X}").compile({}, {"X": "1"})

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT `${COL}` FROM t",
            "SELECT ${1X}",
            "SELECT ${}",
            "SELECT ${A B}",
            "SELECT '${bad-name}'",
        ],
    )
    def test_invalid_masks(self, sql):
        with pytest.raises(MaskError):
            MaskTemplate(sql)
        assert MaskTemplate.has_placeholders(sql)

    def test_comments_are_ignored(self):
        assert MaskTemplate("SELECT 1 /* ${X} */ # ${Y}").names == ()
        assert not MaskTemplate.has_placeholders("SELECT 1 -- ${X}")
        assert not MaskTemplate.has_placeholders("SELECT 1")

    @pytest.mark.parametrize(
        ("selected", "kind", "default", "is_list", "result"),
        [
            (
                "3391234567",
                PlaceholderType.TEXT,
                "3391234567",
                False,
                "cli = '${P}'",
            ),
            ("2026", PlaceholderType.INTEGER, "2026", False, "y = ${P}"),
            (
                "'2026-11-03 10:00:00'",
                PlaceholderType.DATETIME,
                "2026-11-03 10:00:00",
                False,
                "d = ${P}",
            ),
            (
                "1, 2, 3",
                PlaceholderType.INTEGER,
                "1, 2, 3",
                True,
                "c IN (${P})",
            ),
            ("'a', 'b'", PlaceholderType.TEXT, "a, b", True, "t IN (${P})"),
            ("it''s", PlaceholderType.TEXT, "it's", False, "n = '${P}'"),
        ],
    )
    def test_make_placeholder(self, selected, kind, default, is_list, result):
        sql = "SELECT * FROM t WHERE cli = '3391234567' AND y = 2026 "
        sql += "AND d = '2026-11-03 10:00:00' AND c IN (1, 2, 3) "
        sql += "AND t IN ('a', 'b') AND n = 'it''s'"
        start = sql.index(selected)
        new_sql, placeholder = MaskTemplate.make_placeholder(
            sql, start, start + len(selected), "P"
        )
        assert result in new_sql
        assert placeholder.kind is kind
        assert placeholder.default == default
        assert placeholder.is_list is is_list
        # The mask compiled with the example gives back the query.
        compiled = MaskTemplate(new_sql).compile(
            {"P": placeholder}, {"P": placeholder.default}
        )
        assert ReadOnlyValidator().validate(compiled).ok

    def test_selection_with_spaces_is_trimmed(self):
        sql = "SELECT * FROM t WHERE y =  2026 "
        new_sql, _ = MaskTemplate.make_placeholder(sql, 26, 32, "Y")
        assert new_sql == "SELECT * FROM t WHERE y =  ${Y} "

    @pytest.mark.parametrize(
        ("selected", "name"),
        [
            ("cli", "P"),
            ("FROM t", "P"),
            ("2026", "1BAD"),
            ("tab", "P"),
            ("note", "P"),
        ],
    )
    def test_make_placeholder_refuses_non_values(self, selected, name):
        sql = "SELECT * FROM t WHERE cli = 1 AND y = 2026 AND `tab`.x = 1 "
        sql += "-- note"
        start = sql.index(selected)
        with pytest.raises(MaskError):
            MaskTemplate.make_placeholder(
                sql, start, start + len(selected), name
            )

    def test_empty_selection_is_refused(self):
        with pytest.raises(MaskError):
            MaskTemplate.make_placeholder("SELECT 1", 3, 3, "P")
