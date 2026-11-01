"""JSON export."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from querylean.export.result_exporter import ResultExporter
from querylean.ui.results.value_formatter import ValueFormatter


class JsonExporter(ResultExporter):
    """Array of objects, one per row, keyed by column name (UTF-8).

    - NULL becomes ``null``; booleans, integers and finite floats stay
      numbers;
    - DECIMAL values become strings, so that no digit is lost;
    - dates, times, binary and the other values use the same text as the
      exports (``ValueFormatter.full_text``);
    - repeated column names (``SELECT a.id, b.id``) get a suffix: ``id``,
      ``id_2``, ...
    """

    @property
    def label(self) -> str:
        return "JSON"

    @property
    def extension(self) -> str:
        return ".json"

    def write(
        self, path: Path, columns: list[str], rows: list[tuple[Any, ...]]
    ) -> int:
        keys = JsonExporter.unique_keys(columns)
        records = [
            {
                key: JsonExporter.__json_value(value)
                for key, value in zip(keys, row, strict=True)
            }
            for row in rows
        ]
        with path.open("w", encoding="utf-8") as handle:
            json.dump(records, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return 0

    @staticmethod
    def unique_keys(columns: list[str]) -> list[str]:
        """Column names made unique by appending ``_2``, ``_3``, ..."""
        used: set[str] = set()
        keys = []
        for name in columns:
            key = name
            counter = 2
            while key in used:
                key = "{}_{}".format(name, counter)
                counter += 1
            used.add(key)
            keys.append(key)
        return keys

    @staticmethod
    def __json_value(value: Any) -> Any:
        if value is None or isinstance(value, bool | int):
            return value
        if isinstance(value, float) and math.isfinite(value):
            return value
        # DECIMAL, non-finite floats, dates, binary, ...
        return ValueFormatter.full_text(value)
