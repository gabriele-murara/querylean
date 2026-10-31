"""Gutter widget that shows line numbers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from querylean.ui.editor.sql_editor import SqlEditor


class LineNumberArea(QWidget):
    """Delegates sizing and painting to its ``SqlEditor``."""

    def __init__(self, editor: SqlEditor) -> None:
        super().__init__(editor)
        self.__editor = editor

    @property
    def editor(self) -> SqlEditor:
        """Editor this gutter belongs to."""
        return self.__editor

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.__editor.line_number_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        self.__editor.paint_line_numbers(event)
