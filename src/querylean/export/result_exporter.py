"""Abstract writer of a query result to a file."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from querylean.export.export_error import ExportError
from querylean.export.export_report import ExportReport
from querylean.files.private_file import PrivateFile
from querylean.log.log_manager import LogManager


class ResultExporter(ABC):
    """Writes column names and rows to a file of one format.

    ``export`` writes through ``PrivateFile``: an existing file is replaced
    only by a complete export, and the file is readable only by the current
    user (mode 0600) because it may contain sensitive data.
    """

    __log = LogManager.get_logger(__name__)

    @property
    @abstractmethod
    def label(self) -> str:
        """Format name shown to the user (e.g. "Excel")."""

    @property
    @abstractmethod
    def extension(self) -> str:
        """File extension with the leading dot (e.g. ".xlsx")."""

    @property
    def name_filter(self) -> str:
        """File dialog filter, e.g. "Excel (*.xlsx)"."""
        return "{} (*{})".format(self.label, self.extension)

    @abstractmethod
    def write(
        self, path: Path, columns: list[str], rows: list[tuple[Any, ...]]
    ) -> int:
        """Write the result to ``path`` and return the number of cells whose
        text was cut to fit the format limits."""

    def export(
        self, path: Path, columns: list[str], rows: list[tuple[Any, ...]]
    ) -> ExportReport:
        """Atomically write the result to ``path``. Raises ``ExportError``
        with a user-facing message."""
        path = Path(path)
        try:
            with PrivateFile.replace(path, self.extension) as tmp_path:
                shortened = self.write(tmp_path, columns, rows)
        except OSError as exc:
            self.__log.error("Export to {} failed: {}", path, exc)
            msg = "Cannot write the file {}: {}"
            raise ExportError(msg.format(path, exc.strerror or exc)) from exc
        except Exception as exc:
            self.__log.exception("Export to {} failed", path)
            msg = "Export failed: the details are in the log file."
            raise ExportError(msg) from exc
        self.__log.info(
            "Exported {} rows to {} ({})", len(rows), path, self.label
        )
        return ExportReport(path, len(rows), shortened)
