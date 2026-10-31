"""Keyring backend that is always locked."""

from __future__ import annotations

import keyring.errors

from fakes.memory_keyring import MemoryKeyring


class LockedKeyring(MemoryKeyring):
    """Every read and write fails with ``KeyringLocked``."""

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringLocked("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.KeyringLocked("locked")
