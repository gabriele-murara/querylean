"""GUI tests of the export of the displayed result."""

import csv
import json
from pathlib import Path

from openpyxl import load_workbook
from PySide6.QtWidgets import QFileDialog, QToolBar, QToolButton

from support.main_window_test_base import MainWindowTestBase


class TestMainWindowExport(MainWindowTestBase):
    """ "Export" action: availability, formats, truncation notice, errors."""

    @classmethod
    def export(cls, qtbot, window, path) -> None:
        window.export_to(path)
        qtbot.waitUntil(lambda: not window.exporting, timeout=cls.WAIT_MS)

    def test_disabled_without_result(self, qtbot, window):
        assert not window.export_action.isEnabled()
        self.connect(qtbot, window)
        assert not window.export_action.isEnabled()

    def test_enabled_after_query(self, qtbot, window):
        self.connect(qtbot, window)
        self.run(qtbot, window, "SELECT n FROM t")
        assert window.export_action.isEnabled()

    def test_disabled_for_result_without_columns(
        self, qtbot, window, connector
    ):
        self.connect(qtbot, window)
        connector.connections[0].handler = lambda sql: ([], [])
        self.run(qtbot, window, "SELECT n FROM t")
        assert not window.export_action.isEnabled()

    def test_exports_every_format(self, qtbot, window, tmp_path):
        self.connect(qtbot, window)
        self.run(qtbot, window, "SELECT n FROM t")

        self.export(qtbot, window, tmp_path / "r.csv")
        assert "Exported 3 rows" in window.message_label.text()
        with (tmp_path / "r.csv").open(encoding="utf-8", newline="") as f:
            assert list(csv.reader(f)) == [["n"], ["0"], ["1"], ["2"]]

        self.export(qtbot, window, tmp_path / "r.json")
        data = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
        assert data == [{"n": 0}, {"n": 1}, {"n": 2}]

        self.export(qtbot, window, tmp_path / "r.xlsx")
        sheet = load_workbook(tmp_path / "r.xlsx").active
        assert [c.value for c in sheet["A"]] == ["n", 0, 1, 2]
        assert window.export_action.isEnabled()

    def test_truncated_result_is_noted(
        self, qtbot, window, connector, tmp_path
    ):
        self.connect(qtbot, window)
        window.active_connection.config.row_limit = 100
        connector.connections[0].row_count = 5000
        self.run(qtbot, window, "SELECT n FROM t")
        self.export(qtbot, window, tmp_path / "r.csv")
        text = window.message_label.text()
        assert "Exported 100 rows" in text
        assert "limited to the first 100 rows" in text

    def test_export_still_possible_after_disconnect(
        self, qtbot, window, tmp_path
    ):
        self.connect(qtbot, window)
        self.run(qtbot, window, "SELECT n FROM t")
        window.toggle_connection()
        qtbot.waitUntil(
            lambda: window.connect_action.text() == "Connect",
            timeout=self.WAIT_MS,
        )
        assert window.export_action.isEnabled()
        self.export(qtbot, window, tmp_path / "r.csv")
        assert (tmp_path / "r.csv").exists()

    def test_unsupported_extension(self, qtbot, window, tmp_path):
        self.connect(qtbot, window)
        self.run(qtbot, window, "SELECT n FROM t")
        window.export_to(tmp_path / "r.txt")
        assert not window.exporting
        assert "Unsupported format" in window.message_label.text()
        assert not (tmp_path / "r.txt").exists()

    def test_write_error_is_shown(self, qtbot, window, tmp_path):
        self.connect(qtbot, window)
        self.run(qtbot, window, "SELECT n FROM t")
        self.export(qtbot, window, tmp_path / "missing" / "r.csv")
        assert "Cannot write" in window.message_label.text()
        assert window.export_action.isEnabled()

    def test_dialog_adds_extension_of_selected_format(
        self, qtbot, window, tmp_path, monkeypatch
    ):
        self.connect(qtbot, window)
        self.run(qtbot, window, "SELECT n FROM t")
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            lambda *args: (str(tmp_path / "r"), "JSON (*.json)"),
        )
        window.export_results()
        qtbot.waitUntil(lambda: not window.exporting, timeout=self.WAIT_MS)
        assert (tmp_path / "r.json").exists()

    def test_dialog_cancelled(self, qtbot, window, tmp_path, monkeypatch):
        self.connect(qtbot, window)
        self.run(qtbot, window, "SELECT n FROM t")
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", lambda *args: ("", "")
        )
        window.export_results()
        assert not window.exporting
        assert list(tmp_path.glob("r*")) == []

    def test_toolbar_button_opens_format_menu(self, window):
        texts = [a.text() for a in window.export_menu.actions()]
        assert texts == [
            "Excel (.xlsx)",
            "CSV (.csv)",
            "JSON (.json)",
            "",
            "Export…",
        ]
        assert window.export_menu.actions()[3].isSeparator()
        toolbar = window.findChild(QToolBar, "main-toolbar")
        button = toolbar.widgetForAction(window.export_action)
        assert isinstance(button, QToolButton)
        assert (
            button.popupMode() == QToolButton.ToolButtonPopupMode.InstantPopup
        )

    def test_format_entry_offers_only_that_format(
        self, qtbot, window, tmp_path, monkeypatch
    ):
        self.connect(qtbot, window)
        self.run(qtbot, window, "SELECT n FROM t")
        offered = []

        def dialog(parent, _caption, start, filters, selected):
            offered.append((Path(start).name, filters))
            return str(tmp_path / "r.json"), selected

        monkeypatch.setattr(QFileDialog, "getSaveFileName", dialog)
        csv_entry = window.export_menu.actions()[1]
        csv_entry.trigger()
        qtbot.waitUntil(lambda: not window.exporting, timeout=self.WAIT_MS)
        assert offered == [("result.csv", "CSV (*.csv)")]
        # The chosen format wins over a different typed extension.
        written = tmp_path / "r.json.csv"
        with written.open(encoding="utf-8", newline="") as f:
            assert next(csv.reader(f)) == ["n"]

    def test_export_any_entry_offers_every_format(
        self, qtbot, window, tmp_path, monkeypatch
    ):
        self.connect(qtbot, window)
        self.run(qtbot, window, "SELECT n FROM t")
        offered = []

        def dialog(parent, _caption, start, filters, selected):
            offered.append(filters)
            return str(tmp_path / "r.json"), selected

        monkeypatch.setattr(QFileDialog, "getSaveFileName", dialog)
        window.export_menu.actions()[-1].trigger()
        qtbot.waitUntil(lambda: not window.exporting, timeout=self.WAIT_MS)
        assert offered == ["Excel (*.xlsx);;CSV (*.csv);;JSON (*.json)"]
        assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
