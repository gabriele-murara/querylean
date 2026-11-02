"""Saved connections, one JSON file each."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from querylean.config.config_error import ConfigError
from querylean.config.connection_config import ConnectionConfig
from querylean.config.connection_profile import ConnectionProfile
from querylean.config.private_json_file import PrivateJsonFile
from querylean.log.log_manager import LogManager


class ConnectionStore:
    """Directory with one ``<id>.json`` file (mode 0600) per connection.

    A file holds the connection settings, never the password. Unreadable or
    invalid files are skipped (and logged), so one damaged file does not
    hide the other connections.
    """

    SUFFIX = ".json"
    __FORMAT_VERSION = 1
    __ID = re.compile(r"^[0-9a-f]{32}$")
    __log = LogManager.get_logger(__name__)

    def __init__(self, directory: Path) -> None:
        self.__directory = Path(directory)

    @property
    def directory(self) -> Path:
        """Folder holding the connection files."""
        return self.__directory

    @staticmethod
    def new_id() -> str:
        """Identifier for a new connection."""
        return uuid.uuid4().hex

    @staticmethod
    def is_valid_id(profile_id: str) -> bool:
        """True for identifiers produced by ``new_id``."""
        return bool(ConnectionStore.__ID.match(profile_id))

    def path_of(self, profile_id: str) -> Path:
        """File of the connection ``profile_id``."""
        if not ConnectionStore.is_valid_id(profile_id):
            raise ValueError("Invalid connection id: {!r}".format(profile_id))
        return self.__directory / "{}{}".format(
            profile_id, ConnectionStore.SUFFIX
        )

    def load_all(self) -> list[ConnectionProfile]:
        """Saved connections sorted by display name (case insensitive)."""
        if not self.__directory.is_dir():
            return []
        profiles = []
        pattern = "*{}".format(ConnectionStore.SUFFIX)
        for path in self.__directory.glob(pattern):
            profile = self.__load(path)
            if profile is not None:
                profiles.append(profile)
        profiles.sort(key=lambda p: (p.display_name.casefold(), p.profile_id))
        return profiles

    def save(self, profile: ConnectionProfile) -> None:
        """Atomically write ``profile``. Raises ``ConfigError``."""
        path = self.path_of(profile.profile_id)
        payload = {
            "version": ConnectionStore.__FORMAT_VERSION,
            "connection": profile.config.to_dict(),
        }
        try:
            PrivateJsonFile.write(path, payload)
        except OSError as exc:
            self.__log.error("Cannot save connection {}: {}", path, exc)
            msg = "Cannot save the connection in {}: {}"
            raise ConfigError(msg.format(path, exc.strerror or exc)) from exc
        self.__log.info("Connection {} saved", profile.profile_id)

    def delete(self, profile_id: str) -> None:
        """Remove the file of ``profile_id``. Raises ``ConfigError``."""
        path = self.path_of(profile_id)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            self.__log.error("Cannot delete connection {}: {}", path, exc)
            msg = "Cannot delete the connection {}: {}"
            raise ConfigError(msg.format(path, exc.strerror or exc)) from exc
        self.__log.info("Connection {} deleted", profile_id)

    def __load(self, path: Path) -> ConnectionProfile | None:
        if not ConnectionStore.is_valid_id(path.stem):
            self.__log.warning("Ignoring unexpected file {}", path)
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.__log.warning("Unreadable connection {}: {}", path, exc)
            return None
        if not isinstance(data, dict) or not isinstance(
            data.get("connection"), dict
        ):
            self.__log.warning("Invalid connection file {}", path)
            return None
        config = ConnectionConfig.from_dict(data["connection"])
        return ConnectionProfile(path.stem, config)
