"""Page buttons of the result table."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget


class ResultsPager(QWidget):
    """ "«", "‹", "Page N of M", "›" and "»" to move between the pages of
    a result. Hidden while there is a single page; ``show_counting`` shows
    it, without buttons, while the rows are counted.

    ``page_changed`` is emitted with the new page (from 0) when the user
    or ``set_page`` moves to another page; ``set_page_count`` (back to the
    first page) and ``show_page`` do not emit it.
    """

    page_changed = Signal(int)

    __TEXT = "Page {} of {}"
    COUNTING = "Counting the rows…"
    __ROWS = "{:,} rows"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("results-pager")
        self.__page = 0
        self.__count = 1
        self.__first = ResultsPager.__button("«", "First page")
        self.__previous = ResultsPager.__button("‹", "Previous page")
        self.__next = ResultsPager.__button("›", "Next page")
        self.__last = ResultsPager.__button("»", "Last page")
        self.__label = QLabel()
        self.__label.setTextFormat(Qt.TextFormat.PlainText)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.__first)
        layout.addWidget(self.__previous)
        layout.addWidget(self.__label)
        layout.addWidget(self.__next)
        layout.addWidget(self.__last)
        self.__first.clicked.connect(lambda: self.set_page(0))
        self.__previous.clicked.connect(lambda: self.set_page(self.__page - 1))
        self.__next.clicked.connect(lambda: self.set_page(self.__page + 1))
        self.__last.clicked.connect(lambda: self.set_page(self.__count - 1))
        self.__update()
        self.hide()

    @property
    def page(self) -> int:
        """Current page, from 0."""
        return self.__page

    @property
    def page_count(self) -> int:
        """Number of pages (at least 1)."""
        return self.__count

    @property
    def label(self) -> QLabel:
        """ "Page N of M"."""
        return self.__label

    @property
    def first_button(self) -> QToolButton:
        """Goes to the first page."""
        return self.__first

    @property
    def previous_button(self) -> QToolButton:
        """Goes to the previous page."""
        return self.__previous

    @property
    def next_button(self) -> QToolButton:
        """Goes to the next page."""
        return self.__next

    @property
    def last_button(self) -> QToolButton:
        """Goes to the last page."""
        return self.__last

    def set_page_count(self, count: int, rows: int | None = None) -> None:
        """Show ``count`` pages from the first one (``rows`` in all, in the
        tooltip); hidden with one page."""
        self.__count = max(count, 1)
        self.__page = 0
        self.__label.setToolTip(
            ResultsPager.__ROWS.format(rows) if rows is not None else ""
        )
        self.__update()
        self.setVisible(self.__count > 1)

    def show_counting(self) -> None:
        """Show that the rows are being counted, without buttons."""
        self.__count = 1
        self.__page = 0
        self.__label.setToolTip("")
        self.__update()
        self.__label.setText(ResultsPager.COUNTING)
        self.show()

    def set_page(self, page: int) -> None:
        """Move to ``page`` (kept within the pages)."""
        page = self.__bounded(page)
        if page == self.__page:
            return
        self.__page = page
        self.__update()
        self.page_changed.emit(page)

    def show_page(self, page: int) -> None:
        """Mark ``page`` as the current one without emitting
        ``page_changed`` (e.g. back to it when another could not be
        read)."""
        self.__page = self.__bounded(page)
        self.__update()

    def __bounded(self, page: int) -> int:
        return min(max(page, 0), self.__count - 1)

    def __update(self) -> None:
        self.__label.setText(
            ResultsPager.__TEXT.format(
                "{:,}".format(self.__page + 1), "{:,}".format(self.__count)
            )
        )
        at_start = self.__page == 0
        at_end = self.__page >= self.__count - 1
        self.__first.setEnabled(not at_start)
        self.__previous.setEnabled(not at_start)
        self.__next.setEnabled(not at_end)
        self.__last.setEnabled(not at_end)

    @staticmethod
    def __button(text: str, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        return button
