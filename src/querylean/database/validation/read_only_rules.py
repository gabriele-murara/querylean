"""Static rule set of the read-only validator."""

from __future__ import annotations

from sqlglot import exp


class ReadOnlyRules:
    """Allowed statements, forbidden words, functions and syntax-tree nodes."""

    NOT_ALLOWED = "Query not allowed: this application supports "
    NOT_ALLOWED += "read operations only (SELECT, SHOW, "
    NOT_ALLOWED += "DESCRIBE, EXPLAIN)."
    MULTIPLE_STATEMENTS = "The text contains more than one SQL statement: "
    MULTIPLE_STATEMENTS += "this version runs one at a time."

    # First word of every accepted statement.
    SELECT_FIRST_WORDS = frozenset({"SELECT", "WITH"})
    DESCRIBE_FIRST_WORDS = frozenset({"DESCRIBE", "DESC", "EXPLAIN"})
    SHOW_FIRST_WORD = "SHOW"
    ALLOWED_FIRST_WORDS = (
        SELECT_FIRST_WORDS | DESCRIBE_FIRST_WORDS | {SHOW_FIRST_WORD}
    )

    # Words of write, modify and administration statements. They are
    # rejected wherever they appear outside strings and comments: unquoted,
    # qualified (``t.update``) or as a quoted identifier (`` `delete` ``),
    # so a column or alias with one of these names is rejected too.
    # SET, START, BEGIN, CHECK and ANALYZE are not listed: their statements
    # are already excluded by ALLOWED_FIRST_WORDS, and the words are part of
    # reads such as SHOW CHARACTER SET or EXPLAIN ANALYZE.
    FORBIDDEN_WORDS = frozenset(
        {
            "INSERT",
            "UPDATE",
            "DELETE",
            "REPLACE",
            "TRUNCATE",
            "MERGE",
            "UPSERT",
            "CREATE",
            "DROP",
            "ALTER",
            "RENAME",
            "GRANT",
            "REVOKE",
            "CALL",
            "DO",
            "HANDLER",
            "LOAD",
            "IMPORT",
            "LOCK",
            "UNLOCK",
            "INTO",
            "OUTFILE",
            "DUMPFILE",
            "PREPARE",
            "EXECUTE",
            "DEALLOCATE",
            "COMMIT",
            "ROLLBACK",
            "SAVEPOINT",
            "XA",
            "FLUSH",
            "RESET",
            "PURGE",
            "KILL",
            "SHUTDOWN",
            "RESTART",
            "INSTALL",
            "UNINSTALL",
            "OPTIMIZE",
            "REPAIR",
            "CLONE",
            "SIGNAL",
            "RESIGNAL",
            "DECLARE",
        }
    )
    # Forbidden words that are also read-only functions: allowed only as an
    # unquoted, unqualified name directly followed by "(" (REPLACE(s, a, b),
    # TRUNCATE(x, d)). The statements never have that form.
    FUNCTION_NAME_EXCEPTIONS = frozenset({"REPLACE", "TRUNCATE"})
    # Allowed only as the second word of SHOW CREATE ...
    SHOW_CREATE_EXCEPTION = "CREATE"

    # Functions with side effects (locks, file access, replication waits).
    FORBIDDEN_FUNCTIONS = frozenset(
        {
            "GET_LOCK",
            "RELEASE_LOCK",
            "RELEASE_ALL_LOCKS",
            "IS_FREE_LOCK",
            "IS_USED_LOCK",
            "LOAD_FILE",
            "MASTER_POS_WAIT",
            "SOURCE_POS_WAIT",
            "WAIT_FOR_EXECUTED_GTID_SET",
            "WAIT_UNTIL_SQL_THREAD_AFTER_GTIDS",
            "SET_VAR",
            "NAME_CONST",
        }
    )

    # sqlglot node classes (resolved by name: some only exist in certain
    # versions).
    SELECT_ROOTS: tuple[type, ...] = tuple(
        c
        for c in (
            getattr(exp, name, None)
            for name in (
                "Select",
                "Union",
                "Except",
                "Intersect",
                "SetOperation",
                "Subquery",
            )
        )
        if isinstance(c, type)
    )
    FORBIDDEN_NODES: tuple[type, ...] = tuple(
        c
        for c in (
            getattr(exp, name, None)
            for name in (
                "Insert",
                "Update",
                "Delete",
                "Merge",
                "Create",
                "Drop",
                "Alter",
                "AlterTable",
                "TruncateTable",
                "Command",
                "Set",
                "SetItem",
                "Use",
                "Transaction",
                "Commit",
                "Rollback",
                "LoadData",
                "Copy",
                "Into",
                "Lock",
                "Kill",
                "Pragma",
                "Grant",
                "Revoke",
                "Cache",
                "Uncache",
                "Refresh",
                "Analyze",
                "Execute",
                "Declare",
                "Block",
                "IfBlock",
                "WhileBlock",
            )
        )
        if isinstance(c, type)
    )
