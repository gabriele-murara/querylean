"""Menu of the "Bookmarked queries" toolbar button."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QWidget

from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.ui.safe_text import SafeText


class BookmarksMenu(QMenu):
    """One entry per bookmarked query of the current connection (a click
    runs it), then a "Delete" sub-menu. Without bookmarks a disabled entry
    explains how to add one.

    Signals carry the bookmark name; the menu holds no logic.
    """

    run_requested = Signal(str)
    delete_requested = Signal(str)

    TITLE = "Bookmarked queries"
    EMPTY_TEXT = "No bookmarked queries for this connection"
    DELETE_TEXT = "Delete"
    __MAX_TOOLTIP = 300

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(BookmarksMenu.TITLE, parent)
        self.setToolTipsVisible(True)
        self.__delete_menu: QMenu | None = None
        self.set_bookmarks([])

    @property
    def delete_menu(self) -> QMenu | None:
        """The "Delete" sub-menu (None without bookmarks)."""
        return self.__delete_menu

    def set_bookmarks(self, bookmarks: list[QueryBookmark]) -> None:
        """Rebuild the entries for ``bookmarks``."""
        self.clear()
        self.__delete_menu = None
        if not bookmarks:
            empty = self.addAction(BookmarksMenu.EMPTY_TEXT)
            empty.setEnabled(False)
            return
        for bookmark in bookmarks:
            entry = self.addAction(bookmark.name)
            entry.setToolTip(
                SafeText.tooltip(BookmarksMenu.__tooltip(bookmark.sql))
            )
            entry.triggered.connect(
                lambda _c=False, n=bookmark.name: self.run_requested.emit(n)
            )
        self.addSeparator()
        self.__delete_menu = self.addMenu(BookmarksMenu.DELETE_TEXT)
        for bookmark in bookmarks:
            entry = self.__delete_menu.addAction(bookmark.name)
            entry.triggered.connect(
                lambda _c=False, n=bookmark.name: self.delete_requested.emit(n)
            )

    def names(self) -> list[str]:
        """Names of the bookmarks offered, in menu order."""
        return [
            action.text()
            for action in self.actions()
            if action.isEnabled()
            and not action.isSeparator()
            and action.menu() is None
        ]

    @staticmethod
    def __tooltip(sql: str) -> str:
        text = " ".join(sql.split())
        limit = BookmarksMenu.__MAX_TOOLTIP
        if len(text) <= limit:
            return text
        return "{}…".format(text[: limit - 1])
