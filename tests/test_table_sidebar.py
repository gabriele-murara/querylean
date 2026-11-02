"""GUI tests of the table side bar."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from querylean.completion.schema_model import SchemaModel
from querylean.database.schema.column_info import ColumnInfo
from querylean.database.schema.table_catalog import TableCatalog
from querylean.database.schema.table_info import TableInfo
from querylean.ui.sidebar.table_sidebar import TableSidebar


class TestTableSidebar:
    """Tree of tables and columns, filter, signals and status messages."""

    TABLES = [TableInfo("customers"), TableInfo("v_totals", is_view=True)]
    COLUMNS = (
        ColumnInfo("id", "int", nullable=False, key="PRI"),
        ColumnInfo("full name", "varchar(64)", comment="Shown name"),
    )

    def make(self, qtbot, schema=None) -> TableSidebar:
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        sidebar.set_schema(schema)
        sidebar.show()
        return sidebar

    def test_starts_not_connected(self, qtbot):
        sidebar = self.make(qtbot)
        assert sidebar.tree_widget.topLevelItemCount() == 0
        assert sidebar.status_label.text() == TableSidebar.NOT_CONNECTED
        assert not sidebar.refresh_button.isEnabled()

    def test_lists_tables_and_marks_views(self, qtbot):
        sidebar = self.make(qtbot)
        sidebar.set_tables(self.TABLES)
        assert sidebar.tables() == self.TABLES
        tree = sidebar.tree_widget
        items = [tree.topLevelItem(i) for i in range(2)]
        assert [i.text(0) for i in items] == ["customers", "v_totals"]
        assert not items[0].font(0).italic()
        assert items[1].font(0).italic()
        assert sidebar.status_label.text() == "2 tables"
        assert sidebar.refresh_button.isEnabled()

    def test_double_click_and_enter_choose_the_table(self, qtbot):
        sidebar = self.make(qtbot)
        sidebar.set_tables(self.TABLES)
        tree = sidebar.tree_widget
        rect = tree.visualItemRect(tree.topLevelItem(1))
        # A real double click is press/release then a double click event.
        qtbot.mouseClick(
            tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center()
        )
        with qtbot.waitSignal(sidebar.table_chosen) as blocker:
            qtbot.mousePress(
                tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center()
            )
            qtbot.mouseDClick(
                tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center()
            )
        assert blocker.args == [self.TABLES[1]]
        tree.setCurrentItem(tree.topLevelItem(0))
        with qtbot.waitSignal(sidebar.table_chosen) as blocker:
            qtbot.keyClick(tree, Qt.Key.Key_Return)
        assert blocker.args == [self.TABLES[0]]

    def test_click_chooses_the_table_and_shows_the_columns(self, qtbot):
        schema = SchemaModel()
        schema.set_columns("customers", self.COLUMNS)
        sidebar = self.make(qtbot, schema)
        sidebar.set_tables(self.TABLES)
        tree = sidebar.tree_widget
        chosen = []
        sidebar.table_chosen.connect(chosen.append)
        rect = tree.visualItemRect(tree.topLevelItem(0))
        qtbot.mouseClick(
            tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center()
        )
        assert tree.topLevelItem(0).isExpanded()
        assert chosen == [self.TABLES[0]]
        assert sidebar.column_names("customers") == ["id", "full name"]
        key = tree.topLevelItem(0).child(0)
        assert key.font(0).bold()
        assert key.text(1) == "int"
        assert "primary key" in key.toolTip(0)
        assert "Shown name" in tree.topLevelItem(0).child(1).toolTip(0)

    def test_unknown_columns_are_requested(self, qtbot):
        schema = SchemaModel()
        sidebar = self.make(qtbot, schema)
        sidebar.set_tables(self.TABLES)
        item = sidebar.table_item("v_totals")
        with qtbot.waitSignal(sidebar.columns_requested) as blocker:
            item.setExpanded(True)
        assert blocker.args == ["v_totals"]
        assert item.child(0).text(0) == TableSidebar.LOADING_COLUMNS
        schema.set_columns("v_totals", self.COLUMNS)
        sidebar.refresh_columns()
        assert sidebar.column_names("v_totals") == ["id", "full name"]

    def test_column_errors(self, qtbot):
        schema = SchemaModel()
        sidebar = self.make(qtbot, schema)
        sidebar.set_tables(self.TABLES)
        sidebar.table_item("customers").setExpanded(True)
        sidebar.set_columns_error("customers", "Access denied")
        child = sidebar.table_item("customers").child(0)
        assert child.text(0) == TableSidebar.NO_COLUMNS
        assert child.toolTip(0) == "Access denied"

    def test_column_is_chosen(self, qtbot):
        schema = SchemaModel()
        schema.set_columns("customers", self.COLUMNS)
        sidebar = self.make(qtbot, schema)
        sidebar.set_tables(self.TABLES)
        tree = sidebar.tree_widget
        tree.topLevelItem(0).setExpanded(True)
        tree.setCurrentItem(tree.topLevelItem(0).child(1))
        with qtbot.waitSignal(sidebar.column_chosen) as blocker:
            qtbot.keyClick(tree, Qt.Key.Key_Return)
        assert blocker.args == [self.TABLES[0], "full name"]

    def test_context_menu(self, qtbot):
        schema = SchemaModel()
        schema.set_columns("customers", self.COLUMNS)
        sidebar = self.make(qtbot, schema)
        sidebar.set_tables(self.TABLES)
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

    def test_shift_adds_the_column(self, qtbot):
        schema = SchemaModel()
        schema.set_columns("customers", self.COLUMNS)
        sidebar = self.make(qtbot, schema)
        sidebar.set_tables(self.TABLES)
        tree = sidebar.tree_widget
        sidebar.table_item("customers").setExpanded(True)
        column = sidebar.table_item("customers").child(1)
        center = tree.visualItemRect(column).center()
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
        sidebar = self.make(qtbot)
        sidebar.set_tables(
            [TableInfo("customers"), TableInfo("orders"), TableInfo("users")]
        )
        sidebar.filter_edit.setText("US")
        assert sidebar.visible_tables() == ["customers", "users"]
        assert sidebar.status_label.text() == "2 of 3 tables"
        # A reload keeps the filter.
        sidebar.set_tables([TableInfo("customers"), TableInfo("orders")])
        assert sidebar.visible_tables() == ["customers"]
        sidebar.filter_edit.clear()
        assert sidebar.visible_tables() == ["customers", "orders"]
        assert sidebar.status_label.text() == "2 tables"

    def test_reload_keeps_expanded_tables(self, qtbot):
        schema = SchemaModel()
        schema.set_columns("customers", self.COLUMNS)
        sidebar = self.make(qtbot, schema)
        sidebar.set_tables(self.TABLES)
        sidebar.table_item("customers").setExpanded(True)
        sidebar.set_tables(self.TABLES)
        assert sidebar.table_item("customers").isExpanded()
        assert sidebar.column_names("customers") == ["id", "full name"]

    def test_status_messages(self, qtbot):
        sidebar = self.make(qtbot)
        sidebar.set_tables([])
        assert sidebar.status_label.text() == TableSidebar.NO_TABLES
        sidebar.set_tables(self.TABLES)
        sidebar.set_loading()
        assert sidebar.tree_widget.topLevelItemCount() == 2
        assert sidebar.status_label.text() == TableSidebar.LOADING
        assert not sidebar.refresh_button.isEnabled()
        sidebar.set_error("Access denied")
        assert sidebar.tree_widget.topLevelItemCount() == 0
        assert sidebar.status_label.text() == "Access denied"
        assert sidebar.refresh_button.isEnabled()
        sidebar.show_message(TableSidebar.NOT_CONNECTED)
        assert not sidebar.refresh_button.isEnabled()

    def test_truncated_list_is_signalled(self, qtbot):
        sidebar = self.make(qtbot)
        tables = [
            TableInfo("t{}".format(i)) for i in range(TableCatalog.MAX_TABLES)
        ]
        sidebar.set_tables(tables)
        assert "Showing only the first" in sidebar.status_label.text()
