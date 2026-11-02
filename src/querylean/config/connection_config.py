"""Parameters of one saved MySQL connection (never the password)."""

from __future__ import annotations

from typing import Any


class ConnectionConfig:
    """Connection settings. Setters normalise values: strings are stripped and
    numbers are clamped to their allowed range, so an instance is always valid
    to use."""

    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 3306
    DEFAULT_CONNECT_TIMEOUT = 5
    DEFAULT_QUERY_TIMEOUT = 30
    DEFAULT_ROW_LIMIT = 1000
    MAX_ROW_LIMIT = 10_000
    MAX_TIMEOUT_SECONDS = 3600
    MAX_PORT = 65535

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        database: str = "",
        username: str = "",
        connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
        query_timeout: int = DEFAULT_QUERY_TIMEOUT,
        row_limit: int = DEFAULT_ROW_LIMIT,
        name: str = "",
    ) -> None:
        self.__name = ""
        self.__host = ""
        self.__port = ConnectionConfig.DEFAULT_PORT
        self.__database = ""
        self.__username = ""
        self.__connect_timeout = ConnectionConfig.DEFAULT_CONNECT_TIMEOUT
        self.__query_timeout = ConnectionConfig.DEFAULT_QUERY_TIMEOUT
        self.__row_limit = ConnectionConfig.DEFAULT_ROW_LIMIT
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.connect_timeout = connect_timeout
        self.query_timeout = query_timeout
        self.row_limit = row_limit
        self.name = name

    # --------------------------------------------------------------- properties
    @property
    def name(self) -> str:
        """Optional name shown in the connection list."""
        return self.__name

    @name.setter
    def name(self, value: str) -> None:
        self.__name = str(value).strip()

    @property
    def host(self) -> str:
        """Server host name or address."""
        return self.__host

    @host.setter
    def host(self, value: str) -> None:
        self.__host = str(value).strip()

    @property
    def port(self) -> int:
        """TCP port (1-65535)."""
        return self.__port

    @port.setter
    def port(self, value: int) -> None:
        self.__port = ConnectionConfig.__clamp(
            value, 1, ConnectionConfig.MAX_PORT, ConnectionConfig.DEFAULT_PORT
        )

    @property
    def database(self) -> str:
        """Default schema."""
        return self.__database

    @database.setter
    def database(self, value: str) -> None:
        self.__database = str(value).strip()

    @property
    def username(self) -> str:
        """MySQL account name."""
        return self.__username

    @username.setter
    def username(self, value: str) -> None:
        self.__username = str(value).strip()

    @property
    def connect_timeout(self) -> int:
        """Connection timeout in seconds."""
        return self.__connect_timeout

    @connect_timeout.setter
    def connect_timeout(self, value: int) -> None:
        self.__connect_timeout = ConnectionConfig.__clamp(
            value,
            1,
            ConnectionConfig.MAX_TIMEOUT_SECONDS,
            ConnectionConfig.DEFAULT_CONNECT_TIMEOUT,
        )

    @property
    def query_timeout(self) -> int:
        """Query execution timeout in seconds."""
        return self.__query_timeout

    @query_timeout.setter
    def query_timeout(self, value: int) -> None:
        self.__query_timeout = ConnectionConfig.__clamp(
            value,
            1,
            ConnectionConfig.MAX_TIMEOUT_SECONDS,
            ConnectionConfig.DEFAULT_QUERY_TIMEOUT,
        )

    @property
    def row_limit(self) -> int:
        """Maximum number of rows fetched per query (1-10,000)."""
        return self.__row_limit

    @row_limit.setter
    def row_limit(self, value: int) -> None:
        self.__row_limit = ConnectionConfig.__clamp(
            value,
            1,
            ConnectionConfig.MAX_ROW_LIMIT,
            ConnectionConfig.DEFAULT_ROW_LIMIT,
        )

    # ---------------------------------------------------------------- behaviour
    def default_name(self) -> str:
        """``<user>@<host>/<database>``: the name used when none is set."""
        return "{}@{}/{}".format(self.__username, self.__host, self.__database)

    def display_name(self) -> str:
        """The configured name, or ``default_name()`` when it is empty."""
        return self.__name or self.default_name()

    def missing_fields(self) -> list[str]:
        """Labels (shown to the user) of required fields that are empty."""
        missing = []
        if not self.__host:
            missing.append("Host")
        if not self.__database:
            missing.append("Database")
        if not self.__username:
            missing.append("Username")
        return missing

    def is_complete(self) -> bool:
        """True when every required field is set."""
        return not self.missing_fields()

    def copy(self) -> ConnectionConfig:
        """Independent copy of this configuration."""
        return ConnectionConfig(**self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        """Serializable representation."""
        return {
            "name": self.__name,
            "host": self.__host,
            "port": self.__port,
            "database": self.__database,
            "username": self.__username,
            "connect_timeout": self.__connect_timeout,
            "query_timeout": self.__query_timeout,
            "row_limit": self.__row_limit,
        }

    @staticmethod
    def from_dict(data: object) -> ConnectionConfig:
        """Build a configuration from untrusted data, ignoring values of the
        wrong type."""
        config = ConnectionConfig()
        if not isinstance(data, dict):
            return config
        for name, default in config.to_dict().items():
            value = data.get(name)
            if isinstance(value, type(default)) and not isinstance(value, bool):
                setattr(config, name, value)
        return config

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ConnectionConfig)
            and self.to_dict() == other.to_dict()
        )

    def __hash__(self) -> int:
        return hash(tuple(self.to_dict().items()))

    def __repr__(self) -> str:
        fields = ", ".join(
            "{}={!r}".format(key, value)
            for key, value in self.to_dict().items()
        )
        return "ConnectionConfig({})".format(fields)

    @staticmethod
    def __clamp(value: object, low: int, high: int, default: int) -> int:
        if isinstance(value, bool):
            return default
        try:
            number = int(value)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            return default
        return max(low, min(high, number))
