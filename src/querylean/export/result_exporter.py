"""Abstract writer of a query result to a file."""

from __future__ import annotations

import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from querylean.export.export_error import ExportError
from querylean.export.export_report import ExportReport
from querylean.log.log_manager import LogManager


class ResultExporter(ABC):
    """Writes column names and rows to a file of one format.

    ``export`` writes to a temporary file in the target directory and then
    renames it, so an existing file is replaced only by a complete export.
    The file is created readable only by the current user (mode 0600): it
    may contain sensitive data.
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
        tmp_name = None
        try:
            fd, tmp_name = tempfile.mkstemp(
                prefix=".querylean-", suffix=self.extension, dir=path.parent
            )
            os.close(fd)
            shortened = self.write(Path(tmp_name), columns, rows)
            os.replace(tmp_name, path)
            tmp_name = None
        except OSError as exc:
            self.__log.error("Export to {} failed: {}", path, exc)
            msg = "Cannot write the file {}: {}"
            raise ExportError(msg.format(path, exc.strerror or exc)) from exc
        except Exception as exc:
            self.__log.exception("Export to {} failed", path)
            msg = "Export failed: the details are in the log file."
            raise ExportError(msg) from exc
        finally:
            if tmp_name is not None:
                Path(tmp_name).unlink(missing_ok=True)
        self.__log.info(
            "Exported {} rows to {} ({})", len(rows), path, self.label
        )
        return ExportReport(path, len(rows), shortened)
