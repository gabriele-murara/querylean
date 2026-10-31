# CLAUDE.md

**Nome del prodotto: QueryLean.** Tutti gli identificatori tecnici usano `querylean` in minuscolo: pacchetto Python, comando, `APP_NAME`, servizio keyring, cartelle di configurazione e log, file di packaging, bundle id `computer.murara.querylean`, artefatti `querylean-<ver>-<arch>.*`, DB e utente di test `querylean_test`/`querylean_ro`. Fanno eccezione le variabili d'ambiente, che per convenzione sono maiuscole (`QUERYLEAN_TEST_*`). "QueryLean" è solo il nome visibile all'utente (titolo della finestra, `QueryLean.app`, voce del menu).

Client desktop minimale (Linux/macOS, **no Windows**) per eseguire **solo query MySQL di lettura**. Le specifiche complete sono in `PROJECT.md`, la documentazione utente e di build in `README.md`. Codice, commenti, messaggi utente e documentazione sono in **italiano**.

## Comandi

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # setup (aggiungere [build] per PyInstaller)
.venv/bin/python -m querylean                        # avvio dai sorgenti
.venv/bin/python -m querylean --smoke-test           # verifica import/pacchetto (usato in CI)
.venv/bin/ruff check src tests                               # lint (deve essere pulito)
.venv/bin/pytest -q                                          # unit + GUI; conftest imposta QT_QPA_PLATFORM=offscreen
.venv/bin/pytest tests/test_readonly_validator.py -q         # solo validatore
PYTHON=.venv/bin/python APPIMAGE_EXTRACT_AND_RUN=1 packaging/build_linux_appimage.sh   # → dist/*.AppImage
```

Test d'integrazione (`tests/integration/`): vengono saltati se mancano le variabili `QUERYLEAN_TEST_HOST/PORT/DATABASE/USER/PASSWORD`. Per prepararli, un amministratore esegue una sola volta `sudo mysql < tests/integration/setup_test_db.sql`, che crea il database `querylean_test` e l'utente `querylean_ro` con solo SELECT. Sono test non distruttivi: non vanno mai puntati su database reali.

## Architettura

```
src/querylean/
  main.py                      avvio, logging, excepthook (niente stack trace all'utente), --smoke-test
  database/readonly_validator  validate(sql) -> ValidationResult(ok, statement, reason)
  database/connection_manager  unica connessione; connect/disconnect/test/ensure_connected/abort_session/kill_running_query
  database/query_executor      execute(sql, row_limit, timeout) -> QueryResult; cancel(reason)
  database/errors.py           DatabaseError(message, kind) + traduzione errori driver → messaggi italiani
  config/config_manager.py     JSON atomico 0600 in platformdirs (ConnectionConfig + UiPreferences)
  config/secret_storage.py     password nel keyring OS; backend in chiaro/fail = non disponibile
  utils/logging_config.py      RotatingFileHandler + RedactingFilter (redacting_filter globale)
  ui/db_worker.py              DbWorker in un QThread dedicato; richieste e risposte tramite Signal
  ui/main_window.py            toolbar, SqlEditor, ResultsTable, watchdog QTimer
```

Flusso di una query: `MainWindow.execute_query` → segnale `query_requested` → `DbWorker` (thread DB) → `QueryExecutor.execute` (valida, poi `ensure_connected`, `MAX_EXECUTION_TIME`, fetch limitato) → segnale `query_finished` o `query_failed(message, kind)`. L'interruzione (`cancel_query`) gira in un thread a sé e manda `KILL QUERY` da una **connessione separata**.

## Invarianti da non rompere

- **Sicurezza read-only su più livelli**:
  - Il validatore è **fail-closed**: in caso di dubbio rifiuta. Lavora su tre livelli: lexer MySQL interno, controllo dei token, AST sqlglot.
  - Al server si invia il **testo originale** (`ValidationResult.statement`), mai SQL rigenerato.
  - Non sostituire il validatore con una ricerca di parole chiave nel testo.
  - Ogni nuova forma ammessa richiede test, sia di accettazione sia di rifiuto, in `tests/test_readonly_validator.py`.
- **Opzioni di connessione da mantenere**:
  - niente `MULTI_STATEMENTS`, niente `LOCAL_FILES`;
  - `use_pure=True`;
  - `SET SESSION TRANSACTION READ ONLY`;
  - rimozione di `NO_BACKSLASH_ESCAPES` dal `sql_mode`, così il lexing del server coincide con quello del validatore.
- **Sola lettura**: la garanzia primaria è l'account MySQL con solo SELECT. L'app non deve mai creare utenti né modificare privilegi.
- **Password**:
  - mai su file di configurazione, log o messaggi;
  - registrarla con `redacting_filter.register_secret()` appena è nota;
  - `ConnectionParams.__repr__` la maschera.
- **Thread**:
  - nessuna operazione di database nel thread GUI;
  - `ConnectionManager` va usato solo dal thread del worker, tranne `kill_running_query`;
  - una sola query attiva alla volta.
- **Limite di righe**:
  - va applicato durante il fetch: cursore non bufferizzato, `fetchmany` fino a `limit+1`;
  - se le righe sono troncate, `abort_session()` invece di scaricare il resto; la riconnessione è trasparente.
  - Il massimo è 10.000.
- **Errori**: all'utente solo messaggi comprensibili (`DatabaseError.message`); i dettagli vanno nel log.
- **Tabella risultati**: non modificabile. NULL è mostrato come `NULL` in corsivo e si distingue da `""`. Nella copia TSV il NULL diventa una cella vuota.

## Convenzioni

- Python ≥ 3.11, `ruff` (line-length 100, regole `E F W I B UP`). I metodi override di Qt usano `# noqa: N802`.
- Dipendenza **PySide6-Essentials**, non `PySide6`: evita WebEngine e gli addon pesanti.
- `mysql-connector-python>=9.3`, necessario per `read_timeout`/`write_timeout`.
- Nei test unitari il database è finto: usare `tests/fakes.py` (`FakeConnector`/`FakeConnection`) e iniettarlo in `ConnectionManager(connector)`. Per il keyring, `MemoryKeyring` da `tests/test_secret_storage.py`.
- Nei test GUI, `MainWindow(config_manager, secrets, DbThread(ConnectionManager(FakeConnector())))` usa `tmp_path` per la configurazione. Va attesa con `qtbot.waitUntil`.
- **Non aggiungere funzionalità escluse** da `PROJECT.md` §16: multi-connessione, browser schemi, cronologia, export, autocomplete, plugin, telemetria, ecc.

## Packaging

- La build si fa con PyInstaller in modalità onedir (`packaging/querylean.spec`).
- Prodotti: Linux AppImage (`build_linux_appimage.sh`, build su Ubuntu 22.04) e macOS `.app` + `.dmg` (`build_macos_dmg.sh`, firma ad-hoc, un'architettura per build).
- La CI è in `.github/workflows/ci.yml`. Esegue lint e test con MySQL 8 come service; costruisce AppImage e DMG arm64/x86_64, con smoke test su ciascuno.
- Il pacchetto macOS non è ancora verificato: non dichiararlo compatibile finché la CI non passa.
