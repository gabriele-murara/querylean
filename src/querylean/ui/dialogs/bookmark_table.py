"""Table of bookmarks with a check box per row."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.ui.icons.toolbar_icons import ToolbarIcons
from querylean.ui.safe_text import SafeText


class BookmarkTable(QTableWidget):
    """Read-only table of the export and import dialogs: column 0 holds the
    bookmark name with its icon and the check box of the row; a row added
    as not checkable has no check box and is greyed out. The text of every
    cell is plain (never HTML), tooltips go through ``SafeText.tooltip``.
    """

    QUERY_TYPE = "Query"
    MASK_TYPE = "Mask"
    NAME_COLUMN = 0
    __MAX_QUERY_TEXT = 80
    __READ_ONLY = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def __init__(
        self,
        columns: Sequence[str],
        rows: int,
        stretch: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(rows, len(columns), parent)
        self.setHorizontalHeaderLabels(list(columns))
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)

    @staticmethod
    def kind_text(bookmark: QueryBookmark) -> str:
        """``MASK_TYPE`` or ``QUERY_TYPE``."""
        if bookmark.is_mask:
            return BookmarkTable.MASK_TYPE
        return BookmarkTable.QUERY_TYPE

    def set_bookmark_row(
        self,
        row: int,
        bookmark: QueryBookmark,
        cells: Sequence[tuple[int, str, str]],
        *,
        checkable: bool = True,
    ) -> None:
        """Fill ``row``: the name (checked when ``checkable``) and the
        ``(column, text, tooltip)`` cells (empty tooltip: none)."""
        name = QTableWidgetItem(bookmark.name)
        name.setIcon(
            ToolbarIcons.mask() if bookmark.is_mask else ToolbarIcons.query()
        )
        if checkable:
            name.setFlags(
                BookmarkTable.__READ_ONLY | Qt.ItemFlag.ItemIsUserCheckable
            )
            name.setCheckState(Qt.CheckState.Checked)
        else:
            name.setFlags(Qt.ItemFlag.ItemIsSelectable)
        self.setItem(row, BookmarkTable.NAME_COLUMN, name)
        for column, text, tooltip in cells:
            self.set_text(row, column, text, tooltip, enabled=checkable)

    def set_text(
        self,
        row: int,
        column: int,
        text: str,
        tooltip: str = "",
        *,
        enabled: bool = True,
    ) -> None:
        """Read-only cell with ``text`` and the optional ``tooltip``."""
        item = QTableWidgetItem(text)
        item.setFlags(
            BookmarkTable.__READ_ONLY
            if enabled
            else Qt.ItemFlag.ItemIsSelectable
        )
        if tooltip:
            item.setToolTip(SafeText.tooltip(tooltip))
        self.setItem(row, column, item)

    @staticmethod
    def query_cell(
        column: int, bookmark: QueryBookmark
    ) -> tuple[int, str, str]:
        """Cell with the query on one line, in full in the tooltip."""
        text = SafeText.one_line(bookmark.sql, BookmarkTable.__MAX_QUERY_TEXT)
        return column, text, bookmark.sql

    @staticmethod
    def placeholders_text(bookmark: QueryBookmark) -> str:
        """``${A}, ${B}`` (empty for a plain query)."""
        return ", ".join(p.token for p in bookmark.placeholders)

    def is_checkable(self, row: int) -> bool:
        """True when ``row`` has a check box."""
        item = self.item(row, BookmarkTable.NAME_COLUMN)
        return bool(item.flags() & Qt.ItemFlag.ItemIsUserCheckable)

    def is_checked(self, row: int) -> bool:
        """True when ``row`` is checked."""
        item = self.item(row, BookmarkTable.NAME_COLUMN)
        return (
            self.is_checkable(row)
            and item.checkState() == Qt.CheckState.Checked
        )

    def set_checked(self, row: int, checked: bool) -> None:
        """Check or uncheck ``row`` (ignored without a check box)."""
        if self.is_checkable(row):
            self.item(row, BookmarkTable.NAME_COLUMN).setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )

    def set_visible_checked(self, checked: bool) -> None:
        """Check or uncheck every visible row."""
        for row in range(self.rowCount()):
            if not self.isRowHidden(row):
                self.set_checked(row, checked)

    def checked_rows(self) -> list[int]:
        """Checked rows, hidden ones included."""
        return [row for row in range(self.rowCount()) if self.is_checked(row)]

    def filter_rows(self, text: str, haystacks: Sequence[str]) -> None:
        """Hide the rows whose ``haystacks`` entry does not contain
        ``text`` (ignoring case and surrounding spaces)."""
        needle = text.strip().casefold()
        for row, haystack in enumerate(haystacks):
            shown = not needle or needle in haystack.casefold()
            self.setRowHidden(row, not shown)
