# QueryLean

*[English](README.md) · Italiano*

Client desktop minimale per **eseguire query di sola lettura** su un database MySQL.
È ispirato a DBeaver, ma volutamente ridotto all'essenziale: connessioni salvate, una alla
volta, un editor SQL e una tabella di risultati copiabili.

## Funzionalità

- Più connessioni MySQL salvate, ciascuna con un nome facoltativo, gestite dal menu **Connections** (Connessioni). Se ne usa una alla volta e si può testare la connessione prima di salvarla.
- La password è conservata nel portachiavi del sistema operativo, mai in chiaro.
- Editor SQL con:
  - numeri di riga;
  - evidenziazione di keyword, stringhe, numeri e commenti;
  - esecuzione con `Ctrl+Invio` (Linux) o `Cmd+Invio` (macOS).
- Barra laterale con le tabelle e le viste del database a cui si ha accesso: un clic su una tabella prepara nell'editor `SELECT * FROM <tabella> LIMIT 1;`.
- Sono ammesse solo istruzioni di lettura (`SELECT`, `WITH … SELECT`, `UNION`, `SHOW`, `DESCRIBE`/`DESC`, `EXPLAIN SELECT`). Ogni query passa da un validatore basato sul parsing.
- Alla connessione vengono controllati i privilegi dell'account: un account che può modificare i dati viene rifiutato, a meno che la connessione sia in [modalità attenzione](#modalità-attenzione).
- L'esecuzione avviene fuori dal thread della GUI, con indicatore di attività, pulsante **Stop** (Interrompi) e timeout.
- Tabella dei risultati non modificabile:
  - `NULL` è distinto dalla stringa vuota;
  - colonne ridimensionabili;
  - copia di celle o righe in formato tabulato, incollabile in Excel e LibreOffice Calc;
  - esportazione del risultato in Excel (`.xlsx`), CSV o JSON.
- Il limite di righe (predefinito 1.000, massimo 10.000) è applicato durante il recupero dei dati.
- Dimensioni della finestra, del divisore e della barra laterale vengono ricordate tra una sessione e l'altra.
- Nessuna telemetria, nessun servizio cloud, nessun database locale.

## Piattaforme supportate

| Piattaforma | Pacchetto | Stato |
| --- | --- | --- |
| Linux x86_64 (Ubuntu 22.04+ o equivalenti con glibc ≥ 2.35) | AppImage | Build e smoke test in CI |
| macOS Apple Silicon (arm64), macOS 12+ | `.dmg` | Build e smoke test in CI (runner `macos-15`) |
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
| Export Excel | openpyxl | Scrive file `.xlsx` senza Excel né LibreOffice; puro Python, licenza MIT |
| Packaging | PyInstaller → AppImage / `.deb` / `.app` + `.dmg` | L'utente finale non deve installare alcun runtime |
| Test | pytest, pytest-qt | |

## Installazione (utente finale)

- **Ubuntu/Lubuntu 24.04 (`.deb`)**: `sudo apt install ./querylean-<versione>-amd64.deb`. QueryLean compare nel menu delle applicazioni (sezione Sviluppo) e si avvia anche da terminale con `querylean`. Si rimuove con `sudo apt remove querylean`.
- **Linux (AppImage)**: scarica `querylean-<versione>-x86_64.AppImage`, rendilo eseguibile (`chmod +x`) e avvialo. Serve FUSE 2: su Ubuntu/Lubuntu 24.04 il pacchetto è `libfuse2t64`, su 22.04 `libfuse2`. In alternativa usa `./querylean-….AppImage --appimage-extract-and-run`.
- **macOS**: apri il `.dmg` e trascina *QueryLean* in *Applicazioni*. Il pacchetto non è firmato con un certificato Developer ID (vedi [Firma e notarizzazione](#firma-e-notarizzazione-macos)): al primo avvio usa *clic destro → Apri*, oppure esegui `xattr -dr com.apple.quarantine "/Applications/QueryLean.app"`.

### Requisiti di sistema

- **Linux**: un servizio di portachiavi compatibile con *Secret Service* (GNOME Keyring, KWallet ≥ 5.97 o KeePassXC con l'integrazione attiva) per salvare la password. Senza portachiavi l'applicazione funziona comunque, ma la password va reinserita a ogni avvio. Servono inoltre le librerie grafiche di base (`libegl1`, `libgl1`, `libxkbcommon0`, `libfontconfig1`), normalmente già presenti in un desktop Ubuntu.
- **macOS**: nessun requisito aggiuntivo; si usa il Portachiavi di sistema.

## Uso

La barra in alto contiene, nell'ordine: **Run** (Esegui, ▶), **Stop** (Interrompi, attivo solo durante l'esecuzione), **Export** (Esporta, menu a tendina, attivo quando c'è un risultato), **Connect**/**Disconnect** (Connetti/Disconnetti), **Connections** (Connessioni, menu a tendina) e **About** (Informazioni: versione, autore, licenza). Lo stato della connessione è in basso a destra. L'interfaccia è in inglese. A sinistra, per tutta l'altezza della finestra, c'è la barra **Tables** (Tabelle).

1. **Connections** → **New connection…** (Connessioni → Nuova connessione…): compila nome (facoltativo), host, porta, database, username, password e i timeout, poi usa **Test connection** (Test connessione) e **Save** (Salva). Salvare non apre la connessione (vedi [Connessioni](#connessioni)).
2. **Connect** apre la connessione attiva, quella con la spunta nel menu **Connections**: lo stato passa da *Disconnected* (Disconnesso) a *Connecting* (Connessione in corso) e poi a *Connected* (Connesso) o *Connection error* (Errore di connessione). Se la password non è nel portachiavi, viene richiesta.
3. Scrivi la query e premi **Run** oppure `Ctrl/Cmd+Invio`. In alternativa scegli una tabella nella barra laterale (vedi [Barra delle tabelle](#barra-delle-tabelle)). Sotto i risultati compaiono righe e tempo, poi "Query executed:" (Query eseguita:) seguito dalla query appena eseguita, su una riga. Oltre i 160 caratteri la query è troncata con "…"; il testo completo è nel tooltip del messaggio.
4. Seleziona celle o righe e premi `Ctrl/Cmd+C`. Il menu contestuale offre anche le varianti "con intestazioni" e "righe intere".
5. Per salvare il risultato su file apri il menu **Export** e scegli il formato (vedi [Esportazione](#esportazione)).

### Connessioni

Il pulsante **Connections** (Connessioni) apre un menu con **New connection…** (Nuova connessione…) e, sotto, le connessioni salvate in ordine alfabetico. Ogni connessione è mostrata con il suo nome oppure, se il nome è vuoto, come `<utente>@<host>/<database>`. La connessione attiva ha la spunta.

Ogni voce ha un sottomenu:

- **Connect** (Connetti): la rende attiva e si connette. Se si è già connessi a un'altra, quella viene chiusa prima.
- **Edit…** (Modifica…): apre la finestra di compilazione con i valori salvati. Se è la connessione in uso, le modifiche valgono dalla prossima connessione.
- **Delete…** (Elimina…): chiede conferma, poi cancella il file della connessione. Se è quella in uso, la chiude.

Il pulsante **Connect** (Connetti) della barra usa la connessione attiva; se non ne esiste nessuna, apre **New connection…**. Una connessione appena salvata diventa attiva se in quel momento non si è connessi.

Ogni connessione è un file JSON a sé (vedi [File locali](#file-locali)) e non contiene mai la password.

Una connessione con la **Caution mode** (modalità attenzione) attiva compare nel menu come "<nome> (caution mode)" (vedi [Modalità attenzione](#modalità-attenzione)).

### Barra delle tabelle

Dopo la connessione la barra **Tables** (Tabelle) elenca tabelle e viste del database configurato (`SHOW FULL TABLES`), cioè solo quelle a cui l'account ha accesso. Le viste sono in corsivo e in fondo c'è il numero di elementi.

- Un clic su una voce, oppure `Invio` sulla voce selezionata, sostituisce il contenuto dell'editor con `SELECT * FROM <tabella> LIMIT 1;`. La query **non viene eseguita**: premi **Run** per lanciarla. Il testo precedente si recupera con `Ctrl/Cmd+Z`.
- Il nome della tabella è sempre tra backtick, con gli eventuali backtick interni raddoppiati, quindi funzionano anche nomi con spazi o parole riservate.
- Il pulsante ⟳ ricarica l'elenco, per esempio dopo la creazione di una tabella. Alla disconnessione l'elenco si svuota.
- La lettura dell'elenco passa dal validatore, rispetta il timeout delle query e mostra al massimo 10.000 voci. Un errore (per esempio permessi insufficienti) viene mostrato nella barra, senza chiudere la connessione.

### Regole di esecuzione

- Se nell'editor c'è del testo selezionato, viene eseguita **solo la selezione**.
- Senza selezione viene eseguito **l'intero contenuto** dell'editor.
- Un editor vuoto (o con soli spazi) non esegue nulla.
- È ammessa **una sola istruzione**; un `;` finale è tollerato. Con più istruzioni la query viene rifiutata: per eseguirne una, selezionala.

### Copia

Le celle copiate sono separate da tabulazioni e le righe da a capo. La selezione viene copiata come rettangolo, e le celle non selezionate al suo interno restano vuote. Un `NULL` diventa una cella vuota, mentre tabulazioni e a capo dentro i valori diventano spazi, così la griglia resta allineata. I valori binari non UTF-8 sono mostrati in esadecimale (`0x…`, troncati a 64 byte).

### Esportazione

**Export** (Esporta) salva su file il risultato mostrato nella tabella, con le intestazioni delle colonne. Il pulsante apre un menu:

- **Excel (.xlsx)**, **CSV (.csv)**, **JSON (.json)**: la finestra di salvataggio propone solo quel formato. Se il nome non ha la sua estensione, viene aggiunta.
- **Export…** (Esporta…): la finestra di salvataggio propone tutti i formati. Decide l'estensione del nome (`.xlsx`, `.csv`, `.json`) oppure, se manca, il formato selezionato nella finestra.

- Si esportano **le righe già caricate**, cioè al massimo il limite di righe impostato: la query non viene rieseguita. Se il risultato era troncato, il messaggio finale lo ricorda.
- Il file viene scritto in un thread separato, quindi la finestra resta utilizzabile. Lo si scrive prima in un file temporaneo nella stessa cartella, poi lo si rinomina: un file esistente viene sostituito solo da un'esportazione completa.
- Il file è leggibile solo dal tuo utente (permessi `0600`), perché può contenere dati riservati.
- L'esportazione resta possibile anche dopo la disconnessione.

| Formato | Contenuto |
| --- | --- |
| Excel (`.xlsx`) | Un foglio "Result" con la riga di intestazione in grassetto e bloccata. Numeri, booleani, date e date-ora sono valori nativi di Excel. Il testo non diventa mai una formula, anche se inizia con `=`. Restano testo i valori che Excel altererebbe: interi e DECIMAL con più di 15 cifre significative, date anteriori al 1900, valori `TIME`. `NULL` e stringa vuota sono entrambi celle vuote. I caratteri di controllo non ammessi da Excel diventano `�`; le celle oltre 32.767 caratteri vengono troncate e il messaggio finale le conta |
| CSV (`.csv`) | UTF-8, separatore virgola, riga di intestazione. I campi sono tra virgolette solo quando serve, e gli a capo dentro i valori restano. `NULL` diventa un campo vuoto, come nella copia |
| JSON (`.json`) | UTF-8, un array con un oggetto per riga, con chiave il nome della colonna. `NULL` diventa `null`, mentre interi, numeri a virgola mobile e booleani restano numeri e booleani. I DECIMAL diventano stringhe, per non perdere cifre. I nomi di colonna ripetuti ricevono un suffisso (`id`, `id_2`) |

In tutti i formati i valori binari sono scritti per intero (testo UTF-8 o esadecimale `0x…`, senza il troncamento a 64 byte della tabella), le date in formato ISO e i `TIME` come `hh:mm:ss[.ffffff]`.

### Impostazioni

| Impostazione | Predefinito | Intervallo |
| --- | --- | --- |
| Timeout connessione | 5 s | 1–3600 s |
| Timeout query | 30 s | 1–3600 s |
| Righe massime | 1000 | 1–10.000 |

## Sicurezza

### Sola lettura: due barriere

1. **Account MySQL con privilegi minimi (barriera principale).** A ogni connessione l'applicazione legge i privilegi dell'account con `SHOW GRANTS` e rifiuta la connessione se l'account non è dimostrabilmente di sola lettura (vedi [Controllo dei privilegi](#controllo-dei-privilegi)). Non tenta mai di creare utenti o di modificare permessi.
2. **Validatore applicativo (barriera aggiuntiva)**, in `src/querylean/database/validation/` (`ReadOnlyValidator`). È fail-closed: se una query non può essere classificata con certezza, viene rifiutata. Lavora su tre livelli:
   - **Lexer MySQL**: riconosce stringhe, identificatori e commenti con le regole del server. Rifiuta istruzioni multiple, commenti eseguibili `/*! … */`, hint `/*+ … */`, `--` non seguito da spazio (in MySQL non è un commento), assegnazioni `:=`, stringhe e commenti non chiusi.
   - **Parole e funzioni**: fuori da stringhe e commenti blocca le parole delle istruzioni di scrittura, modifica e amministrazione (`INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `TRUNCATE`, `CREATE`, `DROP`, `ALTER`, `GRANT`, `INTO`, `LOCK`, `CALL`, `LOAD`, `PREPARE`, `EXECUTE`, `COMMIT`, `FLUSH`, `KILL`, …) ovunque compaiano: senza quote, qualificate (`t.update`) o come identificatori quotati (`` `delete` ``). Sono ammesse solo `REPLACE(…)` e `TRUNCATE(…)`, come funzioni di sola lettura. Blocca anche le funzioni con effetti collaterali (`GET_LOCK`, `LOAD_FILE`, …).
   - **Parser sqlglot**: richiede esattamente un'istruzione di un tipo ammesso, senza nodi di DML/DDL, `SELECT … INTO` o `FOR UPDATE`/`LOCK IN SHARE MODE`.

   Al server viene inviato il testo originale, mai SQL rigenerato.

Oltre a queste due barriere, la connessione:

- è aperta **senza** il flag `CLIENT_MULTI_STATEMENTS` e con `LOCAL INFILE` disabilitato;
- imposta `SET SESSION TRANSACTION READ ONLY` e rilegge `@@SESSION.transaction_read_only` (`tx_read_only` sui server meno recenti): se il server non conferma una sessione di sola lettura, la connessione viene chiusa;
- rimuove `NO_BACKSLASH_ESCAPES` dal `sql_mode` di sessione, così il server interpreta le stringhe come il validatore.

> L'applicazione **non** promette una modalità read-only assoluta basata solo sulla GUI. Ad esempio, una funzione memorizzata (stored function) richiamata in una `SELECT` potrebbe modificare dati se l'account ne avesse i privilegi (la sessione READ ONLY blocca le scritture sulle tabelle permanenti, non su quelle temporanee). Per questo il vincolo deve essere garantito dall'account MySQL.

### Controllo dei privilegi

A ogni connessione, compresi **Test connection** (Test connessione) e le riconnessioni trasparenti, l'applicazione esegue `SHOW GRANTS` e ne analizza il risultato in modo fail-closed:

- i privilegi di lettura sono solo `USAGE`, `SELECT`, `SHOW VIEW` e `SHOW DATABASES`; qualsiasi altro privilegio (`INSERT`, `ALL PRIVILEGES`, `EXECUTE`, `PROXY`, `WITH GRANT OPTION`, privilegi dinamici come `BACKUP_ADMIN`, …) rende l'account "con privilegi di scrittura";
- i privilegi su colonne (`UPDATE (col)`) contano come gli altri;
- l'assegnazione di ruoli (`` GRANT `ruolo` TO … ``), righe non riconosciute o un errore di `SHOW GRANTS` rendono l'account "non verificato", e viene trattato come uno con privilegi di scrittura;
- le righe `REVOKE` (revoche parziali) tolgono soltanto privilegi e vengono ignorate.

Un account che non è di sola lettura viene rifiutato con un messaggio che elenca i privilegi trovati. Nel log finiscono solo i nomi dei privilegi, mai le righe dei grant (su MariaDB possono contenere l'hash della password).

### Modalità attenzione

La **Caution mode** (modalità attenzione) è un'opzione di ogni connessione, nella finestra **New connection…**/**Edit…** ("Caution mode: allow an account with write privileges"). Se è attiva:

- viene accettato un account con privilegi di scrittura o con privilegi non verificabili;
- **non cambia nient'altro**: vale lo stesso validatore (solo query di lettura) e la sessione deve essere confermata READ ONLY, altrimenti la connessione viene chiusa;
- mentre si è connessi con un account di questo tipo, lo stato in basso a destra mostra in rosso "CAUTION: account with write privileges" (ATTENZIONE: account con privilegi di scrittura) e il messaggio di connessione elenca i privilegi trovati;
- per tutta la sessione le parti grigie della finestra (sfondo di barra degli strumenti, barra laterale e barra di stato, margini) diventano rosa, come promemoria costante che l'account non è di sola lettura; editor e tabelle mantengono i loro colori. La tinta segue il tema del sistema (rosa tenue con i temi chiari, rosa scuro con quelli scuri) e sparisce alla disconnessione;
- **Test connection** segnala i privilegi trovati.

Con un account di sola lettura la modalità attenzione non ha effetti visibili. Va usata solo quando non è disponibile un account con il solo `SELECT`.

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
- La chiave è quella dell'account MySQL, non della connessione: più connessioni allo stesso account (per esempio su database diversi) condividono la password. Quando si elimina l'ultima connessione che usa un account, la sua password viene tolta dal portachiavi.
- Si legge dal portachiavi solo quando serve, cioè alla connessione o alla modifica.
- **Non** compare mai nei file di configurazione o delle connessioni, né nei log, che passano da un filtro di redazione.
- I backend di keyring in chiaro (`keyrings.alt`) o "fail" sono considerati non disponibili. In quel caso la password resta solo in memoria per la sessione.
- Se il portachiavi è bloccato o nega l'accesso, viene mostrato un messaggio e la password viene richiesta al momento della connessione.

### File locali

| File | Linux | macOS |
| --- | --- | --- |
| Configurazione: connessione attiva, finestra (permessi 0600) | `~/.config/querylean/config.json` | `~/Library/Application Support/querylean/config.json` |
| Connessioni salvate, un file `<id>.json` ciascuna (permessi 0600) | `~/.config/querylean/connections/` | `~/Library/Application Support/querylean/connections/` |
| Log (rotazione 1 MB × 3) | `~/.local/state/querylean/log/` | `~/Library/Logs/querylean/` |

Le versioni fino alla 1.2 avevano una sola connessione dentro `config.json`. Al primo avvio della nuova versione viene salvata come prima connessione, e la sua password nel portachiavi resta valida.

Agli utenti non vengono mai mostrati stack trace: i dettagli tecnici finiscono nel log, senza segreti.

## Timeout e interruzione

- Il **timeout di connessione** è passato al driver (`connection_timeout`).
- Il **timeout di esecuzione** funziona così:
  - prima di ogni query viene impostato `MAX_EXECUTION_TIME` di sessione, che il server applica alle `SELECT`;
  - un watchdog lato client, scaduto il timeout più 2 secondi, invia `KILL QUERY` da una connessione separata. Questo copre anche `SHOW`/`EXPLAIN` e i server che non supportano `MAX_EXECUTION_TIME`, come MariaDB.
- **Stop** invia `KILL QUERY` sulla stessa connessione separata.
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
ruff check src tests packaging   # lint, righe di massimo 80 colonne
ruff format src tests packaging  # formattazione
pytest                           # unit + GUI (offscreen); integrazione se configurata
```

Su Ubuntu servono `python3-venv` e, per i test GUI, le librerie elencate nei requisiti.

### Struttura

Ogni file contiene una sola classe; le regole di stile complete sono in `CLAUDE.md`.

```
src/querylean/
  app/          avvio (Application), metadati (AppInfo), smoke test
  log/          logger dell'applicazione, log ruotato, redazione dei segreti
  config/       modello della configurazione e persistenza JSON
  security/     password nel portachiavi (SecretStore astratta, KeyringSecretStore)
  export/       esportazione Excel/CSV/JSON (ResultExporter astratta)
  database/     errors/, connection/, execution/, schema/ (elenco tabelle), privileges/ (controllo SHOW GRANTS), validation/ (validatore a stadi)
  ui/           main/, dialogs/, editor/, icons/, results/, sidebar/, worker/ (thread QThread)
tests/          una classe Test… per file; fakes/ (doppioni), support/ (basi), integration/
packaging/      spec PyInstaller, script AppImage/.deb/DMG, desktop file, icona,
                generatore delle licenze di terzi, licenses/ (testi delle licenze)
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

### Versione

La versione di QueryLean si legge **solo** dal file `.version` nella radice del progetto (una sola riga). Per cambiarla basta modificare quel file. Lo leggono:

- `pyproject.toml`, come versione dinamica;
- gli script di build, per il nome degli artefatti;
- lo spec PyInstaller, che lo include nel pacchetto e lo usa per `Info.plist` su macOS;
- l'applicazione a runtime, per la finestra **About** e il log.

Dopo una modifica, dai sorgenti va rieseguito `pip install -e .` perché anche i metadati del pacchetto riportino la nuova versione.

Gli script condividono `packaging/common.sh`, che legge la versione da `.version` ed esegue PyInstaller. Con `PYTHON=.venv/bin/python` si sceglie l'interprete.

### Dimensione dei pacchetti

Lo spec (`BundleSlimmer`, in `packaging/bundle_slimmer.py`) toglie dal bundle quello che QueryLean non carica mai:

| Rimosso | Motivo | Risparmio indicativo (bundle Linux) |
|---|---|---|
| Estensione C di mysql-connector (`_mysql_connector` e la sua copia di OpenSSL) | si usa sempre `use_pure=True`; il modulo `ssl` di Python usa la OpenSSL di sistema inclusa nel bundle, più piccola | ~28 MB |
| Tema GTK3 di Qt e le librerie che trascina (GTK, cairo, pango, ATK, …) | non serve: senza, Qt usa il proprio stile | ~20 MB |
| Traduzioni di Qt | l'app non installa un `QTranslator` | ~7 MB |
| Plugin Qt per sistemi embedded o remoti (EGLFS, linuxfb, VNC, evdev, …), formati immagine diversi da SVG, `QtNetwork`, `QtDBus` Python | mai usati da un'app desktop | ~6 MB |
| setuptools e pkg_resources | strumenti di build | ~1 MB |
| Su macOS: secretstorage, jeepney, cryptography | servono solo al portachiavi Linux | ~14 MB |

Su Linux, dopo il filtro, le librerie di sistema che nessun binario rimasto usa più vengono eliminate in automatico (`readelf -d`).

Risultato su Linux x86_64: bundle da 191 a 133 MB, AppImage da 70 a 50 MB, `.deb` da 54 a 39 MB. L'export Excel (openpyxl) aggiunge circa 0,5 MB.

`numpy`, `pandas`, `PIL` e `lxml`, che openpyxl usa solo se presenti, sono esclusi dal bundle.

Cosa resta e perché:

- **ICU (~38 MB)**: è richiesta da `libQt6Core` e non si può togliere né sostituire con quella di sistema (Ubuntu 24.04 ha una versione diversa).
- **cryptography (~14 MB, solo Linux)**: è richiesta da `secretstorage` per il portachiavi.
- **Qt Core/Gui/Widgets, Python, OpenSSL**: indispensabili.
- **Strip dei simboli**: risparmierebbe solo ~3% e invaliderebbe la firma su macOS, quindi non è attivo.

Lo smoke test verifica che `ssl`, `hashlib` e, su Linux, il backend Secret Service siano presenti nel pacchetto, e scrive un file di prova in ogni formato di esportazione. Così un'esclusione di troppo fa fallire la CI invece di disattivare in silenzio TLS o il portachiavi.

### Licenze di terze parti

Ogni pacchetto contiene anche i componenti di terze parti che include (Qt, PySide6, Python, mysql-connector-python, ICU, OpenSSL, le librerie di sistema di Ubuntu e i pacchetti Python). Durante la build, `packaging/third_party_licenses.py`, richiamato dallo spec, genera `licenses/THIRD_PARTY_LICENSES.txt` dentro il bundle:

- **Attribuzione:** ogni file del bundle viene attribuito alla sua origine e da lì si prende la licenza:
  - il pacchetto Python che lo ha installato (file di licenza nel `dist-info`);
  - su Linux, il pacchetto Ubuntu che lo possiede (`dpkg`, file `/usr/share/doc/<pacchetto>/copyright`);
  - l'interprete Python (`LICENSE.txt` della libreria standard).
- **Testi mancanti:** per i componenti che non includono il testo della licenza (PySide6 e shiboken6, ICU incluso in Qt, OpenSSL incluso in Python su macOS) si usano i testi ufficiali conservati in `packaging/licenses/` (LGPL-3.0, GPL-3.0, ICU 73, Apache-2.0).
- **Contenuto:** il file contiene l'elenco dei componenti con versione e licenza, dove trovare il codice sorgente (rilasci di Qt e PySide6, PyPI, pacchetti Ubuntu su Launchpad) e i testi completi delle licenze.
- **Sorgenti di mysql-connector-python:** il connettore è GPLv2 (con l'eccezione Universal FOSS) ed è incluso solo come bytecode, quindi nel pacchetto c'è anche il suo codice sorgente (`licenses/mysql-connector-python-<ver>-source.zip`).
- **Fail-closed:** se un file del bundle non ha un'origine nota, la build fallisce. Una nuova dipendenza non può quindi essere distribuita senza la sua licenza.

Dove trovare le licenze:

- `.deb`: `/usr/share/doc/querylean/THIRD_PARTY_LICENSES.txt`;
- DMG: accanto all'applicazione, insieme a `LICENSE.txt`;
- AppImage: dentro il bundle (`usr/lib/querylean/_internal/licenses/`).

La finestra **About** rimanda al file. Nei pacchetti, lo smoke test fallisce se il file manca.

### Linux (AppImage)

```bash
pip install -e ".[build]"
packaging/build_linux_appimage.sh     # → dist/querylean-<ver>-x86_64.AppImage
```

Lo script scarica `appimagetool` (versione fissata nello script) e il runtime AppImage in `build/`; al secondo avvio li riusa. Senza FUSE usa `APPIMAGE_EXTRACT_AND_RUN=1`. Per la massima compatibilità, conviene fare la build sulla distribuzione più vecchia da supportare (Ubuntu 22.04).

Requisiti per la build su Linux (AppImage e `.deb`):

```bash
sudo apt install curl file desktop-file-utils \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
  libxcb-shape0 libxcb-util1 libxcb-xkb1 libxkbcommon-x11-0
```

Le librerie `libxcb-*` e `libxkbcommon-x11-0` servono al plugin xcb di Qt e vengono incluse nel pacchetto solo se sono installate sulla macchina di build: se mancano la build fallisce, per non produrre un pacchetto che non parte sui sistemi che non le hanno. `desktop-file-utils` serve ad `appimagetool`.

### Ubuntu/Lubuntu 24.04 (.deb)

```bash
pip install -e ".[build]"
packaging/build_linux_deb.sh          # → dist/querylean-<ver>-amd64.deb
```

La build va fatta su Ubuntu 24.04 (o una derivata come Lubuntu): il bundle richiede glibc ≥ 2.38. Il pacchetto installa:

- il bundle PyInstaller in `/opt/querylean`;
- il lanciatore `/usr/bin/querylean`;
- la voce di menu e l'icona;
- le licenze in `/usr/share/doc/querylean/copyright` (formato DEP-5) e quelle di terze parti in `/usr/share/doc/querylean/THIRD_PARTY_LICENSES.txt`.

Qt, Python e le altre librerie sono inclusi nel bundle. Le dipendenze dichiarate sono solo `libc6 (>= 2.38)`, `libegl1`, `libgl1` e `libxcb1`, ricavate dalle librerie che il bundle carica dal sistema. Il portachiavi (`gnome-keyring` o `keepassxc`) e le librerie Wayland sono *Recommends*.

La versione del pacchetto deriva da `.version`: `-` diventa `~` e si aggiunge la revisione `-1` (`X.Y.Z-dev` → `X.Y.Z~dev-1`), così una versione di sviluppo viene ordinata prima della release finale.

### macOS (.app + .dmg)

```bash
pip install -e ".[build]"
packaging/build_macos_dmg.sh          # → dist/querylean-<ver>-<arch>.dmg
```

L'architettura è quella dell'interprete Python usato. Si ottengono quindi due build separate: arm64 su Apple Silicon e x86_64 su Intel. L'immagine disco contiene anche `LICENSE.txt` e `THIRD_PARTY_LICENSES.txt`.

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
- build dell'AppImage (Ubuntu 22.04), del `.deb` (Ubuntu 24.04) e dei DMG arm64 e x86_64, ciascuna con smoke test (`--smoke-test`, che verifica anche le licenze di terze parti);
- il `.deb` viene installato con `apt`, verificato e poi rimosso;
- pubblicazione dei pacchetti come artefatti della build;
- sui tag `vX.Y.Z`, creazione della release su GitHub (vedi sotto).

La CI parte sui push in `main` e nei branch `release-*`, sui tag `v*` e sulle pull request.

### Rilascio

Il flusso di rilascio è questo:

1. Da `develop` si crea il branch `release-X.Y.Z`, dove `X.Y.Z` è la versione attuale senza `-dev`.
2. Nel branch si porta `.version` a `X.Y.Z` e si pubblica il branch: la CI costruisce e verifica tutti i pacchetti.
3. Si fa merge di `release-X.Y.Z` in `main`, si tagga `main` con `vX.Y.Z` e si pubblica il tag.
4. Sul tag, il job `release` della CI:
   - verifica che il tag corrisponda a `.version`;
   - aspetta che tutti i pacchetti siano costruiti e superino lo smoke test;
   - crea la release su GitHub con AppImage, `.deb`, i due DMG, le licenze di terze parti dell'AppImage e il file `SHA256SUMS`;
   - la segna come pre-release se il tag contiene un trattino (es. `vX.Y.Z-rc1`).

Per verificare un download: `sha256sum -c SHA256SUMS --ignore-missing`.

## Limiti di questa versione

- Una sola connessione aperta e una sola query alla volta, una sola istruzione per esecuzione.
- Non sono supportati: TLS/SSH tunnel configurabili da GUI, autocompletamento, cronologia, paginazione.
- L'esportazione salva solo le righe caricate (al massimo 10.000): per esportarne di più serve uno strumento come `mysqldump` o `mysql --batch`.
- `SHOW` è ammesso solo nelle forme riconosciute dal parser; le altre vengono rifiutate.
- Colonne, tabelle e alias il cui nome è una parola di scrittura (`update`, `delete`, `insert`, …) vengono rifiutati anche se quotati o qualificati; i nomi che contengono soltanto una di queste parole (`updated_at`, `delete_flag`) sono ammessi. Viene rifiutata anche la funzione di stringa `INSERT()`. Le parole dentro stringhe e commenti non vengono controllate.
- Sequenze `--` non seguite da spazio fuori dalle stringhe (es. `1--1`) vengono rifiutate per evitare ambiguità con i commenti: scrivi `1 - -1`.
- Il supporto a MariaDB non è garantito: `MAX_EXECUTION_TIME` non esiste e si usa solo il watchdog.

## Licenza

QueryLean è distribuito con [licenza MIT](LICENSE). I pacchetti contengono anche componenti di terze parti, ciascuno con la propria licenza: vedi [Licenze di terze parti](#licenze-di-terze-parti).
