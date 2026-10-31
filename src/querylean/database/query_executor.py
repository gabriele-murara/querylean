"""Esecuzione di una singola query di lettura con limite di righe e timeout."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from mysql.connector import errorcode
from mysql.connector import errors as mysql_errors

from querylean.database.connection_manager import ConnectionManager
from querylean.database.errors import (
    DatabaseError,
    QueryCancelled,
    QueryTimeout,
    is_connection_lost,
    translate_query_error,
)
from querylean.database.readonly_validator import validate

log = logging.getLogger(__name__)

FETCH_BATCH = 500
# Codice restituito da MySQL quando MAX_EXECUTION_TIME viene superato.
ER_QUERY_TIMEOUT = getattr(errorcode, "ER_QUERY_TIMEOUT", 3024)


@dataclass(frozen=True)
class QueryResult:
    statement: str
    columns: list[str]
    rows: list[tuple[Any, ...]]
    truncated: bool
    row_limit: int
    elapsed: float  # secondi


class QueryExecutor:
    """Esegue le query sulla connessione del ConnectionManager.

    `execute` va chiamato dal thread del database; `cancel` può essere chiamato da qualsiasi
    thread e interrompe la query in corso tramite KILL QUERY su una connessione separata.
    """

    def __init__(self, manager: ConnectionManager) -> None:
        self._manager = manager
        self._cancel_reason: str | None = None  # "user" | "timeout"
        self._running = threading.Event()
        self._session_timeout: tuple[int, int] | None = None  # (connection_id, ms)

    @property
    def running(self) -> bool:
        return self._running.is_set()

    def cancel(self, reason: str = "user") -> bool:
        """Richiede l'interruzione della query corrente. Bloccante per al massimo il tempo
        di connessione: chiamarlo fuori dal thread della GUI."""
        if not self._running.is_set():
            return False
        self._cancel_reason = reason
        return self._manager.kill_running_query()

    def execute(self, sql: str, row_limit: int, timeout: int) -> QueryResult:
        validation = validate(sql)
        if not validation.ok:
            raise DatabaseError(validation.reason, kind="rejected")
        statement = validation.statement

        conn = self._manager.ensure_connected()
        self._cancel_reason = None
        self._running.set()
        started = time.monotonic()
        cursor = None
        try:
            self._apply_server_timeout(conn, timeout)
            cursor = conn.cursor()  # non bufferizzato: righe lette solo su richiesta
            cursor.execute(statement)
            columns = [str(col[0]) for col in (cursor.description or [])]
            rows: list[tuple[Any, ...]] = []
            truncated = False
            if columns:
                rows, truncated = _fetch_limited(cursor, row_limit)
            elapsed = time.monotonic() - started

            if truncated:
                # Evita di scaricare il resto del result set: chiude la sessione, che verrà
                # riaperta in modo trasparente alla prossima query.
                cursor = None
                self._manager.abort_session()
            log.info(
                "Query eseguita: %d righe%s in %.3f s",
                len(rows), " (limitate)" if truncated else "", elapsed,
            )
            return QueryResult(statement, columns, rows, truncated, row_limit, elapsed)
        except Exception as exc:
            log.info("Esecuzione fallita: %r", exc)
            raise self._translate(exc, timeout, conn) from None
        finally:
            self._running.clear()
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    self._manager.abort_session()

    # ------------------------------------------------------------------ helpers
    def _apply_server_timeout(self, conn: Any, timeout: int) -> None:
        """Imposta MAX_EXECUTION_TIME (vale per le SELECT) solo quando cambia."""
        ms = int(timeout) * 1000
        key = (self._manager.connection_id or 0, ms)
        if self._session_timeout == key:
            return
        cursor = conn.cursor()
        try:
            cursor.execute(f"SET SESSION MAX_EXECUTION_TIME = {ms}")
        except mysql_errors.Error as exc:
            # Es. MariaDB o MySQL < 5.7.8: resta attivo il watchdog lato client.
            log.warning("MAX_EXECUTION_TIME non supportato: %r", exc)
        finally:
            cursor.close()
        self._session_timeout = key

    def _translate(self, exc: BaseException, timeout: int, conn: Any) -> DatabaseError:
        reason = self._cancel_reason
        errno = getattr(exc, "errno", None)
        if errno == ER_QUERY_TIMEOUT:
            result: DatabaseError = QueryTimeout(timeout)
        elif errno == errorcode.ER_QUERY_INTERRUPTED or reason is not None:
            result = QueryTimeout(timeout) if reason == "timeout" else QueryCancelled()
        else:
            result = translate_query_error(exc)

        # Dopo un errore a metà lettura la sessione potrebbe avere risultati pendenti:
        # meglio ripartire da una sessione pulita.
        if (
            result.kind == "connection_lost"
            or is_connection_lost(exc)
            or getattr(conn, "unread_result", False)
            or reason
        ):
            self._manager.abort_session()
        return result


def _fetch_limited(cursor: Any, row_limit: int) -> tuple[list[tuple[Any, ...]], bool]:
    """Legge al massimo `row_limit` righe (più una, per sapere se ce ne sono altre)."""
    rows: list[tuple[Any, ...]] = []
    wanted = row_limit + 1
    while len(rows) < wanted:
        batch = cursor.fetchmany(min(FETCH_BATCH, wanted - len(rows)))
        if not batch:
            break
        rows.extend(batch)
    truncated = len(rows) > row_limit
    return rows[:row_limit], truncated
