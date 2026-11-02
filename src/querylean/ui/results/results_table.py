"""Result table view with tab-separated copy."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import QAbstractItemView, QMenu, QTableView, QWidget

from querylean.ui.results.results_model import ResultsModel
from querylean.ui.results.value_formatter import ValueFormatter


class ResultsTable(QTableView):
    """Read-only table with extended selection and TSV copy (cells, rows,
    headers)."""

    __MAX_INITIAL_COLUMN_WIDTH = 400

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.__model = ResultsModel(self)
        self.setModel(self.__model)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionsMovable(False)
        self.verticalHeader().setDefaultSectionSize(
            self.fontMetrics().height() + 6
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.__show_menu)

        self.__copy_action = QAction("Copy", self)
        self.__copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.__copy_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.__copy_action.triggered.connect(lambda: self.copy_selection())
        self.addAction(self.__copy_action)

    @property
    def results_model(self) -> ResultsModel:
        """Model holding the current result."""
        return self.__model

    def set_result(
        self, columns: list[str], rows: list[tuple[Any, ...]]
    ) -> None:
        """Show a new result and size the columns to their content."""
        self.__model.set_result(columns, rows)
        self.resizeColumnsToContents()
        for col in range(len(columns)):
            if self.columnWidth(col) > ResultsTable.__MAX_INITIAL_COLUMN_WIDTH:
                self.setColumnWidth(
                    col, ResultsTable.__MAX_INITIAL_COLUMN_WIDTH
                )

    def clear(self) -> None:
        """Remove the displayed result."""
        self.__model.clear()

    def selection_as_tsv(
        self, *, whole_rows: bool = False, headers: bool = False
    ) -> str:
        """Selected cells as TSV. The selection is copied as its bounding
        rectangle; unselected cells inside it are left empty."""
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return ""
        model = self.__model
        rows = sorted({i.row() for i in indexes})
        if whole_rows:
            columns = list(range(model.columnCount()))
            selected = None
        else:
            columns = sorted({i.column() for i in indexes})
            selected = {(i.row(), i.column()) for i in indexes}

        names = model.columns
        lines = []
        if headers:
            lines.append(
                "\t".join(ValueFormatter.copy_text(names[c]) for c in columns)
            )
        for row in rows:
            cells = [
                ValueFormatter.copy_text(model.raw_value(row, col))
                if selected is None or (row, col) in selected
                else ""
                for col in columns
            ]
            lines.append("\t".join(cells))
        return "\n".join(lines)

    def copy_selection(
        self, *, whole_rows: bool = False, headers: bool = False
    ) -> str:
        """Copy the selection to the clipboard and return the copied text."""
        text = self.selection_as_tsv(whole_rows=whole_rows, headers=headers)
        if text:
            QGuiApplication.clipboard().setText(text)
        return text

    def __show_menu(self, pos: QPoint) -> None:
        if not self.selectionModel().selectedIndexes():
            return
        menu = QMenu(self)
        menu.addAction("Copy cells", lambda: self.copy_selection())
        menu.addAction(
            "Copy cells with headers",
            lambda: self.copy_selection(headers=True),
        )
        menu.addSeparator()
        menu.addAction(
            "Copy rows", lambda: self.copy_selection(whole_rows=True)
        )
        menu.addAction(
            "Copy rows with headers",
            lambda: self.copy_selection(whole_rows=True, headers=True),
        )
        menu.exec(self.viewport().mapToGlobal(pos))
