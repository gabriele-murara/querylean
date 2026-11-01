"""GUI tests of the table side bar."""

from PySide6.QtCore import Qt

from querylean.database.schema.table_catalog import TableCatalog
from querylean.database.schema.table_info import TableInfo
from querylean.ui.sidebar.table_sidebar import TableSidebar


class TestTableSidebar:
    """Listing, views, choice signal and status messages."""

    TABLES = [TableInfo("customers"), TableInfo("v_totals", is_view=True)]

    def test_starts_not_connected(self, qtbot):
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        assert sidebar.list_widget.count() == 0
        assert sidebar.status_label.text() == TableSidebar.NOT_CONNECTED
        assert not sidebar.refresh_button.isEnabled()

    def test_lists_tables_and_marks_views(self, qtbot):
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        sidebar.set_tables(self.TABLES)
        assert sidebar.tables() == self.TABLES
        items = [sidebar.list_widget.item(i) for i in range(2)]
        assert [i.text() for i in items] == ["customers", "v_totals"]
        assert not items[0].font().italic()
        assert items[1].font().italic()
        assert sidebar.status_label.text() == "2 tabelle"
        assert sidebar.refresh_button.isEnabled()

    def test_click_and_enter_choose_the_table(self, qtbot):
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        sidebar.show()
        sidebar.set_tables(self.TABLES)
        view = sidebar.list_widget
        rect = view.visualItemRect(view.item(1))
        with qtbot.waitSignal(sidebar.table_chosen) as blocker:
            qtbot.mouseClick(
                view.viewport(), Qt.MouseButton.LeftButton, pos=rect.center()
            )
        assert blocker.args == [self.TABLES[1]]
        view.setCurrentRow(0)
        with qtbot.waitSignal(sidebar.table_chosen) as blocker:
            qtbot.keyClick(view, Qt.Key.Key_Return)
        assert blocker.args == [self.TABLES[0]]

    def test_status_messages(self, qtbot):
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        sidebar.set_tables([])
        assert sidebar.status_label.text() == TableSidebar.NO_TABLES
        sidebar.set_tables(self.TABLES)
        sidebar.set_loading()
        assert sidebar.list_widget.count() == 2
        assert sidebar.status_label.text() == TableSidebar.LOADING
        assert not sidebar.refresh_button.isEnabled()
        sidebar.set_error("Accesso negato")
        assert sidebar.list_widget.count() == 0
        assert sidebar.status_label.text() == "Accesso negato"
        assert sidebar.refresh_button.isEnabled()
        sidebar.show_message(TableSidebar.NOT_CONNECTED)
        assert not sidebar.refresh_button.isEnabled()

    def test_truncated_list_is_signalled(self, qtbot):
        sidebar = TableSidebar()
        qtbot.addWidget(sidebar)
        tables = [
            TableInfo("t{}".format(i)) for i in range(TableCatalog.MAX_TABLES)
        ]
        sidebar.set_tables(tables)
        assert "Mostrate solo le prime" in sidebar.status_label.text()
