"""Abstract secret store."""

from __future__ import annotations

from abc import ABC, abstractmethod

from querylean.app.app_info import AppInfo


class SecretStore(ABC):
    """Stores the connection password outside of the configuration file.

    Implementations must never fall back to plaintext storage: when no secure
    backend is available they raise ``SecretStorageError``.
    """

    SERVICE_NAME = AppInfo.NAME

    @staticmethod
    def account_key(username: str, host: str, port: int) -> str:
        """Key identifying the password of one MySQL account."""
        return "{}@{}:{}".format(username, host, port)

    @abstractmethod
    def is_available(self) -> bool:
        """True when a secure backend can be used."""

    @abstractmethod
    def get_password(self, key: str) -> str | None:
        """Stored password for ``key``, or ``None``."""

    @abstractmethod
    def set_password(self, key: str, password: str) -> None:
        """Store ``password`` for ``key``."""

    @abstractmethod
    def delete_password(self, key: str) -> None:
        """Remove the password for ``key``; a missing entry is not an error."""
