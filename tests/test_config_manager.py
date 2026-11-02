"""Tests of configuration persistence."""

import json
import os
import stat

import pytest

from querylean.config.app_config import AppConfig
from querylean.config.config_error import ConfigError
from querylean.config.config_manager import ConfigManager
from querylean.config.connection_config import ConnectionConfig
from querylean.config.connection_profile import ConnectionProfile
from querylean.config.connection_store import ConnectionStore
from querylean.config.ui_preferences import UiPreferences


class TestConfigManager:
    """Round trip, permissions, no password, corrupted files, write errors,
    migration of the single connection of older versions."""

    def test_defaults_when_missing(self, tmp_path):
        manager = ConfigManager(tmp_path / "config.json")
        cfg = manager.load()
        assert cfg.active_connection == ""
        assert manager.connections.load_all() == []
        assert manager.connections.directory == tmp_path / "connections"
        assert manager.bookmarks.directory == tmp_path / "bookmarks"

    def test_roundtrip_and_permissions(self, tmp_path):
        path = tmp_path / "sub" / "config.json"
        manager = ConfigManager(path)
        cfg = AppConfig(
            "a" * 32,
            UiPreferences(window_geometry="abc", sidebar_state="def"),
        )
        manager.save(cfg)
        loaded = manager.load()
        assert loaded.active_connection == "a" * 32
        assert loaded.ui.window_geometry == "abc"
        assert loaded.ui.sidebar_state == "def"
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        assert "connection" not in json.loads(path.read_text())

    def test_corrupted_file_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("{not json")
        assert ConfigManager(path).load().active_connection == ""

    def test_save_error_is_reported(self, tmp_path):
        blocker = tmp_path / "file"
        blocker.write_text("")
        with pytest.raises(ConfigError):
            ConfigManager(blocker / "config.json").save(AppConfig())

    def test_single_connection_is_migrated_once(self, tmp_path):
        path = tmp_path / "config.json"
        legacy = {"host": "db", "database": "app", "username": "ro"}
        legacy.update({"query_timeout": 0, "row_limit": 99999})
        path.write_text(json.dumps({"version": 1, "connection": legacy}))
        manager = ConfigManager(path)
        cfg = manager.load()
        profiles = manager.connections.load_all()
        assert len(profiles) == 1
        migrated = profiles[0].config
        assert migrated.host == "db" and migrated.username == "ro"
        # Values are clamped as for any other configuration.
        assert migrated.query_timeout == 1 and migrated.row_limit == 10_000
        assert cfg.active_connection == profiles[0].profile_id
        # config.json no longer holds the connection: no second migration.
        assert "connection" not in json.loads(path.read_text())
        reloaded = ConfigManager(path).load()
        assert reloaded.active_connection == profiles[0].profile_id
        assert len(manager.connections.load_all()) == 1

    def test_default_legacy_connection_is_not_migrated(self, tmp_path):
        path = tmp_path / "config.json"
        legacy = ConnectionConfig().to_dict()
        path.write_text(json.dumps({"connection": legacy}))
        manager = ConfigManager(path)
        assert manager.load().active_connection == ""
        assert manager.connections.load_all() == []

    def test_migration_skipped_when_connections_exist(self, tmp_path):
        path = tmp_path / "config.json"
        manager = ConfigManager(path)
        existing = ConnectionProfile(
            ConnectionStore.new_id(), ConnectionConfig(username="x")
        )
        manager.connections.save(existing)
        legacy = {"host": "db", "database": "app", "username": "ro"}
        path.write_text(json.dumps({"connection": legacy}))
        manager.load()
        profiles = manager.connections.load_all()
        assert [p.profile_id for p in profiles] == [existing.profile_id]
