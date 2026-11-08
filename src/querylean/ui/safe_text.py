"""Text from the server or the user shown in widgets that render HTML."""

from __future__ import annotations

import html


class SafeText:
    """Qt shows tooltips (and labels in automatic mode) as rich text when
    the text looks like HTML. Names, comments, error messages and queries
    come from the server or the user, so they are escaped: markup in them
    is shown as typed and never rendered (no images, links or layout).
    ``one_line`` shortens such text for previews."""

    @staticmethod
    def tooltip(text: str) -> str:
        """``text`` as a tooltip that shows it literally, line breaks
        included."""
        return SafeText.html(text)

    @staticmethod
    def html(text: str) -> str:
        """``text`` as rich text that shows it literally, line breaks
        included, for widgets in automatic format (tooltips,
        ``QMessageBox``, ``QInputDialog`` labels). Always marked as rich
        text: escaped text alone (``a &amp; b``) could be taken as plain
        and shown with its entities."""
        escaped = html.escape(text).replace("\n", "<br>")
        return "<qt>{}</qt>".format(escaped)

    @staticmethod
    def one_line(text: str, limit: int) -> str:
        """``text`` on one line (whitespace runs collapsed), cut with "…"
        to at most ``limit`` characters: for previews of queries and
        values in menus, tables and labels."""
        single_line = " ".join(text.split())
        if len(single_line) <= limit:
            return single_line
        return "{}…".format(single_line[: limit - 1])
