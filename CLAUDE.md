# CLAUDE.md

**Nome del prodotto: QueryLean.** Tutti gli identificatori tecnici usano `querylean` in minuscolo:

- pacchetto Python e comando;
- `AppInfo.NAME` e servizio keyring;
- cartelle di configurazione e log;
- file di packaging e artefatti `querylean-<ver>-<arch>.*`;
- bundle id `computer.murara.querylean`;
- DB e utente di test `querylean_test`/`querylean_ro`.

Fanno eccezione le variabili d'ambiente, che per convenzione sono maiuscole (`QUERYLEAN_TEST_*`). "QueryLean" (`AppInfo.DISPLAY_NAME`) è solo il nome visibile all'utente: titolo della finestra, `QueryLean.app`, voce del menu.

Client desktop minimale (Linux/macOS, **no Windows**) per eseguire **solo query MySQL di lettura**. Le specifiche complete sono in `PROJECT.md`, la documentazione utente e di build in `README.md`.

## Comandi

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # setup (aggiungere [build] per PyInstaller)
.venv/bin/python -m querylean                                # avvio dai sorgenti
.venv/bin/python -m querylean --smoke-test                   # verifica import/pacchetto (usato in CI)
.venv/bin/ruff check src tests packaging                     # lint (deve essere pulito)
.venv/bin/ruff format src tests packaging                    # formattazione a 80 colonne
.venv/bin/pytest -q                                          # unit + GUI; conftest imposta QT_QPA_PLATFORM=offscreen
.venv/bin/pytest tests/test_read_only_validator.py -q        # solo validatore
PYTHON=.venv/bin/python APPIMAGE_EXTRACT_AND_RUN=1 packaging/build_linux_appimage.sh   # → dist/*.AppImage
```

Test d'integrazione (`tests/integration/`): vengono saltati se mancano le variabili `QUERYLEAN_TEST_HOST/PORT/DATABASE/USER/PASSWORD`. Per prepararli, un amministratore esegue una sola volta `sudo mysql < tests/integration/setup_test_db.sql`, che crea il database `querylean_test` e l'utente `querylean_ro` con solo SELECT. Sono test non distruttivi: non vanno mai puntati su database reali.

## Stile del codice (obbligatorio)

- **Un file `.py` contiene una sola classe**, e il nome del file è il nome della classe in snake_case (`ConnectionManager` → `connection_manager.py`).
  - Fanno eccezione solo `__init__.py` (che contiene solo la docstring), `__main__.py`, `conftest.py` e `packaging/launcher.py`.
- **Package organizzati per responsabilità**: le classi vanno raggruppate secondo la stessa logica, ad esempio `database/validation/`, `ui/results/`. Una nuova classe va nel package del suo dominio; un package nuovo si crea solo per un'area logica nuova.
- **Nessuna funzione a livello di modulo**:
  - le utilità si raccolgono in classi con metodi `@staticmethod` (es. `ErrorTranslator`, `ValueFormatter`, `MySqlLexer`, `LogManager`);
  - le costanti diventano attributi di classe: `UPPER_CASE` se usate da fuori, `__UPPER_CASE` se interne;
  - niente variabili né alias di tipo a livello di modulo.
- **Attributi privati**:
  - ogni attributo d'istanza si chiama `self.__nome` ed è esposto con `@property` e, solo se deve essere modificabile, con `@nome.setter`;
  - i value object immutabili (`QueryResult`, `ValidationResult`, `SqlToken`, …) hanno solo property;
  - i metodi interni si chiamano `__metodo`;
  - un setter può normalizzare o validare (es. `ConnectionConfig` riporta i valori nei limiti), quindi anche dentro la classe si assegna tramite la property quando serve quella logica.
- **Classi astratte** (`abc.ABC` + `@abstractmethod`) quando una funzionalità ha più implementazioni intercambiabili. Esempi:
  - `SecretStore` → `KeyringSecretStore`;
  - `ValidationStage` → `LexicalStage`, `KeywordStage`, `SyntaxTreeStage`.

  Non creare astrazioni senza un secondo uso plausibile.
- **Lingua**:
  - in **inglese**: docstring (modulo, classe, metodi pubblici), commenti nel codice, messaggi di log;
  - in **italiano**: testi rivolti all'utente (GUI, `DatabaseError.message`, motivi di rifiuto del validatore) e documentazione (`README.md`, questo file).
- **Logging**:
  - usare il logger del progetto: `__log = LogManager.get_logger(__name__)` come attributo privato di classe, poi `self.__log.info(...)` o `NomeClasse.__log.info(...)` nei metodi statici;
  - passare gli argomenti in stile `%s`, non f-string;
  - **`print` è vietato** (anche in test e script Python): per l'output in console c'è `LogManager.configure(console=True)`.
- **Test**: anche i test seguono le regole.
  - Ogni file contiene una classe `Test…` con i test come metodi e le fixture come metodi `@pytest.fixture`.
  - I doppioni stanno in `tests/fakes/`, una classe per file.
  - Le fixture condivise stanno in classi base sotto `tests/support/`; il nome non inizia con `Test`, così pytest non le raccoglie.
- Override di Qt (`keyPressEvent`, `rowCount`, …) mantengono il nome Qt con `# noqa: N802`. Gli slot privati (`__on_...`) funzionano anche con connessioni tra thread.
- **Righe di massimo 80 colonne**:
  - vale per codice, docstring e commenti Python, compresi `packaging/querylean.spec` e `packaging/launcher.py`, e per gli script shell;
  - `ruff` lo verifica (`line-length = 80` in `pyproject.toml`) e `ruff format` lo applica al codice;
  - docstring, commenti e stringhe lunghe vanno spezzati a mano: le stringhe si dividono per concatenazione implicita tra parentesi (`("prima parte "` / `"seconda parte")`);
  - non usare `# noqa: E501`.
- Il codice va formattato con `.venv/bin/ruff format src tests packaging`; `ruff format --check` deve risultare pulito.
- Python ≥ 3.11, `ruff` con regole `E F W I B UP`.

## Logger

Il logger è implementato **nel progetto** (`querylean/log/`) e non importato da py-nano-logger. Motivi:

- py-nano-logger non ha rotazione né redazione dei segreti;
- usa `print`;
- si installa da un indice pip privato con `--trusted-host` (rischio per build riproducibili, CI e PyInstaller);
- richiede Python 3.12 e la dipendenza `boolifyer`.

`AppLogger` ne ricalca l'interfaccia: `debug`/`info`/`warning`/`error`/`critical` più `exception`, con `stacklevel=2`. Gli altri componenti:

- `LogManager.configure()`: `RotatingFileHandler` da 1 MB × 3 sul logger `querylean`, con `SecretRedactor` applicato a ogni handler;
- `LogManager.register_secret()`: maschera un segreto nei log.

## Architettura

```
src/querylean/
  app/                 AppInfo (NAME, DISPLAY_NAME, VERSION, AUTHOR, …), Application.run() (entry point, excepthook), SmokeTest
  log/                 AppLogger, LogManager, SecretRedactor
  config/              ConnectionConfig, UiPreferences, AppConfig, ConfigManager (JSON atomico 0600), ConfigError
  security/            SecretStore (astratta), KeyringSecretStore, SecretStorageError
  database/
    errors/            DatabaseError(message, kind), QueryCancelled, QueryTimeout, ErrorTranslator
    connection/        ConnectionParams (kwargs del driver, password mascherata), ConnectionManager
    execution/         QueryExecutor (execute/cancel), QueryResult
    validation/        ReadOnlyValidator → stadi ValidationStage su ValidationContext;
                       MySqlLexer, SqlToken, LexedStatement, ReadOnlyRules, ValidationResult
  ui/
    main/              MainWindow, ConnectionState
    dialogs/           ConnectionDialog, AboutDialog (versione/autore da AppInfo)
    icons/             ToolbarIcons (icone disegnate con QPainter: nessun asset da impacchettare)
    editor/            SqlEditor, SqlHighlighter, LineNumberArea
    results/           ResultsTable, ResultsModel, ValueFormatter
    worker/            DbWorker (QObject nel thread DB), DbThread (avvio/arresto)
tests/                 test_<classe>.py; fakes/; support/; integration/
```

`AppInfo.VERSION` e `AppInfo.AUTHOR` devono coincidere con `version` e `authors` in `pyproject.toml`: lo verifica `tests/test_app_info.py`, e gli script di build leggono la versione da `pyproject.toml`.

Flusso di una query:

1. `MainWindow.execute_query` emette il segnale `query_requested`.
2. `DbWorker`, nel thread del database, chiama `QueryExecutor.execute`, che:
   - valida con `ReadOnlyValidator`;
   - chiama `ensure_connected`;
   - imposta `MAX_EXECUTION_TIME`;
   - esegue il fetch limitato.
3. L'esito torna alla GUI con il segnale `query_finished` oppure `query_failed(message, kind)`.

L'interruzione (`DbWorker.cancel_query`) gira in un thread a sé e manda `KILL QUERY` da una **connessione separata**.

## Invarianti da non rompere

- **Sicurezza read-only su più livelli**:
  - Il validatore è **fail-closed**: in caso di dubbio rifiuta, anche per eccezioni impreviste.
  - Ha tre stadi indipendenti: lexer MySQL, parole e funzioni, AST sqlglot.
  - Al server si invia il **testo originale** (`ValidationResult.statement`), mai SQL rigenerato.
  - Non sostituirlo con una ricerca di parole chiave nel testo.
  - Ogni nuova forma ammessa richiede test, sia di accettazione sia di rifiuto, in `tests/test_read_only_validator.py`.
- **Opzioni di connessione da mantenere** (`ConnectionParams.to_connect_kwargs`, `ConnectionManager`):
  - niente `MULTI_STATEMENTS`, niente `LOCAL_FILES`;
  - `use_pure=True`;
  - `SET SESSION TRANSACTION READ ONLY`;
  - rimozione di `NO_BACKSLASH_ESCAPES` dal `sql_mode`.
- **Sola lettura**: la garanzia primaria è l'account MySQL con solo SELECT. L'app non deve mai creare utenti né modificare privilegi.
- **Password**:
  - mai su file di configurazione, log o messaggi;
  - registrarla con `LogManager.register_secret()` appena è nota (il setter `MainWindow.password` lo fa già);
  - `ConnectionParams.__repr__` la maschera.
- **Thread**:
  - nessuna operazione di database nel thread GUI;
  - `ConnectionManager` va usato solo dal thread del worker, tranne `kill_running_query`;
  - una sola query attiva alla volta.
- **Limite di righe**:
  - va applicato durante il fetch: cursore non bufferizzato, `fetchmany` fino a `limit+1`;
  - se le righe sono troncate, `abort_session()`; la riconnessione è trasparente.
  - Il massimo è 10.000.
- **Errori**: all'utente solo messaggi comprensibili (`DatabaseError.message`), mai stack trace; i dettagli vanno nel log.
- **Tabella risultati**: non modificabile. NULL è mostrato come `NULL` in corsivo e si distingue da `""`. Nella copia TSV il NULL diventa una cella vuota.

## Dipendenze e test

- Dipendenza **PySide6-Essentials**, non `PySide6`: evita WebEngine e gli addon pesanti.
- `mysql-connector-python>=9.3`, necessario per `read_timeout`/`write_timeout`.
- Nei test unitari il database è finto: `tests/fakes/` (`FakeConnector`, `FakeConnection`, `FakeCursor`), da iniettare con `ConnectionManager(connector)`.
  - Per simulare `KILL QUERY` si usa `FakeConnection.on_kill`.
  - Per il keyring ci sono `MemoryKeyring` e `LockedKeyring`.
- I test GUI estendono `support/main_window_test_base.MainWindowTestBase`, che fornisce le fixture `connector`/`window` e gli helper `configure`/`connect`/`run`. Vanno attesi con `qtbot.waitUntil`.
- **Non aggiungere funzionalità escluse** da `PROJECT.md` §16: multi-connessione, browser schemi, cronologia, export, autocomplete, plugin, telemetria, ecc.

## Packaging

- La build si fa con PyInstaller in modalità onedir (`packaging/querylean.spec`, entry `packaging/launcher.py` → `Application.run()`).
- Prodotti: Linux AppImage (`build_linux_appimage.sh`, build su Ubuntu 22.04) e macOS `.app` + `.dmg` (`build_macos_dmg.sh`, firma ad-hoc, un'architettura per build).
- La CI è in `.github/workflows/ci.yml`. Esegue lint e test con MySQL 8 come service; costruisce AppImage e DMG arm64/x86_64, con smoke test su ciascuno.
- Il pacchetto macOS non è ancora verificato: non dichiararlo compatibile finché la CI non passa.
