"""Painting of the rows of the completion list."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from querylean.completion.completion_item import CompletionItem


class CompletionDelegate(QStyledItemDelegate):
    """Icon, name and, aligned on the right in a softer color, the detail
    (column type and table, "keyword", "function"…)."""

    ITEM_ROLE = Qt.ItemDataRole.UserRole
    __ICON = 16
    __PADDING = 6
    __GAP = 24

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        item = index.data(CompletionDelegate.ITEM_ROLE)
        if not isinstance(item, CompletionItem):
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.icon = type(opt.icon)()
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget
        )
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        palette = opt.palette
        rect = opt.rect.adjusted(CompletionDelegate.__PADDING, 0, 0, 0)
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        size = CompletionDelegate.__ICON
        if icon is not None:
            icon_rect = QRect(
                rect.left(),
                rect.top() + (rect.height() - size) // 2,
                size,
                size,
            )
            icon.paint(painter, icon_rect)
        text_rect = rect.adjusted(size + CompletionDelegate.__PADDING, 0, 0, 0)
        text_rect.setRight(opt.rect.right() - CompletionDelegate.__PADDING)
        metrics = opt.fontMetrics
        label_width = metrics.horizontalAdvance(item.label)
        painter.save()
        text_role = (
            QPalette.ColorRole.HighlightedText
            if selected
            else QPalette.ColorRole.Text
        )
        painter.setPen(palette.color(text_role))
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            metrics.elidedText(
                item.label, Qt.TextElideMode.ElideRight, text_rect.width()
            ),
        )
        detail_room = text_rect.width() - label_width - CompletionDelegate.__GAP
        if item.detail and detail_room > metrics.horizontalAdvance("…"):
            if not selected:
                painter.setPen(
                    palette.color(QPalette.ColorRole.PlaceholderText)
                )
            painter.drawText(
                text_rect,
                int(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
                ),
                metrics.elidedText(
                    item.detail, Qt.TextElideMode.ElideLeft, detail_room
                ),
            )
        painter.restore()

    def sizeHint(  # noqa: N802
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        item = index.data(CompletionDelegate.ITEM_ROLE)
        if not isinstance(item, CompletionItem):
            return super().sizeHint(option, index)
        metrics = option.fontMetrics
        width = (
            CompletionDelegate.__PADDING * 3
            + CompletionDelegate.__ICON
            + metrics.horizontalAdvance(item.label)
        )
        if item.detail:
            width += CompletionDelegate.__GAP + metrics.horizontalAdvance(
                item.detail
            )
        height = max(metrics.height() + 6, CompletionDelegate.__ICON + 4)
        return QSize(width, height)
