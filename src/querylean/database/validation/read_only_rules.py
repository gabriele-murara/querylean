"""Static rule set of the read-only validator."""

from __future__ import annotations

from sqlglot import exp


class ReadOnlyRules:
    """Allowed statements, forbidden words, functions and syntax-tree nodes."""

    NOT_ALLOWED = (
        "Query non consentita: questa applicazione supporta esclusivamente "
        "operazioni di lettura (SELECT, SHOW, DESCRIBE, EXPLAIN)."
    )
    MULTIPLE_STATEMENTS = (
        "Sono presenti più istruzioni SQL: questa versione ne esegue una "
        "sola per volta."
    )

    # First word of every accepted statement.
    SELECT_FIRST_WORDS = frozenset({"SELECT", "WITH"})
    DESCRIBE_FIRST_WORDS = frozenset({"DESCRIBE", "DESC", "EXPLAIN"})
    SHOW_FIRST_WORD = "SHOW"
    ALLOWED_FIRST_WORDS = (
        SELECT_FIRST_WORDS | DESCRIBE_FIRST_WORDS | {SHOW_FIRST_WORD}
    )

    # MySQL reserved words (unusable as unquoted identifiers) that never appear
    # in an accepted read query. Statements starting with other words (TRUNCATE,
    # SET, USE, ...) are already excluded by ALLOWED_FIRST_WORDS.
    FORBIDDEN_WORDS = frozenset(
        {
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE",
            "DROP",
            "ALTER",
            "RENAME",
            "GRANT",
            "REVOKE",
            "CALL",
            "LOAD",
            "LOCK",
            "UNLOCK",
            "INTO",
            "OUTFILE",
            "DUMPFILE",
        }
    )
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
