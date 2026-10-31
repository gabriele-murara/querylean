"""Static application metadata."""

from __future__ import annotations


class AppInfo:
    """Application identifiers shared by every package.

    ``VERSION`` must match ``project.version`` in ``pyproject.toml`` (a unit test
    enforces it).
    """

    NAME = "querylean"
    DISPLAY_NAME = "QueryLean"
    VERSION = "0.1.0"
