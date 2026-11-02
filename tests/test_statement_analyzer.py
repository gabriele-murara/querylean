"""Tests of the analysis of the cursor context (``|`` marks the cursor)."""

import pytest

from querylean.completion.statement_analyzer import StatementAnalyzer
from querylean.completion.statement_context import StatementContext
from querylean.completion.table_reference import TableReference


class TestStatementAnalyzer:
    """Expected element, word under the cursor, tables and aliases."""

    @staticmethod
    def analyze(marked: str) -> StatementContext:
        position = marked.index("|")
        return StatementAnalyzer.analyze(marked.replace("|", ""), position)

    @pytest.mark.parametrize(
        ("marked", "kind"),
        [
            ("|", StatementContext.STATEMENT_START),
            ("SEL|", StatementContext.STATEMENT_START),
            ("SELECT 1; sh|", StatementContext.STATEMENT_START),
            ("SELECT |", StatementContext.EXPRESSION),
            ("SELECT id, |", StatementContext.EXPRESSION),
            ("SELECT | FROM users", StatementContext.EXPRESSION),
            ("SELECT id |", StatementContext.AFTER_OPERAND),
            ("SELECT * |", StatementContext.AFTER_OPERAND),
            ("SELECT * FROM |", StatementContext.TABLE_NAME),
            ("SELECT * FROM a, |", StatementContext.TABLE_NAME),
            ("SELECT * FROM a x JOIN |", StatementContext.TABLE_NAME),
            ("SELECT * FROM a |", StatementContext.AFTER_TABLE),
            ("SELECT * FROM a x |", StatementContext.AFTER_TABLE),
            ("SELECT * FROM a WHERE |", StatementContext.EXPRESSION),
            ("SELECT * FROM a WHERE x = |", StatementContext.EXPRESSION),
            ("SELECT * FROM a WHERE x = 1 |", StatementContext.AFTER_OPERAND),
            ("SELECT * FROM a WHERE x = 1 AND |", StatementContext.EXPRESSION),
            ("SELECT * FROM a ORDER BY |", StatementContext.EXPRESSION),
            ("SELECT * FROM a ORDER BY x DESC, |", StatementContext.EXPRESSION),
            (
                "SELECT * FROM a GROUP BY x HAVING |",
                StatementContext.EXPRESSION,
            ),
            ("SELECT * FROM a JOIN b ON |", StatementContext.EXPRESSION),
            ("SELECT COUNT(| FROM a", StatementContext.EXPRESSION),
            ("SELECT COALESCE(a, | FROM a", StatementContext.EXPRESSION),
            ("SELECT * FROM a WHERE x IN (|", StatementContext.SUBQUERY),
            ("SELECT * FROM (|", StatementContext.SUBQUERY),
            ("SELECT * FROM a WHERE (x = 1 OR |", StatementContext.EXPRESSION),
            ("SELECT x AS |", StatementContext.NONE),
            ("SELECT * FROM a LIMIT |", StatementContext.NONE),
            ("SELECT * FROM a LIMIT 1|", StatementContext.NONE),
            ("SELECT 'abc|", StatementContext.NONE),
            ("SELECT 'a|bc'", StatementContext.NONE),
            ("SELECT 1 -- note|", StatementContext.NONE),
            ("SELECT /* x| */ 1", StatementContext.NONE),
            ("SELECT @var|", StatementContext.NONE),
            ("SELECT 1 UNION |", StatementContext.STATEMENT_START),
            ("SELECT 1 UNION ALL |", StatementContext.STATEMENT_START),
            ("WITH c AS (SELECT 1) |", StatementContext.STATEMENT_START),
            ("DESCRIBE |", StatementContext.TABLE_NAME),
            ("DESC us|", StatementContext.TABLE_NAME),
            ("EXPLAIN |", StatementContext.STATEMENT_START),
            ("SHOW |", StatementContext.SHOW),
            ("SHOW FULL |", StatementContext.SHOW),
            ("SHOW COLUMNS FROM |", StatementContext.TABLE_NAME),
            ("SHOW INDEX IN |", StatementContext.TABLE_NAME),
            ("SHOW CREATE TABLE |", StatementContext.TABLE_NAME),
            ("SELECT u.| FROM users u", StatementContext.QUALIFIED),
        ],
    )
    def test_kind(self, marked, kind):
        assert self.analyze(marked).kind == kind

    def test_word_around_the_cursor_is_replaced(self):
        context = self.analyze("SELECT na|me FROM t")
        assert context.prefix == "na"
        assert (context.start, context.end) == (7, 11)

    def test_quoted_word(self):
        context = self.analyze("SELECT * FROM `order it|")
        assert context.kind == StatementContext.TABLE_NAME
        assert context.quoted and context.prefix == "order it"
        assert context.start == 14
        context = self.analyze("SELECT * FROM `ord|ers` x")
        assert context.prefix == "ord" and context.end == 22

    def test_qualifiers(self):
        context = self.analyze("SELECT o.us| FROM orders o")
        assert context.qualifier == ("o",) and context.prefix == "us"
        context = self.analyze("SELECT app.users.| FROM app.users")
        assert context.qualifier == ("app", "users")
        context = self.analyze("SELECT `my t`.| FROM `my t`")
        assert context.qualifier == ("my t",)
        context = self.analyze("SELECT * FROM app.|")
        assert context.kind == StatementContext.QUALIFIED
        assert context.expects_table

    def test_references_and_aliases(self):
        sql = "SELECT | FROM users u JOIN orders AS o ON o.uid = u.id "
        sql += "LEFT JOIN app.items, `my t` WHERE 1"
        context = self.analyze(sql)
        assert context.references == (
            TableReference("users", "u"),
            TableReference("orders", "o"),
            TableReference("items", None, "app"),
        )
        context = self.analyze("SELECT | FROM a, b x, `my t` AS m")
        assert context.references == (
            TableReference("a"),
            TableReference("b", "x"),
            TableReference("my t", "m"),
        )

    def test_keywords_are_not_aliases(self):
        context = self.analyze("SELECT | FROM a WHERE x = 1 ORDER BY y")
        assert context.references == (TableReference("a"),)
        context = self.analyze("SELECT | FROM a LEFT JOIN b USING (id)")
        assert context.references == (TableReference("a"), TableReference("b"))

    def test_derived_tables_and_subqueries(self):
        context = self.analyze(
            "SELECT d.| FROM (SELECT id FROM users) AS d JOIN orders o"
        )
        assert TableReference(None, "d") in context.references
        assert TableReference("users") in context.references
        assert TableReference("orders", "o") in context.references

    def test_common_table_expressions(self):
        context = self.analyze(
            "WITH a AS (SELECT 1), b (x) AS (SELECT 2) SELECT * FROM |"
        )
        assert context.ctes == ("a", "b")
        context = self.analyze("WITH RECURSIVE r AS (SELECT 1) SELECT |")
        assert context.ctes == ("r",)

    def test_only_the_current_statement(self):
        context = self.analyze(
            "SELECT * FROM a; SELECT | FROM b x; SELECT * FROM c"
        )
        assert context.references == (TableReference("b", "x"),)

    def test_word_being_typed_is_not_a_reference(self):
        context = self.analyze("SELECT * FROM us|")
        assert context.references == ()

    def test_digits_are_not_completed(self):
        assert self.analyze("SELECT 1|").kind == StatementContext.NONE
