"""Test d'integrazione contro un'istanza MySQL di test (non distruttivi).

Prerequisiti: eseguire `tests/integration/setup_test_db.sql` e impostare
QUERYLEAN_TEST_HOST, QUERYLEAN_TEST_PORT, QUERYLEAN_TEST_DATABASE, QUERYLEAN_TEST_USER,
QUERYLEAN_TEST_PASSWORD.
Senza queste variabili i test vengono saltati.
"""

import os
import threading
import time

import pytest

from querylean.config.config_manager import ConnectionConfig
from querylean.database.connection_manager import ConnectionManager
from querylean.database.errors import DatabaseError, QueryCancelled, QueryTimeout
from querylean.database.query_executor import QueryExecutor

pytestmark = pytest.mark.integration

ENV = {name: os.environ.get(f"QUERYLEAN_TEST_{name}") for name in
       ("HOST", "PORT", "DATABASE", "USER", "PASSWORD")}

if not ENV["USER"] or ENV["PASSWORD"] is None:
    pytest.skip("Variabili QUERYLEAN_TEST_* non impostate: test d'integrazione saltati",
                allow_module_level=True)

CONFIG = ConnectionConfig(
    host=ENV["HOST"] or "127.0.0.1",
    port=int(ENV["PORT"] or 3306),
    database=ENV["DATABASE"] or "querylean_test",
    username=ENV["USER"],
    connect_timeout=5,
)


@pytest.fixture
def manager():
    m = ConnectionManager()
    m.connect(CONFIG, ENV["PASSWORD"])
    yield m
    m.disconnect()


@pytest.fixture
def executor(manager):
    return QueryExecutor(manager)


def test_select_types_and_nulls(executor):
    result = executor.execute("SELECT * FROM people ORDER BY id", row_limit=100, timeout=10)
    assert result.columns[:3] == ["id", "name", "note"]
    by_id = {row[0]: row for row in result.rows}
    assert by_id[2][1] is None and by_id[2][2] == ""
    assert by_id[1][2] == "UPDATE; DELETE"
    assert len(result.rows) == 3 and not result.truncated


def test_show_describe_explain(executor):
    assert executor.execute("SHOW TABLES", 100, 10).rows
    assert executor.execute("DESCRIBE people", 100, 10).rows
    assert executor.execute("EXPLAIN SELECT * FROM people", 100, 10).rows


def test_row_limit_is_applied_and_session_recovers(executor, manager):
    result = executor.execute("SELECT n FROM numbers ORDER BY n", row_limit=1000, timeout=10)
    assert len(result.rows) == 1000 and result.truncated
    assert result.rows[-1] == (1000,)
    again = executor.execute("SELECT COUNT(*) FROM numbers", row_limit=10, timeout=10)
    assert again.rows == [(2500,)]


def test_server_side_timeout(executor):
    started = time.monotonic()
    with pytest.raises(QueryTimeout):
        # MAX_EXECUTION_TIME interrompe le SELECT lente (SLEEP restituisce 1 se interrotta,
        # quindi si usa un join pesante per forzare l'errore lato server).
        executor.execute(
            "SELECT COUNT(*) FROM numbers a, numbers b, numbers c WHERE a.n + b.n = c.n",
            row_limit=10, timeout=1,
        )
    assert time.monotonic() - started < 10


def test_cancel_running_query(executor):
    errors = []

    def run():
        try:
            executor.execute(
                "SELECT COUNT(*) FROM numbers a, numbers b, numbers c WHERE a.n + b.n = c.n",
                row_limit=10, timeout=60,
            )
        except DatabaseError as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    time.sleep(0.5)
    assert executor.cancel("user")
    thread.join(10)
    assert not thread.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], QueryCancelled)
    assert executor.execute("SELECT 1", 10, 10).rows == [(1,)]


@pytest.mark.parametrize("sql", [
    "DELETE FROM people",
    "UPDATE people SET name = 'x'",
    "INSERT INTO people (id) VALUES (99)",
    "DROP TABLE people",
    "SELECT 1; DELETE FROM people",
    "SELECT * FROM people INTO OUTFILE '/tmp/querylean.txt'",
])
def test_write_queries_rejected_before_execution(executor, sql):
    with pytest.raises(DatabaseError) as info:
        executor.execute(sql, 10, 10)
    assert info.value.kind == "rejected"


@pytest.mark.parametrize("sql", [
    "DELETE FROM people WHERE id = -1",
    "INSERT INTO people (id) VALUES (-1)",
    "CREATE TABLE querylean_should_not_exist (id INT)",
])
def test_server_blocks_writes_even_bypassing_validator(manager, sql):
    """Seconda barriera: privilegi dell'account e sessione READ ONLY (non distruttivo)."""
    import mysql.connector

    conn = manager.ensure_connected()
    cursor = conn.cursor()
    with pytest.raises(mysql.connector.Error):
        cursor.execute(sql)
    cursor.close()


def test_driver_refuses_multiple_statements(manager):
    import mysql.connector

    conn = manager.ensure_connected()
    cursor = conn.cursor()
    with pytest.raises(mysql.connector.Error):
        cursor.execute("SELECT 1; SELECT 2")
    try:
        cursor.close()
    except mysql.connector.Error:
        pass


def test_wrong_password_is_reported():
    with pytest.raises(DatabaseError) as info:
        ConnectionManager().connect(CONFIG, "definitely-wrong-password")
    assert info.value.kind == "auth"
