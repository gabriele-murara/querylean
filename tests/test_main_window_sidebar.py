"""GUI tests of the table side bar inside the main window."""

import pytest
from mysql.connector import errors as mysql_errors
from PySide6.QtCore import Qt

from fakes.schema_handler import SchemaHandler
from querylean.config.config_manager import ConfigManager
from querylean.database.schema.table_info import TableInfo
from querylean.ui.main.connection_state import ConnectionState
from querylean.ui.sidebar.table_sidebar import TableSidebar
from support.main_window_test_base import MainWindowTestBase


class TestMainWindowSidebar(MainWindowTestBase):
    """Loading on connect, choice of a table, refresh, errors, layout."""

    @pytest.fixture
    def handler(self, connector):
        handler = SchemaHandler(
            [("customers", "BASE TABLE"), ("order items", "VIEW")]
        )
        connector.configure = lambda conn: setattr(conn, "handler", handler)
        return handler

    @classmethod
    def wait_tables(cls, qtbot, window, count) -> None:
        qtbot.waitUntil(
            lambda: window.sidebar.tree_widget.topLevelItemCount() == count,
            timeout=cls.WAIT_MS,
        )

    def test_sidebar_is_left_of_editor_and_results(self, window):
        splitter = window.sidebar_splitter
        assert splitter.widget(0) is window.sidebar
        assert splitter.widget(1) is window.splitter
        assert splitter.sizes()[0] > 0

    def test_tables_load_on_connect(self, qtbot, window, handler):
        assert window.sidebar.status_label.text() == TableSidebar.NOT_CONNECTED
        self.connect(qtbot, window)
        self.wait_tables(qtbot, window, 2)
        assert window.sidebar.tables() == [
            TableInfo("customers"),
            TableInfo("order items", is_view=True),
        ]

    def test_choosing_a_table_fills_the_editor(self, qtbot, window, handler):
        self.connect(qtbot, window)
        self.wait_tables(qtbot, window, 2)
        window.editor.setPlainText("SELECT 1")
        window.sidebar.table_chosen.emit(window.sidebar.tables()[1])
        text = window.editor.toPlainText()
        assert text == "SELECT * FROM `order items` LIMIT 1;"
        assert window.running is False  # filled, not executed
        window.editor.undo()
        assert window.editor.toPlainText() == "SELECT 1"

    def test_click_and_double_click_fill_the_editor(
        self, qtbot, window, handler
    ):
        self.connect(qtbot, window)
        self.wait_tables(qtbot, window, 2)
        window.editor.setPlainText("SELECT 1")
        tree = window.sidebar.tree_widget
        center = tree.visualItemRect(tree.topLevelItem(0)).center()
        qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=center)
        expected = "SELECT * FROM `customers` LIMIT 1;"
        assert window.editor.toPlainText() == expected
        assert tree.topLevelItem(0).isExpanded()
        assert window.running is False
        # The second click of a double click changes nothing more.
        qtbot.mousePress(tree.viewport(), Qt.MouseButton.LeftButton, pos=center)
        qtbot.mouseDClick(
            tree.viewport(), Qt.MouseButton.LeftButton, pos=center
        )
        assert window.editor.toPlainText() == expected
        window.editor.undo()
        assert window.editor.toPlainText() == "SELECT 1"

    def test_chosen_query_runs(self, qtbot, window, handler):
        self.connect(qtbot, window)
        self.wait_tables(qtbot, window, 2)
        window.use_table(window.sidebar.tables()[0])
        window.execute_query()
        qtbot.waitUntil(lambda: not window.running, timeout=self.WAIT_MS)
        assert window.results.results_model.rowCount() == 1

    def test_refresh_reloads(self, qtbot, window, handler):
        self.connect(qtbot, window)
        self.wait_tables(qtbot, window, 2)
        handler.tables.append(("suppliers", "BASE TABLE"))
        window.sidebar.refresh_button.click()
        self.wait_tables(qtbot, window, 3)
        assert window.sidebar.refresh_button.isEnabled()

    def test_disconnect_clears_the_list(self, qtbot, window, handler):
        self.connect(qtbot, window)
        self.wait_tables(qtbot, window, 2)
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.state == ConnectionState.DISCONNECTED,
            timeout=self.WAIT_MS,
        )
        assert window.sidebar.tree_widget.topLevelItemCount() == 0
        assert window.sidebar.status_label.text() == TableSidebar.NOT_CONNECTED
        window.refresh_tables()  # ignored when disconnected
        assert window.sidebar.status_label.text() == TableSidebar.NOT_CONNECTED

    def test_listing_error_is_shown(self, qtbot, window, handler):
        handler.error = mysql_errors.ProgrammingError(
            msg="Access denied", errno=1142
        )
        self.connect(qtbot, window)
        qtbot.waitUntil(
            lambda: (
                window.sidebar.status_label.text()
                not in (TableSidebar.NOT_CONNECTED, TableSidebar.LOADING)
            ),
            timeout=self.WAIT_MS,
        )
        assert window.sidebar.tree_widget.topLevelItemCount() == 0
        assert window.sidebar.refresh_button.isEnabled()
        assert window.state == ConnectionState.CONNECTED

    def test_sidebar_width_is_saved(self, qtbot, window, tmp_path):
        window.close()
        saved = ConfigManager(tmp_path / "config.json").load()
        assert saved.ui.sidebar_state
