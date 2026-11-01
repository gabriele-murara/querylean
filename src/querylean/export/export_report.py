"""Outcome of an export."""

from __future__ import annotations

from pathlib import Path


class ExportReport:
    """Immutable summary of a completed export."""

    def __init__(self, path: Path, rows: int, shortened_cells: int) -> None:
        self.__path = path
        self.__rows = rows
        self.__shortened_cells = shortened_cells

    @property
    def path(self) -> Path:
        """Written file."""
        return self.__path

    @property
    def rows(self) -> int:
        """Number of exported rows (header excluded)."""
        return self.__rows

    @property
    def shortened_cells(self) -> int:
        """Cells whose text had to be cut to fit the format limits."""
        return self.__shortened_cells
