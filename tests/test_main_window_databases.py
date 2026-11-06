"""GUI tests of connections that cover all the accessible databases."""

import pytest

from fakes.schema_handler import SchemaHandler
from querylean.config.connection_config import ConnectionConfig
from querylean.database.schema.column_catalog import ColumnCatalog
from querylean.database.schema.table_catalog import TableCatalog
from querylean.database.schema.table_info import TableInfo
from querylean.ui.main.connection_state import ConnectionState
from support.main_window_test_base import MainWindowTestBase


class TestMainWindowDatabases(MainWindowTestBase):
    """Database list, active database, qualified previews, completion."""

    SHOP = (
        [("orders", "BASE TABLE")],
        {"orders": [("id", "int", "NO", "PRI", None, "", "")]},
    )
    CRM = ([("notes", "BASE TABLE")], {})

    @pytest.fixture
    def handler(self, connector):
        handler = SchemaHandler(schemas={"shop": self.SHOP, "crm": self.CRM})

        def configure(conn):
            conn.handler = handler
            conn.databases = ["information_schema", "shop", "crm"]

        connector.configure = configure
        return handler

    def open(self, qtbot, window, database="") -> None:
        window.save_connection(
            ConnectionConfig(
                host="db",
                username="ro",
                database=database,
                all_databases=True,
            ),
            "pw",
            remember=False,
        )
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.CONNECTED,
            timeout=self.WAIT_MS,
        )
        qtbot.waitUntil(
            lambda: len(window.sidebar.databases()) == 3,
            timeout=self.WAIT_MS,
        )

    def test_lists_the_databases(self, qtbot, window, handler, connector):
        self.open(qtbot, window)
        assert window.all_databases
        assert window.sidebar.databases() == [
            "information_schema",
            "shop",
            "crm",
        ]
        assert window.schema.database == ""
        assert "database" not in connector.connections[0].kwargs
        assert "db:" not in window.state_label.text()
        # Nothing is expanded: no table listing yet.
        assert TableCatalog.list_statement("shop") not in handler.statements

    def test_selecting_a_database_makes_it_active(
        self, qtbot, window, handler, connector
    ):
        self.open(qtbot, window)
        window.sidebar.database_selected.emit("shop")
        qtbot.waitUntil(
            lambda: window.schema.database == "shop", timeout=self.WAIT_MS
        )
        assert connector.connections[0].init_db == ["shop"]
        assert "db: <b>shop</b>" in window.state_label.text()
        assert window.sidebar.active_database == "shop"
        assert "Active database: shop" in window.message_label.text()
        # The tables and columns of the active database are read.
        qtbot.waitUntil(
            lambda: window.schema.has_columns("orders", "shop"),
            timeout=self.WAIT_MS,
        )
        assert TableCatalog.list_statement("shop") in handler.statements
        assert ColumnCatalog.all_statement("shop") in handler.statements
        # Selecting it again changes nothing.
        window.select_database("shop")
        assert connector.connections[0].init_db == ["shop"]

    def test_unknown_database_is_reported(self, qtbot, window, handler):
        self.open(qtbot, window)
        window.select_database("nowhere")
        qtbot.waitUntil(
            lambda: "nowhere" in window.message_label.text(),
            timeout=self.WAIT_MS,
        )
        assert window.schema.database == ""

    def test_initial_database_is_active(self, qtbot, window, handler):
        self.open(qtbot, window, database="crm")
        assert window.schema.database == "crm"
        qtbot.waitUntil(
            lambda: window.schema.has_tables("crm"), timeout=self.WAIT_MS
        )
        assert window.sidebar.active_database == "crm"

    def test_tables_preview_is_qualified(self, qtbot, window, handler):
        self.open(qtbot, window)
        window.sidebar.database_item("shop").setExpanded(True)
        qtbot.waitUntil(
            lambda: (
                window.sidebar.tables("shop")
                == [TableInfo("orders", database="shop")]
            ),
            timeout=self.WAIT_MS,
        )
        table = window.sidebar.tables("shop")[0]
        window.sidebar.table_chosen.emit(table)
        assert window.editor.toPlainText() == (
            "SELECT * FROM `shop`.`orders` LIMIT 1;"
        )
        window.sidebar.column_added.emit(table, "id")
        assert window.editor.toPlainText() == (
            "SELECT `id` FROM `shop`.`orders` LIMIT 1;"
        )

    def test_completion_with_database_qualifier(self, qtbot, window, handler):
        self.open(qtbot, window)
        editor = window.editor
        editor.setFocus()
        editor.setPlainText("SELECT * FROM ")
        editor.moveCursor(editor.textCursor().MoveOperation.End)
        result = editor.complete()
        labels = [item.label for item in result.items]
        assert "shop" in labels and "crm" in labels
        editor.setPlainText("SELECT * FROM shop.")
        editor.moveCursor(editor.textCursor().MoveOperation.End)
        result = editor.complete()
        # The tables of "shop" are read on demand, then proposed.
        assert result.missing_databases == ("shop",)
        qtbot.waitUntil(
            lambda: window.schema.has_tables("shop"), timeout=self.WAIT_MS
        )
        result = editor.complete()
        assert [item.label for item in result.items] == ["orders"]

    def test_refresh_reloads_the_databases(self, qtbot, window, handler):
        self.open(qtbot, window)
        window.sidebar.database_selected.emit("shop")
        qtbot.waitUntil(
            lambda: window.schema.has_tables("shop"), timeout=self.WAIT_MS
        )
        handler.schemas["shop"][0].append(("invoices", "BASE TABLE"))
        window.refresh_tables()
        qtbot.waitUntil(
            lambda: len(window.sidebar.tables("shop")) == 2,
            timeout=self.WAIT_MS,
        )
        assert window.schema.database == "shop"
