"""Read-only Qt model of a query result."""

from __future__ import annotations

import decimal
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QWidget

from querylean.ui.results.value_formatter import ValueFormatter
from querylean.ui.safe_text import SafeText


class ResultsModel(QAbstractTableModel):
    """Never editable table model that renders NULL distinctly from ''."""

    MAX_CELL_CHARS = 2000
    __NULL_COLOR = "#999999"
    __TOOLTIP_MIN_CHARS = 80
    # Default parent of rowCount/columnCount: the (invalid) root index.
    __ROOT = QModelIndex()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.__columns: list[str] = []
        self.__rows: list[tuple[Any, ...]] = []
        self.__null_font = QFont()
        self.__null_font.setItalic(True)

    @property
    def columns(self) -> list[str]:
        """Column names."""
        return list(self.__columns)

    def set_result(
        self, columns: list[str], rows: list[tuple[Any, ...]]
    ) -> None:
        """Replace the displayed result."""
        self.beginResetModel()
        self.__columns = list(columns)
        self.__rows = rows
        self.endResetModel()

    def clear(self) -> None:
        """Remove every row and column."""
        self.set_result([], [])

    def raw_value(self, row: int, column: int) -> Any:
        """Value as returned by the driver."""
        return self.__rows[row][column]

    def rowCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex = __ROOT,
    ) -> int:
        return 0 if parent.isValid() else len(self.__rows)

    def columnCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex = __ROOT,
    ) -> int:
        return 0 if parent.isValid() else len(self.__columns)

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return (
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        )  # never editable

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None
        value = self.__rows[index.row()][index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            if value is None:
                return ValueFormatter.NULL_TEXT
            text = ValueFormatter.format_value(value)
            limit = ResultsModel.MAX_CELL_CHARS
            if len(text) <= limit:
                return text
            return "{}…".format(text[:limit])
        if role == Qt.ItemDataRole.ToolTipRole and value is not None:
            text = ValueFormatter.format_value(value)
            if len(text) > ResultsModel.__TOOLTIP_MIN_CHARS:
                # Stored data: shown literally, never rendered as HTML.
                return SafeText.tooltip(text[: ResultsModel.MAX_CELL_CHARS])
            return None
        if value is None:
            if role == Qt.ItemDataRole.FontRole:
                return self.__null_font
            if role == Qt.ItemDataRole.ForegroundRole:
                return QColor(ResultsModel.__NULL_COLOR)
        if (
            role == Qt.ItemDataRole.TextAlignmentRole
            and isinstance(value, int | float | decimal.Decimal)
            and not isinstance(value, bool)
        ):
            return int(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return (
                self.__columns[section]
                if section < len(self.__columns)
                else None
            )
        return str(section + 1)
