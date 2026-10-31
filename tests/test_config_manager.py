import json
import os
import stat

import pytest

from querylean.config.config_manager import (
    AppConfig,
    ConfigError,
    ConfigManager,
    ConnectionConfig,
    UiPreferences,
)


def test_defaults_when_missing(tmp_path):
    config = ConfigManager(tmp_path / "config.json").load()
    assert config.connection == ConnectionConfig()
    assert config.connection.host == "localhost"
    assert config.connection.port == 3306
    assert config.connection.connect_timeout == 5
    assert config.connection.query_timeout == 30
    assert config.connection.row_limit == 1000


def test_roundtrip_and_permissions(tmp_path):
    path = tmp_path / "sub" / "config.json"
    manager = ConfigManager(path)
    cfg = AppConfig(
        ConnectionConfig(host="db", port=3307, database="app", username="ro", row_limit=500),
        UiPreferences(window_geometry="abc"),
    )
    manager.save(cfg)
    loaded = manager.load()
    assert loaded.connection == cfg.connection
    assert loaded.ui.window_geometry == "abc"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_password_is_never_written(tmp_path):
    path = tmp_path / "config.json"
    ConfigManager(path).save(AppConfig(ConnectionConfig(username="ro"), UiPreferences()))
    data = json.loads(path.read_text())
    assert "password" not in json.dumps(data).lower()


def test_corrupted_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json")
    assert ConfigManager(path).load().connection == ConnectionConfig()


def test_invalid_values_are_clamped_or_ignored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"connection": {
        "port": "abc", "row_limit": 99999, "query_timeout": 0, "host": 5,
        "connect_timeout": True,
    }}))
    cfg = ConfigManager(path).load().connection
    assert cfg.port == 3306
    assert cfg.row_limit == 10_000
    assert cfg.query_timeout == 1
    assert cfg.host == "localhost"
    assert cfg.connect_timeout == 5


def test_missing_fields():
    assert ConnectionConfig().missing_fields() == ["Database", "Username"]
    assert ConnectionConfig(host=" ", database="d", username="u").missing_fields() == ["Host"]


def test_save_error_is_reported(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("")
    with pytest.raises(ConfigError):
        ConfigManager(blocker / "config.json").save(
            AppConfig(ConnectionConfig(), UiPreferences())
        )
