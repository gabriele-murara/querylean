import logging

import pytest
from mysql.connector import errors as mysql_errors
from mysql.connector.constants import ClientFlag

from fakes import FakeConnector
from querylean.config.config_manager import ConnectionConfig
from querylean.database.connection_manager import ConnectionManager
from querylean.database.errors import DatabaseError

CFG = ConnectionConfig(host="db", port=3307, database="app", username="ro")


@pytest.fixture
def connector():
    return FakeConnector()


@pytest.fixture
def manager(connector):
    return ConnectionManager(connector)


def test_connect_uses_safe_driver_options(manager, connector):
    manager.connect(CFG, "s3cret")
    kwargs = connector.connections[0].kwargs
    assert kwargs["host"] == "db" and kwargs["port"] == 3307
    assert kwargs["database"] == "app" and kwargs["user"] == "ro"
    assert kwargs["connection_timeout"] == 5
    assert -ClientFlag.MULTI_STATEMENTS in kwargs["client_flags"]
    assert kwargs["allow_local_infile"] is False


def test_session_is_set_read_only(manager, connector):
    manager.connect(CFG, "pw")
    assert "SET SESSION TRANSACTION READ ONLY" in connector.connections[0].executed
    assert manager.is_connected()


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (mysql_errors.ProgrammingError(msg="denied", errno=1045), "auth"),
        (mysql_errors.ProgrammingError(msg="unknown db", errno=1049), "database"),
        (mysql_errors.DatabaseError(msg="no access", errno=1044), "database"),
        (mysql_errors.InterfaceError(msg="Can't connect", errno=2003), "unreachable"),
        (mysql_errors.InterfaceError(msg="Unknown host", errno=2005), "unreachable"),
        (TimeoutError("timed out"), "timeout"),
        (mysql_errors.InterfaceError(msg="Connection timed out", errno=2003), "timeout"),
    ],
)
def test_connect_errors_are_translated(manager, connector, error, kind):
    connector.error = error
    with pytest.raises(DatabaseError) as info:
        manager.connect(CFG, "pw")
    assert info.value.kind == kind
    assert "Traceback" not in info.value.message
    assert not manager.is_connected()


def test_disconnect_and_reconnect(manager, connector):
    manager.connect(CFG, "pw")
    first = connector.connections[0]
    manager.disconnect()
    assert not first.open and not manager.is_connected()
    manager.connect(CFG, "pw")
    assert manager.is_connected() and len(connector.connections) == 2


def test_ensure_connected_reopens_aborted_session(manager, connector):
    manager.connect(CFG, "pw")
    manager.abort_session()
    assert connector.connections[0].closed_by == "shutdown"
    conn = manager.ensure_connected()
    assert conn is connector.connections[1]


def test_ensure_connected_without_params_raises(manager):
    with pytest.raises(DatabaseError) as info:
        manager.ensure_connected()
    assert info.value.kind == "not_connected"


def test_test_connection_closes_its_connection(manager, connector):
    assert manager.test_connection(CFG, "pw") == "8.0.36"
    assert not connector.connections[0].open
    assert not manager.is_connected()


def test_kill_uses_separate_connection(manager, connector):
    manager.connect(CFG, "pw")
    target = manager.connection_id
    assert manager.kill_running_query()
    killer = connector.connections[1]
    assert killer.executed == [f"KILL QUERY {target}"]
    assert not killer.open


def test_password_never_logged(manager, connector, caplog):
    from querylean.utils.logging_config import redacting_filter

    caplog.handler.addFilter(redacting_filter)
    caplog.set_level(logging.DEBUG)
    connector.error = mysql_errors.ProgrammingError(msg="denied for pw-XYZ", errno=1045)
    with pytest.raises(DatabaseError):
        manager.connect(CFG, "pw-XYZ")
    assert "pw-XYZ" not in caplog.text
