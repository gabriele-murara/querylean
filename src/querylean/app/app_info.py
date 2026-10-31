"""Static application metadata."""

from __future__ import annotations

from querylean.app.version_file import VersionFile


class AppInfo:
    """Application identifiers shared by every package.

    The version is not a constant: ``version()`` reads it from the
    ``.version`` file, its only source. ``AUTHOR`` must match the first entry
    of ``project.authors`` in ``pyproject.toml`` (a unit test enforces it).
    """

    NAME = "querylean"
    DISPLAY_NAME = "QueryLean"
    AUTHOR = "Gabriele Murara"
    COPYRIGHT_YEAR = "2026"
    LICENSE = "MIT"
    # User-facing description (Italian), shown in the "Informazioni" dialog.
    DESCRIPTION = (
        "Client desktop minimale per eseguire query MySQL di sola lettura: "
        "una connessione, un editor SQL e una tabella dei risultati."
    )

    @staticmethod
    def version() -> str:
        """Product version, read from the ``.version`` file."""
        return VersionFile.read()
