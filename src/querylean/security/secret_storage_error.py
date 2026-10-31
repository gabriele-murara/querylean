"""Secret storage error."""

from __future__ import annotations


class SecretStorageError(Exception):
    """The keychain is unavailable or denied access. The message is user facing."""
