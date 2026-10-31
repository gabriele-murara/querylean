"""Tests of the connection configuration model."""

from querylean.config.connection_config import ConnectionConfig


class TestConnectionConfig:
    """Defaults, normalising setters, required fields and serialisation."""

    def test_defaults(self):
        cfg = ConnectionConfig()
        assert (cfg.host, cfg.port, cfg.database, cfg.username) == (
            "localhost",
            3306,
            "",
            "",
        )
        assert (cfg.connect_timeout, cfg.query_timeout, cfg.row_limit) == (
            5,
            30,
            1000,
        )

    def test_setters_normalise_values(self):
        cfg = ConnectionConfig(
            host="  db  ", row_limit=99_999, port=0, query_timeout=-5
        )
        assert cfg.host == "db"
        assert cfg.row_limit == ConnectionConfig.MAX_ROW_LIMIT
        assert cfg.port == 1
        assert cfg.query_timeout == 1
        cfg.port = "abc"
        assert cfg.port == ConnectionConfig.DEFAULT_PORT

    def test_missing_fields(self):
        assert ConnectionConfig().missing_fields() == ["Database", "Username"]
        assert ConnectionConfig(
            host=" ", database="d", username="u"
        ).missing_fields() == ["Host"]
        assert ConnectionConfig(database="d", username="u").is_complete()

    def test_copy_is_independent_and_equal(self):
        cfg = ConnectionConfig(database="d", username="u")
        clone = cfg.copy()
        assert clone == cfg and clone is not cfg
        clone.database = "other"
        assert cfg.database == "d"

    def test_from_dict_ignores_wrong_types(self):
        cfg = ConnectionConfig.from_dict(
            {
                "port": "abc",
                "row_limit": 99999,
                "host": 5,
                "connect_timeout": True,
                "username": "ro",
            }
        )
        assert cfg.port == 3306
        assert cfg.row_limit == 10_000
        assert cfg.host == "localhost"
        assert cfg.connect_timeout == 5
        assert cfg.username == "ro"
        assert ConnectionConfig.from_dict("not a dict") == ConnectionConfig()
