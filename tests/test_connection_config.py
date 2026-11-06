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

    def test_caution_databases_default_and_serialised(self):
        assert ConnectionConfig().caution_databases == ()
        assert ConnectionConfig().caution_mode is False
        cfg = ConnectionConfig(
            database="d", username="u", caution_databases=["d", "x"]
        )
        assert cfg.caution_mode is True
        assert cfg.to_dict()["caution_databases"] == ["d", "x"]
        assert ConnectionConfig.from_dict(cfg.to_dict()) == cfg
        assert cfg.copy().caution_databases == ("d", "x")
        assert hash(cfg) == hash(cfg.copy())

    def test_caution_databases_are_cleaned(self):
        cfg = ConnectionConfig()
        cfg.caution_databases = [" a ", "", "a", "b", 3, None]
        assert cfg.caution_databases == ("a", "b")
        cfg.caution_databases = "solo"
        assert cfg.caution_databases == ("solo",)
        for value in (1, "x", None, {"a": 1}):
            loaded = ConnectionConfig.from_dict({"caution_databases": value})
            assert loaded.caution_databases == (), value

    def test_legacy_caution_mode_accepts_its_database(self):
        # Up to 1.7 caution mode was one flag for the connection.
        legacy = {"database": "app", "caution_mode": True}
        assert ConnectionConfig.from_dict(legacy).caution_databases == ("app",)
        for value in (1, "true", False, None):
            loaded = ConnectionConfig.from_dict(
                {"database": "app", "caution_mode": value}
            )
            assert loaded.caution_databases == (), value
        assert ConnectionConfig.from_dict({"host": "db"}).caution_mode is False
        assert "caution_mode" not in ConnectionConfig().to_dict()

    def test_all_databases(self):
        cfg = ConnectionConfig(host="db", username="ro", all_databases=True)
        assert cfg.is_complete()  # the database is optional
        assert cfg.default_name() == "ro@db/*"
        assert cfg.scope_label() == "*"
        assert ConnectionConfig.from_dict(cfg.to_dict()).all_databases
        assert ConnectionConfig.from_dict(
            {"all_databases": 1}
        ).all_databases is (False)
        assert (
            "Database"
            in ConnectionConfig(host="db", username="ro").missing_fields()
        )
