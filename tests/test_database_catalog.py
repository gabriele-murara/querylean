"""Tests of the listing of the databases."""

import pytest

from fakes.fake_connector import FakeConnector
from querylean.config.connection_config import ConnectionConfig
from querylean.database.connection.connection_manager import ConnectionManager
from querylean.database.execution.query_executor import QueryExecutor
from querylean.database.schema.database_catalog import DatabaseCatalog
from querylean.database.validation.read_only_validator import (
    ReadOnlyValidator,
)


class TestDatabaseCatalog:
    """Names in server order, through the validator."""

    @pytest.fixture
    def catalog(self) -> DatabaseCatalog:
        connector = FakeConnector()
        connector.configure = lambda conn: setattr(
            conn, "databases", ["information_schema", b"shop", "crm"]
        )
        manager = ConnectionManager(connector)
        manager.connect(
            ConnectionConfig(host="db", database="crm", username="ro"), "pw"
        )
        return DatabaseCatalog(QueryExecutor(manager))

    def test_statement_passes_the_validator(self):
        assert ReadOnlyValidator().validate(DatabaseCatalog.LIST_STATEMENT).ok

    def test_list(self, catalog):
        assert catalog.list_databases(10) == [
            "information_schema",
            "shop",
            "crm",
        ]
