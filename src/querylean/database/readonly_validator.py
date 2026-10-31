"""Validatore delle query di sola lettura.

La validazione è fail-closed e procede su tre livelli indipendenti:

1. un lexer MySQL interno individua stringhe, identificatori quotati e commenti con le
   stesse regole del server e rifiuta i costrutti che il server eseguirebbe ma un parser
   generico ignorerebbe (commenti eseguibili ``/*! */``, hint ``/*+ */``, ``--`` non
   seguito da spazio), le istruzioni multiple e le assegnazioni ``:=``;
2. i token significativi (fuori da stringhe e commenti) vengono confrontati con un elenco
   di parole riservate e funzioni che modificano dati o stato;
3. sqlglot analizza l'istruzione con il dialetto MySQL: deve risultare esattamente una
   istruzione, di un tipo ammesso, priva di nodi di scrittura, ``INTO`` o lock.

Al server viene inviato il testo originale (senza ``;`` finale), mai SQL rigenerato.
Il validatore è una barriera aggiuntiva: la garanzia principale resta l'account MySQL
con soli privilegi di lettura.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

log = logging.getLogger(__name__)

NOT_ALLOWED = (
    "Query non consentita: questa applicazione supporta esclusivamente operazioni di lettura "
    "(SELECT, SHOW, DESCRIBE, EXPLAIN)."
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    statement: str = ""  # testo da inviare al server
    reason: str = ""  # messaggio per l'utente se ok è False

    @classmethod
    def reject(cls, reason: str) -> ValidationResult:
        return cls(False, "", reason)


class _Rejected(Exception):
    pass


# Parole riservate in MySQL (non utilizzabili come identificatori non quotati) che non
# compaiono mai in una query di lettura ammessa. Le istruzioni che iniziano con altre
# parole (TRUNCATE, SET, USE, ...) sono già escluse dall'elenco delle istruzioni ammesse.
_FORBIDDEN_WORDS = frozenset(
    {
        "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "RENAME", "GRANT",
        "REVOKE", "CALL", "LOAD", "LOCK", "UNLOCK", "INTO", "OUTFILE", "DUMPFILE",
    }
)
# Ammesse soltanto come prima parola di SHOW CREATE ...
_SHOW_CREATE_EXCEPTION = "CREATE"

# Funzioni con effetti collaterali (lock, accesso a file, attese su replica).
_FORBIDDEN_FUNCTIONS = frozenset(
    {
        "GET_LOCK", "RELEASE_LOCK", "RELEASE_ALL_LOCKS", "IS_FREE_LOCK", "IS_USED_LOCK",
        "LOAD_FILE", "MASTER_POS_WAIT", "SOURCE_POS_WAIT", "WAIT_FOR_EXECUTED_GTID_SET",
        "WAIT_UNTIL_SQL_THREAD_AFTER_GTIDS", "SET_VAR", "NAME_CONST",
    }
)

_ALLOWED_SHOW_PREFIXES = (
    "SHOW",
    "DESCRIBE",
    "DESC",
    "EXPLAIN",
)


# --------------------------------------------------------------------------- lexer
@dataclass(frozen=True)
class _Token:
    kind: str  # "word", "string", "qident", "symbol", "number"
    text: str
    start: int


def _lex(sql: str) -> tuple[list[_Token], str]:
    """Scansiona `sql` come farebbe MySQL. Restituisce i token significativi e il testo
    dell'unica istruzione (senza `;` finale). Solleva _Rejected."""
    tokens: list[_Token] = []
    i, n = 0, len(sql)
    statement_end: int | None = None

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        if statement_end is not None and not ch.isspace() and not _starts_comment(sql, i):
            raise _Rejected(
                "Sono presenti più istruzioni SQL: questa versione ne esegue una sola per volta."
            )

        if ch.isspace():
            i += 1
        elif ch == "#":
            i = _skip_line(sql, i)
        elif ch == "-" and nxt == "-":
            after = sql[i + 2] if i + 2 < n else ""
            if after == "" or after.isspace() or ord(after) < 32:
                i = _skip_line(sql, i)
            else:
                raise _Rejected(
                    "Sequenza «--» ambigua: in MySQL è un commento solo se seguita da uno "
                    "spazio. Aggiungi uno spazio o riformula l'espressione."
                )
        elif ch == "/" and nxt == "*":
            marker = sql[i + 2] if i + 2 < n else ""
            if marker in ("!", "+"):
                raise _Rejected(
                    "I commenti eseguibili MySQL (/*! … */) e gli hint dell'ottimizzatore "
                    "(/*+ … */) non sono consentiti."
                )
            end = sql.find("*/", i + 2)
            if end < 0:
                raise _Rejected("Commento /* … */ non chiuso.")
            i = end + 2
        elif ch in ("'", '"'):
            end = _scan_quoted(sql, i, ch, backslash=True)
            tokens.append(_Token("string", sql[i:end], i))
            i = end
        elif ch == "`":
            end = _scan_quoted(sql, i, ch, backslash=False)
            tokens.append(_Token("qident", sql[i:end], i))
            i = end
        elif ch == ";":
            statement_end = i
            i += 1
        elif ch == ":" and nxt == "=":
            raise _Rejected("L'assegnazione di variabili (:=) non è consentita.")
        elif ch.isalpha() or ch in "_$" or ord(ch) > 127:
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] in "_$" or ord(sql[j]) > 127):
                j += 1
            tokens.append(_Token("word", sql[i:j], i))
            i = j
        elif ch.isdigit():
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] in "._"):
                j += 1
            tokens.append(_Token("number", sql[i:j], i))
            i = j
        else:
            tokens.append(_Token("symbol", ch, i))
            i += 1

    statement = sql[:statement_end] if statement_end is not None else sql
    return tokens, statement.strip()


def _starts_comment(sql: str, i: int) -> bool:
    ch = sql[i]
    if ch == "#":
        return True
    two = sql[i : i + 2]
    if two == "/*":
        return True
    if two == "--":
        after = sql[i + 2] if i + 2 < len(sql) else ""
        return after == "" or after.isspace()
    return False


def _skip_line(sql: str, i: int) -> int:
    end = sql.find("\n", i)
    return len(sql) if end < 0 else end + 1


def _scan_quoted(sql: str, start: int, quote: str, *, backslash: bool) -> int:
    """Restituisce l'indice successivo alla quota di chiusura."""
    i, n = start + 1, len(sql)
    while i < n:
        ch = sql[i]
        if backslash and ch == "\\":
            i += 2
            continue
        if ch == quote:
            if i + 1 < n and sql[i + 1] == quote:  # quota raddoppiata
                i += 2
                continue
            return i + 1
        i += 1
    raise _Rejected("Stringa o identificatore tra virgolette non chiuso.")


# --------------------------------------------------------------------------- token checks
def _check_tokens(tokens: list[_Token]) -> str:
    """Controlla le parole significative. Restituisce la prima parola (maiuscola)."""
    words = [t for t in tokens if t.kind == "word"]
    if not tokens or not words or tokens[0].kind != "word" and tokens[0].text != "(":
        raise _Rejected(NOT_ALLOWED)

    first = next((t.text.upper() for t in tokens if t.kind == "word"), "")
    is_show = first == "SHOW"

    for index, token in enumerate(tokens):
        if token.kind != "word":
            continue
        upper = token.text.upper()
        prev = tokens[index - 1] if index > 0 else None
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        qualified = prev is not None and prev.kind == "symbol" and prev.text == "."

        if upper in _FORBIDDEN_WORDS and not qualified:
            if not (is_show and upper == _SHOW_CREATE_EXCEPTION and index == 1):
                raise _Rejected(f"{NOT_ALLOWED} Parola chiave non ammessa: {upper}.")
        if (
            upper in _FORBIDDEN_FUNCTIONS
            and following is not None
            and following.text == "("
        ):
            raise _Rejected(f"La funzione {upper}() non è consentita in modalità sola lettura.")
    return first


# --------------------------------------------------------------------------- AST checks
def _classes(*names: str) -> tuple[type, ...]:
    return tuple(c for c in (getattr(exp, name, None) for name in names) if isinstance(c, type))


_SELECT_ROOTS = _classes("Select", "Union", "Except", "Intersect", "SetOperation", "Subquery")
_FORBIDDEN_NODES = _classes(
    "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "AlterTable",
    "TruncateTable", "Command", "Set", "SetItem", "Use", "Transaction", "Commit", "Rollback",
    "LoadData", "Copy", "Into", "Lock", "Kill", "Pragma", "Grant", "Revoke", "Cache",
    "Uncache", "Refresh", "Analyze", "Execute", "Declare", "Block", "IfBlock", "WhileBlock",
)


def _check_ast(statement: str, first_word: str) -> None:
    try:
        expressions = sqlglot.parse(statement, read="mysql")
    except SqlglotError as exc:
        log.info("Parsing SQL fallito: %s", exc)
        raise _Rejected(
            "Impossibile analizzare la query in modo sicuro: verifica la sintassi. "
            "Le query non riconosciute vengono rifiutate."
        ) from None

    expressions = [e for e in expressions if e is not None]
    if len(expressions) != 1:
        raise _Rejected(
            "Sono presenti più istruzioni SQL: questa versione ne esegue una sola per volta."
        )
    root = expressions[0]

    if first_word == "SHOW":
        if not isinstance(root, exp.Show):
            raise _Rejected(f"{NOT_ALLOWED} Forma di SHOW non riconosciuta.")
    elif first_word in ("DESCRIBE", "DESC", "EXPLAIN"):
        if not isinstance(root, exp.Describe):
            raise _Rejected(f"{NOT_ALLOWED} Forma di {first_word} non riconosciuta.")
        target = root.this
        if not isinstance(target, (exp.Table, *_SELECT_ROOTS)):
            raise _Rejected(f"{NOT_ALLOWED} {first_word} è ammesso solo su tabelle o SELECT.")
    elif first_word in ("SELECT", "WITH") or first_word == "":
        if not isinstance(root, _SELECT_ROOTS):
            raise _Rejected(NOT_ALLOWED)
    else:
        raise _Rejected(NOT_ALLOWED)

    for node in root.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise _Rejected(f"{NOT_ALLOWED} Costrutto non ammesso: {type(node).__name__}.")
        if isinstance(node, exp.Select) and (node.args.get("locks") or node.args.get("into")):
            raise _Rejected(f"{NOT_ALLOWED} SELECT … INTO e i lock non sono consentiti.")
        if isinstance(node, exp.Func):
            name = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).upper()
            if name in _FORBIDDEN_FUNCTIONS:
                raise _Rejected(f"La funzione {name}() non è consentita in modalità sola lettura.")


# --------------------------------------------------------------------------- API
def validate(sql: str) -> ValidationResult:
    """Valida una singola istruzione di lettura. Non solleva eccezioni."""
    if not sql or not sql.strip():
        return ValidationResult.reject("La query è vuota.")
    try:
        tokens, statement = _lex(sql)
        if not statement or not tokens:
            raise _Rejected("La query è vuota.")
        first_word = _check_tokens(tokens)
        if first_word not in ("SELECT", "WITH", *_ALLOWED_SHOW_PREFIXES):
            # Le SELECT tra parentesi iniziano con "(": la prima parola sarà SELECT.
            raise _Rejected(NOT_ALLOWED)
        _check_ast(statement, first_word)
    except _Rejected as rejection:
        return ValidationResult.reject(str(rejection))
    except Exception:  # fail-closed su qualunque errore inatteso
        log.exception("Errore inatteso nel validatore")
        return ValidationResult.reject(
            "Impossibile verificare la query in modo sicuro: la query è stata rifiutata."
        )
    return ValidationResult(True, statement, "")
