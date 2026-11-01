"""Background thread writing an export file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from querylean.export.export_error import ExportError
from querylean.export.result_exporter import ResultExporter


class ExportThread(QThread):
    """Runs one ``ResultExporter.export`` outside the GUI thread (an Excel
    file of 10,000 rows takes seconds).

    The rows are only read: the result list is never modified after the
    query, a new query replaces it. Emits ``exported(ExportReport)`` or
    ``export_failed(message)``.
    """

    exported = Signal(object)
    export_failed = Signal(str)

    def __init__(
        self,
        exporter: ResultExporter,
        path: Path,
        columns: list[str],
        rows: list[tuple[Any, ...]],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("querylean-export")
        self.__exporter = exporter
        self.__path = Path(path)
        self.__columns = list(columns)
        self.__rows = rows

    @property
    def exporter(self) -> ResultExporter:
        """Format writer."""
        return self.__exporter

    @property
    def path(self) -> Path:
        """Destination file."""
        return self.__path

    def run(self) -> None:
        """Write the file and report the outcome."""
        try:
            report = self.__exporter.export(
                self.__path, self.__columns, self.__rows
            )
        except ExportError as exc:
            self.export_failed.emit(str(exc))
            return
        self.exported.emit(report)
