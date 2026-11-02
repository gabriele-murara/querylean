"""Tests of the saved connection files."""

import json
import os
import stat

import pytest

from querylean.config.config_error import ConfigError
from querylean.config.connection_config import ConnectionConfig
from querylean.config.connection_profile import ConnectionProfile
from querylean.config.connection_store import ConnectionStore


class TestConnectionStore:
    """One private JSON file per connection, names, invalid files."""

    @pytest.fixture
    def store(self, tmp_path):
        return ConnectionStore(tmp_path / "connections")

    @staticmethod
    def profile(**fields) -> ConnectionProfile:
        return ConnectionProfile(
            ConnectionStore.new_id(), ConnectionConfig(**fields)
        )

    def test_save_load_delete(self, store):
        first = self.profile(name="Produzione", host="db", username="ro")
        second = self.profile(host="db2", database="app", username="ro")
        store.save(first)
        store.save(second)
        path = store.path_of(first.profile_id)
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["connection"]["name"] == "Produzione"
        assert "password" not in path.read_text(encoding="utf-8").lower()
        # Sorted by display name, case insensitive.
        loaded = store.load_all()
        assert [p.display_name for p in loaded] == [
            "Produzione",
            "ro@db2/app",
        ]
        assert loaded[0].config == first.config
        store.delete(first.profile_id)
        assert [p.profile_id for p in store.load_all()] == [second.profile_id]

    def test_missing_directory_is_empty(self, store):
        assert store.load_all() == []

    def test_invalid_files_are_skipped(self, store):
        good = self.profile(username="ro")
        store.save(good)
        directory = store.directory
        (directory / "{}.json".format("b" * 32)).write_text("{not json")
        (directory / "{}.json".format("c" * 32)).write_text("[1, 2]")
        (directory / "notes.json").write_text("{}")
        assert [p.profile_id for p in store.load_all()] == [good.profile_id]

    def test_ids_are_validated(self, store):
        assert ConnectionStore.is_valid_id(ConnectionStore.new_id())
        with pytest.raises(ValueError):
            store.path_of("../config")

    def test_write_error_is_reported(self, tmp_path):
        blocker = tmp_path / "file"
        blocker.write_text("")
        store = ConnectionStore(blocker / "connections")
        with pytest.raises(ConfigError):
            store.save(self.profile(username="ro"))

    def test_display_name(self):
        config = ConnectionConfig(host="db", database="app", username="ro")
        assert config.display_name() == "ro@db/app"
        config.name = "  Produzione  "
        assert config.display_name() == "Produzione"
        assert config.default_name() == "ro@db/app"
