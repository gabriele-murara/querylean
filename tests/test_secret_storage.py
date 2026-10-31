import keyring.errors
import pytest
from keyring.backend import KeyringBackend
from keyring.backends import fail

from querylean.config.secret_storage import (
    SERVICE_NAME,
    SecretStorage,
    SecretStorageError,
    account_key,
)


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.store = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        if (service, username) not in self.store:
            raise keyring.errors.PasswordDeleteError("missing")
        del self.store[(service, username)]


class LockedKeyring(MemoryKeyring):
    def get_password(self, service, username):
        raise keyring.errors.KeyringLocked("locked")

    def set_password(self, service, username, password):
        raise keyring.errors.KeyringLocked("locked")


def test_roundtrip():
    backend = MemoryKeyring()
    storage = SecretStorage(backend)
    key = account_key("ro", "db", 3306)
    storage.set_password(key, "pw")
    assert backend.store == {(SERVICE_NAME, "ro@db:3306"): "pw"}
    assert storage.get_password(key) == "pw"
    storage.delete_password(key)
    storage.delete_password(key)  # idempotente
    assert storage.get_password(key) is None


def test_fail_backend_is_unavailable_and_never_stores():
    storage = SecretStorage(fail.Keyring())
    assert not storage.is_available()
    with pytest.raises(SecretStorageError):
        storage.set_password("k", "pw")


def test_plaintext_backend_is_rejected():
    class PlaintextKeyring(MemoryKeyring):
        pass

    PlaintextKeyring.__module__ = "keyrings.alt.file"
    storage = SecretStorage(PlaintextKeyring())
    assert not storage.is_available()
    with pytest.raises(SecretStorageError):
        storage.set_password("k", "pw")


def test_locked_keyring_errors_are_handled():
    storage = SecretStorage(LockedKeyring())
    with pytest.raises(SecretStorageError) as info:
        storage.get_password("k")
    assert "Reinserisci" in str(info.value)
    with pytest.raises(SecretStorageError):
        storage.set_password("k", "pw")
