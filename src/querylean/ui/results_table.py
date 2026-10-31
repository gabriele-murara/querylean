"""Tabella dei risultati in sola lettura, con copia in formato tabulato."""

from __future__ import annotations

import datetime as dt
import decimal
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QAction, QColor, QFont, QGuiApplication, QKeySequence
from PySide6.QtWidgets import QAbstractItemView, QMenu, QTableView, QWidget

NULL_TEXT = "NULL"
MAX_BINARY_PREVIEW = 64
MAX_CELL_CHARS = 2000

_Index = QModelIndex | QPersistentModelIndex


def format_value(value: Any) -> str:
    """Rappresentazione testuale di un valore (NULL escluso)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, bytes | bytearray):
        data = bytes(value)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            preview = data[:MAX_BINARY_PREVIEW].hex()
            return f"0x{preview}{'…' if len(data) > MAX_BINARY_PREVIEW else ''}"
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat(sep=" ") if isinstance(value, dt.datetime) else value.isoformat()
    if isinstance(value, dt.timedelta):  # colonne TIME
        total = int(value.total_seconds())
        sign = "-" if total < 0 else ""
        total = abs(total)
        return f"{sign}{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"
    if isinstance(value, decimal.Decimal):
        return format(value, "f")
    if isinstance(value, set):
        return ",".join(sorted(str(v) for v in value))
    return str(value)


def copy_text(value: Any) -> str:
    """Valore per la copia tabulata: NULL diventa cella vuota, tab e a capo spazi."""
    if value is None:
        return ""
    text = format_value(value)
    return text.replace("\t", " ").replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


class ResultsModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._columns: list[str] = []
        self._rows: list[tuple[Any, ...]] = []
        self._null_font = QFont()
        self._null_font.setItalic(True)

    def set_result(self, columns: list[str], rows: list[tuple[Any, ...]]) -> None:
        self.beginResetModel()
        self._columns = list(columns)
        self._rows = rows
        self.endResetModel()

    def clear(self) -> None:
        self.set_result([], [])

    @property
    def columns(self) -> list[str]:
        return self._columns

    def raw_value(self, row: int, column: int) -> Any:
        return self._rows[row][column]

    def rowCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._columns)

    def flags(self, index: _Index) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable  # mai editabile

    def data(self, index: _Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        value = self._rows[index.row()][index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            if value is None:
                return NULL_TEXT
            text = format_value(value)
            return text if len(text) <= MAX_CELL_CHARS else text[:MAX_CELL_CHARS] + "…"
        if role == Qt.ItemDataRole.ToolTipRole and value is not None:
            text = format_value(value)
            return text[:MAX_CELL_CHARS] if len(text) > 80 else None
        if value is None:
            if role == Qt.ItemDataRole.FontRole:
                return self._null_font
            if role == Qt.ItemDataRole.ForegroundRole:
                return QColor("#999999")
        if role == Qt.ItemDataRole.TextAlignmentRole and isinstance(
            value, int | float | decimal.Decimal
        ) and not isinstance(value, bool):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._columns[section] if section < len(self._columns) else None
        return str(section + 1)


class ResultsTable(QTableView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.results_model = ResultsModel(self)
        self.setModel(self.results_model)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionsMovable(False)
        self.verticalHeader().setDefaultSectionSize(self.fontMetrics().height() + 6)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

        self.copy_action = QAction("Copia", self)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.copy_action.triggered.connect(lambda: self.copy_selection())
        self.addAction(self.copy_action)

    def set_result(self, columns: list[str], rows: list[tuple[Any, ...]]) -> None:
        self.results_model.set_result(columns, rows)
        self.resizeColumnsToContents()
        for col in range(len(columns)):
            if self.columnWidth(col) > 400:
                self.setColumnWidth(col, 400)

    def clear(self) -> None:
        self.results_model.clear()

    # -- copia ----------------------------------------------------------------------
    def selection_as_tsv(self, *, whole_rows: bool = False, headers: bool = False) -> str:
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return ""
        model = self.results_model
        rows = sorted({i.row() for i in indexes})
        if whole_rows:
            columns = list(range(model.columnCount()))
            selected = None
        else:
            columns = sorted({i.column() for i in indexes})
            selected = {(i.row(), i.column()) for i in indexes}

        lines = []
        if headers:
            lines.append("\t".join(copy_text(model.columns[c]) for c in columns))
        for row in rows:
            cells = [
                copy_text(model.raw_value(row, col))
                if selected is None or (row, col) in selected
                else ""
                for col in columns
            ]
            lines.append("\t".join(cells))
        return "\n".join(lines)

    def copy_selection(self, *, whole_rows: bool = False, headers: bool = False) -> str:
        text = self.selection_as_tsv(whole_rows=whole_rows, headers=headers)
        if text:
            QGuiApplication.clipboard().setText(text)
        return text

    def _show_menu(self, pos: Any) -> None:
        if not self.selectionModel().selectedIndexes():
            return
        menu = QMenu(self)
        menu.addAction("Copia celle", lambda: self.copy_selection())
        menu.addAction("Copia celle con intestazioni",
                       lambda: self.copy_selection(headers=True))
        menu.addSeparator()
        menu.addAction("Copia righe", lambda: self.copy_selection(whole_rows=True))
        menu.addAction("Copia righe con intestazioni",
                       lambda: self.copy_selection(whole_rows=True, headers=True))
        menu.exec(self.viewport().mapToGlobal(pos))
