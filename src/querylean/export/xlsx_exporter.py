"""Excel (xlsx) export."""

from __future__ import annotations

import datetime as dt
import decimal
import math
import re
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
from openpyxl.worksheet._write_only import WriteOnlyWorksheet

from querylean.export.result_exporter import ResultExporter
from querylean.ui.results.value_formatter import ValueFormatter


class XlsxExporter(ResultExporter):
    """Excel workbook with one sheet: bold, frozen header row, then the rows.

    - Numbers, booleans, dates and date-times are native Excel values.
    - Values Excel would alter are written as text: integers and DECIMAL
      values with more than 15 significant digits (Excel keeps only 15),
      non-finite floats, dates before 1900, time zone aware date-times,
      TIME values.
    - Text is always a string cell, never a formula, even when it starts
      with "=".
    - NULL is an empty cell; so is the empty string (Excel shows them
      alike).
    - Characters XML forbids are replaced with U+FFFD; text longer than an
      Excel cell allows is cut (counted in the report).
    """

    SHEET_TITLE = "Risultato"
    MAX_CELL_CHARS = 32767
    MAX_EXACT_DIGITS = 15
    __MIN_YEAR = 1900
    __ILLEGAL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
    __REPLACEMENT = "�"

    @property
    def label(self) -> str:
        return "Excel"

    @property
    def extension(self) -> str:
        return ".xlsx"

    def write(
        self, path: Path, columns: list[str], rows: list[tuple[Any, ...]]
    ) -> int:
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet(XlsxExporter.SHEET_TITLE)
        sheet.freeze_panes = "A2"
        bold = Font(bold=True)
        shortened = 0
        header = []
        for name in columns:
            cell, cut = XlsxExporter.__text_cell(sheet, name)
            cell.font = bold
            header.append(cell)
            shortened += cut
        sheet.append(header)
        for row in rows:
            cells = []
            for value in row:
                cell, cut = XlsxExporter.__cell(sheet, value)
                cells.append(cell)
                shortened += cut
            sheet.append(cells)
        workbook.save(str(path))
        return shortened

    @staticmethod
    def __cell(sheet: WriteOnlyWorksheet, value: Any) -> tuple[Any, int]:
        native = XlsxExporter.__native(value)
        if native is not None or value is None:
            return WriteOnlyCell(sheet, value=native), 0
        return XlsxExporter.__text_cell(sheet, ValueFormatter.full_text(value))

    @staticmethod
    def __native(value: Any) -> Any:
        """Excel value for ``value``, or None when it must be text."""
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            digits = len(str(abs(value)))
            return value if digits <= XlsxExporter.MAX_EXACT_DIGITS else None
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, decimal.Decimal):
            if not value.is_finite():
                return None
            digits = len(value.normalize().as_tuple().digits)
            if digits > XlsxExporter.MAX_EXACT_DIGITS:
                return None
            return float(value)
        if isinstance(value, dt.datetime):
            if value.tzinfo is not None:
                return None
            return value if value.year >= XlsxExporter.__MIN_YEAR else None
        if isinstance(value, dt.date):
            return value if value.year >= XlsxExporter.__MIN_YEAR else None
        return None

    @staticmethod
    def __text_cell(sheet: WriteOnlyWorksheet, text: str) -> tuple[Any, int]:
        text = XlsxExporter.__ILLEGAL_CHARS.sub(
            XlsxExporter.__REPLACEMENT, text
        )
        cut = 0
        if len(text) > XlsxExporter.MAX_CELL_CHARS:
            text = text[: XlsxExporter.MAX_CELL_CHARS]
            cut = 1
        cell = WriteOnlyCell(sheet, value=text)
        # openpyxl turns text starting with "=" into a formula.
        cell.data_type = "s"
        return cell, cut
