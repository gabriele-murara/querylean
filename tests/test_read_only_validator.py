"""Tests of the read-only validator: behaviour of the parser, not keyword
search."""

import pytest

from querylean.database.validation.read_only_rules import ReadOnlyRules
from querylean.database.validation.read_only_validator import ReadOnlyValidator
from querylean.database.validation.validation_stage import ValidationStage


class TestReadOnlyValidator:
    """Accepted and rejected statements, bypass attempts, pipeline structure."""

    __JOIN = "select * from users u join orders o on o.user_id = u.id "
    __JOIN += "where o.total > 10"
    __SUBQUERY = "SELECT u.name, (SELECT COUNT(*) FROM orders o "
    __SUBQUERY += "WHERE o.user_id = u.id) AS n FROM users u"
    __CTE = "WITH recent AS (SELECT * FROM orders WHERE created > NOW() - "
    __CTE += "INTERVAL 1 DAY) SELECT * FROM recent"
    __RECURSIVE_CTE = "WITH RECURSIVE n AS (SELECT 1 AS x UNION ALL "
    __RECURSIVE_CTE += "SELECT x + 1 FROM n WHERE x < 5) SELECT * FROM n"

    ALLOWED = [
        "SELECT * FROM users",
        "SELECT id, name FROM users WHERE active = 1",
        "SELECT COUNT(*) FROM orders",
        __JOIN,
        __SUBQUERY,
        "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)",
        __CTE,
        __RECURSIVE_CTE,
        "SELECT a FROM t1 UNION SELECT a FROM t2",
        "(SELECT 1)",
        "-- commento iniziale\nSELECT 1",
        "SELECT 1 # commento finale",
        "/* blocco */ SELECT /* in mezzo */ 1",
        "SELECT 'UPDATE users SET admin = 1' AS testo",
        "SELECT * FROM logs WHERE message LIKE '%DELETE FROM%'",
        'SELECT "drop table x; --" AS s',
        "SELECT 'it''s', 'a\\'b; DROP TABLE x'",
        "SELECT `select`, `order` FROM `table`",
        "SELECT updated_at, deleted, insert_id, created_by FROM t",
        "SELECT `last_update`, t.`delete_flag` FROM t",
        "SELECT * FROM users;",
        "SELECT * FROM users;  -- fine\n",
        "SELECT REPLACE(name, 'a', 'b'), TRUNCATE(price, 2) FROM products",
        "SELECT replace (name, 'a', 'b') FROM products",
        "SHOW CHARACTER SET",
        "SHOW GRANTS",
        "EXPLAIN ANALYZE SELECT * FROM users",
        "SELECT SUBSTRING(name FROM 1 FOR 3) FROM users",
        "SELECT 1 - -1",
        "SELECT @@version, DATABASE(), NOW()",
        "SELECT * FROM t ORDER BY a DESC LIMIT 10 OFFSET 5",
        "SELECT a, COUNT(*) FROM t GROUP BY a HAVING COUNT(*) > 1",
        "SELECT ROW_NUMBER() OVER (PARTITION BY a ORDER BY b) FROM t",
        "SHOW TABLES",
        "SHOW DATABASES",
        "SHOW COLUMNS FROM users",
        "SHOW CREATE TABLE users",
        "SHOW INDEX FROM users",
        "DESCRIBE users",
        "DESC users",
        "EXPLAIN SELECT * FROM users",
    ]

    REJECTED = [
        "INSERT INTO users (name) VALUES ('x')",
        "UPDATE users SET name = 'x'",
        "DELETE FROM users",
        "REPLACE INTO users (id) VALUES (1)",
        "CREATE TABLE t (id INT)",
        "ALTER TABLE users ADD COLUMN x INT",
        "DROP TABLE users",
        "TRUNCATE TABLE users",
        "RENAME TABLE a TO b",
        "GRANT SELECT ON *.* TO 'u'@'%'",
        "REVOKE SELECT ON *.* FROM 'u'@'%'",
        "CALL my_procedure()",
        "LOAD DATA INFILE '/tmp/x' INTO TABLE t",
        "SET @a = 1",
        "SET GLOBAL read_only = 0",
        "USE mysql",
        "LOCK TABLES users READ",
        "UNLOCK TABLES",
        "HANDLER users OPEN",
        "DO SLEEP(1)",
        "BEGIN",
        "COMMIT",
        "KILL 1",
        "FLUSH PRIVILEGES",
        # write words anywhere outside strings and comments, also as
        # identifiers or aliases (edge cases to be handled later)
        "SELECT `update` FROM t",
        "SELECT t.update FROM t",
        "SELECT t.`delete` FROM t",
        "SELECT a AS `insert` FROM t",
        "SELECT a AS drop_me, b `drop` FROM t",
        "SELECT * FROM `delete`",
        "SELECT * FROM app.`update`",
        "SELECT `REPLACE`(name, 'a', 'b') FROM t",
        "SELECT t.replace(name, 'a', 'b') FROM t",
        "SELECT replace FROM t",
        "SELECT truncate FROM t",
        "SELECT INSERT('abc', 1, 1, 'x')",
        "SELECT * FROM t WHERE commit = 1",
        "SELECT `execute` FROM t",
        "SELECT * FROM t WHERE flush = 1",
        "SHOW CREATE TABLE `update`",
        "DESCRIBE `delete`",
        "WITH `insert` AS (SELECT 1) SELECT * FROM `insert`",
        # multiple statements
        "SELECT 1; SELECT 2",
        "SELECT 1; DROP TABLE users",
        "SELECT 1;;",
        "SELECT 1; -- ok\nDELETE FROM users",
        # bypass attempts with comments, whitespace and letter case
        "/* SELECT */ DELETE FROM users",
        "-- SELECT\nDELETE FROM users",
        "# SELECT\nUPDATE users SET a = 1",
        "  \n\t dElEtE   FROM users",
        "SELECT 1 /*!50000 , (SELECT 1) INTO OUTFILE '/tmp/x' */",
        "/*!40101 DROP TABLE users */",
        "SELECT /*+ SET_VAR(sql_mode='') */ 1",
        "SELECT 1--1\n, sleep(1)",
        # reads with side effects
        "SELECT * FROM users INTO OUTFILE '/tmp/u.txt'",
        "SELECT * FROM users INTO DUMPFILE '/tmp/u.bin'",
        "SELECT id INTO @x FROM users LIMIT 1",
        "SELECT * FROM users FOR UPDATE",
        "SELECT * FROM users FOR SHARE",
        "SELECT * FROM users LOCK IN SHARE MODE",
        "SELECT @a := 1",
        "SELECT GET_LOCK('x', 10)",
        "SELECT RELEASE_LOCK('x')",
        "SELECT LOAD_FILE('/etc/passwd')",
        "EXPLAIN DELETE FROM users",
        "EXPLAIN UPDATE users SET a = 1",
        "WITH x AS (SELECT 1) DELETE FROM users",
        # unrecognised or ambiguous syntax
        "SELECT 'stringa non chiusa",
        "SELECT `identificatore non chiuso",
        "SELECT 1 /* commento non chiuso",
        "PREPARE s FROM 'DELETE FROM users'",
        "EXECUTE s",
        "VALUES ROW(1)",
        "TABLE users",
        "foo bar",
        "",
        "   ",
        "-- solo commento",
        ";",
    ]

    @pytest.fixture
    def validator(self) -> ReadOnlyValidator:
        return ReadOnlyValidator()

    @pytest.mark.parametrize("sql", ALLOWED)
    def test_allowed(self, validator, sql):
        result = validator.validate(sql)
        assert result.ok, "{!r} rejected: {}".format(sql, result.reason)

    @pytest.mark.parametrize("sql", REJECTED)
    def test_rejected(self, validator, sql):
        result = validator.validate(sql)
        assert not result.ok, "{!r} accepted".format(sql)
        assert result.reason

    def test_trailing_semicolon_is_stripped_and_original_text_kept(
        self, validator
    ):
        result = validator.validate("  SELECT  *   FROM users ; ")
        assert result.ok
        assert result.statement == "SELECT  *   FROM users"

    def test_comments_are_preserved_in_statement_sent_to_server(
        self, validator
    ):
        assert (
            validator.validate("SELECT 1 -- nota").statement
            == "SELECT 1 -- nota"
        )

    @pytest.mark.parametrize(
        "word",
        sorted(
            ReadOnlyRules.FORBIDDEN_WORDS
            - ReadOnlyRules.FUNCTION_NAME_EXCEPTIONS
        ),
    )
    def test_every_forbidden_word_is_rejected_as_identifier(
        self, validator, word
    ):
        for sql in (
            "SELECT {} FROM t".format(word.lower()),
            "SELECT t.{} FROM t".format(word),
            "SELECT `{}` FROM t".format(word.lower()),
            "SELECT a AS `{}` FROM t".format(word),
        ):
            result = validator.validate(sql)
            assert not result.ok, "{!r} accepted".format(sql)

    def test_keyword_inside_string_does_not_trigger_rejection(self, validator):
        assert validator.validate(
            "SELECT 'DROP TABLE users; DELETE FROM x' AS s"
        ).ok
        assert not validator.validate(
            "SELECT 1 FROM t WHERE 1 = 1 AND 0 ; DROP TABLE users"
        ).ok

    def test_semicolon_inside_string_is_not_a_statement_separator(
        self, validator
    ):
        assert validator.validate("SELECT ';' AS sep").ok
        assert validator.validate("SELECT `a;b` FROM t").ok

    def test_reject_message_is_user_friendly(self, validator):
        assert (
            "read operations" in validator.validate("DELETE FROM users").reason
        )

    def test_pipeline_has_three_independent_stages(self, validator):
        names = [stage.name for stage in validator.stages]
        assert names == ["LexicalStage", "KeywordStage", "SyntaxTreeStage"]
        assert all(
            isinstance(stage, ValidationStage) for stage in validator.stages
        )

    def test_validation_stage_is_abstract(self):
        with pytest.raises(TypeError):
            ValidationStage()

    def test_unexpected_error_in_a_stage_rejects(self):
        class BrokenStage(ValidationStage):
            def apply(self, context):
                raise RuntimeError("boom")

        result = ReadOnlyValidator([BrokenStage()]).validate("SELECT 1")
        assert not result.ok
