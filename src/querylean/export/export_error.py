"""Export failure."""

from __future__ import annotations


class ExportError(Exception):
    """Raised when a result cannot be exported; the message is shown to the
    user."""
