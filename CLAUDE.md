# CLAUDE.md

**Nome del prodotto: QueryLean.** Tutti gli identificatori tecnici usano `querylean` in minuscolo:

- pacchetto Python e comando;
- `AppInfo.NAME` e servizio keyring;
- cartelle di configurazione e log;
- file di packaging e artefatti `querylean-<ver>-<arch>.*`;
- bundle id `computer.murara.querylean`;
- DB e utente di test `querylean_test`/`querylean_ro`.

Fanno eccezione le variabili d'ambiente, che per convenzione sono maiuscole (`QUERYLEAN_TEST_*`). "QueryLean" (`AppInfo.DISPLAY_NAME`) è solo il nome visibile all'utente: titolo della finestra, `QueryLean.app`, voce del menu.

Client desktop minimale (Linux/macOS, **no Windows**) per eseguire **solo query MySQL di lettura**, con più connessioni salvate e una sola aperta alla volta; una connessione usa un database oppure tutti quelli accessibili. Le specifiche complete sono in `PROJECT.md`, la documentazione utente e di build in `README.md` (inglese) e `README_ITA.md` (italiano).

**I due README vanno tenuti allineati.** Ogni modifica che tocca la documentazione si applica a **entrambi** i file nella stessa modifica, con lo stesso contenuto e la stessa struttura delle sezioni. Riguarda funzionalità, comandi, packaging, dimensioni, limiti e CI. Non si aggiorna mai uno solo dei due.

## Comandi

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev,build]"   # setup ([build]: PyInstaller, serve anche ai test delle licenze)
.venv/bin/python -m querylean                                # avvio dai sorgenti
.venv/bin/python -m querylean --smoke-test                   # verifica import/pacchetto (usato in CI)
.venv/bin/ruff check src tests packaging                     # lint (deve essere pulito)
.venv/bin/ruff format src tests packaging                    # formattazione a 80 colonne
.venv/bin/pytest -q                                          # unit + GUI; conftest imposta QT_QPA_PLATFORM=offscreen
.venv/bin/pytest tests/test_read_only_validator.py -q        # solo validatore
PYTHON=.venv/bin/python APPIMAGE_EXTRACT_AND_RUN=1 packaging/build_linux_appimage.sh   # → dist/*.AppImage
PYTHON=.venv/bin/python packaging/build_linux_deb.sh                              # → dist/*.deb (su 24.04)
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
  - in **inglese**: docstring (modulo, classe, metodi pubblici), commenti nel codice, messaggi di log e **tutti i testi rivolti all'utente** (GUI, finestra About, `DatabaseError.message`, motivi di rifiuto del validatore, descrizioni dei pacchetti). Dalla 1.3 l'interfaccia è in inglese, per scelta dell'utente;
  - in **italiano**: documentazione (`README_ITA.md`, questo file). Nel README italiano i testi della GUI restano in inglese, seguiti dalla traduzione tra parentesi alla prima occorrenza, ad esempio **Run** (Esegui);
  - in **inglese**, come traduzione fedele di `README_ITA.md`: `README.md`.
- **Logging**:
  - usare il logger del progetto: `__log = LogManager.get_logger(__name__)` come attributo privato di classe, poi `self.__log.info(...)` o `NomeClasse.__log.info(...)` nei metodi statici;
  - anche i messaggi di log seguono le regole delle "Stringhe": segnaposto di `.format()` e argomenti passati al logger, `self.__log.info("Connected to {}:{}", host, port)`. Il logger chiama `.format()` solo se il livello è attivo, quindi non si formatta prima la stringa. Niente `%s`;
  - un messaggio di log senza argomenti non viene formattato: le graffe e i `%` nel testo restano come sono. Con argomenti, le graffe letterali vanno raddoppiate (`{{` e `}}`);
  - **`print` è vietato** (anche in test e script Python): per l'output in console c'è `LogManager.configure(console=True)`.
- **Test**: anche i test seguono le regole.
  - Ogni file contiene una classe `Test…` con i test come metodi e le fixture come metodi `@pytest.fixture`.
  - I doppioni stanno in `tests/fakes/`, una classe per file.
  - Le fixture condivise stanno in classi base sotto `tests/support/`; il nome non inizia con `Test`, così pytest non le raccoglie.
- Override di Qt (`keyPressEvent`, `rowCount`, …) mantengono il nome Qt con `# noqa: N802`. Gli slot privati (`__on_...`) funzionano anche con connessioni tra thread.
- **Righe di massimo 80 colonne**:
  - vale per codice, docstring e commenti Python, compresi `packaging/querylean.spec` e `packaging/launcher.py`, e per gli script shell;
  - `ruff` lo verifica (`line-length = 80` in `pyproject.toml`) e `ruff format` lo applica al codice;
  - docstring e commenti lunghi vanno spezzati a mano; le stringhe lunghe si costruiscono come descritto in "Stringhe";
  - non usare `# noqa: E501`;
  - `ruff` non conta i pragma finali (`# noqa: …`) nella lunghezza: `tests/test_line_length.py` misura la riga fisica di `.py`, `.sh` e `.spec`.
- **Stringhe**:
  - **niente concatenazione di stringhe**: né con `+` tra testo e valori (`"Errore: " + msg`), né per concatenazione implicita tra letterali adiacenti (`("prima parte "` / `"seconda parte")`);
  - **i valori si inseriscono sempre con il metodo `.format()`**: niente f-string e niente formattazione con `%`;
  - un testo lungo si costruisce su più righe con `+=` di soli letterali, applicando `.format()` alla fine:

    ```python
    msg = "bala blablablablablablabla"
    msg += "bala blablablablablablabla {}"
    msg = msg.format(value)
    ```

  - la regola vale anche per il logging (vedi "Logging") e per il formato dei record (`LogManager` usa `logging.Formatter(..., style="{")`);
  - `tests/test_string_style.py` verifica tutto il codice (`src`, `tests`, `packaging`): fallisce con f-string, concatenazioni implicite, `+` tra stringhe, formattazione con `%` e segnaposto `%s` nelle chiamate di log;
  - la regola `UP032` di ruff (che suggerisce le f-string al posto di `.format()`) è disattivata in `pyproject.toml`.
- Il codice va formattato con `.venv/bin/ruff format src tests packaging`; `ruff format --check` deve risultare pulito.
- Python ≥ 3.11, `ruff` con regole `E F W I B UP`.

## Logger

Il logger è implementato **nel progetto** (`querylean/log/`) e non importato da py-nano-logger. Motivi:

- py-nano-logger non ha rotazione né redazione dei segreti;
- usa `print`;
- si installa da un indice pip privato con `--trusted-host` (rischio per build riproducibili, CI e PyInstaller);
- richiede Python 3.12 e la dipendenza `boolifyer`.

`AppLogger` ne ricalca l'interfaccia: `debug`/`info`/`warning`/`error`/`critical` più `exception`. I messaggi usano i segnaposto di `.format()` e il record arriva agli handler già formattato; il chiamante è attribuito correttamente (`stacklevel=3`). Gli altri componenti:

- `LogManager.configure()`: `RotatingFileHandler` da 1 MB × 3 sul logger `querylean`, con `SecretRedactor` applicato a ogni handler;
- `LogManager.register_secret()`: maschera un segreto nei log.

## Architettura

```
src/querylean/
  app/                 AppInfo (NAME, DISPLAY_NAME, AUTHOR, …, version()), VersionFile, BundleResources (percorsi nel bundle: `_MEIPASS` o radice), Application.run() (entry point, excepthook), SmokeTest
  log/                 AppLogger, LogManager, SecretRedactor
  config/              ConnectionConfig (anche name, display_name, all_databases, caution_databases), ConnectionProfile (id + config), ConnectionStore (connections/<id>.json),
                       UiPreferences, AppConfig (active_connection + ui), ConfigManager (config.json + migrazione; espone connections e bookmarks), ConfigError
  bookmarks/           QueryBookmark (nome, sql, target `user@host:port/database`, placeholders → maschera, last_values), BookmarkStore (bookmarks/<id connessione>.json, formato 2),
                       MaskTemplate (segnaposto `${NOME}`: analisi, compilazione, make_placeholder, candidates/make_placeholders), ValueCandidate, PlaceholderOccurrence, Placeholder, PlaceholderType, MaskError,
                       BookmarkEntry (connessione salvata + segnalibro), BookmarkExport (file JSON `querylean-bookmarks` per l'esportazione),
                       BookmarkImport (lettura non fidata del file esportato) → ImportedBookmark (segnalibro + motivo del rifiuto), BookmarkImportPlan (unione con i segnalibri salvati), NameConflict (RENAME/REPLACE/SKIP)
  completion/          SqlScanner/ScanToken (tokenizer tollerante), StatementAnalyzer → StatementContext (+ TableReference),
                       SchemaModel (tabelle/colonne della sessione), SqlVocabulary, CompletionEngine → CompletionResult/CompletionItem/CompletionKind
  files/               PrivateFile (sostituzione atomica di un file 0600: temporaneo + os.replace), PrivateJsonFile (JSON tramite PrivateFile)
  security/            SecretStore (astratta), KeyringSecretStore, SecretStorageError
  export/              ResultExporter (astratta: scrittura tramite PrivateFile) → XlsxExporter, CsvExporter, JsonExporter;
                       ResultExporters (elenco e ricerca per estensione/filtro), ExportReport, ExportError
  database/
    errors/            DatabaseError(message, kind), QueryCancelled, QueryTimeout, ErrorTranslator
    connection/        ConnectionParams (kwargs del driver, password mascherata, with_database), ConnectionManager (sessione READ ONLY verificata, controllo dei grant per database, use_database con COM_INIT_DB)
    privileges/        GrantAnalyzer (analisi fail-closed di SHOW GRANTS) → AccountPrivileges (GrantScope per grant: database/jolly e privilegi),
                       AccountCheck (database della connessione scrivibili, accettati, rifiutati)
    execution/         QueryExecutor (execute/cancel), QueryResult, DriverValue (testo dei valori del driver: bytes → UTF-8), PagedQuery (count e pagine di un risultato troncato)
    schema/            DatabaseCatalog (SHOW DATABASES), TableCatalog (SHOW FULL TABLES [FROM db] tramite QueryExecutor), TableInfo (database, reference, select_statement),
                       MySqlIdentifier (quoting con backtick), MySqlLiteral (stringhe con ' e \ escapati),
                       ColumnCatalog (information_schema.COLUMNS e SHOW FULL COLUMNS tramite QueryExecutor), ColumnInfo
    validation/        ReadOnlyValidator → stadi ValidationStage su ValidationContext;
                       MySqlLexer, SqlToken, LexedStatement, ReadOnlyRules, ValidationResult
  ui/
    main/              MainWindow, StopButton (Stop lampeggiante sotto i risultati, solo per query lunghe), ConnectionState, CautionPalette (sfondo rosa in modalità attenzione), ConnectionsMenu, BookmarksMenu ("Bookmarked queries": esecuzione, Delete, Export…, Import…) (menu "Connections": New connection…, Connect/Edit…/Delete… per connessione, Export/Import bookmarked queries…)
    dialogs/           ConnectionDialog, SaveMaskDialog (salvataggio di una maschera), FillMaskDialog (valori ed esecuzione di una maschera), MakePlaceholdersDialog (Ctrl+Shift+P senza selezione: scelta dei valori da trasformare), ExportBookmarksDialog (scelta dei segnalibri da esportare), ImportBookmarksDialog (segnalibri da importare, connessione e conflitti di nome), BookmarkChooser (filtro, Select all/none e BookmarkTable, la tabella con caselle, condivisi dai due), QueryPreview e StatusLabel (anteprima della query ed esito, condivisi dai dialog; `StatusLabel.HINT_STYLE` = colore dei suggerimenti), AboutDialog (versione/autore da AppInfo)
    icons/             ToolbarIcons, CompletionIcons (icone disegnate con QPainter: nessun asset da impacchettare)
    editor/            SqlEditor (autocompletamento), SqlCompleter (popup), CompletionDelegate, SqlHighlighter, LineNumberArea
    results/           ResultsTable (`show_rows`: righe di un'altra pagina), ResultsModel (`offset` per i numeri di riga), ResultsPager (« ‹ Page N of M › », "Counting the rows…", nascosto con una sola pagina), ValueFormatter
    sidebar/           TableSidebar (albero database → tabelle → colonne con filtro; database_selected → MainWindow.select_database; table_chosen → MainWindow.use_table, column_chosen → MainWindow.use_column, column_added → add_column)
    safe_text.py       SafeText (tooltip con testo non fidato: escape HTML; `one_line`: anteprima su una riga troncata con "…")
    worker/            DbWorker (QObject nel thread DB), DbThread (avvio/arresto), ExportThread (scrittura dell'export)
tests/                 test_<classe>.py; fakes/; support/; integration/
```

**Versione: la fonte unica è il file `.version`** nella radice del progetto (una sola riga). La versione va letta **sempre e solo** da lì, e non va mai scritta altrove, nemmeno come costante, in un default o in un commento con il numero.

**È VIETATO all'agente modificare, sovrascrivere, ricreare, rinominare o cancellare il file `.version`.**

- Il numero di versione lo decide e lo cambia solo l'utente.
- Il divieto vale anche se un test, una build o una richiesta sembrano richiederlo: in quel caso ci si ferma e si chiede.
- Il file si può solo leggere.

- **Runtime**: `AppInfo.version()` → `VersionFile.read()`. Dai sorgenti legge `<root>/.version`; nel pacchetto PyInstaller legge `sys._MEIPASS/.version`. Se il file manca o non è valido restituisce `VersionFile.UNKNOWN` e lo smoke test fallisce.
- **`pyproject.toml`**: `dynamic = ["version"]` con `[tool.setuptools.dynamic] version = { file = ".version" }`.
- **Build**: `build_*.sh` leggono `.version`; `querylean.spec` lo include nel pacchetto (`datas`) e lo usa per `CFBundleShortVersionString`.
- **Test**: `tests/test_app_info.py` verifica che la versione venga da `.version`. Fallisce se il numero di versione compare scritto in `src/`, `packaging/`, `pyproject.toml` o nei workflow.

`AppInfo.AUTHOR` deve coincidere con `authors` in `pyproject.toml`.

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
  - Al server si invia il **testo originale** (`ValidationResult.statement`), mai SQL rigenerato. Unica eccezione: le pagine (`PagedQuery`), che racchiudono il testo originale invariato e vengono validate di nuovo per intero.
  - Non sostituirlo con una ricerca di parole chiave nel testo.
  - Ogni nuova forma ammessa richiede test, sia di accettazione sia di rifiuto, in `tests/test_read_only_validator.py`.
- **Opzioni di connessione da mantenere** (`ConnectionParams.to_connect_kwargs`, `ConnectionManager`):
  - niente `MULTI_STATEMENTS`, niente `LOCAL_FILES`;
  - `use_pure=True`;
  - `SET SESSION TRANSACTION READ ONLY`;
  - rimozione di `NO_BACKSLASH_ESCAPES`, `ANSI_QUOTES` e `ANSI` dal `sql_mode`, poi rilettura fail-closed (`ConnectionManager.LEXER_MODES` ancora presenti o valore illeggibile = connessione chiusa, anche in modalità attenzione): con `ANSI_QUOTES` un testo che il validatore legge come stringa `"…"` potrebbe nascondere SQL.
- **Sola lettura**: la garanzia primaria è l'account MySQL con solo SELECT. L'app non deve mai creare utenti né modificare privilegi.
- **Parole vietate "a prescindere"** (scelta dell'utente, 1.4): le parole di `ReadOnlyRules.FORBIDDEN_WORDS` si rifiutano ovunque fuori da stringhe e commenti, anche qualificate (`t.update`) o come identificatori quotati (`` `delete` ``), quindi anche come nomi di colonna, tabella o alias. Uniche eccezioni: `SHOW CREATE` e le funzioni `REPLACE(`/`TRUNCATE(` (`FUNCTION_NAME_EXCEPTIONS`, solo senza quote né qualificazione). La gestione di campi e alias con questi nomi è rimandata: non aggiungere eccezioni senza richiesta.
- **Controllo della sessione e dell'account** (`ConnectionManager.__open`, a ogni connessione, test e riconnessione):
  - dopo il setup si rilegge `@@SESSION.transaction_read_only` (poi `tx_read_only`): se non vale 1 la connessione si chiude, **anche in modalità attenzione**; lo stesso per `@@SESSION.sql_mode` con `ANSI_QUOTES`/`NO_BACKSLASH_ESCAPES`;
  - `SHOW GRANTS` → `GrantAnalyzer`: sono di lettura solo `USAGE`, `SELECT`, `SHOW VIEW`, `SHOW DATABASES`; ruoli, righe sconosciute o errori rendono l'account non verificato (= scrivibile su **ogni** database). Non allargare l'elenco senza richiesta;
  - ogni grant diventa un `GrantScope`: database del grant (`db.*`, `db.tab`, `PROCEDURE db.x`) con i jolly MySQL `%`/`_` (escape `\`) confrontati senza distinzione di maiuscole, oppure `None` (= tutti) per `*.*`, `PROXY` e oggetti non riconducibili a un database. Nel dubbio il grant deve coprire **più** database, mai meno;
  - il perimetro è il database configurato oppure, con `all_databases`, quelli di `SHOW DATABASES` (lettura interna nel `__open`; se fallisce la connessione si chiude). `information_schema` non è mai scrivibile;
  - `AccountCheck`: ogni database scrivibile del perimetro non presente in `ConnectionConfig.caution_databases` fa rifiutare la connessione (`DatabaseError` kind `write_account`); `test_connection` non rifiuta ma restituisce il check, che la finestra usa per far accettare i database uno per uno;
  - nel log solo i nomi dei privilegi, mai le righe dei grant (su MariaDB contengono l'hash della password).
- **Modalità attenzione** (`ConnectionConfig.caution_databases`, per database; `caution_mode` è derivato e il vecchio flag delle connessioni ≤ 1.7 diventa il loro database): rilassa **solo** il controllo dell'account per i database accettati. Validatore, sessione READ ONLY e tutte le altre barriere restano identici. La GUI la segnala (`MainWindow.caution_active`, `CAUTION_LABEL` nello stato, titolo del menu con `ConnectionsMenu.CAUTION_TITLE`, sfondo della finestra tinto di rosa con `CautionPalette`: solo il ruolo `Window` della palette, mai editor e tabelle; si ripristina con `setPalette(QPalette())` quando la sessione non è più in attenzione).
- **Connessioni salvate**:
  - una connessione = un file `connections/<id>.json` (0600) scritto con `PrivateJsonFile`; `config.json` tiene solo `active_connection` e le preferenze;
  - un file illeggibile viene saltato (con log), non deve impedire il caricamento delle altre;
  - la migrazione del vecchio `config.json` a connessione singola avviene una sola volta e non tocca il portachiavi;
  - la password è indicizzata per account (`SecretStore.account_key`): si toglie dal portachiavi solo quando nessuna connessione salvata usa più quell'account.
- **Query nei segnalibri** (1.6):
  - un segnalibro appartiene a una connessione salvata (file `bookmarks/<id>.json`, 0600, scritto con `PrivateJsonFile`) **e** al suo target `user@host:port/database` (`QueryBookmark.target_of`);
  - il menu mostra solo i segnalibri della sessione aperta (`MainWindow.__session_id` + `session_target`, fissati in `__start_connect` con la config effettivamente usata);
  - l'esecuzione passa da `DbWorker.bookmark_requested`, che rifiuta (kind `bookmark_target`) se il target non coincide con `ConnectionManager.config`, poi dal normale `QueryExecutor` (validatore incluso). Non eseguire segnalibri con `query_requested`;
  - si salvano solo query accettate da `ReadOnlyValidator`; un file danneggiato non va mai sovrascritto (`ConfigError`);
  - eliminare una connessione elimina i suoi segnalibri.
- **Esportazione dei segnalibri** (1.11, `BookmarkExport`):
  - `MainWindow.export_bookmarks` elenca i segnalibri di **tutte** le connessioni salvate (target attuale di ciascuna, `bookmark_entries`), anche senza sessione; voci in **Connections** e in **Bookmarked queries**;
  - file scritto con `PrivateJsonFile` (0600, atomico) che contiene **solo query e maschere**, per condividerle con altri utenti che le eseguono sui propri server con le proprie credenziali: **nessun dato di connessione** (host, porta, utente, database, target, nome della connessione, id, password, impostazioni). La connessione nel dialog serve solo a scegliere; `last_values` solo se richiesto (casella disattivata come predefinito); segnalibri identici scritti una volta;
  - formato `{"format": "querylean-bookmarks", "format_version": 1, "exported_at", "exported_by", "bookmarks": [...]}`; ogni segnalibro ha le chiavi di `QueryBookmark.to_dict` senza `target` più `kind` (solo informativo). Una modifica incompatibile incrementa `FORMAT_VERSION`;
  - la lettura per l'import è `BookmarkImport` (vedi sotto).
- **Importazione dei segnalibri** (1.12, `BookmarkImport`, `MainWindow.import_bookmarks`):
  - il file è **non fidato**: `format` esatto, `format_version` intero tra 1 e `BookmarkExport.FORMAT_VERSION` (più recente = rifiutato), solo file regolari (una FIFO o un dispositivo bloccherebbero il thread GUI), al massimo `MAX_FILE_SIZE` (5 MB, letto senza superarlo) e `MAX_BOOKMARKS`; JSON illeggibile o troppo annidato = `ConfigError`;
  - ogni segnalibro si ricostruisce con `QueryBookmark.from_dict` dalle sole chiavi note (`name`, `sql`, `placeholders`, `last_values`): `kind`, chiavi sconosciute e un eventuale `target` nel file non si usano mai; il target è sempre quello attuale della connessione scelta nel dialog (`QueryBookmark.target_of`), mai un dato del file;
  - si importano solo query accettate da `ReadOnlyValidator` (le maschere compilate con i predefiniti, `BookmarkImport.refusal`), come al salvataggio; le righe rifiutate non hanno casella; `MainWindow.import_bookmarks_into` ricontrolla con il validatore prima di scrivere. L'esecuzione resta quella dei segnalibri (`bookmark_requested`, validatore);
  - `BookmarkStore.import_bookmarks` scrive una volta sola (nessuna scrittura se nulla cambia; un file danneggiato non si sovrascrive); i nomi già usati seguono `NameConflict` (predefinito `RENAME`, "nome (2)"), i segnalibri identici non si duplicano;
  - nomi, query e testi del file nei widget solo come testo semplice o tramite `SafeText`.
- **Maschere** (1.10):
  - un valore non diventa mai SQL: fuori dagli apici `PlaceholderType.literal` (numero controllato, `TRUE`/`FALSE` o `MySqlLiteral.quote`), dentro gli apici contenuto di stringa con escape di `\` e dell'apice; una lista è fatta di letterali dello stesso tipo separati da virgola. Niente segnaposto per nomi (backtick rifiutati) né per testo SQL libero; non aggiungere tipi "raw" senza richiesta;
  - `MaskTemplate` riconosce i segnaposto fuori dai commenti, nelle stringhe e fuori; un `${` malformato rende la query una maschera non valida (`MaskError`), mai SQL eseguibile;
  - si salva solo una maschera la cui compilazione con i predefiniti passa `ReadOnlyValidator`; i segnaposto salvati devono corrispondere esattamente a quelli del testo (`QueryBookmark.from_dict`, altrimenti il segnalibro si scarta);
  - **Run** rifiuta un testo con segnaposto (messaggio rosso più `MainWindow.placeholder_notice`, finestra aperta con `open()`, mai bloccante, testo in PlainText); dal menu una maschera apre `FillMaskDialog`: ogni valore è obbligatorio ("sempre compilato"), gli ultimi valori (`QueryBookmark.last_values`, salvati con `BookmarkStore.remember_values` solo dopo **Run**) sono gialli finché non cambiano, **Run** si attiva solo se la compilazione riesce e passa `ReadOnlyValidator`;
  - la query compilata si esegue come un segnalibro (`bookmark_requested` con il target della maschera, poi validatore), mai con `query_requested`; il nome si modifica nella stessa finestra e si applica (`BookmarkStore.rename`, mai su un nome già usato per lo stesso target) solo con **Run** o **Open in editor**; **Open in editor** carica la maschera senza eseguirla; un nuovo salvataggio con lo stesso nome conserva gli ultimi valori dei segnaposto rimasti.
- **Password**:
  - mai su file di configurazione, log o messaggi;
  - registrarla con `LogManager.register_secret()` appena è nota (in `MainWindow` lo fa `__remember_session`, usato da ogni percorso che riceve una password);
  - `ConnectionParams.__repr__` la maschera.
- **Thread**:
  - nessuna operazione di database nel thread GUI;
  - `ConnectionManager` va usato solo dal thread del worker, tranne `kill_running_query`;
  - una sola query attiva alla volta.
- **Limite di righe**:
  - va applicato durante il fetch: cursore non bufferizzato, `fetchmany` fino a `limit+1`;
  - se le righe sono troncate, `abort_session()`; la riconnessione è trasparente.
  - Il massimo è 10.000.
  - **Pagine** (scelta dell'utente, 1.12): solo se il risultato è troncato e la query è `SELECT`/`WITH` (`PagedQuery.is_pageable`), `MainWindow` chiede il conteggio (`count_requested`, `PagedQuery.count_statement`) e poi le pagine oltre la prima (`page_requested`, `PagedQuery.page_statement`, pagina = `row_limit` del risultato). Lo statement validato va **invariato** dentro una tabella derivata, chiuso su una riga a sé (un commento finale non può nascondere la parentesi); le istruzioni costruite passano **sempre** da `QueryExecutor` (validatore, timeout, limite di righe), mai SQL fuori dal validatore. Il worker le esegue solo se la sessione ha ancora il target della query (`DbWorker.PAGES_TARGET`); le pagine si scartano a ogni nuova query, cambio di database attivo o sessione non `CONNECTED`. Nessun cursore tenuto aperto tra una pagina e l'altra.
  - Sotto i risultati una sola riga: Stop, avanzamento, messaggio (`Running: …`/`Query executed: …`), righe · tempo · avviso del limite e, a destra, `ResultsPager`.
- **Export**:
  - esporta solo le righe già caricate (`MainWindow.__result`), senza rieseguire la query e senza superare il limite di righe;
  - il file si scrive in `ExportThread`, mai nel thread GUI;
  - la scrittura è atomica con permessi 0600 (`PrivateFile`: file temporaneo nella cartella di destinazione + `os.replace`);
  - in Excel il testo è sempre una cella stringa, mai una formula (`data_type = "s"`);
  - in tutti i formati i valori sono scritti senza perdite (`ValueFormatter.full_text`, non `format_value`).
- **Barra delle tabelle**:
  - l'elenco si legge con `TableCatalog` tramite `QueryExecutor` (validatore, timeout, limite di righe), nel thread del worker (`tables_requested` → `tables_loaded`/`tables_failed`), mai con SQL fuori dal validatore;
  - i nomi entrano nella query solo tramite `MySqlIdentifier.quote`;
  - un clic (ma anche doppio clic/`Invio`) sulla tabella sostituisce il testo dell'editor in modo annullabile (`SqlEditor.replace_query`, nessun nuovo passo se il testo è già quello) e non esegue la query; lo stesso clic espande la tabella e ne mostra le colonne, la sola freccia la espande senza toccare l'editor; doppio clic/`Invio` su una colonna sostituisce allo stesso modo il testo con `TableInfo.column_statement` (`SELECT `col` FROM `tab` LIMIT 1;`), senza eseguirla; con Shift (`column_added`) la colonna si aggiunge alla lista della query di anteprima riconosciuta da `TableInfo.selected_columns` (solo il formato scritto da `columns_statement`), altrimenti si riparte da `SELECT `col``;
  - le colonne si leggono con `ColumnCatalog` tramite `QueryExecutor`, nel thread del worker: tutte insieme alla connessione (`columns_requested`, una query su `information_schema.COLUMNS`, al massimo 10.000 righe; la tabella troncata si scarta), poi su richiesta tabella per tabella (`table_columns_requested`, `SHOW FULL COLUMNS FROM` con `MySqlIdentifier.quote`). `MainWindow.load_columns` evita richieste doppie; un errore memorizza le colonne come vuote (nessun nuovo tentativo fino al refresh o alla riconnessione);
  - `SchemaModel` vive in `MainWindow`, è condiviso da barra e autocompletamento (chiavi per database, `database` = database attivo) e si svuota quando la sessione non è più `CONNECTED`; le risposte arrivate dopo la chiusura vanno ignorate;
  - nei segnali del worker un database vuoto significa "il database predefinito della sessione" (connessione a database singolo, query non qualificate come prima); con `all_databases` si passa sempre il nome e `TableInfo.database` qualifica le anteprime (`` `db`.`tab` ``).
- **Tutti i database** (1.8):
  - il database attivo si cambia solo con `ConnectionManager.use_database` (`cmd_init_db`, comando di protocollo, mai SQL `USE`) e resta nelle riconnessioni (`ConnectionParams.with_database`); solo con `all_databases`;
  - la barra colora i database per accesso (`TableSidebar.set_write_access`: verde `READ_ONLY_COLOR`, rosa `WRITE_COLOR` + `ToolbarIcons.warning()` in colonna 1); `MainWindow` lo ricalcola a ogni elenco con `AccountCheck(check.privileges, databases)`, quindi vale anche per i database comparsi dopo la connessione; senza check (None) nessun colore;
  - il target dei segnalibri usa `ConnectionConfig.scope_label()` (`*` per tutti i database), quindi non dipende dal database attivo.
- **Autocompletamento** (1.7):
  - `Ctrl+Spazio` (su macOS il Control fisico, che Qt riporta come `MetaModifier`) apre le proposte; `Ctrl/Cmd+Invio` resta l'esecuzione e chiude l'elenco;
  - l'analisi usa `SqlScanner`, tollerante e separato dal lexer del validatore: non va mai usato per validare, e il validatore non va mai rilassato per l'autocompletamento;
  - non si propongono mai parole di `ReadOnlyRules.FORBIDDEN_WORDS` né funzioni vietate (`SqlVocabulary`); ogni nuova parola chiave o funzione proposta deve passare il validatore (`tests/test_sql_vocabulary.py`);
  - l'inserimento sostituisce la parola sotto il cursore in un solo passo annullabile; nessuna query viene eseguita dall'autocompletamento;
  - le colonne mancanti si chiedono con `SqlEditor.columns_needed` → `MainWindow.load_columns`; quando arrivano, `refresh_completion` aggiorna l'elenco.
- **Query rifiutate dal validatore** (kind `rejected`): oltre al messaggio rosso, `MainWindow.read_only_notice` (finestra aperta con `open()`, mai bloccante) spiega che si eseguono solo query di lettura; compare **solo** in quel caso, mai alla connessione (lì basta la tinta rosa della modalità attenzione).
- **Testo non fidato nei widget** (dati del server, query, nomi scritti dall'utente): mai interpretato come HTML.
  - Tooltip sempre tramite `SafeText.tooltip` (anche le celle della tabella risultati);
  - `QLabel` con testo variabile in `Qt.TextFormat.PlainText` (stato della barra, stato della finestra di connessione, messaggi); la riga di stato in rich text usa `html.escape`;
  - `QMessageBox` e etichette di `QInputDialog`: `setTextFormat(PlainText)`, oppure `SafeText.html` (escape **e** marcatura `<qt>`: il solo `html.escape` può essere preso per testo semplice e mostrare `&amp;`), usato da `MainWindow.__confirm`/`__warn` e `SqlEditor`.
- **Nomi dei database**: si usano esattamente come li restituisce il server (`DriverValue.text`, mai `strip`); `GrantScope.covers` confronta anche con gli spazi compattati, come le righe dei grant normalizzate da `GrantAnalyzer`.
- **Accettazione della modalità attenzione** nella finestra: cambiare host, porta, username, database o `all_databases` toglie la spunta a tutti i database (`__withdraw_acceptance`).
- **Errori**: all'utente solo messaggi comprensibili (`DatabaseError.message`), mai stack trace; i dettagli vanno nel log.
- **Tabella risultati**: non modificabile. NULL è mostrato come `NULL` in corsivo e si distingue da `""`. Nella copia TSV il NULL diventa una cella vuota.

## Dipendenze e test

- Dipendenza **PySide6-Essentials**, non `PySide6`: evita WebEngine e gli addon pesanti.
- `mysql-connector-python>=9.3`, necessario per `read_timeout`/`write_timeout`.
- `openpyxl` per l'export Excel. Lo spec esclude `numpy`, `pandas`, `PIL` e `lxml`, che openpyxl usa solo se installati.
- Nei test unitari il database è finto: `tests/fakes/` (`FakeConnector`, `FakeConnection`, `FakeCursor`), da iniettare con `ConnectionManager(connector)`.
  - Per simulare `KILL QUERY` si usa `FakeConnection.on_kill`.
  - I controlli di sessione rispondono da `FakeConnection.session_variables` e `FakeConnection.grants` (default: sessione READ ONLY, `sql_mode` senza modi di quoting e account con solo SELECT), senza passare dall'`handler`.
  - `SchemaHandler` risponde a `SHOW FULL TABLES [FROM db]` e alle due letture delle colonne (`tables`, `columns` per il database predefinito, `schemas` per gli altri, `error`, `columns_error`, `statements`).
  - `FakeConnection.databases` risponde a `SHOW DATABASES` (anche al controllo interno) e `cmd_init_db` registra i cambi di database in `init_db`.
  - Per il keyring ci sono `MemoryKeyring` e `LockedKeyring`.
- I test GUI estendono `support/main_window_test_base.MainWindowTestBase`, che fornisce le fixture `connector`/`window` e gli helper `configure`/`connect`/`run`. Vanno attesi con `qtbot.waitUntil`.
- **Non aggiungere funzionalità escluse** da `PROJECT.md` §16: multi-connessione, browser schemi, cronologia, autocomplete, plugin, telemetria, ecc. Eccezioni richieste dall'utente:
  - 1.1: esportazione in Excel, CSV e JSON; altre forme di esportazione restano escluse;
  - 1.2: barra laterale con l'elenco delle tabelle del database configurato, che prepara `SELECT * FROM <tabella> LIMIT 1;`. Niente indici o altri database, niente esecuzione automatica;
  - 1.3: più connessioni salvate (profili), ma **una sola connessione aperta alla volta**. Niente connessioni simultanee, schede o finestre multiple.
  - 1.4: modalità attenzione per account con privilegi di scrittura (sempre e solo query di lettura) e validatore più severo.
  - 1.6: query nei segnalibri per connessione (salva con nome, menu "Bookmarked queries" che le esegue). Niente cronologia automatica, cartelle o condivisione tra connessioni (esportazione e importazione da file sono arrivate con la 1.11 e la 1.12);
  - 1.7: colonne delle tabelle nella barra laterale (albero tabella → colonne, filtro, menu contestuale) e autocompletamento SQL nell'editor (tabelle, colonne, alias, parole chiave, funzioni). Niente indici, chiavi esterne, altri database, snippet o formattazione automatica del codice;
  - 1.8: connessione a tutti i database accessibili (albero database → tabelle → colonne, database attivo) e modalità attenzione accettata per singolo database. Niente connessioni simultanee né altri server;
  - 1.10: maschere (segnalibri con segnaposto tipizzati `${NOME}`, liste per `IN`, finestre Save mask e Run mask con gli ultimi valori usati). Niente cronologia dei valori oltre l'ultima esecuzione, né funzioni o espressioni come valori.
  - 1.11: esportazione dei segnalibri e delle maschere in un file JSON strutturato;
  - 1.12: importazione di quel file in una connessione salvata scelta dall'utente. Niente sincronizzazione, import da altri formati o da URL;
  - 1.12: pagine dei risultati troncati (conteggio e `LIMIT`/`OFFSET` su tabella derivata, vedi "Limite di righe"), nonostante PROJECT.md §8.1 escluda la paginazione remota.

## Packaging

- La build si fa con PyInstaller in modalità onedir (`packaging/querylean.spec`, entry `packaging/launcher.py` → `Application.run()`).
- Prodotti:
  - Linux AppImage (`build_linux_appimage.sh`, build su Ubuntu 22.04);
  - `.deb` per Ubuntu/Lubuntu 24.04 (`build_linux_deb.sh`, build su 24.04): bundle in `/opt/querylean`, lanciatore `/usr/bin/querylean`, versione Debian derivata da `.version`;
  - macOS `.app` + `.dmg` (`build_macos_dmg.sh`, firma ad-hoc, un'architettura per build).
- Gli script includono `packaging/common.sh` (versione da `.version`, funzione `querylean_pyinstaller`).
- **Dimensione**: `BundleSlimmer` (`packaging/bundle_slimmer.py`, usato dallo spec) toglie estensione C di mysql-connector, tema GTK3, traduzioni Qt e plugin Qt inutili; su Linux toglie anche le librerie di sistema orfane.
  - Prima di escludere altro, verifica che il modulo o la libreria non venga caricato a runtime.
  - Lo smoke test controlla `ssl`, `hashlib` e il backend Secret Service e scrive un file per ogni formato di export: un modulo critico che manca deve far fallire la CI.
  - Non aggiungere `--strip` né UPX.
- **Licenze di terze parti** (`packaging/third_party_licenses.py`, classe `ThirdPartyLicenses`, richiamata dallo spec dopo `BundleSlimmer`):
  - genera `licenses/THIRD_PARTY_LICENSES.txt` nel bundle, più lo zip dei sorgenti di mysql-connector-python (GPLv2 incluso solo come bytecode);
  - attribuisce ogni file del bundle al pacchetto Python, al pacchetto Ubuntu (`dpkg`) o all'interprete. Un file senza origine nota fa **fallire la build**: non aggirare l'errore, ma aggiungi l'origine o il testo della licenza;
  - `packaging/licenses/` contiene i testi ufficiali per i componenti che non li includono (LGPL-3.0, GPL-3.0, ICU 73, Apache-2.0). Non vanno modificati; se Qt aggiorna ICU, va aggiunto il testo della nuova versione;
  - il `.deb` collega il file in `/usr/share/doc/querylean/` e ha un `copyright` DEP-5; il DMG lo mette accanto all'app; la finestra About vi rimanda (`AboutDialog.third_party_html`);
  - nei pacchetti lo smoke test fallisce se il file manca.
- Le dipendenze del `.deb` (`Depends`) vanno ricavate dalle librerie che il bundle carica dal sistema (`readelf -d`, con `LC_ALL=C`), non scritte a intuito.
- **Librerie xcb**: su Linux `BundleSlimmer.check_required_libraries` fa fallire la build se mancano le librerie del plugin xcb di Qt (`REQUIRED_LINUX_LIBRARIES`). Vanno installate sulla macchina di build (in CI: `QT_XCB_PACKAGES`); non togliere il controllo.
- Il comando `querylean` installato da pip (`[project.gui-scripts]`) punta a `querylean.app.application:Application.run`; `tests/test_app_info.py` verifica che il riferimento sia valido.
- La CI è in `.github/workflows/ci.yml`. Parte su `main`, `release-*`, tag `v*` e pull request. Esegue lint e test (dipendenze `[dev,build]`) con MySQL 8 come service; costruisce AppImage, `.deb` (installato e rimosso con `apt`, smoke test con `/usr/bin/querylean`) e DMG arm64/x86_64, con smoke test su ciascuno. Sui tag `vX.Y.Z` il job `release` crea la release GitHub.

## Rilascio

Politica di rilascio decisa dall'utente:

1. Da `develop` si crea il branch `release-X.Y.Z`, con `X.Y.Z` = versione attuale senza `-dev`.
2. Nel branch si modifica `.version` (lo fa **l'utente**) e si pubblica il branch.
3. Si fa merge di `release-X.Y.Z` in `main` e si tagga `main` con `vX.Y.Z`, con un tag annotato creato **dopo** il merge. Il messaggio del tag ha sempre questo formato, con il riepilogo in inglese:

   ```
   QueryLean - Release X.Y.Z - <riepilogo sintetico delle nuove funzionalità / bugfix>
   ```

   Esempio: `git tag -a vX.Y.Z -m "QueryLean - Release X.Y.Z - Table side bar with a one-click preview query; the status line shows the executed query"`.
4. Sul tag la CI pubblica la release (pacchetti, licenze di terze parti, `SHA256SUMS`); il job verifica che il tag corrisponda a `.version`.

Le correzioni alla build durante un rilascio si fanno su `develop` e si portano nel branch `release-X.Y.Z` con un merge: il merge non tocca `.version` del branch di rilascio. Non creare, spostare o cancellare tag e non fare merge in `main` senza richiesta esplicita.
- Il pacchetto macOS non è ancora verificato: non dichiararlo compatibile finché la CI non passa.
