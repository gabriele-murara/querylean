"""Side bar with the tables available to the connected user."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from querylean.database.schema.table_catalog import TableCatalog
from querylean.database.schema.table_info import TableInfo
from querylean.ui.icons.toolbar_icons import ToolbarIcons


class TableSidebar(QWidget):
    """Title "Tables" with a refresh button, the list of tables and views
    (views in italics) and a status line.

    A click on a table, or Enter on the current one, emits
    ``table_chosen(TableInfo)``; the refresh button emits
    ``refresh_requested``.
    """

    table_chosen = Signal(object)
    refresh_requested = Signal()

    NOT_CONNECTED = "Connect to see the tables."
    LOADING = "Loading the tables…"
    NO_TABLES = "No tables available."
    __TABLE_ROLE = Qt.ItemDataRole.UserRole
    __MIN_WIDTH = 160
    __ICON_SIZE = 16

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("table-sidebar")
        self.setMinimumWidth(TableSidebar.__MIN_WIDTH)

        title = QLabel("Tables")
        bold = QFont(title.font())
        bold.setBold(True)
        title.setFont(bold)
        self.__refresh_button = QToolButton()
        self.__refresh_button.setIcon(ToolbarIcons.refresh())
        size = TableSidebar.__ICON_SIZE
        self.__refresh_button.setIconSize(QSize(size, size))
        self.__refresh_button.setAutoRaise(True)
        self.__refresh_button.setToolTip("Refresh the list of tables")
        self.__refresh_button.clicked.connect(self.refresh_requested)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(title, 1)
        header.addWidget(self.__refresh_button)

        self.__list = QListWidget()
        self.__list.setUniformItemSizes(True)
        self.__list.itemClicked.connect(self.__on_item)
        self.__list.itemActivated.connect(self.__on_item)

        self.__status_label = QLabel()
        self.__status_label.setWordWrap(True)
        self.__status_label.setStyleSheet("color: palette(placeholder-text);")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self.__list, 1)
        layout.addWidget(self.__status_label)
        self.show_message(TableSidebar.NOT_CONNECTED)

    @property
    def list_widget(self) -> QListWidget:
        """List of tables."""
        return self.__list

    @property
    def refresh_button(self) -> QToolButton:
        """ "Refresh" button."""
        return self.__refresh_button

    @property
    def status_label(self) -> QLabel:
        """Status line (loading, errors, counts)."""
        return self.__status_label

    def tables(self) -> list[TableInfo]:
        """Listed tables, in display order."""
        return [
            self.__list.item(i).data(TableSidebar.__TABLE_ROLE)
            for i in range(self.__list.count())
        ]

    def set_loading(self) -> None:
        """Keep the current list and announce a reload."""
        self.__refresh_button.setEnabled(False)
        self.__set_status(TableSidebar.LOADING)

    def set_tables(self, tables: list[TableInfo]) -> None:
        """Show ``tables``."""
        self.__list.clear()
        italic = QFont(self.__list.font())
        italic.setItalic(True)
        for table in tables:
            item = QListWidgetItem(table.name)
            item.setData(TableSidebar.__TABLE_ROLE, table)
            if table.is_view:
                item.setFont(italic)
                item.setToolTip("View {}".format(table.name))
            else:
                item.setToolTip("Table {}".format(table.name))
            self.__list.addItem(item)
        self.__refresh_button.setEnabled(True)
        if not tables:
            self.__set_status(TableSidebar.NO_TABLES)
        elif len(tables) >= TableCatalog.MAX_TABLES:
            msg = "Showing only the first {} tables."
            self.__set_status(msg.format(TableCatalog.MAX_TABLES))
        else:
            self.__set_status("{} tables".format(len(tables)))

    def set_error(self, message: str) -> None:
        """Show a loading error; the refresh button stays available."""
        self.__list.clear()
        self.__refresh_button.setEnabled(True)
        self.__set_status(message, error=True)

    def show_message(self, message: str) -> None:
        """Empty the list and show ``message`` (e.g. when disconnected)."""
        self.__list.clear()
        self.__refresh_button.setEnabled(False)
        self.__set_status(message)

    def __set_status(self, text: str, *, error: bool = False) -> None:
        self.__status_label.setStyleSheet(
            "color: #c62828;" if error else "color: palette(placeholder-text);"
        )
        self.__status_label.setText(text)

    def __on_item(self, item: QListWidgetItem) -> None:
        table = item.data(TableSidebar.__TABLE_ROLE)
        if isinstance(table, TableInfo):
            self.table_chosen.emit(table)
