"""What an import does with a name already used by a saved bookmark."""

from __future__ import annotations

from enum import Enum


class NameConflict(Enum):
    """Choice for an imported bookmark whose name is taken by a different
    bookmark of the same connection and target. ``label`` is the text of
    the choice in the import dialog."""

    RENAME = "Import it with a new name"
    REPLACE = "Replace the saved query"
    SKIP = "Skip it"

    @property
    def label(self) -> str:
        """User-facing description."""
        return str(self.value)
