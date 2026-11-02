"""Atomic writing of JSON files readable only by the user."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from querylean.files.private_file import PrivateFile


class PrivateJsonFile:
    """Writes JSON through ``PrivateFile``: atomically, with 0600
    permissions and flushed to disk before the rename."""

    @staticmethod
    def write(path: Path, payload: Any) -> None:
        """Atomically write ``payload`` to ``path``, creating the parent
        directory. Raises ``OSError``."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with (
            PrivateFile.replace(path) as tmp_path,
            tmp_path.open("w", encoding="utf-8") as handle,
        ):
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
