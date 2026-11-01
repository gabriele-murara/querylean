"""CSV export."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from querylean.export.result_exporter import ResultExporter
from querylean.ui.results.value_formatter import ValueFormatter


class CsvExporter(ResultExporter):
    """Comma separated values, UTF-8, header row first.

    Fields are quoted only when needed (comma, quote or line break), so line
    breaks inside values are kept. NULL becomes an empty field, as in the
    TSV copy.
    """

    @property
    def label(self) -> str:
        return "CSV"

    @property
    def extension(self) -> str:
        return ".csv"

    def write(
        self, path: Path, columns: list[str], rows: list[tuple[Any, ...]]
    ) -> int:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            for row in rows:
                writer.writerow(
                    [
                        "" if value is None else ValueFormatter.full_text(value)
                        for value in row
                    ]
                )
        return 0
