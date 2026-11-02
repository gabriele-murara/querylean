"""Atomic writing of JSON files readable only by the user."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class PrivateJsonFile:
    """Writes JSON through a temporary file in the same directory and
    ``os.replace``, with 0600 permissions: a reader never sees a partial
    file and other users cannot read it."""

    @staticmethod
    def write(path: Path, payload: Any) -> None:
        """Atomically write ``payload`` to ``path``, creating the parent
        directory. Raises ``OSError``."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".{}-".format(path.stem), suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp_name, 0o600)
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
