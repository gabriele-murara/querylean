import pytest

from querylean.database.readonly_validator import validate

ALLOWED = [
    "SELECT * FROM users",
    "SELECT id, name FROM users WHERE active = 1",
    "SELECT COUNT(*) FROM orders",
    "select * from users u join orders o on o.user_id = u.id where o.total > 10",
    "SELECT u.name, (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) AS n FROM users u",
    "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)",
    "WITH recent AS (SELECT * FROM orders WHERE created > NOW() - INTERVAL 1 DAY) "
    "SELECT * FROM recent",
    "WITH RECURSIVE n AS (SELECT 1 AS x UNION ALL SELECT x + 1 FROM n WHERE x < 5) "
    "SELECT * FROM n",
    "SELECT a FROM t1 UNION SELECT a FROM t2",
    "(SELECT 1)",
    "-- commento iniziale\nSELECT 1",
    "SELECT 1 # commento finale",
    "/* blocco */ SELECT /* in mezzo */ 1",
    "SELECT 'UPDATE users SET admin = 1' AS testo",
    "SELECT * FROM logs WHERE message LIKE '%DELETE FROM%'",
    "SELECT \"drop table x; --\" AS s",
    "SELECT 'it''s', 'a\\'b; DROP TABLE x'",
    "SELECT `select`, `update` FROM `table`",
    "SELECT * FROM users;",
    "SELECT * FROM users;  -- fine\n",
    "SELECT REPLACE(name, 'a', 'b'), TRUNCATE(price, 2) FROM products",
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
    # istruzioni multiple
    "SELECT 1; SELECT 2",
    "SELECT 1; DROP TABLE users",
    "SELECT 1;;",
    "SELECT 1; -- ok\nDELETE FROM users",
    # aggiramenti con commenti, spazi e maiuscole
    "/* SELECT */ DELETE FROM users",
    "-- SELECT\nDELETE FROM users",
    "# SELECT\nUPDATE users SET a = 1",
    "  \n\t dElEtE   FROM users",
    "SELECT 1 /*!50000 , (SELECT 1) INTO OUTFILE '/tmp/x' */",
    "/*!40101 DROP TABLE users */",
    "SELECT /*+ SET_VAR(sql_mode='') */ 1",
    "SELECT 1--1\n, sleep(1)",
    # letture con effetti collaterali
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
    # sintassi non riconosciuta o ambigua
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


@pytest.mark.parametrize("sql", ALLOWED)
def test_allowed(sql):
    result = validate(sql)
    assert result.ok, f"{sql!r} rifiutata: {result.reason}"


@pytest.mark.parametrize("sql", REJECTED)
def test_rejected(sql):
    result = validate(sql)
    assert not result.ok, f"{sql!r} accettata"
    assert result.reason


def test_trailing_semicolon_is_stripped_and_original_text_kept():
    result = validate("  SELECT  *   FROM users ; ")
    assert result.ok
    assert result.statement == "SELECT  *   FROM users"


def test_comments_are_preserved_in_statement_sent_to_server():
    result = validate("SELECT 1 -- nota")
    assert result.statement == "SELECT 1 -- nota"


def test_keyword_inside_string_does_not_trigger_rejection():
    # Verifica la struttura, non la semplice presenza della parola nel testo.
    assert validate("SELECT 'DROP TABLE users; DELETE FROM x' AS s").ok
    assert not validate("SELECT 1 FROM t WHERE 1 = 1 AND 0 ; DROP TABLE users").ok


def test_semicolon_inside_string_is_not_a_statement_separator():
    assert validate("SELECT ';' AS sep").ok
    assert validate("SELECT `a;b` FROM t").ok


def test_reject_message_is_user_friendly():
    result = validate("DELETE FROM users")
    assert "sola lettura" in result.reason or "lettura" in result.reason
