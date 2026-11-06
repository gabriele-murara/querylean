"""Text from the server or the user shown in widgets that render HTML."""

from __future__ import annotations

import html


class SafeText:
    """Qt shows tooltips (and labels in automatic mode) as rich text when
    the text looks like HTML. Names, comments, error messages and queries
    come from the server or the user, so they are escaped: markup in them
    is shown as typed and never rendered (no images, links or layout)."""

    @staticmethod
    def tooltip(text: str) -> str:
        """``text`` as a tooltip that shows it literally, line breaks
        included."""
        escaped = html.escape(text).replace("\n", "<br>")
        return "<qt>{}</qt>".format(escaped)
