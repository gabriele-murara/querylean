"""Local persistence of the configuration (never the password)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from platformdirs import user_config_dir

from querylean.app.app_info import AppInfo
from querylean.config.app_config import AppConfig
from querylean.config.config_error import ConfigError
from querylean.config.connection_config import ConnectionConfig
from querylean.config.ui_preferences import UiPreferences
from querylean.log.log_manager import LogManager


class ConfigManager:
    """Reads and atomically writes the JSON configuration file (mode 0600)."""

    __FORMAT_VERSION = 1
    __log = LogManager.get_logger(__name__)

    def __init__(self, path: Path | None = None) -> None:
        self.__path = path or ConfigManager.default_path()

    @property
    def path(self) -> Path:
        """Location of the configuration file."""
        return self.__path

    @path.setter
    def path(self, value: Path) -> None:
        self.__path = Path(value)

    @staticmethod
    def default_path() -> Path:
        """Platform specific configuration file path."""
        return (
            Path(user_config_dir(AppInfo.NAME, appauthor=False)) / "config.json"
        )

    def load(self) -> AppConfig:
        """Load the configuration; a missing or corrupted file yields the
        defaults."""
        if not self.__path.exists():
            return AppConfig()
        try:
            data = json.loads(self.__path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.__log.warning(
                "Unreadable configuration ({}): using defaults", exc
            )
            return AppConfig()
        if not isinstance(data, dict):
            data = {}
        return AppConfig(
            ConnectionConfig.from_dict(data.get("connection")),
            UiPreferences.from_dict(data.get("ui")),
        )

    def save(self, config: AppConfig) -> None:
        """Atomically write ``config`` with 0600 permissions. Raises
        ``ConfigError``."""
        payload = {
            "version": ConfigManager.__FORMAT_VERSION,
            "connection": config.connection.to_dict(),
            "ui": config.ui.to_dict(),
        }
        try:
            self.__path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix=".config-", suffix=".tmp", dir=self.__path.parent
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(tmp_name, 0o600)
                os.replace(tmp_name, self.__path)
            except BaseException:
                Path(tmp_name).unlink(missing_ok=True)
                raise
        except OSError as exc:
            self.__log.error("Cannot save the configuration: {}", exc)
            msg = "Impossibile salvare la configurazione in {}: {}"
            msg = msg.format(self.__path, exc.strerror or exc)
            raise ConfigError(msg) from exc
