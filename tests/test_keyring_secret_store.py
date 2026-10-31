"""Tests of the keychain-backed secret store."""

import pytest
from keyring.backends import fail

from fakes.locked_keyring import LockedKeyring
from fakes.memory_keyring import MemoryKeyring
from querylean.security.keyring_secret_store import KeyringSecretStore
from querylean.security.secret_storage_error import SecretStorageError
from querylean.security.secret_store import SecretStore


class TestKeyringSecretStore:
    """Round trip, refusal of insecure backends and keychain errors."""

    def test_roundtrip(self):
        backend = MemoryKeyring()
        store = KeyringSecretStore(backend)
        key = SecretStore.account_key("ro", "db", 3306)
        store.set_password(key, "pw")
        assert backend.store == {(SecretStore.SERVICE_NAME, "ro@db:3306"): "pw"}
        assert store.get_password(key) == "pw"
        store.delete_password(key)
        store.delete_password(key)  # idempotent
        assert store.get_password(key) is None

    def test_secret_store_is_abstract(self):
        with pytest.raises(TypeError):
            SecretStore()

    def test_fail_backend_is_unavailable_and_never_stores(self):
        store = KeyringSecretStore(fail.Keyring())
        assert not store.is_available()
        with pytest.raises(SecretStorageError):
            store.set_password("k", "pw")

    def test_plaintext_backend_is_rejected(self):
        plaintext = type("PlaintextKeyring", (MemoryKeyring,), {"__module__": "keyrings.alt.file"})
        store = KeyringSecretStore(plaintext())
        assert not store.is_available()
        with pytest.raises(SecretStorageError):
            store.set_password("k", "pw")

    def test_locked_keyring_errors_are_handled(self):
        store = KeyringSecretStore(LockedKeyring())
        with pytest.raises(SecretStorageError) as info:
            store.get_password("k")
        assert "Reinserisci" in str(info.value)
        with pytest.raises(SecretStorageError):
            store.set_password("k", "pw")
