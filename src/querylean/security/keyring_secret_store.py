"""Secret store backed by the operating system keychain."""

from __future__ import annotations

import keyring
import keyring.errors
from keyring.backend import KeyringBackend

from querylean.log.log_manager import LogManager
from querylean.security.secret_storage_error import SecretStorageError
from querylean.security.secret_store import SecretStore


class KeyringSecretStore(SecretStore):
    """Uses ``keyring``: Secret Service on Linux, Keychain on macOS.

    Plaintext or "fail" backends (``keyrings.alt``, ``keyring.backends.fail``)
    are treated as unavailable so that the password is never stored in clear
    text.
    """

    __INSECURE_MODULES = (
        "keyring.backends.fail",
        "keyring.backends.null",
        "keyrings.alt",
    )
    __INSECURE_NAMES = ("PlaintextKeyring", "EncryptedKeyring", "Keyring")
    __log = LogManager.get_logger(__name__)

    def __init__(self, backend: KeyringBackend | None = None) -> None:
        self.__backend = backend

    @property
    def backend(self) -> KeyringBackend:
        """Injected backend, or the one selected by ``keyring``."""
        return self.__backend or keyring.get_keyring()

    @backend.setter
    def backend(self, value: KeyringBackend | None) -> None:
        self.__backend = value

    def is_available(self) -> bool:
        try:
            return KeyringSecretStore.__is_secure(self.backend)
        except Exception:
            return False

    def get_password(self, key: str) -> str | None:
        backend = self.__require_backend()
        try:
            return backend.get_password(SecretStore.SERVICE_NAME, key)
        except keyring.errors.KeyringError as exc:
            self.__log.warning("Keychain read failed: {}", type(exc).__name__)
            msg = "Cannot read the password from the keyring "
            msg += "(locked or access denied). Enter the password again."
            raise SecretStorageError(msg) from exc

    def set_password(self, key: str, password: str) -> None:
        backend = self.__require_backend()
        try:
            backend.set_password(SecretStore.SERVICE_NAME, key, password)
        except keyring.errors.KeyringError as exc:
            self.__log.warning("Keychain write failed: {}", type(exc).__name__)
            msg = "Cannot save the password in the keyring "
            msg += "(locked or access denied). The password will be kept "
            msg += "for this session only."
            raise SecretStorageError(msg) from exc

    def delete_password(self, key: str) -> None:
        backend = self.__require_backend()
        try:
            backend.delete_password(SecretStore.SERVICE_NAME, key)
        except keyring.errors.PasswordDeleteError:
            pass
        except keyring.errors.KeyringError as exc:
            self.__log.warning("Keychain delete failed: {}", type(exc).__name__)
            raise SecretStorageError(
                "Cannot remove the password from the keyring."
            ) from exc

    def __require_backend(self) -> KeyringBackend:
        backend = self.backend
        if not KeyringSecretStore.__is_secure(backend):
            msg = "No secure keyring is available. On Linux a service "
            msg += "compatible with Secret Service is required "
            msg += "(e.g. GNOME Keyring or KWallet). The password will not "
            msg += "be saved and must be entered again."
            raise SecretStorageError(msg)
        return backend

    @staticmethod
    def __is_secure(backend: KeyringBackend) -> bool:
        backends = getattr(backend, "backends", None)  # ChainerBackend
        if backends is not None:
            # The chainer may write to any of its backends: all of them must be
            # secure.
            return bool(backends) and all(
                KeyringSecretStore.__is_secure(b) for b in backends
            )
        module = type(backend).__module__
        if module.startswith(KeyringSecretStore.__INSECURE_MODULES):
            return False
        if (
            module.startswith("keyrings.")
            and type(backend).__name__ in KeyringSecretStore.__INSECURE_NAMES
        ):
            return False
        try:
            return backend.priority > 0
        except Exception:
            return False
