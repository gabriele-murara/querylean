"""Tests of the column listings, through the executor and a fake server."""

import pytest
from mysql.connector import errors as mysql_errors

from fakes.fake_connector import FakeConnector
from fakes.schema_handler import SchemaHandler
from querylean.config.connection_config import ConnectionConfig
from querylean.database.connection.connection_manager import ConnectionManager
from querylean.database.errors.database_error import DatabaseError
from querylean.database.execution.query_executor import QueryExecutor
from querylean.database.schema.column_catalog import ColumnCatalog
from querylean.database.schema.column_info import ColumnInfo
from querylean.database.validation.read_only_validator import (
    ReadOnlyValidator,
)


class TestColumnCatalog:
    """Whole database, single table, truncation, errors, validation."""

    COLUMNS = {
        "users": [
            ("id", "int", "NO", "PRI", None, "auto_increment", ""),
            ("name", b"varchar(64)", "YES", "", "x", "", "Full name"),
        ],
        "my t": [("v", "text", "YES", "", None, "", "")],
    }

    @pytest.fixture
    def handler(self) -> SchemaHandler:
        return SchemaHandler([("users", "BASE TABLE")], self.COLUMNS)

    @pytest.fixture
    def catalog(self, handler) -> ColumnCatalog:
        connector = FakeConnector()
        connector.configure = lambda conn: setattr(conn, "handler", handler)
        manager = ConnectionManager(connector)
        manager.connect(
            ConnectionConfig(host="db", database="app", username="ro"), "pw"
        )
        return ColumnCatalog(QueryExecutor(manager))

    def test_statements_pass_the_validator(self):
        validator = ReadOnlyValidator()
        assert validator.validate(ColumnCatalog.all_statement()).ok
        statement = ColumnCatalog.all_statement("it's\\db")
        assert "TABLE_SCHEMA = 'it''s\\\\db'" in statement
        assert validator.validate(statement).ok
        statement = ColumnCatalog.table_statement("odd`name")
        assert statement == "SHOW FULL COLUMNS FROM `odd``name`"
        assert validator.validate(statement).ok
        statement = ColumnCatalog.table_statement("t", "my db")
        assert statement == "SHOW FULL COLUMNS FROM `my db`.`t`"
        assert validator.validate(statement).ok

    def test_list_all(self, catalog):
        columns = catalog.list_all(30)
        assert list(columns) == ["my t", "users"]
        users = columns["users"]
        assert users[0] == ColumnInfo(
            "id", "int", nullable=False, key="PRI", extra="auto_increment"
        )
        assert users[0].is_primary
        assert users[1].data_type == "varchar(64)"  # bytes decoded
        assert users[1].default == "x" and users[1].comment == "Full name"

    def test_list_for_one_table(self, catalog):
        columns = catalog.list_for("users", 30)
        assert [c.name for c in columns] == ["id", "name"]
        assert not columns[0].nullable and columns[1].nullable
        assert catalog.list_for("my t", 30)[0].name == "v"

    def test_truncated_listing_drops_the_partial_table(
        self, catalog, monkeypatch
    ):
        monkeypatch.setattr(ColumnCatalog, "MAX_COLUMNS", 2)
        # Rows: my t.v, users.id (cut: users.name is beyond the limit).
        assert list(catalog.list_all(30)) == ["my t"]

    def test_errors_are_raised(self, catalog, handler):
        handler.columns_error = mysql_errors.ProgrammingError(
            msg="denied", errno=1142
        )
        with pytest.raises(DatabaseError):
            catalog.list_all(30)
        with pytest.raises(DatabaseError):
            catalog.list_for("users", 30)

    def test_column_description(self):
        column = ColumnInfo(
            "id",
            "int unsigned",
            nullable=False,
            key="pri",
            default="0",
            extra="auto_increment",
            comment="Key",
        )
        assert column.key == "PRI" and column.key_label() == "primary key"
        assert column.describe().splitlines() == [
            "id",
            "int unsigned",
            "NOT NULL",
            "primary key",
            "default: 0",
            "auto_increment",
            "“Key”",
        ]
        assert ColumnInfo("x", key="UNI").key_label() == "unique"
        assert ColumnInfo("x", key="MUL").key_label() == "indexed"
