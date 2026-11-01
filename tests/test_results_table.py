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
