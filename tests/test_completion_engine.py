"""Tests of the autocompletion proposals (``|`` marks the cursor)."""

import pytest

from querylean.completion.completion_engine import CompletionEngine
from querylean.completion.completion_kind import CompletionKind
from querylean.completion.schema_model import SchemaModel
from querylean.database.schema.column_info import ColumnInfo
from querylean.database.schema.table_info import TableInfo


class TestCompletionEngine:
    """Proposals per context, ranking, insertion text, missing columns."""

    @pytest.fixture
    def schema(self) -> SchemaModel:
        schema = SchemaModel()
        schema.database = "app"
        schema.set_tables(
            [
                TableInfo("users"),
                TableInfo("orders"),
                TableInfo("order items"),
                TableInfo("active_users", is_view=True),
                TableInfo("invoices"),
            ]
        )
        schema.set_all_columns(
            {
                "users": (
                    ColumnInfo("id", "int", key="PRI"),
                    ColumnInfo("name", "varchar(64)"),
                    ColumnInfo("email", "varchar(255)"),
                    ColumnInfo("created_at", "datetime"),
                    ColumnInfo("order", "int"),
                ),
                "orders": (
                    ColumnInfo("id", "int", key="PRI"),
                    ColumnInfo("user_id", "int", key="MUL"),
                    ColumnInfo("total", "decimal(10,2)"),
                ),
            }
        )
        return schema

    @pytest.fixture
    def engine(self, schema) -> CompletionEngine:
        return CompletionEngine(schema)

    @staticmethod
    def complete(engine, marked):
        position = marked.index("|")
        return engine.complete(marked.replace("|", ""), position)

    def labels(self, engine, marked, count=None):
        items = self.complete(engine, marked).items
        return [item.label for item in items][:count]

    def inserts(self, engine, marked, count=None):
        items = self.complete(engine, marked).items
        return [item.insert_text for item in items][:count]

    def test_statement_start(self, engine):
        # Phrases also match on a later word ("EXPLAIN SELECT").
        assert self.labels(engine, "se|") == ["SELECT", "EXPLAIN SELECT"]
        # Keywords follow the case of the typed text.
        assert self.inserts(engine, "se|", 1) == ["select "]
        assert self.inserts(engine, "SE|", 1) == ["SELECT "]
        assert "SHOW" in self.labels(engine, "|")

    def test_tables_after_from(self, engine):
        assert self.labels(engine, "SELECT * FROM |") == [
            "users",
            "orders",
            "order items",
            "active_users",
            "invoices",
        ]
        assert self.labels(engine, "SELECT * FROM or|") == [
            "order items",
            "orders",
        ]
        assert self.inserts(engine, "SELECT * FROM or|", 1) == ["`order items`"]
        items = self.complete(engine, "SELECT * FROM act|").items
        assert items[0].kind == CompletionKind.VIEW

    def test_tables_match_inside_the_name(self, engine):
        # "users" is a word of active_users, "voi" is only inside invoices.
        assert self.labels(engine, "SELECT * FROM users|")[:2] == [
            "users",
            "active_users",
        ]
        assert self.labels(engine, "SELECT * FROM voi|") == ["invoices"]

    def test_columns_of_the_tables_in_the_query(self, engine):
        labels = self.labels(engine, "SELECT | FROM users u")
        assert labels[:5] == ["id", "name", "email", "created_at", "order"]
        assert "u" in labels  # the alias, to qualify columns
        assert "total" not in labels

    def test_columns_in_where_and_on(self, engine):
        assert self.labels(engine, "SELECT * FROM users WHERE na|") == ["name"]
        labels = self.labels(
            engine, "SELECT * FROM users u JOIN orders o ON o.user_id = |"
        )
        assert "total" in labels and "email" in labels

    def test_ambiguous_columns_are_qualified(self, engine):
        items = self.complete(
            engine, "SELECT i| FROM users u JOIN orders o ON o.user_id = u.id"
        ).items
        assert [i.insert_text for i in items[:2]] == ["u.id", "o.id"]
        assert items[0].detail == "int · users"
        assert items[0].kind == CompletionKind.KEY_COLUMN

    def test_qualified_columns(self, engine):
        assert self.labels(engine, "SELECT o.| FROM orders o") == [
            "id",
            "user_id",
            "total",
        ]
        assert self.labels(engine, "SELECT o.to| FROM orders o") == ["total"]
        assert self.labels(engine, "SELECT orders.| FROM orders") == [
            "id",
            "user_id",
            "total",
        ]
        # A table of the database, even if not in the query yet.
        assert self.labels(engine, "SELECT users.em|") == ["email"]
        assert self.labels(engine, "SELECT app.users.em| FROM app.users") == [
            "email"
        ]
        # Another database: unknown.
        assert self.labels(engine, "SELECT other.users.| FROM x") == []

    def test_reserved_column_names_are_quoted(self, engine):
        assert self.inserts(engine, "SELECT u.ord| FROM users u") == ["`order`"]

    def test_database_qualifier_lists_tables(self, engine):
        labels = self.labels(engine, "SELECT * FROM app.|")
        assert labels[0] == "users" and "orders" in labels
        assert self.labels(engine, "SELECT * FROM other.|") == []

    def test_derived_tables_and_ctes_have_no_columns(self, engine):
        assert self.labels(engine, "SELECT d.| FROM (SELECT 1) d") == []
        labels = self.labels(
            engine, "WITH recent AS (SELECT 1) SELECT * FROM r|"
        )
        assert labels == ["recent"]
        items = self.complete(
            engine, "WITH recent AS (SELECT 1) SELECT * FROM r|"
        ).items
        assert items[0].kind == CompletionKind.CTE

    def test_keywords_after_a_table(self, engine):
        assert self.labels(engine, "SELECT * FROM users u w|") == [
            "WHERE",
            "WINDOW",
        ]
        assert self.labels(engine, "SELECT * FROM users u le|") == [
            "LEFT JOIN",
            "LEFT OUTER JOIN",
        ]

    def test_keywords_after_an_operand(self, engine):
        labels = self.labels(engine, "SELECT * FROM users WHERE id = 1 |")
        assert labels[:3] == ["AS", "AND", "OR"]
        assert self.labels(engine, "SELECT * FROM users WHERE id = 1 an|") == [
            "AND"
        ]
        assert self.labels(engine, "SELECT * FROM users ORDER BY name d|") == [
            "DESC",
            "DIV",
        ]

    def test_functions(self, engine):
        items = self.complete(engine, "SELECT COU| FROM users").items
        assert items[0].label == "COUNT"
        assert items[0].insert_text == "COUNT()"
        assert items[0].caret_back == 1
        now = self.complete(engine, "SELECT now| FROM users").items[0]
        assert (now.insert_text, now.caret_back) == ("now()", 0)

    def test_forbidden_words_are_never_proposed(self, engine):
        for marked in (
            "ins|",
            "upd|",
            "del|",
            "SELECT ins| FROM users",
            "SELECT get_l| FROM users",
            "SELECT * FROM users u dr|",
        ):
            labels = [label.upper() for label in self.labels(engine, marked)]
            assert not any(
                word in labels
                for word in ("INSERT", "UPDATE", "DELETE", "GET_LOCK", "DROP")
            ), marked

    def test_columns_first_then_functions_and_keywords(self, engine):
        labels = self.labels(engine, "SELECT c| FROM users")
        assert labels[0] == "created_at"
        assert "COUNT" in labels and "CASE" in labels

    def test_columns_of_every_table_without_from(self, engine):
        items = self.complete(engine, "SELECT ema|").items
        assert items[0].label == "email"
        items = self.complete(engine, "SELECT id|").items
        assert items[0].label == "id" and items[0].detail == "int · 2 tables"

    def test_no_proposals_in_strings_comments_and_numbers(self, engine):
        for marked in (
            "SELECT 'us|",
            "SELECT 1 -- us|",
            "SELECT * FROM users LIMIT 1|",
            "SELECT id AS u|",
        ):
            assert self.labels(engine, marked) == [], marked

    def test_missing_columns_are_reported(self, engine, schema):
        result = self.complete(engine, "SELECT i.| FROM invoices i")
        assert result.items == ()
        assert result.missing_tables == ("invoices",)
        # Unknown tables are not requested.
        result = self.complete(engine, "SELECT x.| FROM nowhere x")
        assert result.missing_tables == ()
        schema.set_columns("invoices", (ColumnInfo("number", "int"),))
        assert self.labels(engine, "SELECT i.| FROM invoices i") == ["number"]

    def test_quoted_word_stays_quoted(self, engine):
        assert self.inserts(engine, "SELECT * FROM `ord|") == [
            "`order items`",
            "`orders`",
        ]

    def test_exact_match_comes_first(self, engine):
        assert self.labels(engine, "SELECT * FROM users WHERE id|")[0] == "id"

    def test_show(self, engine):
        assert "FULL COLUMNS FROM" in self.labels(engine, "SHOW fu|")
        assert self.labels(engine, "SHOW COLUMNS FROM us|")[0] == "users"
        assert self.labels(engine, "DESCRIBE ord|") == ["order items", "orders"]

    def test_limit_on_the_number_of_proposals(self, schema):
        schema.set_tables([TableInfo("t{}".format(i)) for i in range(500)])
        engine = CompletionEngine(schema)
        result = self.complete(engine, "SELECT * FROM |")
        assert len(result.items) == CompletionEngine.MAX_ITEMS
