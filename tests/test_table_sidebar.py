"""GUI tests of the side bar of databases, tables and columns."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from querylean.completion.schema_model import SchemaModel
from querylean.database.schema.column_info import ColumnInfo
from querylean.database.schema.table_catalog import TableCatalog
from querylean.database.schema.table_info import TableInfo
from querylean.ui.safe_text import SafeText
from querylean.ui.sidebar.table_sidebar import TableSidebar


class TestTableSidebar:
    """Tree of databases, tables and columns, filter, signals, status."""

    TABLES = [TableInfo("customers"), TableInfo("v_totals", is_view=True)]
    COLUMNS = (
        ColumnInfo("id", "int", nullable=False, key="PRI"),
        ColumnInfo("full name", "varchar(64)", comment="Shown name"),
    )

    def make(self, qtbot, schema=None, tables=None) -> TableSidebar:
        """Side bar with the database "app" and ``tables`` in it."""
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        sidebar.set_schema(schema)
        sidebar.show()
        sidebar.set_databases(["app"], "app")
        sidebar.set_tables(self.TABLES if tables is None else tables, "app")
        return sidebar

    @staticmethod
    def center(tree, item):
        return tree.visualItemRect(item).center()

    def test_starts_not_connected(self, qtbot):
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        assert sidebar.tree_widget.topLevelItemCount() == 0
        assert sidebar.status_label.text() == TableSidebar.NOT_CONNECTED
        assert not sidebar.refresh_button.isEnabled()

    def test_lists_tables_and_marks_views(self, qtbot):
        sidebar = self.make(qtbot)
        assert sidebar.databases() == ["app"]
        assert sidebar.database_item("app").isExpanded()
        assert sidebar.database_item("app").font(0).bold()  # active
        assert sidebar.tables() == self.TABLES
        items = [sidebar.table_item(t.name) for t in self.TABLES]
        assert [i.text(0) for i in items] == ["customers", "v_totals"]
        assert not items[0].font(0).italic()
        assert items[1].font(0).italic()
        assert sidebar.status_label.text() == "2 tables"
        assert sidebar.refresh_button.isEnabled()

    def test_databases_request_their_tables(self, qtbot):
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        sidebar.show()
        requested = []
        sidebar.tables_requested.connect(requested.append)
        sidebar.set_databases(["app", "shop", "crm"], "shop")
        assert sidebar.status_label.text() == "3 databases"
        assert requested == []  # nothing expanded yet
        assert sidebar.database_item("shop").font(0).bold()
        assert not sidebar.database_item("app").font(0).bold()
        tree = sidebar.tree_widget
        selected = []
        sidebar.database_selected.connect(selected.append)
        crm = sidebar.database_item("crm")
        qtbot.mouseClick(
            tree.viewport(),
            Qt.MouseButton.LeftButton,
            pos=self.center(tree, crm),
        )
        assert requested == ["crm"] and selected == ["crm"]
        assert crm.child(0).text(0) == TableSidebar.LOADING_TABLES
        sidebar.set_tables([TableInfo("notes", database="crm")], "crm")
        assert sidebar.tables("crm") == [TableInfo("notes", database="crm")]
        sidebar.set_active_database("crm")
        assert sidebar.active_database == "crm"
        assert crm.font(0).bold()
        assert not sidebar.database_item("shop").font(0).bold()
        # A reload keeps the expanded databases.
        sidebar.set_databases(["app", "shop", "crm"], "crm")
        assert sidebar.database_item("crm").isExpanded()

    def test_table_errors(self, qtbot):
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        sidebar.set_databases(["app", "shop"])
        sidebar.set_tables_error("shop", "Access denied")
        child = sidebar.database_item("shop").child(0)
        assert child.text(0) == TableSidebar.NO_TABLES
        assert child.toolTip(0) == SafeText.tooltip("Access denied")
        assert sidebar.status_label.text() == "Access denied"

    def test_double_click_and_enter_choose_the_table(self, qtbot):
        sidebar = self.make(qtbot)
        tree = sidebar.tree_widget
        pos = self.center(tree, sidebar.table_item("v_totals"))
        # A real double click is press/release then a double click event.
        qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=pos)
        with qtbot.waitSignal(sidebar.table_chosen) as blocker:
            qtbot.mousePress(
                tree.viewport(), Qt.MouseButton.LeftButton, pos=pos
            )
            qtbot.mouseDClick(
                tree.viewport(), Qt.MouseButton.LeftButton, pos=pos
            )
        assert blocker.args == [self.TABLES[1]]
        tree.setCurrentItem(sidebar.table_item("customers"))
        with qtbot.waitSignal(sidebar.table_chosen) as blocker:
            qtbot.keyClick(tree, Qt.Key.Key_Return)
        assert blocker.args == [self.TABLES[0]]

    def test_click_chooses_the_table_and_shows_the_columns(self, qtbot):
        schema = SchemaModel()
        schema.set_columns("customers", self.COLUMNS, "app")
        sidebar = self.make(qtbot, schema)
        tree = sidebar.tree_widget
        chosen, selected = [], []
        sidebar.table_chosen.connect(chosen.append)
        sidebar.database_selected.connect(selected.append)
        item = sidebar.table_item("customers")
        qtbot.mouseClick(
            tree.viewport(),
            Qt.MouseButton.LeftButton,
            pos=self.center(tree, item),
        )
        assert item.isExpanded()
        assert chosen == [self.TABLES[0]]
        assert selected == ["app"]
        assert sidebar.column_names("customers") == ["id", "full name"]
        key = item.child(0)
        assert key.font(0).bold()
        assert key.text(1) == "int"
        assert "primary key" in key.toolTip(0)
        assert "Shown name" in item.child(1).toolTip(0)

    def test_unknown_columns_are_requested(self, qtbot):
        schema = SchemaModel()
        sidebar = self.make(qtbot, schema)
        item = sidebar.table_item("v_totals")
        with qtbot.waitSignal(sidebar.columns_requested) as blocker:
            item.setExpanded(True)
        assert blocker.args == ["app", "v_totals"]
        assert item.child(0).text(0) == TableSidebar.LOADING_COLUMNS
        schema.set_columns("v_totals", self.COLUMNS, "app")
        sidebar.refresh_columns()
        assert sidebar.column_names("v_totals") == ["id", "full name"]

    def test_column_errors(self, qtbot):
        sidebar = self.make(qtbot, SchemaModel())
        sidebar.table_item("customers").setExpanded(True)
        sidebar.set_columns_error("customers", "Access denied", "app")
        child = sidebar.table_item("customers").child(0)
        assert child.text(0) == TableSidebar.NO_COLUMNS
        assert child.toolTip(0) == SafeText.tooltip("Access denied")

    def test_column_is_chosen(self, qtbot):
        schema = SchemaModel()
        schema.set_columns("customers", self.COLUMNS, "app")
        sidebar = self.make(qtbot, schema)
        tree = sidebar.tree_widget
        sidebar.table_item("customers").setExpanded(True)
        tree.setCurrentItem(sidebar.table_item("customers").child(1))
        with qtbot.waitSignal(sidebar.column_chosen) as blocker:
            qtbot.keyClick(tree, Qt.Key.Key_Return)
        assert blocker.args == [self.TABLES[0], "full name"]

    def test_context_menu(self, qtbot):
        schema = SchemaModel()
        schema.set_columns("customers", self.COLUMNS, "app")
        sidebar = self.make(qtbot, schema)
        menu = sidebar.context_menu(sidebar.database_item("app"))
        texts = [a.text() for a in menu.actions()]
        assert texts == [TableSidebar.USE_TEXT, TableSidebar.COPY_TEXT]
        assert not menu.actions()[0].isEnabled()  # already active
        table = sidebar.table_item("customers")
        table.setExpanded(True)
        menu = sidebar.context_menu(table)
        texts = [a.text() for a in menu.actions()]
        assert texts == [TableSidebar.PREPARE_TEXT, TableSidebar.COPY_TEXT]
        with qtbot.waitSignal(sidebar.table_chosen):
            menu.actions()[0].trigger()
        menu.actions()[1].trigger()
        assert QApplication.clipboard().text() == "customers"
        menu = sidebar.context_menu(table.child(1))
        texts = [a.text() for a in menu.actions()]
        assert texts == [
            TableSidebar.COLUMN_TEXT,
            TableSidebar.ADD_TEXT,
            TableSidebar.COPY_TEXT,
        ]
        with qtbot.waitSignal(sidebar.column_chosen) as blocker:
            menu.actions()[0].trigger()
        assert blocker.args == [self.TABLES[0], "full name"]
        with qtbot.waitSignal(sidebar.column_added) as blocker:
            menu.actions()[1].trigger()
        assert blocker.args == [self.TABLES[0], "full name"]

    def test_use_database_from_the_menu(self, qtbot):
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        sidebar.set_databases(["app", "shop"], "app")
        menu = sidebar.context_menu(sidebar.database_item("shop"))
        assert menu.actions()[0].isEnabled()
        with qtbot.waitSignal(sidebar.database_selected) as blocker:
            menu.actions()[0].trigger()
        assert blocker.args == ["shop"]

    def test_shift_adds_the_column(self, qtbot):
        schema = SchemaModel()
        schema.set_columns("customers", self.COLUMNS, "app")
        sidebar = self.make(qtbot, schema)
        tree = sidebar.tree_widget
        sidebar.table_item("customers").setExpanded(True)
        column = sidebar.table_item("customers").child(1)
        center = self.center(tree, column)
        chosen, added = [], []
        sidebar.column_chosen.connect(lambda t, c: chosen.append(c))
        sidebar.column_added.connect(lambda t, c: added.append(c))
        shift = Qt.KeyboardModifier.ShiftModifier
        viewport = tree.viewport()
        left = Qt.MouseButton.LeftButton
        qtbot.mouseClick(viewport, left, shift, pos=center)
        assert (chosen, added) == ([], [])  # a click alone does nothing
        qtbot.mousePress(viewport, left, shift, pos=center)
        qtbot.mouseDClick(viewport, left, shift, pos=center)
        assert (chosen, added) == ([], ["full name"])
        qtbot.mousePress(viewport, left, pos=center)
        qtbot.mouseDClick(viewport, left, pos=center)
        assert (chosen, added) == (["full name"], ["full name"])
        tree.setCurrentItem(column)
        qtbot.keyClick(tree, Qt.Key.Key_Return, shift)
        assert added == ["full name", "full name"]

    def test_filter(self, qtbot):
        sidebar = self.make(
            qtbot,
            tables=[
                TableInfo("customers"),
                TableInfo("orders"),
                TableInfo("users"),
            ],
        )
        sidebar.filter_edit.setText("US")
        assert sidebar.visible_tables() == ["customers", "users"]
        assert sidebar.status_label.text() == "2 of 3 tables"
        # A reload keeps the filter.
        sidebar.set_tables([TableInfo("customers"), TableInfo("orders")], "app")
        assert sidebar.visible_tables() == ["customers"]
        sidebar.filter_edit.clear()
        assert sidebar.visible_tables() == ["customers", "orders"]
        assert sidebar.status_label.text() == "2 tables"

    def test_filter_on_database_names(self, qtbot):
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        sidebar.set_databases(["app", "shop"])
        sidebar.set_tables([TableInfo("users", database="app")], "app")
        sidebar.set_tables([TableInfo("orders", database="shop")], "shop")
        sidebar.filter_edit.setText("sho")
        assert sidebar.visible_tables() == ["orders"]
        assert sidebar.database_item("app").isHidden()
        sidebar.filter_edit.setText("user")
        assert sidebar.visible_tables() == ["users"]
        assert sidebar.database_item("shop").isHidden()

    def test_reload_keeps_expanded_tables(self, qtbot):
        schema = SchemaModel()
        schema.set_columns("customers", self.COLUMNS, "app")
        sidebar = self.make(qtbot, schema)
        sidebar.table_item("customers").setExpanded(True)
        sidebar.set_tables(self.TABLES, "app")
        assert sidebar.table_item("customers").isExpanded()
        assert sidebar.column_names("customers") == ["id", "full name"]

    def test_status_messages(self, qtbot):
        sidebar = self.make(qtbot, tables=[])
        assert sidebar.status_label.text() == TableSidebar.NO_TABLES
        sidebar.set_tables(self.TABLES, "app")
        sidebar.set_loading()
        assert len(sidebar.tables()) == 2
        assert sidebar.status_label.text() == TableSidebar.LOADING
        assert not sidebar.refresh_button.isEnabled()
        sidebar.set_error("Access denied")
        assert sidebar.tree_widget.topLevelItemCount() == 0
        assert sidebar.status_label.text() == "Access denied"
        assert sidebar.refresh_button.isEnabled()
        sidebar.show_message(TableSidebar.NOT_CONNECTED)
        assert not sidebar.refresh_button.isEnabled()

    def test_truncated_list_is_signalled(self, qtbot):
        tables = [
            TableInfo("t{}".format(i)) for i in range(TableCatalog.MAX_TABLES)
        ]
        sidebar = self.make(qtbot, tables=tables)
        assert "Showing only the first" in sidebar.status_label.text()

    def test_write_access_colors_and_warning(self, qtbot):
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        sidebar.set_write_access({"shop": "INSERT, UPDATE"})
        sidebar.set_databases(["app", "shop"], "app")
        app = sidebar.database_item("app")
        shop = sidebar.database_item("shop")
        assert sidebar.is_writable("app") is False
        assert sidebar.is_writable("shop") is True
        assert app.foreground(0).color().name() == TableSidebar.READ_ONLY_COLOR
        assert shop.foreground(0).color().name() == TableSidebar.WRITE_COLOR
        assert app.icon(1).isNull()
        assert not shop.icon(1).isNull()
        assert "read-only" in app.toolTip(0)
        assert "INSERT, UPDATE" in shop.toolTip(0)
        # The marks survive a change of the active database.
        sidebar.set_active_database("shop")
        assert not shop.icon(1).isNull()
        assert shop.text(1) == "active"

    def test_unknown_write_access_has_no_colors(self, qtbot):
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        sidebar.set_databases(["app"])
        item = sidebar.database_item("app")
        assert sidebar.is_writable("app") is None
        assert item.icon(1).isNull()
        assert item.data(0, Qt.ItemDataRole.ForegroundRole) is None
        sidebar.set_write_access({"app": "DELETE"})
        sidebar.show_message(TableSidebar.NOT_CONNECTED)
        assert sidebar.is_writable("app") is None

    def test_server_text_is_never_rendered_as_html(self, qtbot):
        schema = SchemaModel()
        schema.set_columns(
            "<b>t</b>",
            (ColumnInfo("<img src='x'>", comment="<a href='y'>z</a>"),),
            "app",
        )
        sidebar = self.make(qtbot, schema, tables=[TableInfo("<b>t</b>")])
        item = sidebar.table_item("<b>t</b>")
        item.setExpanded(True)
        assert "&lt;b&gt;" in item.toolTip(0)
        column = item.child(0)
        assert column.text(0) == "<img src='x'>"  # item text is plain
        assert "<img" not in column.toolTip(0)
        assert "<a " not in column.toolTip(0)
        sidebar.set_error("<b>denied</b>")
        assert sidebar.status_label.textFormat() == Qt.TextFormat.PlainText
