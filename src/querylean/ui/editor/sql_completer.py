"""Popup list of the autocompletion proposals."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRect, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QCompleter, QWidget

from querylean.completion.completion_item import CompletionItem
from querylean.ui.editor.completion_delegate import CompletionDelegate
from querylean.ui.icons.completion_icons import CompletionIcons
from querylean.ui.safe_text import SafeText


class SqlCompleter(QCompleter):
    """Shows ranked proposals below the cursor.

    The list is filled already filtered and ordered by the completion
    engine (``UnfilteredPopupCompletion``); the editor handles the keys
    that accept or dismiss a proposal, while arrows and page keys move in
    the list. A mouse click emits ``item_chosen``.
    """

    item_chosen = Signal(object)  # CompletionItem

    MAX_VISIBLE = 12
    MIN_WIDTH = 260
    MAX_WIDTH = 640

    def __init__(self, widget: QWidget) -> None:
        super().__init__(widget)
        self.__model = QStandardItemModel(self)
        self.__items: tuple[CompletionItem, ...] = ()
        self.setModel(self.__model)
        self.setWidget(widget)
        self.setCompletionMode(
            QCompleter.CompletionMode.UnfilteredPopupCompletion
        )
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setMaxVisibleItems(SqlCompleter.MAX_VISIBLE)
        popup = self.popup()
        popup.setItemDelegate(CompletionDelegate(popup))
        popup.setUniformItemSizes(True)
        popup.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        popup.setObjectName("completion-popup")
        popup.clicked.connect(self.__on_clicked)

    @property
    def items(self) -> tuple[CompletionItem, ...]:
        """Proposals in the list."""
        return self.__items

    @property
    def visible(self) -> bool:
        """True while the list is shown."""
        return self.popup().isVisible()

    def show_items(
        self, items: tuple[CompletionItem, ...], rect: QRect
    ) -> None:
        """Fill the list with ``items``, select the first one and show it
        under ``rect`` (widget coordinates)."""
        self.__items = tuple(items)
        self.__model.clear()
        for item in self.__items:
            row = QStandardItem(item.label)
            row.setData(item, CompletionDelegate.ITEM_ROLE)
            row.setData(
                CompletionIcons.icon(item.kind), Qt.ItemDataRole.DecorationRole
            )
            if item.tooltip:
                row.setToolTip(SafeText.tooltip(item.tooltip))
            row.setEditable(False)
            self.__model.appendRow(row)
        popup = self.popup()
        width = popup.sizeHintForColumn(0)
        width += popup.verticalScrollBar().sizeHint().width() + 8
        width = min(max(width, SqlCompleter.MIN_WIDTH), SqlCompleter.MAX_WIDTH)
        area = QRect(rect)
        area.setWidth(width)
        self.complete(area)
        if self.__model.rowCount():
            popup.setCurrentIndex(self.__model.index(0, 0))

    def current_item(self) -> CompletionItem | None:
        """Selected proposal, if any."""
        index = self.popup().currentIndex()
        if not index.isValid() or not self.popup().isVisible():
            return None
        item = index.data(CompletionDelegate.ITEM_ROLE)
        return item if isinstance(item, CompletionItem) else None

    def select(self, row: int) -> None:
        """Select the proposal at ``row``."""
        index = self.__model.index(row, 0)
        if index.isValid():
            self.popup().setCurrentIndex(index)

    def hide_popup(self) -> None:
        """Close the list."""
        self.popup().hide()

    def __on_clicked(self, index: QModelIndex) -> None:
        item = index.data(CompletionDelegate.ITEM_ROLE)
        if isinstance(item, CompletionItem):
            self.item_chosen.emit(item)
