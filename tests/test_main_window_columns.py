"""GUI tests of the columns in the side bar and in the completion."""

import pytest
from mysql.connector import errors as mysql_errors
from PySide6.QtCore import Qt

from fakes.schema_handler import SchemaHandler
from querylean.database.schema.column_catalog import ColumnCatalog
from querylean.ui.main.connection_state import ConnectionState
from querylean.ui.sidebar.table_sidebar import TableSidebar
from support.main_window_test_base import MainWindowTestBase


class TestMainWindowColumns(MainWindowTestBase):
    """Loading on connect, on demand, errors, insertion, disconnection."""

    COLUMNS = {
        "customers": [
            ("id", "int", "NO", "PRI", None, "auto_increment", ""),
            ("full name", "varchar(64)", "YES", "", None, "", ""),
        ],
    }

    @pytest.fixture
    def handler(self, connector):
        handler = SchemaHandler(
            [("customers", "BASE TABLE"), ("order items", "VIEW")],
            self.COLUMNS,
        )
        connector.configure = lambda conn: setattr(conn, "handler", handler)
        return handler

    def wait_columns(self, qtbot, window) -> None:
        qtbot.waitUntil(
            lambda: window.schema.has_columns("customers"),
            timeout=self.WAIT_MS,
        )

    def test_columns_load_on_connect(self, qtbot, window, handler):
        self.connect(qtbot, window)
        self.wait_columns(qtbot, window)
        assert ColumnCatalog.ALL_STATEMENT in handler.statements
        assert window.schema.database == "app"
        names = [c.name for c in window.schema.columns_of("customers")]
        assert names == ["id", "full name"]
        qtbot.waitUntil(
            lambda: window.sidebar.table_item("customers") is not None,
            timeout=self.WAIT_MS,
        )
        window.sidebar.table_item("customers").setExpanded(True)
        assert window.sidebar.column_names("customers") == ["id", "full name"]

    def test_completion_uses_the_columns(self, qtbot, window, handler):
        self.connect(qtbot, window)
        self.wait_columns(qtbot, window)
        editor = window.editor
        editor.setPlainText("SELECT c. FROM customers c")
        cursor = editor.textCursor()
        cursor.setPosition(9)
        editor.setTextCursor(cursor)
        editor.setFocus()
        result = editor.complete()
        assert [i.label for i in result.items] == ["id", "full name"]

    def test_missing_columns_are_read_on_demand(self, qtbot, window, handler):
        self.connect(qtbot, window)
        self.wait_columns(qtbot, window)
        assert not window.schema.has_columns("order items")
        handler.columns["order items"] = [
            ("code", "char(3)", "NO", "", None, "", "")
        ]
        window.sidebar.table_item("order items").setExpanded(True)
        qtbot.waitUntil(
            lambda: window.sidebar.column_names("order items") == ["code"],
            timeout=self.WAIT_MS,
        )
        statement = ColumnCatalog.table_statement("order items")
        assert handler.statements.count(statement) == 1
        # Known now: not requested again.
        window.load_columns("order items")
        assert handler.statements.count(statement) == 1

    def test_column_errors_are_shown_once(self, qtbot, window, handler):
        self.connect(qtbot, window)
        self.wait_columns(qtbot, window)
        handler.columns["order items"] = []
        handler.columns_error = mysql_errors.ProgrammingError(
            msg="denied", errno=1142
        )
        window.sidebar.table_item("order items").setExpanded(True)
        item = window.sidebar.table_item("order items")
        qtbot.waitUntil(
            lambda: item.child(0).text(0) == TableSidebar.NO_COLUMNS,
            timeout=self.WAIT_MS,
        )
        assert window.state == ConnectionState.CONNECTED
        assert window.schema.columns_of("order items") == ()

    def test_listing_error_falls_back_to_tables(self, qtbot, window, handler):
        handler.columns_error = mysql_errors.ProgrammingError(
            msg="denied", errno=1142
        )
        self.connect(qtbot, window)
        qtbot.waitUntil(
            lambda: window.sidebar.table_item("customers") is not None,
            timeout=self.WAIT_MS,
        )
        assert not window.schema.has_columns("customers")
        assert window.state == ConnectionState.CONNECTED

    def test_chosen_column_goes_to_the_editor(self, qtbot, window, handler):
        self.connect(qtbot, window)
        self.wait_columns(qtbot, window)
        window.editor.setPlainText("SELECT  FROM customers")
        cursor = window.editor.textCursor()
        cursor.setPosition(7)
        window.editor.setTextCursor(cursor)
        window.sidebar.column_chosen.emit("full name")
        assert window.editor.toPlainText() == (
            "SELECT `full name` FROM customers"
        )

    def test_double_click_on_a_column(self, qtbot, window, handler):
        self.connect(qtbot, window)
        self.wait_columns(qtbot, window)
        tree = window.sidebar.tree_widget
        window.sidebar.table_item("customers").setExpanded(True)
        tree.setCurrentItem(window.sidebar.table_item("customers").child(0))
        window.editor.setPlainText("")
        qtbot.keyClick(tree, Qt.Key.Key_Return)
        assert window.editor.toPlainText() == "id"

    def test_disconnect_clears_the_schema(self, qtbot, window, handler):
        self.connect(qtbot, window)
        self.wait_columns(qtbot, window)
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.DISCONNECTED,
            timeout=self.WAIT_MS,
        )
        assert window.schema.tables == []
        assert window.schema.columns_of("customers") is None
        window.load_columns("customers")  # ignored when disconnected
        assert window.schema.columns_of("customers") is None
