"""Esecuzione delle operazioni sul database fuori dal thread della GUI."""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, QThread, Signal, Slot

from querylean.config.config_manager import ConnectionConfig
from querylean.database.connection_manager import ConnectionManager
from querylean.database.errors import DatabaseError
from querylean.database.query_executor import QueryExecutor

log = logging.getLogger(__name__)

UNEXPECTED = "Errore imprevisto. I dettagli tecnici sono stati registrati nel log."


class DbWorker(QObject):
    """Vive in un QThread dedicato: le richieste arrivano tramite segnali e vengono quindi
    eseguite una alla volta, in ordine."""

    # richieste (GUI -> worker)
    connect_requested = Signal(object, str)
    disconnect_requested = Signal()
    test_requested = Signal(object, str)
    query_requested = Signal(str, int, int)

    # risposte (worker -> GUI)
    connected = Signal()
    connect_failed = Signal(str)
    disconnected = Signal()
    test_finished = Signal(bool, str)
    query_finished = Signal(object)
    query_failed = Signal(str, str)  # messaggio, tipo di errore

    def __init__(self, manager: ConnectionManager | None = None) -> None:
        super().__init__()
        self.manager = manager or ConnectionManager()
        self.executor = QueryExecutor(self.manager)
        self.connect_requested.connect(self._connect)
        self.disconnect_requested.connect(self._disconnect)
        self.test_requested.connect(self._test)
        self.query_requested.connect(self._query)

    @Slot(object, str)
    def _connect(self, config: ConnectionConfig, password: str) -> None:
        try:
            self.manager.connect(config, password)
        except DatabaseError as exc:
            self.connect_failed.emit(exc.message)
        except Exception:
            log.exception("Errore imprevisto durante la connessione")
            self.connect_failed.emit(UNEXPECTED)
        else:
            self.connected.emit()

    @Slot()
    def _disconnect(self) -> None:
        try:
            self.manager.disconnect()
        finally:
            self.disconnected.emit()

    @Slot(object, str)
    def _test(self, config: ConnectionConfig, password: str) -> None:
        try:
            version = self.manager.test_connection(config, password)
        except DatabaseError as exc:
            self.test_finished.emit(False, exc.message)
        except Exception:
            log.exception("Errore imprevisto durante il test di connessione")
            self.test_finished.emit(False, UNEXPECTED)
        else:
            suffix = f" (server MySQL {version})" if version else ""
            self.test_finished.emit(True, f"Connessione riuscita{suffix}.")

    @Slot(str, int, int)
    def _query(self, sql: str, row_limit: int, timeout: int) -> None:
        try:
            result = self.executor.execute(sql, row_limit, timeout)
        except DatabaseError as exc:
            self.query_failed.emit(exc.message, exc.kind)
        except Exception:
            log.exception("Errore imprevisto durante l'esecuzione")
            self.query_failed.emit(UNEXPECTED, "generic")
        else:
            self.query_finished.emit(result)

    # -- chiamabili da qualsiasi thread ---------------------------------------------
    def cancel_query(self, reason: str = "user") -> None:
        """Invia KILL QUERY in un thread a sé, senza bloccare la GUI."""
        threading.Thread(
            target=self.executor.cancel, args=(reason,), name="querylean-cancel", daemon=True
        ).start()


class DbThread:
    """Possiede il QThread e il worker; gestisce l'arresto ordinato."""

    def __init__(self, manager: ConnectionManager | None = None) -> None:
        self.thread = QThread()
        self.thread.setObjectName("querylean-db")
        self.worker = DbWorker(manager)
        self.worker.moveToThread(self.thread)
        self.thread.start()

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        """Interrompe l'eventuale query, ferma il thread e chiude la connessione."""
        if self.worker.executor.running:
            self.worker.executor.cancel("user")
        self.thread.quit()
        finished = bool(self.thread.wait(timeout_ms))
        if finished:
            self.worker.manager.disconnect()  # il thread è fermo: accesso sicuro
        else:
            log.warning("Il thread del database non si è fermato entro %d ms", timeout_ms)
            self.worker.manager.abort_session()
            finished = bool(self.thread.wait(1000))
        return finished
