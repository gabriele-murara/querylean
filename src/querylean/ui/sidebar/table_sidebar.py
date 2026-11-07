"""Side bar with the databases, tables and columns available to the
connected user."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPalette
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
from querylean.ui.safe_text import SafeText


class TableSidebar(QWidget):
    """Title "Tables" with a refresh button, a filter, the tree of
    databases, tables and views (views in italics), columns, and a status
    line.

    A click on a database emits ``database_selected(name)`` and expands
    it; its tables are requested with ``tables_requested(database)`` until
    ``set_tables`` provides them. The active database is in bold. Once the
    write access is known (``set_write_access``), read-only databases are
    green and those the account can change are pink with a warning icon.

    Expanding a table shows its columns with type, keys and a tooltip with
    the full definition; columns not loaded yet are requested with
    ``columns_requested(database, table)``. A click on a table emits
    ``database_selected`` (its database) and ``table_chosen(TableInfo)``
    and expands it; double click and Enter emit ``table_chosen`` too.
    Double click (or Enter) on a column emits
    ``column_chosen(TableInfo, name)``; with Shift held it emits
    ``column_added(TableInfo, name)`` instead. The context menu offers the
    same actions and the copy of the name.
    """

    database_selected = Signal(str)
    tables_requested = Signal(str)  # database
    table_chosen = Signal(object)
    column_chosen = Signal(object, str)  # TableInfo, column name
    column_added = Signal(object, str)  # TableInfo, column name (Shift)
    columns_requested = Signal(str, str)  # database, table
    refresh_requested = Signal()

    NOT_CONNECTED = "Connect to see the tables."
    LOADING = "Loading the tables…"
    LOADING_DATABASES = "Loading the databases…"
    NO_TABLES = "No tables available."
    NO_DATABASES = "No databases available."
    LOADING_TABLES = "Loading the tables…"
    LOADING_COLUMNS = "Loading the columns…"
    NO_COLUMNS = "No columns available."
    FILTER_PLACEHOLDER = "Filter tables…"
    PREPARE_TEXT = "Prepare SELECT"
    COLUMN_TEXT = "Prepare SELECT of the column"
    ADD_TEXT = "Add to the SELECT"
    USE_TEXT = "Use as active database"
    READ_ONLY_COLOR = "#2e7d32"
    WRITE_COLOR = "#c2185b"
    COPY_TEXT = "Copy name"
    __TABLE_ROLE = Qt.ItemDataRole.UserRole
    __COLUMN_ROLE = Qt.ItemDataRole.UserRole + 1
    __DATABASE_ROLE = Qt.ItemDataRole.UserRole + 2
    __MIN_WIDTH = 160
    __ICON_SIZE = 16

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("table-sidebar")
        self.setMinimumWidth(TableSidebar.__MIN_WIDTH)
        self.__schema: SchemaModel | None = None
        self.__active = ""
        # Write privileges by database (None while unknown).
        self.__write_access: dict[str, str] | None = None
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
        self.__refresh_button.setToolTip("Refresh the databases and tables")
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
        # Server messages: never rendered as HTML.
        self.__status_label.setTextFormat(Qt.TextFormat.PlainText)
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
        """Tree of databases (top level), tables and columns."""
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

    @property
    def active_database(self) -> str:
        """Database shown in bold (the default one of the session)."""
        return self.__active

    def set_schema(self, schema: SchemaModel | None) -> None:
        """Model the columns are read from when a table is expanded."""
        self.__schema = schema

    # --------------------------------------------------------------- lookup
    def databases(self) -> list[str]:
        """Listed databases, in display order."""
        return [item.text(0) for item in self.__database_items()]

    def database_item(self, name: str) -> QTreeWidgetItem | None:
        """Item of the database ``name``, if listed."""
        for item in self.__database_items():
            if item.data(0, TableSidebar.__DATABASE_ROLE) == name:
                return item
        return None

    def tables(self, database: str | None = None) -> list[TableInfo]:
        """Listed tables of ``database`` (default: all), in display order
        (filtered ones included)."""
        return [
            item.data(0, TableSidebar.__TABLE_ROLE)
            for item in self.__table_items(database)
        ]

    def table_item(
        self, name: str, database: str | None = None
    ) -> QTreeWidgetItem | None:
        """Item of the table ``name`` (in ``database`` when given)."""
        for item in self.__table_items(database):
            if item.data(0, TableSidebar.__TABLE_ROLE).name == name:
                return item
        return None

    def visible_tables(self) -> list[str]:
        """Names of the tables not hidden by the filter."""
        return [
            item.text(0)
            for item in self.__table_items(None)
            if not item.isHidden() and not item.parent().isHidden()
        ]

    def column_names(
        self, table: str, database: str | None = None
    ) -> list[str]:
        """Columns shown under ``table`` (empty while not loaded)."""
        item = self.table_item(table, database)
        if item is None:
            return []
        return [
            item.child(i).text(0)
            for i in range(item.childCount())
            if item.child(i).data(0, TableSidebar.__COLUMN_ROLE) is not None
        ]

    # -------------------------------------------------------------- content
    def set_loading(self, message: str = LOADING) -> None:
        """Keep the current tree and announce a reload."""
        self.__refresh_button.setEnabled(False)
        self.__set_status(message)

    def set_databases(self, databases: list[str], active: str = "") -> None:
        """Show ``databases`` (their tables are added by ``set_tables``);
        a single database is expanded at once. Databases that were
        expanded stay expanded."""
        expanded = {
            item.text(0)
            for item in self.__database_items()
            if item.isExpanded()
        }
        self.__tree.clear()
        self.__active = active
        for database in databases:
            item = QTreeWidgetItem([database, ""])
            item.setData(0, TableSidebar.__DATABASE_ROLE, database)
            item.setIcon(0, CompletionIcons.icon(CompletionKind.DATABASE))
            item.setToolTip(0, SafeText.tooltip("Database {}".format(database)))
            item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            )
            self.__tree.addTopLevelItem(item)
        self.__mark_active()
        self.__refresh_button.setEnabled(True)
        if not databases:
            self.__set_status(TableSidebar.NO_DATABASES)
        elif len(databases) > 1:
            self.__set_status("{} databases".format(len(databases)))
        else:
            self.__set_status(TableSidebar.LOADING)
        for item in self.__database_items():
            if len(databases) == 1 or item.text(0) in expanded:
                item.setExpanded(True)
        self.__apply_filter()

    def set_write_access(self, writable: dict[str, str] | None) -> None:
        """Databases the account can change, with their privileges (the
        others are read-only); None when unknown."""
        self.__write_access = None if writable is None else dict(writable)
        self.__mark_active()

    def is_writable(self, database: str) -> bool | None:
        """True when the account can change ``database``, False when it is
        read-only, None when unknown."""
        if self.__write_access is None:
            return None
        return database in self.__write_access

    def set_active_database(self, database: str) -> None:
        """Show ``database`` as the active one."""
        self.__active = database
        self.__mark_active()

    def set_tables(self, tables: list[TableInfo], database: str) -> None:
        """Show ``tables`` under ``database``; tables that were expanded
        stay expanded."""
        parent = self.database_item(database)
        if parent is None:
            return
        expanded = {
            parent.child(i).text(0)
            for i in range(parent.childCount())
            if parent.child(i).isExpanded()
        }
        TableSidebar.__clear_children(parent)
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
                tip = "View {}"
            else:
                tip = "Table {}"
            item.setToolTip(0, SafeText.tooltip(tip.format(table.name)))
            parent.addChild(item)
        if not tables:
            TableSidebar.__placeholder(parent, TableSidebar.NO_TABLES)
        self.__refresh_button.setEnabled(True)
        self.__count_status(tables)
        self.__apply_filter()
        for name in expanded:
            item = self.table_item(name, database)
            if item is not None:
                item.setExpanded(True)

    def set_tables_error(self, database: str, message: str) -> None:
        """Show that the tables of ``database`` could not be read."""
        parent = self.database_item(database)
        if parent is None:
            return
        TableSidebar.__clear_children(parent)
        child = TableSidebar.__placeholder(parent, TableSidebar.NO_TABLES)
        child.setToolTip(0, SafeText.tooltip(message))
        self.__refresh_button.setEnabled(True)
        self.__set_status(message, error=True)

    def refresh_columns(self) -> None:
        """Update the expanded tables (and those waiting for columns) from
        the schema model."""
        for item in self.__table_items(None):
            if item.isExpanded() or item.childCount():
                self.__fill_columns(item, request=False)

    def set_columns_error(
        self, table: str, message: str, database: str | None = None
    ) -> None:
        """Show that the columns of ``table`` could not be read."""
        item = self.table_item(table, database)
        if item is None:
            return
        TableSidebar.__clear_children(item)
        child = TableSidebar.__placeholder(item, TableSidebar.NO_COLUMNS)
        child.setToolTip(0, SafeText.tooltip(message))

    def set_error(self, message: str) -> None:
        """Show a loading error; the refresh button stays available."""
        self.__tree.clear()
        self.__refresh_button.setEnabled(True)
        self.__set_status(message, error=True)

    def show_message(self, message: str) -> None:
        """Empty the tree and show ``message`` (e.g. when disconnected)."""
        self.__tree.clear()
        self.__active = ""
        self.__write_access = None
        self.__refresh_button.setEnabled(False)
        self.__set_status(message)

    # ------------------------------------------------------------ internals
    def __database_items(self) -> list[QTreeWidgetItem]:
        return [
            self.__tree.topLevelItem(i)
            for i in range(self.__tree.topLevelItemCount())
        ]

    def __table_items(self, database: str | None) -> list[QTreeWidgetItem]:
        items = []
        for parent in self.__database_items():
            if database is not None and parent.text(0) != database:
                continue
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.data(0, TableSidebar.__TABLE_ROLE) is not None:
                    items.append(child)
        return items

    def __database_of(self, item: QTreeWidgetItem) -> str:
        """Database of a database, table or column item."""
        while item.parent() is not None:
            item = item.parent()
        return str(item.data(0, TableSidebar.__DATABASE_ROLE) or "")

    def __mark_active(self) -> None:
        bold = QFont(self.__tree.font())
        bold.setBold(True)
        plain = QFont(self.__tree.font())
        for item in self.__database_items():
            name = item.text(0)
            active = name == self.__active
            item.setFont(0, bold if active else plain)
            item.setText(1, "active" if active else "")
            self.__mark_access(item, name)

    def __mark_access(self, item: QTreeWidgetItem, name: str) -> None:
        """Color, warning icon and tooltip of a database by write access."""
        writes = self.__write_access
        if writes is None:
            item.setData(0, Qt.ItemDataRole.ForegroundRole, None)
            item.setIcon(1, QIcon())
            item.setToolTip(0, SafeText.tooltip("Database {}".format(name)))
            return
        if name in writes:
            item.setForeground(0, QColor(TableSidebar.WRITE_COLOR))
            item.setIcon(1, ToolbarIcons.warning())
            tip = "Database {}: the account can change data ({}). Caution "
            tip += "mode: only read queries are run."
            item.setToolTip(0, SafeText.tooltip(tip.format(name, writes[name])))
        else:
            item.setForeground(0, QColor(TableSidebar.READ_ONLY_COLOR))
            item.setIcon(1, QIcon())
            item.setToolTip(
                0, SafeText.tooltip("Database {}: read-only".format(name))
            )
        item.setToolTip(1, item.toolTip(0))

    def __count_status(self, tables: list[TableInfo]) -> None:
        if len(self.__database_items()) > 1:
            msg = "{} databases".format(len(self.__database_items()))
        elif not tables:
            msg = TableSidebar.NO_TABLES
        elif len(tables) >= TableCatalog.MAX_TABLES:
            msg = "Showing only the first {} tables."
            msg = msg.format(TableCatalog.MAX_TABLES)
        else:
            msg = "{} tables".format(len(tables))
        self.__set_status(msg)

    def __set_status(self, text: str, *, error: bool = False) -> None:
        self.__status_text = text
        self.__status_error = error
        self.__show_status()

    def __show_status(self) -> None:
        text = self.__status_text
        total = len(self.__table_items(None))
        if not self.__status_error and self.__filter.text().strip() and total:
            text = "{} of {} tables".format(len(self.visible_tables()), total)
        self.__status_label.setStyleSheet(
            "color: #c62828;"
            if self.__status_error
            else "color: palette(placeholder-text);"
        )
        self.__status_label.setText(text)

    def __apply_filter(self, *_: object) -> None:
        wanted = self.__filter.text().strip().casefold()
        for parent in self.__database_items():
            name_matches = not wanted or wanted in parent.text(0).casefold()
            any_shown = False
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.data(0, TableSidebar.__TABLE_ROLE) is None:
                    continue
                shown = name_matches or wanted in child.text(0).casefold()
                child.setHidden(not shown)
                any_shown = any_shown or shown
            parent.setHidden(not (name_matches or any_shown))
        self.__show_status()

    def __fill_tables(self, item: QTreeWidgetItem) -> None:
        """Placeholder and request while the tables of a database are not
        listed."""
        if item.childCount():
            return
        TableSidebar.__placeholder(item, TableSidebar.LOADING_TABLES)
        self.tables_requested.emit(item.text(0))

    def __fill_columns(self, item: QTreeWidgetItem, *, request: bool) -> None:
        """Show the columns of the table ``item`` from the schema model, or
        a placeholder while they are loaded."""
        table = item.data(0, TableSidebar.__TABLE_ROLE)
        database = self.__database_of(item)
        columns = (
            self.__schema.columns_of(table.name, database)
            if self.__schema is not None
            else None
        )
        if columns is None:
            if not item.childCount():
                TableSidebar.__placeholder(item, TableSidebar.LOADING_COLUMNS)
            if request:
                self.columns_requested.emit(database, table.name)
            return
        TableSidebar.__clear_children(item)
        if not columns:
            TableSidebar.__placeholder(item, TableSidebar.NO_COLUMNS)
            return
        bold = QFont(self.__tree.font())
        bold.setBold(True)
        for column in columns:
            item.addChild(TableSidebar.__column_item(column, table, bold))

    @staticmethod
    def __placeholder(parent: QTreeWidgetItem, text: str) -> QTreeWidgetItem:
        child = QTreeWidgetItem([text, ""])
        child.setFlags(Qt.ItemFlag.NoItemFlags)
        parent.addChild(child)
        return child

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
        tooltip = SafeText.tooltip(
            "{}\ntable: {}".format(column.describe(), table.name)
        )
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
        if item.data(0, TableSidebar.__DATABASE_ROLE) is not None:
            self.__fill_tables(item)
        elif item.data(0, TableSidebar.__TABLE_ROLE) is not None:
            self.__fill_columns(item, request=True)

    def __on_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        database = item.data(0, TableSidebar.__DATABASE_ROLE)
        if database is not None:
            item.setExpanded(True)
            self.database_selected.emit(database)
            return
        table = item.data(0, TableSidebar.__TABLE_ROLE)
        if isinstance(table, TableInfo):
            item.setExpanded(True)
            self.database_selected.emit(self.__database_of(item))
            self.table_chosen.emit(table)

    def eventFilter(  # noqa: N802
        self, watched: QObject, event: QEvent
    ) -> bool:
        if event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonDblClick,
            QEvent.Type.KeyPress,
        ):
            self.__modifiers = event.modifiers()
        return super().eventFilter(watched, event)

    def __on_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        database = item.data(0, TableSidebar.__DATABASE_ROLE)
        if database is not None:
            item.setExpanded(True)
            self.database_selected.emit(database)
            return
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
        """Menu for ``item``: make it the active database (databases),
        prepare the SELECT (tables), prepare the SELECT of the column or add
        it to the SELECT (columns), and copy the name."""
        database = item.data(0, TableSidebar.__DATABASE_ROLE)
        table = item.data(0, TableSidebar.__TABLE_ROLE)
        column = item.data(0, TableSidebar.__COLUMN_ROLE)
        menu = QMenu(self)
        if database is not None:
            use = menu.addAction(TableSidebar.USE_TEXT)
            use.setEnabled(database != self.__active)
            use.triggered.connect(lambda: self.database_selected.emit(database))
            name = database
        elif isinstance(table, TableInfo):
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
