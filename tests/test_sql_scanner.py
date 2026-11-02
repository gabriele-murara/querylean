"""Tests of the tolerant SQL scanner used by the completion."""

import pytest

from querylean.completion.scan_token import ScanToken
from querylean.completion.sql_scanner import SqlScanner


class TestSqlScanner:
    """Kinds, positions, unterminated tokens, MySQL comment rules."""

    @staticmethod
    def kinds(text):
        return [(t.kind, t.text) for t in SqlScanner.scan(text)]

    def test_words_symbols_and_quoted(self):
        assert self.kinds("SELECT u.id, `a b`.x FROM t") == [
            (ScanToken.WORD, "SELECT"),
            (ScanToken.WORD, "u"),
            (ScanToken.SYMBOL, "."),
            (ScanToken.WORD, "id"),
            (ScanToken.SYMBOL, ","),
            (ScanToken.QUOTED, "`a b`"),
            (ScanToken.SYMBOL, "."),
            (ScanToken.WORD, "x"),
            (ScanToken.WORD, "FROM"),
            (ScanToken.WORD, "t"),
        ]

    @pytest.mark.parametrize(
        ("text", "kind"),
        [
            ("'it''s'", ScanToken.STRING),
            ("'a\\'b'", ScanToken.STRING),
            ('"x"', ScanToken.STRING),
            ("-- note", ScanToken.COMMENT),
            ("# note", ScanToken.COMMENT),
            ("/* a */", ScanToken.COMMENT),
            ("42", ScanToken.NUMBER),
            ("1.5e+3", ScanToken.NUMBER),
            (".5", ScanToken.NUMBER),
            ("0x1F", ScanToken.NUMBER),
            ("1abc", ScanToken.WORD),
            ("@@session.x", ScanToken.VARIABLE),
            ("<=>", ScanToken.SYMBOL),
        ],
    )
    def test_single_tokens(self, text, kind):
        tokens = SqlScanner.scan(text)
        assert [(t.kind, t.text) for t in tokens] == [(kind, text)]

    def test_unterminated_tokens_run_to_the_end(self):
        for text in ("'abc", "`abc", "/* abc"):
            (token,) = SqlScanner.scan(text)
            assert not token.closed
            assert token.end == len(text)

    def test_line_comment_is_never_closed(self):
        (token, word) = SqlScanner.scan("-- c\nx")
        assert token.kind == ScanToken.COMMENT and not token.closed
        assert word.text == "x" and word.start == 5

    def test_dash_dash_without_space_is_not_a_comment(self):
        assert [t.text for t in SqlScanner.scan("1--1")] == ["1", "-", "-", "1"]

    def test_quoted_name(self):
        (token,) = SqlScanner.scan("`a``b`")
        assert token.name == "a`b"
        (token,) = SqlScanner.scan("`open")
        assert token.name == "open"

    def test_unicode_identifiers(self):
        assert self.kinds("città") == [(ScanToken.WORD, "città")]
