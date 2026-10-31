"""Static application metadata."""

from __future__ import annotations


class AppInfo:
    """Application identifiers shared by every package.

    ``VERSION`` must match ``project.version`` in ``pyproject.toml`` and
    ``AUTHOR`` the first entry of ``project.authors`` (a unit test enforces
    both).
    """

    NAME = "querylean"
    DISPLAY_NAME = "QueryLean"
    VERSION = "0.1.0"
    AUTHOR = "Gabriele Murara"
    COPYRIGHT_YEAR = "2026"
    LICENSE = "MIT"
    # User-facing description (Italian), shown in the "Informazioni" dialog.
    DESCRIPTION = (
        "Client desktop minimale per eseguire query MySQL di sola lettura: "
        "una connessione, un editor SQL e una tabella dei risultati."
    )
