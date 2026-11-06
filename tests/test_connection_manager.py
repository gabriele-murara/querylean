"""Tests of the connection lifecycle with a fake driver."""

import logging

import pytest
from mysql.connector import errors as mysql_errors
from mysql.connector.constants import ClientFlag

from fakes.fake_connector import FakeConnector
from querylean.config.connection_config import ConnectionConfig
from querylean.database.connection.connection_manager import ConnectionManager
from querylean.database.connection.connection_params import ConnectionParams
from querylean.database.errors.database_error import DatabaseError
from querylean.log.log_manager import LogManager


class TestConnectionManager:
    """Driver options, error translation, reconnection and KILL QUERY."""

    CFG = ConnectionConfig(host="db", port=3307, database="app", username="ro")

    @pytest.fixture
    def connector(self) -> FakeConnector:
        return FakeConnector()

    @pytest.fixture
    def manager(self, connector) -> ConnectionManager:
        return ConnectionManager(connector)

    def test_connect_uses_safe_driver_options(self, manager, connector):
        manager.connect(self.CFG, "s3cret")
        kwargs = connector.connections[0].kwargs
        assert kwargs["host"] == "db" and kwargs["port"] == 3307
        assert kwargs["database"] == "app" and kwargs["user"] == "ro"
        assert kwargs["connection_timeout"] == 5
        assert (
            kwargs["read_timeout"] == 30 + ConnectionParams.SOCKET_TIMEOUT_GRACE
        )
        assert -ClientFlag.MULTI_STATEMENTS in kwargs["client_flags"]
        assert kwargs["allow_local_infile"] is False

    def test_session_is_set_read_only(self, manager, connector):
        manager.connect(self.CFG, "pw")
        assert (
            "SET SESSION TRANSACTION READ ONLY"
            in connector.connections[0].executed
        )
        assert manager.is_connected

    @pytest.mark.parametrize(
        ("error", "kind"),
        [
            (mysql_errors.ProgrammingError(msg="denied", errno=1045), "auth"),
            (
                mysql_errors.ProgrammingError(msg="unknown db", errno=1049),
                "database",
            ),
            (
                mysql_errors.DatabaseError(msg="no access", errno=1044),
                "database",
            ),
            (
                mysql_errors.InterfaceError(msg="Can't connect", errno=2003),
                "unreachable",
            ),
            (
                mysql_errors.InterfaceError(msg="Unknown host", errno=2005),
                "unreachable",
            ),
            (TimeoutError("timed out"), "timeout"),
            (
                mysql_errors.InterfaceError(
                    msg="Connection timed out", errno=2003
                ),
                "timeout",
            ),
        ],
    )
    def test_connect_errors_are_translated(
        self, manager, connector, error, kind
    ):
        connector.error = error
        with pytest.raises(DatabaseError) as info:
            manager.connect(self.CFG, "pw")
        assert info.value.kind == kind
        assert "Traceback" not in info.value.message
        assert not manager.is_connected

    def test_disconnect_and_reconnect(self, manager, connector):
        manager.connect(self.CFG, "pw")
        first = connector.connections[0]
        manager.disconnect()
        assert not first.is_connected() and not manager.is_connected
        manager.connect(self.CFG, "pw")
        assert manager.is_connected and len(connector.connections) == 2

    def test_config_of_the_session(self, manager):
        assert manager.config is None
        manager.connect(self.CFG, "pw")
        config = manager.config
        assert config == self.CFG
        # A copy: changing it does not touch the session.
        config.database = "other"
        assert manager.config == self.CFG
        manager.abort_session()
        assert manager.config == self.CFG
        manager.disconnect()
        assert manager.config is None

    def test_ensure_connected_reopens_aborted_session(self, manager, connector):
        manager.connect(self.CFG, "pw")
        manager.abort_session()
        assert connector.connections[0].closed_by == "shutdown"
        assert manager.ensure_connected() is connector.connections[1]

    def test_ensure_connected_without_params_raises(self, manager):
        with pytest.raises(DatabaseError) as info:
            manager.ensure_connected()
        assert info.value.kind == "not_connected"

    def test_test_connection_closes_its_connection(self, manager, connector):
        version, check = manager.test_connection(self.CFG, "pw")
        assert version == "8.0.36" and check.privileges.read_only
        assert not check.caution
        assert not connector.connections[0].is_connected()
        assert not manager.is_connected

    def test_kill_uses_separate_connection(self, manager, connector):
        manager.connect(self.CFG, "pw")
        target = manager.connection_id
        assert manager.kill_running_query()
        killer = connector.connections[1]
        assert killer.executed == ["KILL QUERY {}".format(target)]
        assert not killer.is_connected()

    def test_read_only_account_is_accepted(self, manager, connector):
        manager.connect(self.CFG, "pw")
        assert manager.account_privileges.read_only
        executed = connector.connections[0].executed
        assert ConnectionManager.GRANTS_STATEMENT in executed
        # One database: the list of databases is not read.
        assert ConnectionManager.DATABASES_STATEMENT not in executed
        assert manager.account_check.databases == ("app",)
        manager.disconnect()
        assert manager.account_privileges is None
        assert manager.account_check is None

    @pytest.mark.parametrize(
        "grants",
        [
            ["GRANT SELECT, INSERT, UPDATE ON `app`.* TO `rw`@`%`"],
            ["GRANT ALL PRIVILEGES ON *.* TO `root`@`localhost`"],
            ["GRANT `reader`@`%` TO `ro`@`%`"],
            mysql_errors.ProgrammingError(msg="denied", errno=1142),
        ],
    )
    def test_account_not_read_only_is_refused(self, manager, connector, grants):
        connector.configure = lambda conn: setattr(conn, "grants", grants)
        with pytest.raises(DatabaseError) as info:
            manager.connect(self.CFG, "pw")
        assert info.value.kind == ConnectionManager.WRITE_ACCOUNT_KIND
        assert "change data in app" in info.value.message
        assert "Test connection" in info.value.message
        assert not manager.is_connected
        assert connector.connections[0].closed_by is not None

    def test_writes_on_other_databases_do_not_matter(self, manager, connector):
        grants = [
            "GRANT SELECT ON `app`.* TO `ro`@`%`",
            "GRANT INSERT, DELETE ON `other`.* TO `ro`@`%`",
            "GRANT UPDATE ON `app2`.`t` TO `ro`@`%`",
        ]
        connector.configure = lambda conn: setattr(conn, "grants", grants)
        manager.connect(self.CFG, "pw")
        assert manager.is_connected
        assert not manager.account_check.caution
        assert not manager.account_privileges.read_only

    def test_wildcard_database_grants_count(self, manager, connector):
        # In grants "_" is a wildcard unless escaped: "a\\_p%" means
        # names starting with "a_p".
        grants = ["GRANT INSERT ON `a\\_p%`.* TO `rw`@`%`"]
        connector.configure = lambda conn: setattr(conn, "grants", grants)
        manager.connect(self.CFG, "pw")  # "app" does not match
        assert not manager.account_check.caution
        cfg = self.CFG.copy()
        cfg.database = "a_pp"
        with pytest.raises(DatabaseError):
            manager.connect(cfg, "pw")

    def test_accepted_database_allows_write_account(self, manager, connector):
        grants = ["GRANT SELECT, DELETE ON `app`.* TO `rw`@`%`"]
        connector.configure = lambda conn: setattr(conn, "grants", grants)
        cfg = self.CFG.copy()
        cfg.caution_databases = ["app"]
        manager.connect(cfg, "pw")
        assert manager.is_connected
        assert manager.account_privileges.write_privileges == ("DELETE",)
        assert manager.account_check.write_databases == ("app",)
        assert manager.account_check.refused == ()
        # The session is read-only in caution mode too.
        executed = connector.connections[0].executed
        assert "SET SESSION TRANSACTION READ ONLY" in executed

    def test_test_connection_reports_databases_to_accept(
        self, manager, connector
    ):
        grants = ["GRANT ALL PRIVILEGES ON *.* TO `root`@`%`"]
        connector.configure = lambda conn: setattr(conn, "grants", grants)
        _, check = manager.test_connection(self.CFG, "pw")
        assert check.refused == ("app",)
        assert check.reason("app") == "ALL PRIVILEGES"
        assert not manager.is_connected

    def test_all_databases_need_each_acceptance(self, manager, connector):
        def configure(conn):
            conn.grants = [
                "GRANT SELECT ON *.* TO `ro`@`%`",
                "GRANT INSERT ON `shop`.* TO `ro`@`%`",
                "GRANT UPDATE ON `crm`.`notes` TO `ro`@`%`",
            ]
            conn.databases = ["information_schema", "app", "shop", "crm"]

        connector.configure = configure
        cfg = ConnectionConfig(host="db", username="ro", all_databases=True)
        _, check = manager.test_connection(cfg, "pw")
        assert check.databases == ("information_schema", "app", "shop", "crm")
        assert check.write_databases == ("shop", "crm")
        assert check.describe() == "shop (INSERT); crm (UPDATE)"
        cfg.caution_databases = ["shop"]
        with pytest.raises(DatabaseError) as info:
            manager.connect(cfg, "pw")
        assert "crm (UPDATE)" in info.value.message
        assert "shop" not in info.value.message
        cfg.caution_databases = ["shop", "crm"]
        manager.connect(cfg, "pw")
        assert manager.account_check.write_databases == ("shop", "crm")
        # No default database: the driver gets none.
        assert "database" not in connector.connections[-1].kwargs

    def test_global_privileges_cover_every_database(self, manager, connector):
        def configure(conn):
            conn.grants = ["GRANT SELECT, PROCESS ON *.* TO `ro`@`%`"]
            conn.databases = ["information_schema", "app", "shop"]

        connector.configure = configure
        cfg = ConnectionConfig(host="db", username="ro", all_databases=True)
        _, check = manager.test_connection(cfg, "pw")
        # information_schema can never be changed.
        assert check.write_databases == ("app", "shop")

    def test_unverified_grants_make_every_database_writable(
        self, manager, connector
    ):
        def configure(conn):
            conn.grants = ["GRANT `reader`@`%` TO `ro`@`%`"]
            conn.databases = ["app", "shop"]

        connector.configure = configure
        cfg = ConnectionConfig(host="db", username="ro", all_databases=True)
        _, check = manager.test_connection(cfg, "pw")
        assert check.write_databases == ("app", "shop")
        assert "could not be verified" in check.reason("app")

    def test_database_list_failure_closes_the_connection(
        self, manager, connector
    ):
        connector.configure = lambda conn: setattr(
            conn,
            "databases",
            mysql_errors.ProgrammingError(msg="denied", errno=1227),
        )
        cfg = ConnectionConfig(host="db", username="ro", all_databases=True)
        with pytest.raises(DatabaseError) as info:
            manager.connect(cfg, "pw")
        assert "list of databases" in info.value.message
        assert connector.connections[0].closed_by is not None

    def test_use_database_survives_reconnection(self, manager, connector):
        cfg = ConnectionConfig(host="db", username="ro", all_databases=True)
        manager.connect(cfg, "pw")
        assert manager.active_database == ""
        manager.use_database("app")
        assert connector.connections[0].init_db == ["app"]
        assert manager.active_database == "app"
        assert manager.config.all_databases
        manager.abort_session()
        manager.ensure_connected()
        assert connector.connections[1].kwargs["database"] == "app"
        with pytest.raises(DatabaseError):
            manager.use_database("nowhere")
        assert manager.active_database == "app"

    def test_write_account_refused_again_on_reconnection(
        self, manager, connector
    ):
        manager.connect(self.CFG, "pw")
        manager.abort_session()
        connector.configure = lambda conn: setattr(
            conn, "grants", ["GRANT UPDATE ON *.* TO `ro`@`%`"]
        )
        with pytest.raises(DatabaseError) as info:
            manager.ensure_connected()
        assert info.value.kind == ConnectionManager.WRITE_ACCOUNT_KIND

    @pytest.mark.parametrize(
        "variables",
        [
            {"transaction_read_only": 0},
            {"transaction_read_only": "0"},
            {"transaction_read_only": None},
            {},
            {
                "transaction_read_only": mysql_errors.OperationalError(
                    msg="lost", errno=2013
                ),
                "tx_read_only": 0,
            },
        ],
    )
    def test_session_not_confirmed_read_only_is_closed(
        self, manager, connector, variables
    ):
        cfg = self.CFG.copy()
        cfg.caution_databases = ["app"]
        connector.configure = lambda conn: setattr(
            conn, "session_variables", variables
        )
        with pytest.raises(DatabaseError) as info:
            manager.connect(cfg, "pw")
        assert "did not confirm" in info.value.message
        assert not manager.is_connected
        assert connector.connections[0].closed_by is not None

    @pytest.mark.parametrize("value", [1, "1", b"1"])
    def test_read_only_check_falls_back_to_tx_read_only(
        self, manager, connector, value
    ):
        # Older servers (MySQL < 5.7.20, MariaDB < 11.1).
        connector.configure = lambda conn: setattr(
            conn, "session_variables", {"tx_read_only": value}
        )
        manager.connect(self.CFG, "pw")
        assert "SELECT @@SESSION.tx_read_only" in (
            connector.connections[0].executed
        )
        assert manager.is_connected

    def test_password_is_masked_in_params_repr(self):
        assert "pw-XYZ" not in repr(ConnectionParams(self.CFG, "pw-XYZ"))

    def test_password_never_logged(self, manager, connector, caplog):
        caplog.handler.addFilter(LogManager.redactor())
        caplog.set_level(logging.DEBUG)
        connector.error = mysql_errors.ProgrammingError(
            msg="denied for pw-XYZ", errno=1045
        )
        with pytest.raises(DatabaseError):
            manager.connect(self.CFG, "pw-XYZ")
        assert "pw-XYZ" not in caplog.text
