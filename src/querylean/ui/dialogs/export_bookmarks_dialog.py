"""Dialog to choose the bookmarked queries to export."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from querylean.bookmarks.bookmark_entry import BookmarkEntry
from querylean.ui.dialogs.bookmark_chooser import BookmarkChooser
from querylean.ui.dialogs.bookmark_table import BookmarkTable
from querylean.ui.dialogs.status_label import StatusLabel


class ExportBookmarksDialog(QDialog):
    """Every bookmarked query and mask of the saved connections, one per
    row with what tells them apart: name, type (query or mask with its
    placeholders), connection, target ``user@host:port/database`` and
    the query on one line (in full in the tooltip). The connection only
    helps to choose: it is not part of the exported file.

    Rows are checked to be exported (all at first); the filter hides the
    rows that do not contain its text, "Select all"/"Select none" act on
    the visible rows only. "Export…" stays disabled until a row is
    checked. The last values of masks are left out unless requested.
    """

    TITLE = "Export bookmarked queries"
    QUERY_TYPE = BookmarkTable.QUERY_TYPE
    MASK_TYPE = BookmarkTable.MASK_TYPE
    __COLUMNS = (
        "Name",
        "Type",
        "Connection",
        "Target",
        "Placeholders",
        "Query",
    )
    __TYPE, __CONNECTION, __TARGET, __PLACEHOLDERS, __QUERY = range(1, 6)

    def __init__(
        self, entries: Iterable[BookmarkEntry], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(ExportBookmarksDialog.TITLE)
        self.setMinimumSize(820, 420)
        self.__entries = tuple(entries)

        text = "Choose the bookmarked queries to save in a JSON file. "
        text += "Only queries and masks are exported: no connection "
        text += "details or passwords, so they can be shared and run "
        text += "elsewhere with other credentials."
        intro = QLabel(text)
        intro.setTextFormat(Qt.TextFormat.PlainText)
        intro.setWordWrap(True)

        self.__chooser = BookmarkChooser(
            ExportBookmarksDialog.__COLUMNS,
            len(self.__entries),
            ExportBookmarksDialog.__QUERY,
            "Filter by name, connection, target or query",
        )
        self.__table = self.__chooser.table
        for row, entry in enumerate(self.__entries):
            self.__add_row(row, entry)
        self.__chooser.set_haystacks(
            [ExportBookmarksDialog.__haystack(e) for e in self.__entries]
        )

        self.__last_values = QCheckBox("Include the last values used in masks")
        self.__last_values.setToolTip(
            "The values a mask was last run with may be real data"
        )
        self.__status = StatusLabel()

        buttons = QDialogButtonBox()
        self.__export_button: QPushButton = buttons.addButton(
            "Export…", QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.__chooser, 1)
        layout.addWidget(self.__last_values)
        layout.addWidget(self.__status)
        layout.addWidget(buttons)

        self.__chooser.changed.connect(self.refresh)
        self.refresh()

    # -------------------------------------------------------------- widgets
    @property
    def table(self) -> BookmarkTable:
        """One row per bookmark."""
        return self.__table

    @property
    def filter_edit(self) -> QLineEdit:
        """Text that the visible rows contain."""
        return self.__chooser.filter_edit

    @property
    def select_all_button(self) -> QPushButton:
        """Checks the visible rows."""
        return self.__chooser.select_all_button

    @property
    def select_none_button(self) -> QPushButton:
        """Unchecks the visible rows."""
        return self.__chooser.select_none_button

    @property
    def last_values_box(self) -> QCheckBox:
        """Whether the last values of masks are exported."""
        return self.__last_values

    @property
    def status(self) -> StatusLabel:
        """How many bookmarks are checked."""
        return self.__status

    @property
    def export_button(self) -> QPushButton:
        """ "Export…" button."""
        return self.__export_button

    # --------------------------------------------------------------- values
    @property
    def entries(self) -> tuple[BookmarkEntry, ...]:
        """Every listed bookmark, in row order."""
        return self.__entries

    def set_checked(self, row: int, checked: bool) -> None:
        """Choose ``row`` for the export, or not."""
        self.__table.set_checked(row, checked)

    def selected(self) -> list[BookmarkEntry]:
        """Checked bookmarks, in row order (hidden rows included)."""
        return [self.__entries[row] for row in self.__table.checked_rows()]

    def include_last_values(self) -> bool:
        """True when the last values of masks are exported too."""
        return self.__last_values.isChecked()

    def refresh(self, *_: object) -> None:
        """Count the checked rows and enable "Export…"."""
        checked = len(self.selected())
        self.__status.show_neutral(
            BookmarkChooser.SELECTED.format(checked, len(self.__entries))
        )
        self.__export_button.setEnabled(checked > 0)

    def accept(self) -> None:
        """Close with ``Accepted`` only when a bookmark is checked."""
        if self.selected():
            super().accept()

    # ------------------------------------------------------------ internals
    def __add_row(self, row: int, entry: BookmarkEntry) -> None:
        bookmark = entry.bookmark
        self.__table.set_bookmark_row(
            row,
            bookmark,
            (
                (
                    ExportBookmarksDialog.__TYPE,
                    BookmarkTable.kind_text(bookmark),
                    "",
                ),
                (
                    ExportBookmarksDialog.__CONNECTION,
                    entry.profile.display_name,
                    entry.profile.config.default_name(),
                ),
                (ExportBookmarksDialog.__TARGET, bookmark.target, ""),
                (
                    ExportBookmarksDialog.__PLACEHOLDERS,
                    BookmarkTable.placeholders_text(bookmark),
                    "",
                ),
                BookmarkTable.query_cell(
                    ExportBookmarksDialog.__QUERY, bookmark
                ),
            ),
        )

    @staticmethod
    def __haystack(entry: BookmarkEntry) -> str:
        """Text searched by the filter."""
        bookmark = entry.bookmark
        parts = (
            bookmark.name,
            entry.profile.display_name,
            bookmark.target,
            bookmark.sql,
        )
        return "\n".join(parts)
