"""Exporter that fails while writing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from querylean.export.result_exporter import ResultExporter


class FailingExporter(ResultExporter):
    """Writes part of the file, then raises ``error``."""

    def __init__(self, error: Exception) -> None:
        self.__error = error

    @property
    def label(self) -> str:
        return "Test"

    @property
    def extension(self) -> str:
        return ".txt"

    def write(
        self, path: Path, columns: list[str], rows: list[tuple[Any, ...]]
    ) -> int:
        path.write_text("partial", encoding="utf-8")
        raise self.__error
