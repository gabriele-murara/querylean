"""Internal signal raised by validation stages."""

from __future__ import annotations


class ValidationRejected(Exception):
    """Raised by a ``ValidationStage``; the message is user facing."""
