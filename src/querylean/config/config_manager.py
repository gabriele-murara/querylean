"""Persistenza locale della configurazione (mai la password)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from platformdirs import user_config_dir

from querylean import APP_NAME

log = logging.getLogger(__name__)

DEFAULT_ROW_LIMIT = 1000
MAX_ROW_LIMIT = 10_000
MAX_TIMEOUT_SECONDS = 3600


class ConfigError(Exception):
    """Errore di lettura o scrittura della configurazione."""


@dataclass
class ConnectionConfig:
    host: str = "localhost"
    port: int = 3306
    database: str = ""
    username: str = ""
    connect_timeout: int = 5
    query_timeout: int = 30
    row_limit: int = DEFAULT_ROW_LIMIT

    def missing_fields(self) -> list[str]:
        """Campi obbligatori non compilati (etichette per l'utente)."""
        missing = []
        if not self.host.strip():
            missing.append("Host")
        if not self.database.strip():
            missing.append("Database")
        if not self.username.strip():
            missing.append("Username")
        return missing

    def is_complete(self) -> bool:
        return not self.missing_fields()

    def normalized(self) -> ConnectionConfig:
        """Copia con valori ripuliti e riportati entro i limiti ammessi."""
        return ConnectionConfig(
            host=self.host.strip(),
            port=_clamp(self.port, 1, 65535, 3306),
            database=self.database.strip(),
            username=self.username.strip(),
            connect_timeout=_clamp(self.connect_timeout, 1, MAX_TIMEOUT_SECONDS, 5),
            query_timeout=_clamp(self.query_timeout, 1, MAX_TIMEOUT_SECONDS, 30),
            row_limit=_clamp(self.row_limit, 1, MAX_ROW_LIMIT, DEFAULT_ROW_LIMIT),
        )


@dataclass
class UiPreferences:
    window_geometry: str = ""  # base64 di QWidget.saveGeometry()
    splitter_state: str = ""  # base64 di QSplitter.saveState()


@dataclass
class AppConfig:
    connection: ConnectionConfig
    ui: UiPreferences


def _clamp(value: object, low: int, high: int, default: int) -> int:
    try:
        number = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _from_dict(cls, data: object):
    if not isinstance(data, dict):
        return cls()
    known = {f.name: f for f in fields(cls)}
    kwargs = {}
    for name, field in known.items():
        if name in data:
            value = data[name]
            expected = type(field.default)
            if isinstance(value, expected) and not (expected is int and isinstance(value, bool)):
                kwargs[name] = value
    return cls(**kwargs)


def default_config_path() -> Path:
    return Path(user_config_dir(APP_NAME, appauthor=False)) / "config.json"


class ConfigManager:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_config_path()

    def load(self) -> AppConfig:
        """Carica la configurazione; in caso di file assente o corrotto usa i default."""
        if not self.path.exists():
            return AppConfig(ConnectionConfig(), UiPreferences())
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("Configurazione illeggibile (%s): uso i valori predefiniti", exc)
            return AppConfig(ConnectionConfig(), UiPreferences())
        if not isinstance(data, dict):
            data = {}
        connection = _from_dict(ConnectionConfig, data.get("connection")).normalized()
        ui = _from_dict(UiPreferences, data.get("ui"))
        return AppConfig(connection, ui)

    def save(self, config: AppConfig) -> None:
        """Scrittura atomica con permessi 0600. Solleva ConfigError."""
        payload = {
            "version": 1,
            "connection": asdict(config.connection.normalized()),
            "ui": asdict(config.ui),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix=".config-", suffix=".tmp", dir=self.path.parent
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(tmp_name, 0o600)
                os.replace(tmp_name, self.path)
            except BaseException:
                Path(tmp_name).unlink(missing_ok=True)
                raise
        except OSError as exc:
            log.error("Impossibile salvare la configurazione: %s", exc)
            raise ConfigError(
                f"Impossibile salvare la configurazione in {self.path}: {exc.strerror or exc}"
            ) from exc
