"""Tests of the count and page statements of a truncated result."""

import pytest

from querylean.database.execution.paged_query import PagedQuery
from querylean.database.validation.read_only_validator import (
    ReadOnlyValidator,
)


class TestPagedQuery:
    """Pageable statements, built SQL and its validation."""

    @pytest.fixture
    def validator(self) -> ReadOnlyValidator:
        return ReadOnlyValidator()

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM t",
            "select a FROM t ORDER BY a",
            "(SELECT 1) UNION (SELECT 2)",
            "WITH x AS (SELECT 1 AS a) SELECT a FROM x",
            "/* note */ SELECT 1",
        ],
    )
    def test_queries_are_pageable(self, sql):
        assert PagedQuery.is_pageable(sql)

    @pytest.mark.parametrize(
        "sql",
        [
            "SHOW TABLES",
            "DESCRIBE t",
            "EXPLAIN SELECT 1",
            "",
            "SELECT 'unterminated",
        ],
    )
    def test_other_statements_are_not_pageable(self, sql):
        assert not PagedQuery.is_pageable(sql)

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM t",
            "SELECT * FROM t -- final comment",
            "SELECT * FROM t # final comment",
            "WITH x AS (SELECT 1 AS a) SELECT a FROM x",
            "SELECT 1 UNION SELECT 2",
            "SELECT * FROM t LIMIT 5",
        ],
    )
    def test_built_statements_pass_the_validator(self, validator, sql):
        statement = validator.validate(sql).statement
        count = PagedQuery.count_statement(statement)
        page = PagedQuery.page_statement(statement, 1000, 2)
        assert validator.validate(count).ok, count
        assert validator.validate(page).ok, page
        assert count.endswith("\n) AS querylean_count")
        assert page.endswith("\n) AS querylean_page LIMIT 1000 OFFSET 2000")

    def test_page_bounds(self):
        assert PagedQuery.page_statement("SELECT 1", 0, -3).endswith(
            "LIMIT 1 OFFSET 0"
        )
        assert PagedQuery.page_count(1_000_000, 1000) == 1000
        assert PagedQuery.page_count(1001, 1000) == 2
        assert PagedQuery.page_count(0, 1000) == 1
