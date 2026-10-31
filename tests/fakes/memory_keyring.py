"""In-memory keyring backend."""

from __future__ import annotations

import keyring.errors
from keyring.backend import KeyringBackend


class MemoryKeyring(KeyringBackend):
    """Secure-looking keyring that keeps passwords in a dictionary."""

    priority = 1

    def __init__(self) -> None:
        super().__init__()
        self.__store: dict[tuple[str, str], str] = {}

    @property
    def store(self) -> dict[tuple[str, str], str]:
        """Stored passwords keyed by ``(service, username)``."""
        return self.__store

    def get_password(self, service: str, username: str) -> str | None:
        return self.__store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.__store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.__store:
            raise keyring.errors.PasswordDeleteError("missing")
        del self.__store[(service, username)]
