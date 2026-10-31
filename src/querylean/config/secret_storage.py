"""Archiviazione della password nel portachiavi del sistema operativo."""

from __future__ import annotations

import logging

import keyring
import keyring.errors
from keyring.backend import KeyringBackend

from querylean import APP_NAME

log = logging.getLogger(__name__)

SERVICE_NAME = APP_NAME

# Backend che non offrono una protezione reale: vengono considerati non disponibili,
# per non salvare mai la password in chiaro.
_INSECURE_BACKEND_MODULES = ("keyring.backends.fail", "keyring.backends.null", "keyrings.alt")
_INSECURE_BACKEND_NAMES = ("PlaintextKeyring", "EncryptedKeyring", "Keyring")


class SecretStorageError(Exception):
    """Portachiavi non disponibile o inaccessibile."""


def account_key(username: str, host: str, port: int) -> str:
    return f"{username}@{host}:{port}"


def _is_secure(backend: KeyringBackend) -> bool:
    backends = getattr(backend, "backends", None)  # ChainerBackend
    if backends is not None:
        # Il chainer può scrivere su uno qualsiasi dei backend: tutti devono essere sicuri.
        return bool(backends) and all(_is_secure(b) for b in backends)
    module = type(backend).__module__
    if module.startswith(_INSECURE_BACKEND_MODULES):
        return False
    if module.startswith("keyrings.") and type(backend).__name__ in _INSECURE_BACKEND_NAMES:
        return False
    try:
        return backend.priority > 0
    except Exception:
        return False


class SecretStorage:
    def __init__(self, backend: KeyringBackend | None = None) -> None:
        self._backend = backend

    @property
    def backend(self) -> KeyringBackend:
        return self._backend or keyring.get_keyring()

    def is_available(self) -> bool:
        try:
            return _is_secure(self.backend)
        except Exception:
            return False

    def _require_backend(self) -> KeyringBackend:
        backend = self.backend
        if not _is_secure(backend):
            raise SecretStorageError(
                "Nessun portachiavi sicuro disponibile. Su Linux è necessario un servizio "
                "compatibile con Secret Service (es. GNOME Keyring o KWallet). "
                "La password non verrà salvata e andrà reinserita."
            )
        return backend

    def get_password(self, key: str) -> str | None:
        backend = self._require_backend()
        try:
            return backend.get_password(SERVICE_NAME, key)
        except keyring.errors.KeyringError as exc:
            log.warning("Lettura dal portachiavi fallita: %s", type(exc).__name__)
            raise SecretStorageError(
                "Impossibile leggere la password dal portachiavi (bloccato o accesso negato). "
                "Reinserisci la password."
            ) from exc

    def set_password(self, key: str, password: str) -> None:
        backend = self._require_backend()
        try:
            backend.set_password(SERVICE_NAME, key, password)
        except keyring.errors.KeyringError as exc:
            log.warning("Scrittura nel portachiavi fallita: %s", type(exc).__name__)
            raise SecretStorageError(
                "Impossibile salvare la password nel portachiavi (bloccato o accesso negato). "
                "La password resterà valida solo per questa sessione."
            ) from exc

    def delete_password(self, key: str) -> None:
        backend = self._require_backend()
        try:
            backend.delete_password(SERVICE_NAME, key)
        except keyring.errors.PasswordDeleteError:
            pass
        except keyring.errors.KeyringError as exc:
            log.warning("Rimozione dal portachiavi fallita: %s", type(exc).__name__)
            raise SecretStorageError(
                "Impossibile rimuovere la password dal portachiavi."
            ) from exc
