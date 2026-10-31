# QueryLean

Client desktop minimale per **eseguire query di sola lettura** su un database MySQL.
È ispirato a DBeaver, ma volutamente ridotto all'essenziale: una connessione, un editor
SQL e una tabella di risultati copiabili.

## Funzionalità

- Una sola connessione MySQL, configurabile dalla GUI. Si può testare la connessione prima di salvarla.
- La password è conservata nel portachiavi del sistema operativo, mai in chiaro.
- Editor SQL con:
  - numeri di riga;
  - evidenziazione di keyword, stringhe, numeri e commenti;
  - esecuzione con `Ctrl+Invio` (Linux) o `Cmd+Invio` (macOS).
- Sono ammesse solo istruzioni di lettura (`SELECT`, `WITH … SELECT`, `UNION`, `SHOW`, `DESCRIBE`/`DESC`, `EXPLAIN SELECT`). Ogni query passa da un validatore basato sul parsing.
- L'esecuzione avviene fuori dal thread della GUI, con indicatore di attività, pulsante **Interrompi** e timeout.
- Tabella dei risultati non modificabile:
  - `NULL` è distinto dalla stringa vuota;
  - colonne ridimensionabili;
  - copia di celle o righe in formato tabulato, incollabile in Excel e LibreOffice Calc.
- Il limite di righe (predefinito 1.000, massimo 10.000) è applicato durante il recupero dei dati.
- Dimensioni della finestra e del divisore vengono ricordate tra una sessione e l'altra.
- Nessuna telemetria, nessun servizio cloud, nessun database locale.

## Piattaforme supportate

| Piattaforma | Pacchetto | Stato |
| --- | --- | --- |
| Linux x86_64 (Ubuntu 22.04+ o equivalenti con glibc ≥ 2.35) | AppImage | Build e smoke test in CI |
| macOS Apple Silicon (arm64), macOS 12+ | `.dmg` | Build e smoke test in CI (runner `macos-14`) |
| macOS Intel (x86_64), macOS 12+ | `.dmg` | Build e smoke test in CI (runner `macos-15-intel`) |

La compatibilità macOS va considerata confermata solo quando la pipeline CI corrispondente ha esito positivo. Windows non è supportato.

## Stack tecnologico

| Componente | Scelta | Motivo |
| --- | --- | --- |
| Linguaggio | Python 3.11+ | Logica SQL semplice da mantenere |
| GUI | PySide6-Essentials (Qt 6) | GUI nativa su Linux e macOS. Il pacchetto *Essentials* esclude WebEngine e gli altri moduli non necessari, quindi i pacchetti sono più piccoli |
| Driver | mysql-connector-python (implementazione pure Python) | Non richiede un client MySQL installato. Consente il controllo di multi-statement e LOCAL INFILE |
| Parser SQL | sqlglot (dialetto MySQL) | Parser puro Python, usato come secondo livello del validatore |
| Segreti | keyring | Secret Service su Linux, Keychain su macOS |
| Packaging | PyInstaller → AppImage / `.app` + `.dmg` | L'utente finale non deve installare alcun runtime |
| Test | pytest, pytest-qt | |

## Installazione (utente finale)

- **Linux**: scarica `querylean-<versione>-x86_64.AppImage`, rendilo eseguibile (`chmod +x`) e avvialo. Se il sistema non ha FUSE 2 (`libfuse2`), puoi usare `./querylean-….AppImage --appimage-extract-and-run`.
- **macOS**: apri il `.dmg` e trascina *QueryLean* in *Applicazioni*. Il pacchetto non è firmato con un certificato Developer ID (vedi [Firma e notarizzazione](#firma-e-notarizzazione-macos)): al primo avvio usa *clic destro → Apri*, oppure esegui `xattr -dr com.apple.quarantine "/Applications/QueryLean.app"`.

### Requisiti di sistema

- **Linux**: un servizio di portachiavi compatibile con *Secret Service* (GNOME Keyring, KWallet ≥ 5.97 o KeePassXC con l'integrazione attiva) per salvare la password. Senza portachiavi l'applicazione funziona comunque, ma la password va reinserita a ogni avvio. Servono inoltre le librerie grafiche di base (`libegl1`, `libgl1`, `libxkbcommon0`, `libfontconfig1`), normalmente già presenti in un desktop Ubuntu.
- **macOS**: nessun requisito aggiuntivo; si usa il Portachiavi di sistema.

## Uso

1. **Configurazione**: compila host, porta, database, username, password e i timeout, poi usa **Test connessione** e **Salva configurazione**. Salvare non apre la connessione.
2. **Connetti**: lo stato passa da *Disconnesso* a *Connessione in corso* e poi a *Connesso* o *Errore di connessione*. Se la password non è nel portachiavi, viene richiesta.
3. Scrivi la query e premi **Esegui** oppure `Ctrl/Cmd+Invio`.
4. Seleziona celle o righe e premi `Ctrl/Cmd+C`. Il menu contestuale offre anche le varianti "con intestazioni" e "righe intere".

### Regole di esecuzione

- Se nell'editor c'è del testo selezionato, viene eseguita **solo la selezione**.
- Senza selezione viene eseguito **l'intero contenuto** dell'editor.
- Un editor vuoto (o con soli spazi) non esegue nulla.
- È ammessa **una sola istruzione**; un `;` finale è tollerato. Con più istruzioni la query viene rifiutata: per eseguirne una, selezionala.

### Copia

Le celle copiate sono separate da tabulazioni e le righe da a capo. La selezione viene copiata come rettangolo, e le celle non selezionate al suo interno restano vuote. Un `NULL` diventa una cella vuota, mentre tabulazioni e a capo dentro i valori diventano spazi, così la griglia resta allineata. I valori binari non UTF-8 sono mostrati in esadecimale (`0x…`, troncati a 64 byte).

### Impostazioni

| Impostazione | Predefinito | Intervallo |
| --- | --- | --- |
| Timeout connessione | 5 s | 1–3600 s |
| Timeout query | 30 s | 1–3600 s |
| Righe massime | 1000 | 1–10.000 |

## Sicurezza

### Sola lettura: due barriere

1. **Account MySQL con privilegi minimi (barriera principale).** L'applicazione presume che l'account abbia solo privilegi `SELECT`. Non tenta mai di creare utenti o di modificare permessi.
2. **Validatore applicativo (barriera aggiuntiva)**, in `src/querylean/database/readonly_validator.py`. È fail-closed: se una query non può essere classificata con certezza, viene rifiutata. Lavora su tre livelli:
   - **Lexer MySQL**: riconosce stringhe, identificatori e commenti con le regole del server. Rifiuta istruzioni multiple, commenti eseguibili `/*! … */`, hint `/*+ … */`, `--` non seguito da spazio (in MySQL non è un commento), assegnazioni `:=`, stringhe e commenti non chiusi.
   - **Parole e funzioni**: fuori da stringhe e commenti blocca le parole riservate di scrittura (`INSERT`, `UPDATE`, `DELETE`, `INTO`, `LOCK`, `CALL`, `LOAD`, …) e le funzioni con effetti collaterali (`GET_LOCK`, `LOAD_FILE`, …).
   - **Parser sqlglot**: richiede esattamente un'istruzione di un tipo ammesso, senza nodi di DML/DDL, `SELECT … INTO` o `FOR UPDATE`/`LOCK IN SHARE MODE`.

   Al server viene inviato il testo originale, mai SQL rigenerato.

Oltre a queste due barriere, la connessione:

- è aperta **senza** il flag `CLIENT_MULTI_STATEMENTS` e con `LOCAL INFILE` disabilitato;
- imposta `SET SESSION TRANSACTION READ ONLY`;
- rimuove `NO_BACKSLASH_ESCAPES` dal `sql_mode` di sessione, così il server interpreta le stringhe come il validatore.

> L'applicazione **non** promette una modalità read-only assoluta basata solo sulla GUI. Ad esempio, una funzione memorizzata (stored function) richiamata in una `SELECT` potrebbe modificare dati se l'account ne avesse i privilegi. Per questo il vincolo deve essere garantito dall'account MySQL.

### Predisporre un account MySQL di sola lettura

```sql
-- Da eseguire come amministratore. Sostituisci nome, host e password.
CREATE USER 'report_ro'@'%' IDENTIFIED BY 'una-password-robusta';

-- Solo SELECT, solo sul database necessario:
GRANT SELECT ON nome_database.* TO 'report_ro'@'%';

-- In alternativa, ancora più restrittivo: singole tabelle o viste dedicate
-- GRANT SELECT ON nome_database.vista_report TO 'report_ro'@'%';

-- Opzionale: limiti sulle risorse
ALTER USER 'report_ro'@'%' WITH MAX_USER_CONNECTIONS 3;
```

Raccomandazioni:

- Non concedere mai `ALL`, `SUPER`, `FILE`, `PROCESS`, `EXECUTE`, `CREATE ROUTINE` o privilegi globali (`*.*`).
- Restringi l'host (`'report_ro'@'10.0.0.%'`) quando possibile.
- Per limitare colonne o righe visibili, crea **viste dedicate** e concedi `SELECT` solo su quelle.
- Non usare `root` o account amministrativi. L'applicazione non ne richiede.

### Password

- È salvata nel portachiavi del sistema operativo con il servizio `querylean` e la chiave `utente@host:porta`. Su Linux si può verificare con `secret-tool search service querylean`.
- **Non** compare mai nel file di configurazione né nei log, che passano da un filtro di redazione.
- I backend di keyring in chiaro (`keyrings.alt`) o "fail" sono considerati non disponibili. In quel caso la password resta solo in memoria per la sessione.
- Se il portachiavi è bloccato o nega l'accesso, viene mostrato un messaggio e la password viene richiesta al momento della connessione.

### File locali

| File | Linux | macOS |
| --- | --- | --- |
| Configurazione (permessi 0600) | `~/.config/querylean/config.json` | `~/Library/Application Support/querylean/config.json` |
| Log (rotazione 1 MB × 3) | `~/.local/state/querylean/log/` | `~/Library/Logs/querylean/` |

Agli utenti non vengono mai mostrati stack trace: i dettagli tecnici finiscono nel log, senza segreti.

## Timeout e interruzione

- Il **timeout di connessione** è passato al driver (`connection_timeout`).
- Il **timeout di esecuzione** funziona così:
  - prima di ogni query viene impostato `MAX_EXECUTION_TIME` di sessione, che il server applica alle `SELECT`;
  - un watchdog lato client, scaduto il timeout più 2 secondi, invia `KILL QUERY` da una connessione separata. Questo copre anche `SHOW`/`EXPLAIN` e i server che non supportano `MAX_EXECUTION_TIME`, come MariaDB.
- **Interrompi** invia `KILL QUERY` sulla stessa connessione separata.
- Limiti noti:
  - `KILL QUERY` richiede che l'utente possa terminare le proprie query, cosa sempre consentita sulle proprie sessioni;
  - se il server non è raggiungibile, la richiesta di interruzione fallisce dopo il timeout di connessione. La GUI resta comunque reattiva perché la query gira in un thread separato;
  - una query su cui si può interrompere solo l'invio dei risultati può terminare con qualche istante di ritardo.
- **Limite di righe**: si leggono al massimo *N+1* righe con un cursore non bufferizzato. Se ne esistono altre, la sessione viene chiusa senza scaricare il resto del result set e riaperta in modo trasparente alla query successiva.

## Sviluppo

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"         # runtime + pytest, pytest-qt, ruff
python -m querylean      # avvio dai sorgenti
ruff check src tests
pytest                           # unit + GUI (offscreen); integrazione se configurata
```

Su Ubuntu servono `python3-venv` e, per i test GUI, le librerie elencate nei requisiti.

### Struttura

```
src/querylean/
  main.py                    avvio, logging, --smoke-test
  ui/                        finestra principale, dialog, editor, tabella, worker QThread
  database/                  connessione, esecuzione, validatore, traduzione errori
  config/                    configurazione JSON e portachiavi
  utils/logging_config.py    log ruotato con redazione dei segreti
tests/                       unit, GUI (pytest-qt), integration/
packaging/                   spec PyInstaller, script AppImage/DMG, desktop file, icona
.github/workflows/ci.yml     lint, test, build degli artefatti
```

### Test d'integrazione

Sono test non distruttivi contro un database di test dedicato, mai contro database reali.

```bash
sudo mysql < tests/integration/setup_test_db.sql   # crea querylean_test e l'utente querylean_ro (solo SELECT)
QUERYLEAN_TEST_HOST=127.0.0.1 QUERYLEAN_TEST_USER=querylean_ro QUERYLEAN_TEST_PASSWORD=querylean_ro_password \
QUERYLEAN_TEST_DATABASE=querylean_test pytest tests/integration -v
```

Verificano query consentite, tipi e `NULL`, limite di righe, timeout, interruzione, rifiuto delle scritture da parte del validatore e, bypassando il validatore, il blocco lato server (privilegi e sessione READ ONLY). Senza le variabili `QUERYLEAN_TEST_*` vengono saltati. In CI usano un service container `mysql:8.0`.

## Packaging

Le build vanno eseguite sulla piattaforma di destinazione: PyInstaller non fa cross-compilazione.

### Linux (AppImage)

```bash
pip install -e ".[build]"
packaging/build_linux_appimage.sh     # → dist/querylean-<ver>-x86_64.AppImage
```

Lo script scarica `appimagetool` (versione fissata nello script). Senza FUSE usa `APPIMAGE_EXTRACT_AND_RUN=1`. Per la massima compatibilità, conviene fare la build sulla distribuzione più vecchia da supportare (Ubuntu 22.04).

### macOS (.app + .dmg)

```bash
pip install -e ".[build]"
packaging/build_macos_dmg.sh          # → dist/querylean-<ver>-<arch>.dmg
```

L'architettura è quella dell'interprete Python usato. Si ottengono quindi due build separate: arm64 su Apple Silicon e x86_64 su Intel.

#### Firma e notarizzazione (macOS)

Lo script applica una firma *ad-hoc*, sufficiente per i test locali. Per distribuire senza avvisi di Gatekeeper servono un account Apple Developer e un certificato *Developer ID Application*:

```bash
CODESIGN_IDENTITY="Developer ID Application: Nome (TEAMID)" packaging/build_macos_dmg.sh
xcrun notarytool submit dist/querylean-*.dmg --apple-id … --team-id … --password … --wait
xcrun stapler staple dist/querylean-*.dmg
```

Per una firma valida ai fini della notarizzazione serve anche l'hardened runtime (`codesign --options runtime`). Senza certificato il pacchetto funziona, ma l'utente deve autorizzarlo manualmente (vedi Installazione).

### CI/CD

`.github/workflows/ci.yml` esegue questi passi:

- `ruff`;
- test unitari, GUI e integrazione su Ubuntu 22.04 con MySQL 8 in un service container;
- build dell'AppImage e dei DMG arm64 e x86_64, ciascuna con smoke test (`--smoke-test`) del binario;
- pubblicazione dei pacchetti come artefatti della build.

## Limiti della versione 0.1

- Una sola connessione e una sola query alla volta, una sola istruzione per esecuzione.
- Non sono supportati: TLS/SSH tunnel configurabili da GUI, autocompletamento, cronologia, esportazione CSV/Excel, paginazione.
- `SHOW` è ammesso solo nelle forme riconosciute dal parser; le altre vengono rifiutate.
- Le parole riservate di scrittura usate come nomi di colonna devono essere quotate (`` `update` ``) o qualificate (`t.update`), come richiede MySQL.
- Sequenze `--` non seguite da spazio fuori dalle stringhe (es. `1--1`) vengono rifiutate per evitare ambiguità con i commenti: scrivi `1 - -1`.
- Il supporto a MariaDB non è garantito: `MAX_EXECUTION_TIME` non esiste e si usa solo il watchdog.
