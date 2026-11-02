"""Keywords and functions offered by the autocompletion."""

from __future__ import annotations

import re

from querylean.database.schema.mysql_identifier import MySqlIdentifier
from querylean.database.validation.read_only_rules import ReadOnlyRules


class SqlVocabulary:
    """Keyword phrases per context, MySQL functions and identifier quoting.

    Write and administration words (``ReadOnlyRules.FORBIDDEN_WORDS``) and
    forbidden functions are never offered: the validator would reject
    them anyway.
    """

    # MySQL reserved words: an unquoted identifier cannot be one of them,
    # and an alias never is.
    __RESERVED = "ACCESSIBLE ADD ALL ALTER ANALYZE AND AS ASC ASENSITIVE "
    __RESERVED += "BEFORE BETWEEN BIGINT BINARY BLOB BOTH BY CALL CASCADE "
    __RESERVED += "CASE CHANGE CHAR CHARACTER CHECK COLLATE COLUMN "
    __RESERVED += "CONDITION CONSTRAINT CONTINUE CONVERT CREATE CROSS CUBE "
    __RESERVED += "CUME_DIST CURRENT_DATE CURRENT_TIME CURRENT_TIMESTAMP "
    __RESERVED += "CURRENT_USER CURSOR DATABASE DATABASES DAY_HOUR "
    __RESERVED += "DAY_MICROSECOND DAY_MINUTE DAY_SECOND DEC DECIMAL "
    __RESERVED += "DECLARE DEFAULT DELAYED DELETE DENSE_RANK DESC DESCRIBE "
    __RESERVED += "DETERMINISTIC DISTINCT DISTINCTROW DIV DOUBLE DROP DUAL "
    __RESERVED += "EACH ELSE ELSEIF EMPTY ENCLOSED ESCAPED EXCEPT EXISTS "
    __RESERVED += "EXIT EXPLAIN FALSE FETCH FIRST_VALUE FLOAT FOR FORCE "
    __RESERVED += "FOREIGN FROM FULLTEXT FUNCTION GENERATED GET GRANT GROUP "
    __RESERVED += "GROUPING GROUPS HAVING HIGH_PRIORITY HOUR_MICROSECOND "
    __RESERVED += "HOUR_MINUTE HOUR_SECOND IF IGNORE IN INDEX INFILE INNER "
    __RESERVED += "INOUT INSENSITIVE INSERT INT INTEGER INTERSECT INTERVAL "
    __RESERVED += "INTO IS ITERATE JOIN JSON_TABLE KEY KEYS KILL LAG "
    __RESERVED += "LAST_VALUE LATERAL LEAD LEADING LEAVE LEFT LIKE LIMIT "
    __RESERVED += "LINEAR LINES LOAD LOCALTIME LOCALTIMESTAMP LOCK LONG "
    __RESERVED += "LOOP LOW_PRIORITY MATCH MAXVALUE MEDIUMINT MINUTE_SECOND "
    __RESERVED += "MOD MODIFIES NATURAL NOT NO_WRITE_TO_BINLOG NTH_VALUE "
    __RESERVED += "NTILE NULL NUMERIC OF ON OPTIMIZE OPTION OPTIONALLY OR "
    __RESERVED += "ORDER OUT OUTER OUTFILE OVER PARTITION PERCENT_RANK "
    __RESERVED += "PRECISION PRIMARY PROCEDURE PURGE RANGE RANK READ READS "
    __RESERVED += "REAL RECURSIVE REFERENCES REGEXP RELEASE RENAME REPEAT "
    __RESERVED += "REPLACE REQUIRE RESIGNAL RESTRICT RETURN REVOKE RIGHT "
    __RESERVED += "RLIKE ROW ROWS ROW_NUMBER SCHEMA SCHEMAS SELECT SENSITIVE "
    __RESERVED += "SEPARATOR SET SHOW SIGNAL SMALLINT SPATIAL SPECIFIC SQL "
    __RESERVED += "STARTING STORED STRAIGHT_JOIN SYSTEM TABLE TERMINATED "
    __RESERVED += "THEN TINYINT TO TRAILING TRIGGER TRUE UNDO UNION UNIQUE "
    __RESERVED += "UNLOCK UNSIGNED UPDATE USAGE USE USING UTC_DATE UTC_TIME "
    __RESERVED += "UTC_TIMESTAMP VALUES VARBINARY VARCHAR VARYING VIRTUAL "
    __RESERVED += "WHEN WHERE WHILE WINDOW WITH WRITE XOR YEAR_MONTH "
    __RESERVED += "ZEROFILL OFFSET"
    RESERVED = frozenset(__RESERVED.split())

    STATEMENT_KEYWORDS = (
        "SELECT",
        "WITH",
        "WITH RECURSIVE",
        "SHOW",
        "DESCRIBE",
        "EXPLAIN",
        "EXPLAIN SELECT",
    )
    SELECT_KEYWORDS = ("SELECT", "SELECT DISTINCT")
    AFTER_TABLE_KEYWORDS = (
        "AS",
        "JOIN",
        "INNER JOIN",
        "LEFT JOIN",
        "LEFT OUTER JOIN",
        "RIGHT JOIN",
        "RIGHT OUTER JOIN",
        "CROSS JOIN",
        "NATURAL JOIN",
        "STRAIGHT_JOIN",
        "ON",
        "USING",
        "WHERE",
        "GROUP BY",
        "ORDER BY",
        "HAVING",
        "LIMIT",
        "UNION",
        "UNION ALL",
        "WINDOW",
    )
    AFTER_OPERAND_KEYWORDS = (
        "AS",
        "AND",
        "OR",
        "XOR",
        "NOT",
        "IN",
        "NOT IN",
        "LIKE",
        "NOT LIKE",
        "BETWEEN",
        "NOT BETWEEN",
        "IS NULL",
        "IS NOT NULL",
        "REGEXP",
        "COLLATE",
        "DIV",
        "MOD",
        "FROM",
        "WHERE",
        "JOIN",
        "INNER JOIN",
        "LEFT JOIN",
        "RIGHT JOIN",
        "ON",
        "GROUP BY",
        "ORDER BY",
        "HAVING",
        "LIMIT",
        "OFFSET",
        "ASC",
        "DESC",
        "UNION",
        "UNION ALL",
        "WHEN",
        "THEN",
        "ELSE",
        "END",
        "OVER",
        "WITH ROLLUP",
    )
    EXPRESSION_KEYWORDS = (
        "DISTINCT",
        "CASE",
        "WHEN",
        "THEN",
        "ELSE",
        "END",
        "NOT",
        "NULL",
        "TRUE",
        "FALSE",
        "EXISTS",
        "NOT EXISTS",
        "INTERVAL",
        "CURRENT_DATE",
        "CURRENT_TIME",
        "CURRENT_TIMESTAMP",
        "ALL",
        "ANY",
    )
    SHOW_KEYWORDS = (
        "TABLES",
        "FULL TABLES",
        "TABLE STATUS",
        "COLUMNS FROM",
        "FULL COLUMNS FROM",
        "INDEX FROM",
        "CREATE TABLE",
        "CREATE VIEW",
        "DATABASES",
        "VARIABLES",
        "STATUS",
        "WARNINGS",
        "ERRORS",
        "PROCESSLIST",
        "ENGINES",
        "CHARACTER SET",
        "COLLATION",
        "GRANTS",
    )
    # Functions that take no argument: the cursor goes after "()".
    NO_ARGUMENT_FUNCTIONS = frozenset(
        {
            "NOW",
            "CURDATE",
            "CURTIME",
            "SYSDATE",
            "UTC_DATE",
            "UTC_TIME",
            "UTC_TIMESTAMP",
            "UUID",
            "UUID_SHORT",
            "RAND",
            "PI",
            "DATABASE",
            "SCHEMA",
            "USER",
            "CURRENT_USER",
            "SESSION_USER",
            "CONNECTION_ID",
            "VERSION",
            "ROW_NUMBER",
            "RANK",
            "DENSE_RANK",
            "FOUND_ROWS",
            "ROW_COUNT",
        }
    )
    __FUNCTIONS = "ABS ACOS ADDDATE ADDTIME AES_DECRYPT ANY_VALUE ASCII ASIN "
    __FUNCTIONS += "ATAN ATAN2 AVG BIN BIT_AND BIT_COUNT BIT_LENGTH BIT_OR "
    __FUNCTIONS += "BIT_XOR CAST CEIL CEILING CHAR_LENGTH CHARACTER_LENGTH "
    __FUNCTIONS += "COALESCE CONCAT CONCAT_WS CONNECTION_ID CONV CONVERT "
    __FUNCTIONS += "CONVERT_TZ COS COT COUNT CRC32 CUME_DIST CURDATE "
    __FUNCTIONS += "CURRENT_USER CURTIME DATABASE DATE DATE_ADD DATE_FORMAT "
    __FUNCTIONS += "DATE_SUB DATEDIFF DAY DAYNAME DAYOFMONTH DAYOFWEEK "
    __FUNCTIONS += "DAYOFYEAR DEGREES DENSE_RANK ELT EXP EXTRACT FIELD "
    __FUNCTIONS += "FIND_IN_SET FIRST_VALUE FLOOR FORMAT FOUND_ROWS "
    __FUNCTIONS += "FROM_BASE64 FROM_DAYS FROM_UNIXTIME GREATEST GROUP_CONCAT "
    __FUNCTIONS += "HEX HOUR IF IFNULL INET_ATON INET_NTOA INSTR ISNULL "
    __FUNCTIONS += "JSON_ARRAY JSON_ARRAYAGG JSON_CONTAINS JSON_EXTRACT "
    __FUNCTIONS += "JSON_KEYS JSON_LENGTH JSON_OBJECT JSON_OBJECTAGG "
    __FUNCTIONS += "JSON_PRETTY JSON_SEARCH JSON_TYPE JSON_UNQUOTE "
    __FUNCTIONS += "JSON_VALID JSON_VALUE LAG LAST_DAY LAST_VALUE LCASE LEAD "
    __FUNCTIONS += "LEAST LEFT LENGTH LN LOCATE LOG LOG10 LOG2 LOWER LPAD "
    __FUNCTIONS += "LTRIM MAKEDATE MAKETIME MAX MD5 MICROSECOND MID MIN "
    __FUNCTIONS += "MINUTE MOD MONTH MONTHNAME NOW NTH_VALUE NTILE NULLIF "
    __FUNCTIONS += "OCT PERCENT_RANK PERIOD_ADD PERIOD_DIFF PI POSITION POW "
    __FUNCTIONS += "POWER QUARTER QUOTE RADIANS RAND RANK REGEXP_INSTR "
    __FUNCTIONS += "REGEXP_LIKE REGEXP_REPLACE REGEXP_SUBSTR REPEAT REPLACE "
    __FUNCTIONS += "REVERSE RIGHT ROUND ROW_COUNT ROW_NUMBER RPAD RTRIM "
    __FUNCTIONS += "SEC_TO_TIME SECOND SESSION_USER SHA1 SHA2 SIGN SIN SLEEP "
    __FUNCTIONS += "SOUNDEX SPACE SQRT STD STDDEV STDDEV_POP STDDEV_SAMP "
    __FUNCTIONS += "STR_TO_DATE STRCMP SUBDATE SUBSTR SUBSTRING "
    __FUNCTIONS += "SUBSTRING_INDEX SUBTIME SUM SYSDATE TAN TIME TIME_FORMAT "
    __FUNCTIONS += "TIME_TO_SEC TIMEDIFF TIMESTAMP TIMESTAMPADD TIMESTAMPDIFF "
    __FUNCTIONS += "TO_BASE64 TO_DAYS TO_SECONDS TRIM TRUNCATE UCASE UNHEX "
    __FUNCTIONS += "UNIX_TIMESTAMP UPPER USER UTC_DATE UTC_TIME "
    __FUNCTIONS += "UTC_TIMESTAMP UUID UUID_SHORT VAR_POP VAR_SAMP VARIANCE "
    __FUNCTIONS += "VERSION WEEK WEEKDAY WEEKOFYEAR YEAR YEARWEEK"
    __SIMPLE_NAME = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")

    @staticmethod
    def functions() -> tuple[str, ...]:
        """Function names that the validator accepts, sorted."""
        forbidden = ReadOnlyRules.FORBIDDEN_FUNCTIONS | (
            ReadOnlyRules.FORBIDDEN_WORDS
            - ReadOnlyRules.FUNCTION_NAME_EXCEPTIONS
        )
        names = {
            name
            for name in SqlVocabulary.__FUNCTIONS.split()
            if name not in forbidden
        }
        return tuple(sorted(names))

    @staticmethod
    def allowed(phrase: str) -> bool:
        """True when no word of ``phrase`` is a forbidden word."""
        return not any(
            word in ReadOnlyRules.FORBIDDEN_WORDS for word in phrase.split()
        )

    @staticmethod
    def is_reserved(word: str) -> bool:
        """True for MySQL reserved words (case insensitive)."""
        return word.upper() in SqlVocabulary.RESERVED

    @staticmethod
    def needs_quoting(name: str) -> bool:
        """True when ``name`` must be written between backticks."""
        return (
            not SqlVocabulary.__SIMPLE_NAME.fullmatch(name)
            or SqlVocabulary.is_reserved(name)
            or name.upper() in ReadOnlyRules.FORBIDDEN_WORDS
        )

    @staticmethod
    def identifier(name: str) -> str:
        """``name`` as it must be written in a statement."""
        if SqlVocabulary.needs_quoting(name):
            return MySqlIdentifier.quote(name)
        return name
