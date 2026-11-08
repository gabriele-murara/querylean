"""GUI tests of the result table and value formatting."""

import datetime as dt
from decimal import Decimal

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtGui import QGuiApplication

from querylean.ui.results.results_table import ResultsTable
from querylean.ui.results.value_formatter import ValueFormatter


class TestResultsTable:
    """NULL vs empty, read-only model and TSV copy of cells and rows."""

    def test_null_vs_empty_and_copy(self, qtbot):
        table = ResultsTable()
        qtbot.addWidget(table)
        table.set_result(
            ["id", "name", "note", "when", "amount"],
            [
                (1, None, "", dt.date(2024, 1, 2), Decimal("1.50")),
                (2, "a\tb", "x\ny", None, None),
            ],
        )
        model = table.results_model
        assert model.data(model.index(0, 1)) == ValueFormatter.NULL_TEXT
        assert model.data(model.index(0, 2)) == ""
        assert model.data(model.index(0, 1), Qt.ItemDataRole.FontRole).italic()
        assert not (model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable)

        table.selectAll()
        text = table.copy_selection(headers=True)
        expected = "id\tname\tnote\twhen\tamount\n"
        expected += "1\t\t\t2024-01-02\t1.50\n"
        expected += "2\ta b\tx y\t\t"
        assert text == expected
        assert QGuiApplication.clipboard().text() == text

        table.clearSelection()
        table.selectionModel().select(
            model.index(1, 0), QItemSelectionModel.SelectionFlag.Select
        )
        assert table.copy_selection() == "2"
        assert table.copy_selection(whole_rows=True) == "2\ta b\tx y\t\t"

    def test_value_formatting(self):
        assert ValueFormatter.format_value(True) == "true"
        assert ValueFormatter.format_value(b"\xff\x00") == "0xff00"
        assert (
            ValueFormatter.format_value(dt.timedelta(hours=26, seconds=5))
            == "26:00:05"
        )
        assert ValueFormatter.format_value(
            dt.datetime(2024, 1, 2, 3, 4, 5)
        ) == ("2024-01-02 03:04:05")
        assert ValueFormatter.copy_text(None) == ""

    def test_full_text_is_lossless(self):
        data = bytes([0xFF]) * (ValueFormatter.MAX_BINARY_PREVIEW + 1)
        assert ValueFormatter.format_value(data).endswith("…")
        assert ValueFormatter.full_text(data) == "0x{}".format(data.hex())
        time = dt.timedelta(hours=1, microseconds=250)
        assert ValueFormatter.format_value(time) == "01:00:00"
        assert ValueFormatter.full_text(time) == "01:00:00.000250"
        negative = -dt.timedelta(minutes=1, seconds=30)
        assert ValueFormatter.format_value(negative) == "-00:01:30"
        assert ValueFormatter.full_text(Decimal("1.50")) == "1.50"

    def test_long_values_are_shown_literally_in_tooltips(self, qtbot):
        table = ResultsTable()
        qtbot.addWidget(table)
        stored = "<img src='/etc/passwd'><b>{}</b>".format("x" * 200)
        table.set_result(["note"], [(stored,)])
        model = table.results_model
        tip = model.data(model.index(0, 0), Qt.ItemDataRole.ToolTipRole)
        assert "<img" not in tip and "&lt;img" in tip

    def test_rows_of_another_page(self, qtbot):
        table = ResultsTable()
        qtbot.addWidget(table)
        table.set_result(["name"], [("a",)])
        narrow = table.columnWidth(0)
        table.show_rows([("x" * 40,), (None,)], 2000)
        model = table.results_model
        assert model.columns == ["name"]
        assert model.rowCount() == 2
        assert model.offset == 2000
        assert model.headerData(1, Qt.Orientation.Vertical) == "2002"
        assert table.columnWidth(0) > narrow
        wide = table.columnWidth(0)
        table.show_rows([("b",)], 0)
        assert table.columnWidth(0) == wide
        table.selectAll()
        assert table.copy_selection() == "b"
