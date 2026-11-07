"""Tests of the escaping of untrusted text shown as rich text."""

import pytest
from PySide6.QtGui import Qt, QTextDocument

from querylean.ui.safe_text import SafeText


class TestSafeText:
    """Markup is shown literally; line breaks are kept."""

    @pytest.mark.parametrize(
        ("text", "tooltip"),
        [
            ("plain", "<qt>plain</qt>"),
            ("<b>x</b>", "<qt>&lt;b&gt;x&lt;/b&gt;</qt>"),
            ("a & b", "<qt>a &amp; b</qt>"),
            ("one\ntwo", "<qt>one<br>two</qt>"),
            ('it\'s "q"', "<qt>it&#x27;s &quot;q&quot;</qt>"),
        ],
    )
    def test_tooltip(self, text, tooltip):
        assert SafeText.tooltip(text) == tooltip

    @pytest.mark.parametrize(
        "text",
        ["Tom's & co", "a<b", "<img src='x'>", "one\ntwo", "plain"],
    )
    def test_html_is_always_rich_and_shows_the_text(self, text):
        result = SafeText.html(text)
        # Never taken as plain text: entities are always decoded.
        assert Qt.mightBeRichText(result)
        document = QTextDocument()
        document.setHtml(result)
        # <br> comes back as a line separator.
        shown = document.toPlainText().replace(chr(0x2028), chr(10))
        assert shown == text
