"""Tests of query execution with a fake driver."""

import threading
import time

import pytest
from mysql.connector import errors as mysql_errors

from fakes.fake_connector import FakeConnector
from querylean.config.connection_config import ConnectionConfig
from querylean.database.connection.connection_manager import ConnectionManager
from querylean.database.errors.database_error import DatabaseError
from querylean.database.errors.query_cancelled import QueryCancelled
from querylean.database.errors.query_timeout import QueryTimeout
from querylean.database.execution.query_executor import QueryExecutor


class TestQueryExecutor:
    """Validation before execution, row limit, timeouts and cancellation."""

    CFG = ConnectionConfig(host="db", database="app", username="ro")

    @pytest.fixture
    def connector(self) -> FakeConnector:
        return FakeConnector()

    @pytest.fixture
    def manager(self, connector) -> ConnectionManager:
        manager = ConnectionManager(connector)
        manager.connect(self.CFG, "pw")
        return manager

    @pytest.fixture
    def executor(self, manager) -> QueryExecutor:
        return QueryExecutor(manager)

    def test_select_returns_rows_and_metadata(self, connector, executor):
        result = executor.execute("SELECT n FROM t", row_limit=1000, timeout=30)
        assert result.columns == ["n"]
        assert result.rows == [(0,), (1,), (2,)]
        assert not result.truncated
        assert result.elapsed >= 0
        assert "SET SESSION MAX_EXECUTION_TIME = 30000" in connector.connections[0].executed

    def test_rejected_query_never_reaches_server(self, connector, executor):
        with pytest.raises(DatabaseError) as info:
            executor.execute("DELETE FROM t", row_limit=10, timeout=30)
        assert info.value.kind == "rejected"
        assert not any("DELETE" in s for s in connector.connections[0].executed)

    def test_limit_applied_while_fetching(self, connector, executor):
        conn = connector.connections[0]
        conn.row_count = 50_000
        result = executor.execute("SELECT n FROM t", row_limit=1000, timeout=30)
        assert len(result.rows) == 1000
        assert result.truncated
        assert conn.fetched == 1001  # never the whole result set
        assert conn.closed_by == "shutdown"  # the rest of the result set is discarded
        executor.execute("SELECT 1", row_limit=10, timeout=30)
        assert len(connector.connections) == 2  # session reopened transparently

    def test_exact_limit_is_not_truncated(self, connector, executor):
        connector.connections[0].row_count = 10
        result = executor.execute("SELECT n FROM t", row_limit=10, timeout=30)
        assert len(result.rows) == 10 and not result.truncated

    def test_server_timeout_error(self, connector, executor):
        connector.connections[0].handler = lambda sql: mysql_errors.DatabaseError(
            msg="maximum statement execution time exceeded", errno=3024
        )
        with pytest.raises(QueryTimeout):
            executor.execute("SELECT SLEEP(100)", row_limit=10, timeout=1)

    def test_server_error_is_translated(self, connector, executor):
        connector.connections[0].handler = lambda sql: mysql_errors.ProgrammingError(
            msg="You have an error in your SQL syntax", errno=1064
        )
        with pytest.raises(DatabaseError) as info:
            executor.execute("SELECT a FROM t", row_limit=10, timeout=30)
        assert info.value.kind == "syntax"

    def test_socket_read_timeout_drops_session(self, connector, executor):
        connector.connections[0].handler = lambda sql: mysql_errors.ReadTimeoutError(
            msg="read timed out"
        )
        with pytest.raises(DatabaseError) as info:
            executor.execute("SELECT 1", row_limit=10, timeout=1)
        assert info.value.kind == "connection_lost"
        assert connector.connections[0].closed_by == "shutdown"

    @pytest.mark.parametrize(
        ("reason", "expected"),
        [
            (QueryExecutor.CANCEL_BY_USER, QueryCancelled),
            (QueryExecutor.CANCEL_BY_TIMEOUT, QueryTimeout),
        ],
    )
    def test_cancel_interrupts_running_query(self, connector, executor, reason, expected):
        conn = connector.connections[0]
        gate = threading.Event()
        conn.block_fetch = gate

        def on_kill():
            conn.killed = True
            gate.set()

        connector.configure = lambda killer: setattr(killer, "on_kill", on_kill)
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
        thread.join(5)
        assert len(errors) == 1 and isinstance(errors[0], expected)
        assert not executor.running

    def test_cancel_when_idle_is_noop(self, executor):
        assert executor.cancel() is False

    def test_not_connected(self, manager, executor):
        manager.disconnect()
        with pytest.raises(DatabaseError) as info:
            executor.execute("SELECT 1", row_limit=10, timeout=30)
        assert info.value.kind == "not_connected"
