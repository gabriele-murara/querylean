"""Side bar with the tables available to the connected user and their
columns."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from querylean.completion.completion_kind import CompletionKind
from querylean.completion.schema_model import SchemaModel
from querylean.database.schema.column_info import ColumnInfo
from querylean.database.schema.table_catalog import TableCatalog
from querylean.database.schema.table_info import TableInfo
from querylean.ui.icons.completion_icons import CompletionIcons
from querylean.ui.icons.toolbar_icons import ToolbarIcons


class TableSidebar(QWidget):
    """Title "Tables" with a refresh button, a filter, the tree of tables
    and views (views in italics) and a status line.

    Expanding a table shows its columns with type, keys and a tooltip with
    the full definition; columns not loaded yet are requested with
    ``columns_requested(table)``. A click on a table emits
    ``table_chosen(TableInfo)`` and expands it; double click and Enter emit
    ``table_chosen`` too. Double click (or Enter) on a column emits
    ``column_chosen(TableInfo, name)``; with Shift held it emits
    ``column_added(TableInfo, name)`` instead. The context menu offers the
    same actions and the copy of the name.
    """

    table_chosen = Signal(object)
    column_chosen = Signal(object, str)  # TableInfo, column name
    column_added = Signal(object, str)  # TableInfo, column name (Shift)
    columns_requested = Signal(str)
    refresh_requested = Signal()

    NOT_CONNECTED = "Connect to see the tables."
    LOADING = "Loading the tables…"
    NO_TABLES = "No tables available."
    LOADING_COLUMNS = "Loading the columns…"
    NO_COLUMNS = "No columns available."
    FILTER_PLACEHOLDER = "Filter tables…"
    PREPARE_TEXT = "Prepare SELECT"
    COLUMN_TEXT = "Prepare SELECT of the column"
    ADD_TEXT = "Add to the SELECT"
    COPY_TEXT = "Copy name"
    __TABLE_ROLE = Qt.ItemDataRole.UserRole
    __COLUMN_ROLE = Qt.ItemDataRole.UserRole + 1
    __MIN_WIDTH = 160
    __ICON_SIZE = 16

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("table-sidebar")
        self.setMinimumWidth(TableSidebar.__MIN_WIDTH)
        self.__schema: SchemaModel | None = None
        self.__table_count = 0
        self.__status_text = ""
        self.__status_error = False

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

        self.__filter = QLineEdit()
        self.__filter.setPlaceholderText(TableSidebar.FILTER_PLACEHOLDER)
        self.__filter.setClearButtonEnabled(True)
        self.__filter.textChanged.connect(self.__apply_filter)

        self.__tree = QTreeWidget()
        self.__tree.setColumnCount(2)
        self.__tree.setHeaderHidden(True)
        self.__tree.setUniformRowHeights(True)
        self.__tree.setExpandsOnDoubleClick(False)
        self.__tree.setIconSize(QSize(size - 2, size - 2))
        self.__tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree_header = self.__tree.header()
        tree_header.setStretchLastSection(False)
        tree_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tree_header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        # Modifiers of the last click or key press on the tree: Shift turns
        # the choice of a column into its addition.
        self.__modifiers = Qt.KeyboardModifier.NoModifier
        self.__tree.installEventFilter(self)
        self.__tree.viewport().installEventFilter(self)
        self.__tree.itemActivated.connect(self.__on_activated)
        self.__tree.itemClicked.connect(self.__on_clicked)
        self.__tree.itemExpanded.connect(self.__on_expanded)
        self.__tree.customContextMenuRequested.connect(self.__on_menu)

        self.__status_label = QLabel()
        self.__status_label.setWordWrap(True)
        self.__status_label.setStyleSheet("color: palette(placeholder-text);")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self.__filter)
        layout.addWidget(self.__tree, 1)
        layout.addWidget(self.__status_label)
        self.show_message(TableSidebar.NOT_CONNECTED)

    @property
    def tree_widget(self) -> QTreeWidget:
        """Tree of tables (top level) and columns (children)."""
        return self.__tree

    @property
    def filter_edit(self) -> QLineEdit:
        """Filter of the table names."""
        return self.__filter

    @property
    def refresh_button(self) -> QToolButton:
        """ "Refresh" button."""
        return self.__refresh_button

    @property
    def status_label(self) -> QLabel:
        """Status line (loading, errors, counts)."""
        return self.__status_label

    def set_schema(self, schema: SchemaModel | None) -> None:
        """Model the columns are read from when a table is expanded."""
        self.__schema = schema

    def tables(self) -> list[TableInfo]:
        """Listed tables, in display order (filtered ones included)."""
        return [
            self.__tree.topLevelItem(i).data(0, TableSidebar.__TABLE_ROLE)
            for i in range(self.__tree.topLevelItemCount())
        ]

    def table_item(self, name: str) -> QTreeWidgetItem | None:
        """Item of the table ``name``, if listed."""
        for i in range(self.__tree.topLevelItemCount()):
            item = self.__tree.topLevelItem(i)
            if item.data(0, TableSidebar.__TABLE_ROLE).name == name:
                return item
        return None

    def visible_tables(self) -> list[str]:
        """Names of the tables not hidden by the filter."""
        return [
            self.__tree.topLevelItem(i).text(0)
            for i in range(self.__tree.topLevelItemCount())
            if not self.__tree.topLevelItem(i).isHidden()
        ]

    def column_names(self, table: str) -> list[str]:
        """Columns shown under ``table`` (empty while not loaded)."""
        item = self.table_item(table)
        if item is None:
            return []
        return [
            item.child(i).text(0)
            for i in range(item.childCount())
            if item.child(i).data(0, TableSidebar.__COLUMN_ROLE) is not None
        ]

    def set_loading(self) -> None:
        """Keep the current list and announce a reload."""
        self.__refresh_button.setEnabled(False)
        self.__set_status(TableSidebar.LOADING)

    def set_tables(self, tables: list[TableInfo]) -> None:
        """Show ``tables``; tables that were expanded stay expanded."""
        expanded = {
            self.__tree.topLevelItem(i).text(0)
            for i in range(self.__tree.topLevelItemCount())
            if self.__tree.topLevelItem(i).isExpanded()
        }
        self.__tree.clear()
        italic = QFont(self.__tree.font())
        italic.setItalic(True)
        for table in tables:
            item = QTreeWidgetItem([table.name, ""])
            item.setData(0, TableSidebar.__TABLE_ROLE, table)
            item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            )
            kind = (
                CompletionKind.VIEW if table.is_view else CompletionKind.TABLE
            )
            item.setIcon(0, CompletionIcons.icon(kind))
            if table.is_view:
                item.setFont(0, italic)
                item.setToolTip(0, "View {}".format(table.name))
            else:
                item.setToolTip(0, "Table {}".format(table.name))
            self.__tree.addTopLevelItem(item)
        self.__table_count = len(tables)
        self.__refresh_button.setEnabled(True)
        if not tables:
            self.__set_status(TableSidebar.NO_TABLES)
        elif len(tables) >= TableCatalog.MAX_TABLES:
            msg = "Showing only the first {} tables."
            self.__set_status(msg.format(TableCatalog.MAX_TABLES))
        else:
            self.__set_status("{} tables".format(len(tables)))
        self.__apply_filter()
        for name in expanded:
            item = self.table_item(name)
            if item is not None:
                item.setExpanded(True)

    def refresh_columns(self) -> None:
        """Update the expanded tables (and those waiting for columns) from
        the schema model."""
        for i in range(self.__tree.topLevelItemCount()):
            item = self.__tree.topLevelItem(i)
            if item.isExpanded() or item.childCount():
                self.__fill_columns(item, request=False)

    def set_columns_error(self, table: str, message: str) -> None:
        """Show that the columns of ``table`` could not be read."""
        item = self.table_item(table)
        if item is None:
            return
        TableSidebar.__clear_children(item)
        child = QTreeWidgetItem([TableSidebar.NO_COLUMNS, ""])
        child.setToolTip(0, message)
        child.setFlags(Qt.ItemFlag.NoItemFlags)
        item.addChild(child)

    def set_error(self, message: str) -> None:
        """Show a loading error; the refresh button stays available."""
        self.__tree.clear()
        self.__table_count = 0
        self.__refresh_button.setEnabled(True)
        self.__set_status(message, error=True)

    def show_message(self, message: str) -> None:
        """Empty the list and show ``message`` (e.g. when disconnected)."""
        self.__tree.clear()
        self.__table_count = 0
        self.__refresh_button.setEnabled(False)
        self.__set_status(message)

    # ------------------------------------------------------------ internals
    def __set_status(self, text: str, *, error: bool = False) -> None:
        self.__status_text = text
        self.__status_error = error
        self.__show_status()

    def __show_status(self) -> None:
        text = self.__status_text
        shown = len(self.visible_tables())
        if (
            not self.__status_error
            and self.__filter.text().strip()
            and self.__table_count
        ):
            text = "{} of {} tables".format(shown, self.__table_count)
        self.__status_label.setStyleSheet(
            "color: #c62828;"
            if self.__status_error
            else "color: palette(placeholder-text);"
        )
        self.__status_label.setText(text)

    def __apply_filter(self, *_: object) -> None:
        wanted = self.__filter.text().strip().casefold()
        for i in range(self.__tree.topLevelItemCount()):
            item = self.__tree.topLevelItem(i)
            item.setHidden(
                bool(wanted) and wanted not in item.text(0).casefold()
            )
        self.__show_status()

    def __fill_columns(self, item: QTreeWidgetItem, *, request: bool) -> None:
        """Show the columns of the table ``item`` from the schema model, or
        a placeholder while they are loaded."""
        table = item.data(0, TableSidebar.__TABLE_ROLE)
        columns = (
            self.__schema.columns_of(table.name)
            if self.__schema is not None
            else None
        )
        if columns is None:
            if not item.childCount():
                child = QTreeWidgetItem([TableSidebar.LOADING_COLUMNS, ""])
                child.setFlags(Qt.ItemFlag.NoItemFlags)
                item.addChild(child)
            if request:
                self.columns_requested.emit(table.name)
            return
        TableSidebar.__clear_children(item)
        if not columns:
            child = QTreeWidgetItem([TableSidebar.NO_COLUMNS, ""])
            child.setFlags(Qt.ItemFlag.NoItemFlags)
            item.addChild(child)
            return
        bold = QFont(self.__tree.font())
        bold.setBold(True)
        for column in columns:
            item.addChild(TableSidebar.__column_item(column, table, bold))

    @staticmethod
    def __column_item(
        column: ColumnInfo, table: TableInfo, bold: QFont
    ) -> QTreeWidgetItem:
        child = QTreeWidgetItem([column.name, column.data_type])
        child.setData(0, TableSidebar.__COLUMN_ROLE, column)
        kind = (
            CompletionKind.KEY_COLUMN
            if column.is_primary
            else CompletionKind.COLUMN
        )
        child.setIcon(0, CompletionIcons.icon(kind))
        if column.is_primary:
            child.setFont(0, bold)
        tooltip = "{}\ntable: {}".format(column.describe(), table.name)
        child.setToolTip(0, tooltip)
        child.setToolTip(1, tooltip)
        child.setForeground(
            1,
            QGuiApplication.palette().brush(QPalette.ColorRole.PlaceholderText),
        )
        return child

    @staticmethod
    def __clear_children(item: QTreeWidgetItem) -> None:
        for child in item.takeChildren():
            del child

    def __on_expanded(self, item: QTreeWidgetItem) -> None:
        if item.data(0, TableSidebar.__TABLE_ROLE) is not None:
            self.__fill_columns(item, request=True)

    def __on_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        table = item.data(0, TableSidebar.__TABLE_ROLE)
        if isinstance(table, TableInfo):
            item.setExpanded(True)
            self.table_chosen.emit(table)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonDblClick,
            QEvent.Type.KeyPress,
        ):
            self.__modifiers = event.modifiers()
        return super().eventFilter(watched, event)

    def __on_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        table = item.data(0, TableSidebar.__TABLE_ROLE)
        if isinstance(table, TableInfo):
            self.table_chosen.emit(table)
            return
        column = item.data(0, TableSidebar.__COLUMN_ROLE)
        parent = item.parent()
        if isinstance(column, ColumnInfo) and parent is not None:
            owner = parent.data(0, TableSidebar.__TABLE_ROLE)
            if self.__modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.column_added.emit(owner, column.name)
            else:
                self.column_chosen.emit(owner, column.name)

    def __on_menu(self, pos: QPoint) -> None:
        item = self.__tree.itemAt(pos)
        if item is None:
            return
        menu = self.context_menu(item)
        if menu is not None:
            menu.exec(self.__tree.viewport().mapToGlobal(pos))

    def context_menu(self, item: QTreeWidgetItem) -> QMenu | None:
        """Menu for ``item``: prepare the SELECT (tables), prepare the
        SELECT of the column or add it to the SELECT (columns), and copy the
        name."""
        table = item.data(0, TableSidebar.__TABLE_ROLE)
        column = item.data(0, TableSidebar.__COLUMN_ROLE)
        menu = QMenu(self)
        if isinstance(table, TableInfo):
            prepare = menu.addAction(TableSidebar.PREPARE_TEXT)
            prepare.triggered.connect(lambda: self.table_chosen.emit(table))
            name = table.name
        elif isinstance(column, ColumnInfo) and item.parent() is not None:
            owner = item.parent().data(0, TableSidebar.__TABLE_ROLE)
            prepare = menu.addAction(TableSidebar.COLUMN_TEXT)
            prepare.triggered.connect(
                lambda: self.column_chosen.emit(owner, column.name)
            )
            add = menu.addAction(TableSidebar.ADD_TEXT)
            add.triggered.connect(
                lambda: self.column_added.emit(owner, column.name)
            )
            name = column.name
        else:
            return None
        copy = menu.addAction(TableSidebar.COPY_TEXT)
        copy.triggered.connect(
            lambda: QGuiApplication.clipboard().setText(name)
        )
        return menu
