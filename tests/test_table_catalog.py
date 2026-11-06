"""Tests of table listing and identifier quoting."""

import pytest
from mysql.connector import errors as mysql_errors

from fakes.fake_connector import FakeConnector
from fakes.schema_handler import SchemaHandler
from querylean.config.connection_config import ConnectionConfig
from querylean.database.connection.connection_manager import ConnectionManager
from querylean.database.errors.database_error import DatabaseError
from querylean.database.execution.query_executor import QueryExecutor
from querylean.database.schema.mysql_identifier import MySqlIdentifier
from querylean.database.schema.table_catalog import TableCatalog
from querylean.database.schema.table_info import TableInfo
from querylean.database.validation.read_only_validator import (
    ReadOnlyValidator,
)


class TestTableCatalog:
    """SHOW FULL TABLES through the executor, views, quoting."""

    @pytest.fixture
    def handler(self):
        return SchemaHandler(
            [
                ("customers", "BASE TABLE"),
                (b"orders", b"BASE TABLE"),
                ("v_totals", "VIEW"),
            ]
        )

    @pytest.fixture
    def connector(self, handler):
        connector = FakeConnector()
        connector.configure = lambda conn: setattr(conn, "handler", handler)
        return connector

    @pytest.fixture
    def catalog(self, connector):
        manager = ConnectionManager(connector)
        manager.connect(
            ConnectionConfig(host="db", database="app", username="ro"), "pw"
        )
        return TableCatalog(QueryExecutor(manager))

    def test_lists_tables_and_views(self, catalog, connector):
        assert catalog.list_tables(30) == [
            TableInfo("customers"),
            TableInfo("orders"),
            TableInfo("v_totals", is_view=True),
        ]
        executed = connector.connections[0].executed
        assert TableCatalog.LIST_STATEMENT in executed

    def test_listing_passes_the_validator(self):
        assert ReadOnlyValidator().validate(TableCatalog.LIST_STATEMENT).ok

    def test_errors_are_translated(self, catalog, handler):
        handler.error = mysql_errors.ProgrammingError(
            msg="No database selected", errno=1046
        )
        with pytest.raises(DatabaseError):
            catalog.list_tables(30)

    @pytest.mark.parametrize(
        ("name", "quoted"),
        [
            ("users", "`users`"),
            ("my table", "`my table`"),
            ("a`b", "`a``b`"),
            ("select", "`select`"),
        ],
    )
    def test_quote(self, name, quoted):
        assert MySqlIdentifier.quote(name) == quoted

    @pytest.mark.parametrize("name", ["users", "my table", "a`b", "order"])
    def test_select_statement_is_a_valid_read_query(self, name):
        statement = TableInfo(name).select_statement
        expected = "SELECT * FROM {} LIMIT 1;"
        assert statement == expected.format(MySqlIdentifier.quote(name))
        assert ReadOnlyValidator().validate(statement).ok

    @pytest.mark.parametrize(
        ("table", "column"),
        [("users", "id"), ("my table", "full name"), ("a`b", "c`d")],
    )
    def test_column_statement_is_a_valid_read_query(self, table, column):
        statement = TableInfo(table).column_statement(column)
        expected = "SELECT {} FROM {} LIMIT 1;"
        assert statement == expected.format(
            MySqlIdentifier.quote(column), MySqlIdentifier.quote(table)
        )
        assert ReadOnlyValidator().validate(statement).ok

    def test_columns_statement(self):
        table = TableInfo("my t")
        assert table.columns_statement([]) == table.select_statement
        assert table.columns_statement(["a", "b c"]) == (
            "SELECT `a`, `b c` FROM `my t` LIMIT 1;"
        )
        assert (
            ReadOnlyValidator()
            .validate(table.columns_statement(["a", "x`y"]))
            .ok
        )

    @pytest.mark.parametrize(
        ("statement", "columns"),
        [
            ("SELECT * FROM `my t` LIMIT 1;", []),
            ("SELECT `a` FROM `my t` LIMIT 1;", ["a"]),
            ("  SELECT `a`, `b, c` FROM `my t` LIMIT 1;\n", ["a", "b, c"]),
            ("SELECT `x``y` FROM `my t` LIMIT 1;", ["x`y"]),
            ("SELECT * FROM `other` LIMIT 1;", None),
            ("SELECT a FROM `my t` LIMIT 1;", None),
            ("SELECT `a`,`b` FROM `my t` LIMIT 1;", None),
            ("SELECT `a` FROM `my t` LIMIT 5;", None),
            ("SELECT `a` FROM `my t` WHERE 1 LIMIT 1;", None),
            ("", None),
        ],
    )
    def test_selected_columns(self, statement, columns):
        assert TableInfo("my t").selected_columns(statement) == columns

    def test_qualified_statements(self):
        table = TableInfo("t", database="my db")
        assert table.reference == "`my db`.`t`"
        assert table.select_statement == "SELECT * FROM `my db`.`t` LIMIT 1;"
        statement = table.columns_statement(["a", "b"])
        assert statement == "SELECT `a`, `b` FROM `my db`.`t` LIMIT 1;"
        assert table.selected_columns(statement) == ["a", "b"]
        # The same table of another database is another preview.
        assert TableInfo("t").selected_columns(statement) is None
        assert ReadOnlyValidator().validate(statement).ok
        assert TableCatalog.list_statement("my db") == (
            "SHOW FULL TABLES FROM `my db`"
        )
        assert (
            ReadOnlyValidator()
            .validate(TableCatalog.list_statement("my db"))
            .ok
        )
