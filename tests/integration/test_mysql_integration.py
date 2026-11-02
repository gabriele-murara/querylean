"""Integration tests against a test MySQL instance (non destructive).

Prerequisites: run ``tests/integration/setup_test_db.sql`` and set
QUERYLEAN_TEST_HOST, QUERYLEAN_TEST_PORT, QUERYLEAN_TEST_DATABASE,
QUERYLEAN_TEST_USER and QUERYLEAN_TEST_PASSWORD. Without these variables the
tests are skipped.
"""

import os
import threading
import time

import mysql.connector
import pytest

from querylean.config.connection_config import ConnectionConfig
from querylean.database.connection.connection_manager import ConnectionManager
from querylean.database.errors.database_error import DatabaseError
from querylean.database.errors.query_cancelled import QueryCancelled
from querylean.database.errors.query_timeout import QueryTimeout
from querylean.database.execution.query_executor import QueryExecutor
from querylean.database.schema.table_catalog import TableCatalog


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("QUERYLEAN_TEST_USER")
    or "QUERYLEAN_TEST_PASSWORD" not in os.environ,
    reason="QUERYLEAN_TEST_* variables not set: integration tests skipped",
)
class TestMysqlIntegration:
    """Allowed reads, limits, timeouts, cancellation and the server-side
    barriers."""

    # Cartesian product slow enough to exceed short timeouts.
    SLOW_QUERY = "SELECT COUNT(*) FROM numbers a, numbers b, numbers c "
    SLOW_QUERY += "WHERE a.n + b.n = c.n"

    @pytest.fixture
    def config(self) -> ConnectionConfig:
        return ConnectionConfig(
            host=os.environ.get("QUERYLEAN_TEST_HOST") or "127.0.0.1",
            port=int(os.environ.get("QUERYLEAN_TEST_PORT") or 3306),
            database=os.environ.get("QUERYLEAN_TEST_DATABASE")
            or "querylean_test",
            username=os.environ["QUERYLEAN_TEST_USER"],
            connect_timeout=5,
        )

    @pytest.fixture
    def manager(self, config):
        manager = ConnectionManager()
        manager.connect(config, os.environ["QUERYLEAN_TEST_PASSWORD"])
        yield manager
        manager.disconnect()

    @pytest.fixture
    def executor(self, manager) -> QueryExecutor:
        return QueryExecutor(manager)

    def test_select_types_and_nulls(self, executor):
        result = executor.execute(
            "SELECT * FROM people ORDER BY id", row_limit=100, timeout=10
        )
        assert result.columns[:3] == ["id", "name", "note"]
        by_id = {row[0]: row for row in result.rows}
        assert by_id[2][1] is None and by_id[2][2] == ""
        assert by_id[1][2] == "UPDATE; DELETE"
        assert len(result.rows) == 3 and not result.truncated

    def test_show_describe_explain(self, executor):
        assert executor.execute("SHOW TABLES", 100, 10).rows
        assert executor.execute("DESCRIBE people", 100, 10).rows
        assert executor.execute("EXPLAIN SELECT * FROM people", 100, 10).rows

    def test_table_catalog_and_preview_query(self, executor):
        tables = TableCatalog(executor).list_tables(10)
        by_name = {t.name: t for t in tables}
        assert {"people", "numbers"} <= set(by_name)
        assert not by_name["people"].is_view
        result = executor.execute(by_name["people"].select_statement, 100, 10)
        assert len(result.rows) == 1

    def test_row_limit_is_applied_and_session_recovers(self, executor):
        result = executor.execute(
            "SELECT n FROM numbers ORDER BY n", row_limit=1000, timeout=10
        )
        assert len(result.rows) == 1000 and result.truncated
        assert result.rows[-1] == (1000,)
        assert executor.execute(
            "SELECT COUNT(*) FROM numbers", 10, 10
        ).rows == [(2500,)]

    def test_server_side_timeout(self, executor):
        started = time.monotonic()
        with pytest.raises(QueryTimeout):
            executor.execute(self.SLOW_QUERY, row_limit=10, timeout=1)
        assert time.monotonic() - started < 10

    def test_cancel_running_query(self, executor):
        errors = []

        def run():
            try:
                executor.execute(self.SLOW_QUERY, row_limit=10, timeout=60)
            except DatabaseError as exc:
                errors.append(exc)

        thread = threading.Thread(target=run)
        thread.start()
        time.sleep(0.5)
        assert executor.cancel(QueryExecutor.CANCEL_BY_USER)
        thread.join(10)
        assert not thread.is_alive()
        assert len(errors) == 1 and isinstance(errors[0], QueryCancelled)
        assert executor.execute("SELECT 1", 10, 10).rows == [(1,)]

    @pytest.mark.parametrize(
        "sql",
        [
            "DELETE FROM people",
            "UPDATE people SET name = 'x'",
            "INSERT INTO people (id) VALUES (99)",
            "DROP TABLE people",
            "SELECT 1; DELETE FROM people",
            "SELECT * FROM people INTO OUTFILE '/tmp/querylean.txt'",
        ],
    )
    def test_write_queries_rejected_before_execution(self, executor, sql):
        with pytest.raises(DatabaseError) as info:
            executor.execute(sql, 10, 10)
        assert info.value.kind == "rejected"

    @pytest.mark.parametrize(
        "sql",
        [
            "DELETE FROM people WHERE id = -1",
            "INSERT INTO people (id) VALUES (-1)",
            "CREATE TABLE querylean_should_not_exist (id INT)",
        ],
    )
    def test_server_blocks_writes_even_bypassing_validator(self, manager, sql):
        """Second barrier: account privileges and READ ONLY session (non
        destructive)."""
        cursor = manager.ensure_connected().cursor()
        with pytest.raises(mysql.connector.Error):
            cursor.execute(sql)
        cursor.close()

    def test_select_only_account_is_read_only(self, manager):
        """The test account (SELECT only) passes the privilege check and the
        session is confirmed read-only."""
        assert manager.account_privileges.read_only
        cursor = manager.ensure_connected().cursor()
        try:
            cursor.execute("SELECT @@SESSION.transaction_read_only")
        except mysql.connector.Error:
            cursor.execute("SELECT @@SESSION.tx_read_only")
        assert int(cursor.fetchall()[0][0]) == 1
        cursor.close()

    def test_driver_refuses_multiple_statements(self, manager):
        cursor = manager.ensure_connected().cursor()
        with pytest.raises(mysql.connector.Error):
            cursor.execute("SELECT 1; SELECT 2")
        try:
            cursor.close()
        except mysql.connector.Error:
            pass

    def test_wrong_password_is_reported(self, config):
        with pytest.raises(DatabaseError) as info:
            ConnectionManager().connect(config, "definitely-wrong-password")
        assert info.value.kind == "auth"
