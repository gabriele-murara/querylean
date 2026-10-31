"""Tests of configuration persistence."""

import json
import os
import stat

import pytest

from querylean.config.app_config import AppConfig
from querylean.config.config_error import ConfigError
from querylean.config.config_manager import ConfigManager
from querylean.config.connection_config import ConnectionConfig
from querylean.config.ui_preferences import UiPreferences


class TestConfigManager:
    """Round trip, permissions, no password, corrupted files, write errors."""

    def test_defaults_when_missing(self, tmp_path):
        assert (
            ConfigManager(tmp_path / "config.json").load().connection
            == ConnectionConfig()
        )

    def test_roundtrip_and_permissions(self, tmp_path):
        path = tmp_path / "sub" / "config.json"
        manager = ConfigManager(path)
        cfg = AppConfig(
            ConnectionConfig(
                host="db",
                port=3307,
                database="app",
                username="ro",
                row_limit=500,
            ),
            UiPreferences(window_geometry="abc"),
        )
        manager.save(cfg)
        loaded = manager.load()
        assert loaded.connection == cfg.connection
        assert loaded.ui.window_geometry == "abc"
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600

    def test_password_is_never_written(self, tmp_path):
        path = tmp_path / "config.json"
        ConfigManager(path).save(AppConfig(ConnectionConfig(username="ro")))
        assert "password" not in path.read_text().lower()

    def test_corrupted_file_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("{not json")
        assert ConfigManager(path).load().connection == ConnectionConfig()

    def test_invalid_values_are_clamped_or_ignored(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(
            json.dumps({"connection": {"query_timeout": 0, "row_limit": 99999}})
        )
        cfg = ConfigManager(path).load().connection
        assert cfg.query_timeout == 1 and cfg.row_limit == 10_000

    def test_save_error_is_reported(self, tmp_path):
        blocker = tmp_path / "file"
        blocker.write_text("")
        with pytest.raises(ConfigError):
            ConfigManager(blocker / "config.json").save(AppConfig())
