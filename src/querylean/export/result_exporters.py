"""Available export formats."""

from __future__ import annotations

from pathlib import Path

from querylean.export.csv_exporter import CsvExporter
from querylean.export.json_exporter import JsonExporter
from querylean.export.result_exporter import ResultExporter
from querylean.export.xlsx_exporter import XlsxExporter


class ResultExporters:
    """Registry of the exporters, in the order shown to the user."""

    @staticmethod
    def all() -> list[ResultExporter]:
        """One instance of every exporter: Excel, CSV, JSON."""
        return [XlsxExporter(), CsvExporter(), JsonExporter()]

    @staticmethod
    def for_path(path: Path) -> ResultExporter | None:
        """Exporter matching the extension of ``path`` (case insensitive)."""
        suffix = Path(path).suffix.lower()
        for exporter in ResultExporters.all():
            if exporter.extension == suffix:
                return exporter
        return None

    @staticmethod
    def for_name_filter(name_filter: str) -> ResultExporter | None:
        """Exporter whose file dialog filter is ``name_filter``."""
        for exporter in ResultExporters.all():
            if exporter.name_filter == name_filter:
                return exporter
        return None
