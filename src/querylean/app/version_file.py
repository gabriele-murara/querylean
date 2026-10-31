"""Reader of the ``.version`` file, the only source of the product version."""

from __future__ import annotations

import re
import sys
from pathlib import Path


class VersionFile:
    """Reads the QueryLean version from the ``.version`` file.

    The file lives in the project root and is the single source of truth:
    ``pyproject.toml`` reads it as dynamic version, the build scripts read it
    for artefact names and PyInstaller bundles it next to the executable.
    Nothing else may define the version.
    """

    FILE_NAME = ".version"
    # Shown when the file is missing or malformed (user facing, Italian).
    UNKNOWN = "sconosciuta"
    __PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-.+][0-9A-Za-z.-]+)?$")
    # src/querylean/app/version_file.py -> project root.
    __SOURCE_ROOT_DEPTH = 3
    __cache: str | None = None

    @staticmethod
    def path() -> Path:
        """Location of ``.version``: the PyInstaller bundle directory when
        frozen, the project root when running from sources."""
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            return Path(bundle_dir) / VersionFile.FILE_NAME
        root = Path(__file__).resolve().parents[VersionFile.__SOURCE_ROOT_DEPTH]
        return root / VersionFile.FILE_NAME

    @staticmethod
    def parse(path: Path) -> str:
        """Version stored in ``path``, or ``UNKNOWN`` when it is missing or
        not a valid version string."""
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            VersionFile.__warn("Cannot read %s: %s", path, exc)
            return VersionFile.UNKNOWN
        if not VersionFile.__PATTERN.match(text):
            VersionFile.__warn("Invalid version in %s: %r", path, text)
            return VersionFile.UNKNOWN
        return text

    @staticmethod
    def read() -> str:
        """Product version from the ``.version`` file (read once, cached)."""
        if VersionFile.__cache is None:
            VersionFile.__cache = VersionFile.parse(VersionFile.path())
        return VersionFile.__cache

    @staticmethod
    def __warn(message: str, *args: object) -> None:
        # Imported lazily: LogManager depends on AppInfo, which depends on this
        # class, so a module-level import would be circular.
        from querylean.log.log_manager import LogManager

        LogManager.get_logger(__name__).warning(message, *args)
