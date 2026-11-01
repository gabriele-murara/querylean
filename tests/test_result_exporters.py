"""Tests of the Excel, CSV and JSON exporters."""

import csv
import datetime as dt
import json
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from fakes.failing_exporter import FailingExporter
from querylean.export.csv_exporter import CsvExporter
from querylean.export.export_error import ExportError
from querylean.export.json_exporter import JsonExporter
from querylean.export.result_exporters import ResultExporters
from querylean.export.xlsx_exporter import XlsxExporter


class TestResultExporters:
    """Content and types of each format, atomic writing, format lookup."""

    COLUMNS = ["id", "name", "amount", "when", "data"]

    @pytest.fixture
    def rows(self):
        return [
            (1, None, Decimal("1.50"), dt.date(2024, 1, 2), b"\xff\x00"),
            (2, "", Decimal("0.10"), dt.datetime(2024, 1, 2, 3, 4, 5), None),
            (3, 'a,"b"\nc', None, dt.timedelta(hours=26), b"abc"),
        ]

    def test_csv(self, tmp_path, rows):
        path = tmp_path / "r.csv"
        report = CsvExporter().export(path, self.COLUMNS, rows)
        assert report.rows == 3
        assert report.shortened_cells == 0
        with path.open(encoding="utf-8", newline="") as handle:
            read = list(csv.reader(handle))
        assert read == [
            self.COLUMNS,
            ["1", "", "1.50", "2024-01-02", "0xff00"],
            ["2", "", "0.10", "2024-01-02 03:04:05", ""],
            ["3", 'a,"b"\nc', "", "26:00:00", "abc"],
        ]

    def test_csv_binary_is_not_cut(self, tmp_path):
        data = bytes([0xFF]) * 200
        path = tmp_path / "r.csv"
        CsvExporter().export(path, ["b"], [(data,)])
        assert "0x{}".format(data.hex()) in path.read_text(encoding="utf-8")

    def test_json(self, tmp_path, rows):
        path = tmp_path / "r.json"
        JsonExporter().export(path, self.COLUMNS, rows)
        records = json.loads(path.read_text(encoding="utf-8"))
        assert records[0] == {
            "id": 1,
            "name": None,
            "amount": "1.50",
            "when": "2024-01-02",
            "data": "0xff00",
        }
        assert records[1]["name"] == ""
        assert records[1]["data"] is None
        assert records[2]["when"] == "26:00:00"

    def test_json_types_and_duplicate_columns(self, tmp_path):
        path = tmp_path / "r.json"
        JsonExporter().export(
            path,
            ["id", "id", "id_2", "f", "big", "flag", "nan"],
            [(1, 2, 3, 0.5, 2**70, True, float("nan"))],
        )
        assert json.loads(path.read_text(encoding="utf-8")) == [
            {
                "id": 1,
                "id_2": 2,
                "id_2_2": 3,
                "f": 0.5,
                "big": 2**70,
                "flag": True,
                "nan": "nan",
            }
        ]

    def test_json_keeps_unicode(self, tmp_path):
        path = tmp_path / "r.json"
        JsonExporter().export(path, ["città"], [("perché",)])
        assert "perché" in path.read_text(encoding="utf-8")

    def test_xlsx(self, tmp_path, rows):
        path = tmp_path / "r.xlsx"
        XlsxExporter().export(path, self.COLUMNS, rows)
        sheet = load_workbook(path).active
        assert sheet.title == XlsxExporter.SHEET_TITLE
        assert sheet.freeze_panes == "A2"
        values = [[c.value for c in row] for row in sheet.iter_rows()]
        assert values[0] == self.COLUMNS
        assert sheet["A1"].font.bold
        assert values[1] == [
            1,
            None,
            1.5,
            dt.datetime(2024, 1, 2),
            "0xff00",
        ]
        # Excel shows NULL and "" alike: both are empty cells.
        assert values[2] == [
            2,
            None,
            0.1,
            dt.datetime(2024, 1, 2, 3, 4, 5),
            None,
        ]
        assert values[3] == [3, 'a,"b"\nc', None, "26:00:00", "abc"]
        assert sheet["D2"].is_date

    def test_xlsx_never_writes_formulas(self, tmp_path):
        path = tmp_path / "r.xlsx"
        XlsxExporter().export(path, ["=A1"], [("=1+1",), ("=HYPERLINK(1)",)])
        sheet = load_workbook(path).active
        for row in sheet.iter_rows():
            assert row[0].data_type == "s"
        assert sheet["A2"].value == "=1+1"

    def test_xlsx_keeps_precision_as_text(self, tmp_path):
        path = tmp_path / "r.xlsx"
        big = 12345678901234567
        XlsxExporter().export(
            path,
            ["big", "small", "dec", "old", "inf"],
            [
                (
                    big,
                    123456789012345,
                    Decimal("1234567890.123456789"),
                    dt.date(1850, 5, 1),
                    float("inf"),
                )
            ],
        )
        row = [c.value for c in next(load_workbook(path).active.iter_rows(2))]
        assert row == [
            str(big),
            123456789012345,
            "1234567890.123456789",
            "1850-05-01",
            "inf",
        ]

    def test_xlsx_illegal_characters_and_long_text(self, tmp_path):
        path = tmp_path / "r.xlsx"
        long_text = "x" * (XlsxExporter.MAX_CELL_CHARS + 10)
        report = XlsxExporter().export(path, ["t"], [("a\x01b",), (long_text,)])
        assert report.shortened_cells == 1
        sheet = load_workbook(path).active
        assert sheet["A2"].value == "a�b"
        assert len(sheet["A3"].value) == XlsxExporter.MAX_CELL_CHARS

    def test_file_is_private(self, tmp_path):
        path = tmp_path / "r.csv"
        CsvExporter().export(path, ["a"], [(1,)])
        assert path.stat().st_mode & 0o777 == 0o600

    def test_missing_directory_is_reported(self, tmp_path):
        path = tmp_path / "missing" / "r.csv"
        with pytest.raises(ExportError, match="Impossibile scrivere"):
            CsvExporter().export(path, ["a"], [(1,)])

    def test_failure_keeps_existing_file(self, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("old", encoding="utf-8")
        with pytest.raises(ExportError, match="file di log"):
            FailingExporter(ValueError("boom")).export(path, ["a"], [])
        assert path.read_text(encoding="utf-8") == "old"
        assert [p.name for p in tmp_path.iterdir()] == ["r.txt"]

    def test_lookup(self, tmp_path):
        labels = [e.label for e in ResultExporters.all()]
        assert labels == ["Excel", "CSV", "JSON"]
        assert isinstance(
            ResultExporters.for_path(tmp_path / "A.XLSX"), XlsxExporter
        )
        assert ResultExporters.for_path(tmp_path / "a.txt") is None
        assert isinstance(
            ResultExporters.for_name_filter("JSON (*.json)"), JsonExporter
        )
