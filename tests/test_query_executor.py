import threading
import time

import pytest
from mysql.connector import errors as mysql_errors

from fakes import FakeConnector
from querylean.config.config_manager import ConnectionConfig
from querylean.database.connection_manager import ConnectionManager
from querylean.database.errors import DatabaseError, QueryCancelled, QueryTimeout
from querylean.database.query_executor import QueryExecutor

CFG = ConnectionConfig(host="db", database="app", username="ro")


@pytest.fixture
def setup():
    connector = FakeConnector()
    manager = ConnectionManager(connector)
    manager.connect(CFG, "pw")
    return connector, manager, QueryExecutor(manager)


def test_select_returns_rows_and_metadata(setup):
    connector, _, executor = setup
    result = executor.execute("SELECT n FROM t", row_limit=1000, timeout=30)
    assert result.columns == ["n"]
    assert result.rows == [(0,), (1,), (2,)]
    assert not result.truncated
    assert result.elapsed >= 0
    assert "SET SESSION MAX_EXECUTION_TIME = 30000" in connector.connections[0].executed


def test_rejected_query_never_reaches_server(setup):
    connector, _, executor = setup
    with pytest.raises(DatabaseError) as info:
        executor.execute("DELETE FROM t", row_limit=10, timeout=30)
    assert info.value.kind == "rejected"
    assert not any("DELETE" in s for s in connector.connections[0].executed)


def test_limit_applied_while_fetching(setup):
    connector, manager, executor = setup
    conn = connector.connections[0]
    conn.row_count = 50_000
    result = executor.execute("SELECT n FROM t", row_limit=1000, timeout=30)
    assert len(result.rows) == 1000
    assert result.truncated
    assert conn.fetched == 1001  # mai l'intero result set
    assert conn.closed_by == "shutdown"  # resto del result set scartato
    # la query successiva riapre la sessione in modo trasparente
    executor.execute("SELECT 1", row_limit=10, timeout=30)
    assert len(connector.connections) == 2


def test_exact_limit_is_not_truncated(setup):
    connector, _, executor = setup
    connector.connections[0].row_count = 10
    result = executor.execute("SELECT n FROM t", row_limit=10, timeout=30)
    assert len(result.rows) == 10 and not result.truncated


def test_server_timeout_error(setup):
    connector, _, executor = setup
    connector.connections[0].handler = lambda sql: mysql_errors.DatabaseError(
        msg="Query execution was interrupted, maximum statement execution time exceeded",
        errno=3024,
    )
    with pytest.raises(QueryTimeout):
        executor.execute("SELECT SLEEP(100)", row_limit=10, timeout=1)


def test_syntax_error_is_translated(setup):
    connector, _, executor = setup
    connector.connections[0].handler = lambda sql: mysql_errors.ProgrammingError(
        msg="You have an error in your SQL syntax", errno=1064
    )
    with pytest.raises(DatabaseError) as info:
        executor.execute("SELECT a FROM t", row_limit=10, timeout=30)
    assert info.value.kind == "syntax"


@pytest.mark.parametrize(("reason", "expected"), [("user", QueryCancelled),
                                                   ("timeout", QueryTimeout)])
def test_cancel_interrupts_running_query(setup, reason, expected):
    connector, _, executor = setup
    conn = connector.connections[0]
    gate = threading.Event()
    conn.block_fetch = gate

    def kill_handler(c):
        # La connessione "killer" sblocca la query in corso.
        def on_kill(sql):
            return ([], [])
        c.handler = on_kill
    connector.configure = kill_handler

    errors = []

    def run():
        try:
            executor.execute("SELECT n FROM t", row_limit=10, timeout=30)
        except DatabaseError as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    for _ in range(100):
        if executor.running:
            break
        time.sleep(0.01)
    assert executor.cancel(reason)
    assert connector.connections[-1].executed == [f"KILL QUERY {conn.connection_id}"]
    conn.killed = True
    gate.set()
    thread.join(5)
    assert len(errors) == 1 and isinstance(errors[0], expected)
    assert not executor.running


def test_cancel_when_idle_is_noop(setup):
    _, _, executor = setup
    assert executor.cancel() is False


def test_not_connected(setup):
    _, manager, executor = setup
    manager.disconnect()
    with pytest.raises(DatabaseError) as info:
        executor.execute("SELECT 1", row_limit=10, timeout=30)
    assert info.value.kind == "not_connected"


def test_socket_read_timeout_drops_session(setup):
    connector, manager, executor = setup
    connector.connections[0].handler = lambda sql: mysql_errors.ReadTimeoutError(
        msg="read timed out")
    with pytest.raises(DatabaseError) as info:
        executor.execute("SELECT 1", row_limit=10, timeout=1)
    assert info.value.kind == "connection_lost"
    assert connector.connections[0].closed_by == "shutdown"
