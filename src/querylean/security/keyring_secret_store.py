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

    Plaintext or "fail" backends (``keyrings.alt``, ``keyring.backends.fail``) are
    treated as unavailable so that the password is never stored in clear text.
    """

    __INSECURE_MODULES = ("keyring.backends.fail", "keyring.backends.null", "keyrings.alt")
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
            self.__log.warning("Keychain read failed: %s", type(exc).__name__)
            raise SecretStorageError(
                "Impossibile leggere la password dal portachiavi (bloccato o accesso negato). "
                "Reinserisci la password."
            ) from exc

    def set_password(self, key: str, password: str) -> None:
        backend = self.__require_backend()
        try:
            backend.set_password(SecretStore.SERVICE_NAME, key, password)
        except keyring.errors.KeyringError as exc:
            self.__log.warning("Keychain write failed: %s", type(exc).__name__)
            raise SecretStorageError(
                "Impossibile salvare la password nel portachiavi (bloccato o accesso negato). "
                "La password resterà valida solo per questa sessione."
            ) from exc

    def delete_password(self, key: str) -> None:
        backend = self.__require_backend()
        try:
            backend.delete_password(SecretStore.SERVICE_NAME, key)
        except keyring.errors.PasswordDeleteError:
            pass
        except keyring.errors.KeyringError as exc:
            self.__log.warning("Keychain delete failed: %s", type(exc).__name__)
            raise SecretStorageError("Impossibile rimuovere la password dal portachiavi.") from exc

    def __require_backend(self) -> KeyringBackend:
        backend = self.backend
        if not KeyringSecretStore.__is_secure(backend):
            raise SecretStorageError(
                "Nessun portachiavi sicuro disponibile. Su Linux è necessario un servizio "
                "compatibile con Secret Service (es. GNOME Keyring o KWallet). "
                "La password non verrà salvata e andrà reinserita."
            )
        return backend

    @staticmethod
    def __is_secure(backend: KeyringBackend) -> bool:
        backends = getattr(backend, "backends", None)  # ChainerBackend
        if backends is not None:
            # The chainer may write to any of its backends: all of them must be secure.
            return bool(backends) and all(KeyringSecretStore.__is_secure(b) for b in backends)
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
