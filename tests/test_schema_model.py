"""Tests of the in-memory schema used by side bar and completion."""

from querylean.completion.schema_model import SchemaModel
from querylean.database.schema.column_info import ColumnInfo
from querylean.database.schema.table_info import TableInfo


class TestSchemaModel:
    """Case-insensitive lookups, unknown versus empty columns, clear."""

    def test_lookups_ignore_case(self):
        schema = SchemaModel()
        schema.set_tables([TableInfo("Users"), TableInfo("v", is_view=True)])
        assert schema.table("users") == TableInfo("Users")
        assert schema.table("nowhere") is None
        schema.set_columns("USERS", (ColumnInfo("id"),))
        assert schema.columns_of("users") == (ColumnInfo("id"),)

    def test_unknown_and_unavailable_columns(self):
        schema = SchemaModel()
        assert schema.columns_of("t") is None
        assert not schema.has_columns("t")
        schema.set_columns("t", ())
        assert schema.columns_of("t") == ()
        assert schema.has_columns("t")

    def test_bulk_columns_and_clear(self):
        schema = SchemaModel()
        schema.database = "app"
        schema.set_tables([TableInfo("a")])
        schema.set_all_columns({"a": (ColumnInfo("x"),), "b": ()})
        assert schema.has_columns("b")
        schema.clear()
        assert schema.database == ""
        assert schema.tables == []
        assert schema.columns_of("a") is None

    def test_several_databases(self):
        schema = SchemaModel()
        schema.database = "app"
        schema.set_databases(["app", "Shop"])
        schema.set_tables([TableInfo("users")])
        schema.set_tables([TableInfo("orders", database="Shop")], "Shop")
        assert schema.find_database("shop") == "Shop"
        assert schema.find_database("nowhere") is None
        assert schema.tables == [TableInfo("users")]
        assert schema.table("orders") is None
        assert schema.table("ORDERS", "shop") is not None
        assert schema.tables_of("crm") is None
        assert not schema.has_tables("crm")
        schema.set_columns("orders", (ColumnInfo("id"),), "Shop")
        assert schema.columns_of("orders") is None
        assert schema.columns_of("orders", "shop") == (ColumnInfo("id"),)
        # Replacing the tables of one database keeps the others.
        schema.set_tables([], "Shop")
        assert schema.table("users") is not None
        assert schema.table("orders", "Shop") is None
