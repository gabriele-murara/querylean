"""Tests of the escaping of untrusted text shown as rich text."""

import pytest

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
