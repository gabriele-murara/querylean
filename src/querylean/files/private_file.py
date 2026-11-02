"""Atomic replacement of a file readable only by the user."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class PrivateFile:
    """Writes go to a temporary file in the target directory, which then
    replaces the target with ``os.replace``: a reader never sees a partial
    file and an existing file is replaced only by a complete one. The file
    has mode 0600, so other users cannot read it."""

    MODE = 0o600

    @staticmethod
    @contextmanager
    def replace(path: Path, suffix: str = ".tmp") -> Iterator[Path]:
        """Yield a temporary path next to ``path``; when the block ends
        without errors it becomes ``path``, otherwise it is removed.

        ``suffix`` is the extension of the temporary file, for writers that
        check it. The directory must exist. Raises ``OSError``."""
        fd, tmp_name = tempfile.mkstemp(
            prefix=".{}-".format(path.stem), suffix=suffix, dir=path.parent
        )
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            yield tmp_path
            # The writer may have recreated the file with another mode.
            os.chmod(tmp_path, PrivateFile.MODE)
            os.replace(tmp_path, path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
