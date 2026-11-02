"""Local persistence of the configuration (never the password)."""

from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_config_dir

from querylean.app.app_info import AppInfo
from querylean.bookmarks.bookmark_store import BookmarkStore
from querylean.config.app_config import AppConfig
from querylean.config.config_error import ConfigError
from querylean.config.connection_config import ConnectionConfig
from querylean.config.connection_profile import ConnectionProfile
from querylean.config.connection_store import ConnectionStore
from querylean.config.ui_preferences import UiPreferences
from querylean.files.private_json_file import PrivateJsonFile
from querylean.log.log_manager import LogManager


class ConfigManager:
    """Reads and atomically writes ``config.json`` (mode 0600): active
    connection and UI preferences. The saved connections are in the
    ``connections/`` folder next to it (``ConnectionStore``), their
    bookmarked queries in the ``bookmarks/`` folder (``BookmarkStore``).

    Files written by versions with a single connection keep it under the
    ``connection`` key: ``load`` turns it into a saved connection once.
    """

    CONNECTIONS_DIR = "connections"
    BOOKMARKS_DIR = "bookmarks"
    __FORMAT_VERSION = 2
    __log = LogManager.get_logger(__name__)

    def __init__(self, path: Path | None = None) -> None:
        self.__path = path or ConfigManager.default_path()
        self.__connections = ConnectionStore(
            self.__path.parent / ConfigManager.CONNECTIONS_DIR
        )
        self.__bookmarks = BookmarkStore(
            self.__path.parent / ConfigManager.BOOKMARKS_DIR
        )

    @property
    def path(self) -> Path:
        """Location of the configuration file."""
        return self.__path

    @property
    def connections(self) -> ConnectionStore:
        """Saved connections."""
        return self.__connections

    @property
    def bookmarks(self) -> BookmarkStore:
        """Bookmarked queries of the saved connections."""
        return self.__bookmarks

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
        active = data.get("active_connection")
        config = AppConfig(
            active if isinstance(active, str) else "",
            UiPreferences.from_dict(data.get("ui")),
        )
        legacy = data.get("connection")
        if isinstance(legacy, dict):
            self.__migrate(ConnectionConfig.from_dict(legacy), config)
        return config

    def save(self, config: AppConfig) -> None:
        """Atomically write ``config`` with 0600 permissions. Raises
        ``ConfigError``."""
        payload = {
            "version": ConfigManager.__FORMAT_VERSION,
            "active_connection": config.active_connection,
            "ui": config.ui.to_dict(),
        }
        try:
            PrivateJsonFile.write(self.__path, payload)
        except OSError as exc:
            self.__log.error("Cannot save the configuration: {}", exc)
            msg = "Cannot save the configuration in {}: {}"
            msg = msg.format(self.__path, exc.strerror or exc)
            raise ConfigError(msg) from exc

    def __migrate(self, legacy: ConnectionConfig, config: AppConfig) -> None:
        """Save the single connection of an older ``config.json`` as the
        first connection, unless connections already exist."""
        if legacy == ConnectionConfig() or self.__connections.load_all():
            return
        profile = ConnectionProfile(ConnectionStore.new_id(), legacy)
        try:
            self.__connections.save(profile)
            config.active_connection = profile.profile_id
            self.save(config)
        except ConfigError as exc:
            self.__log.warning("Migration of the connection failed: {}", exc)
            return
        self.__log.info("Single connection migrated to {}", profile.profile_id)
