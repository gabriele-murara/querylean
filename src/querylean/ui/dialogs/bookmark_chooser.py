"""Filter, "Select all"/"Select none" and the table of bookmarks."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from querylean.ui.dialogs.bookmark_table import BookmarkTable


class BookmarkChooser(QWidget):
    """Part shared by the export and import dialogs: a filter field that
    hides the rows not containing its text (searched in the texts given
    to ``set_haystacks``, ignoring case), "Select all" and "Select none"
    acting on the visible rows, and the ``BookmarkTable``.

    ``changed`` is emitted when a check box or the visible rows change.
    """

    changed = Signal()

    # Format with the checked rows and all the rows.
    SELECTED = "{} of {} bookmarked queries selected."

    def __init__(
        self,
        columns: Sequence[str],
        rows: int,
        stretch: int,
        filter_hint: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.__haystacks: tuple[str, ...] = ()
        self.__filter = QLineEdit()
        self.__filter.setPlaceholderText(filter_hint)
        self.__filter.setClearButtonEnabled(True)
        self.__select_all = QPushButton("Select all")
        self.__select_none = QPushButton("Select none")
        self.__table = BookmarkTable(columns, rows, stretch)
        top = QHBoxLayout()
        top.addWidget(self.__filter, 1)
        top.addWidget(self.__select_all)
        top.addWidget(self.__select_none)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addWidget(self.__table, 1)

        self.__filter.textChanged.connect(self.apply_filter)
        self.__select_all.clicked.connect(
            lambda: self.__table.set_visible_checked(True)
        )
        self.__select_none.clicked.connect(
            lambda: self.__table.set_visible_checked(False)
        )
        self.__table.itemChanged.connect(lambda _item: self.changed.emit())

    @property
    def table(self) -> BookmarkTable:
        """One row per bookmark."""
        return self.__table

    @property
    def filter_edit(self) -> QLineEdit:
        """Text that the visible rows contain."""
        return self.__filter

    @property
    def select_all_button(self) -> QPushButton:
        """Checks the visible rows."""
        return self.__select_all

    @property
    def select_none_button(self) -> QPushButton:
        """Unchecks the visible rows."""
        return self.__select_none

    def set_haystacks(self, haystacks: Sequence[str]) -> None:
        """Text searched by the filter, one per row."""
        self.__haystacks = tuple(haystacks)
        self.apply_filter()

    def apply_filter(self, *_: object) -> None:
        """Hide the rows that do not contain the filter text."""
        self.__table.filter_rows(self.__filter.text(), self.__haystacks)
        self.changed.emit()
