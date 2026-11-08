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
  - esecuzione con `Ctrl+Invio` (Linux) o `Cmd+Invio` (macOS);
  - [autocompletamento](#autocompletamento) di tabelle, colonne, alias, parole chiave e funzioni con `Ctrl+Spazio`, che si apre anche da solo mentre si scrive.
- Una connessione usa un database oppure [tutti i database](#tutti-i-database) a cui l'account ha accesso.
- Barra laterale con i database, le tabelle e le viste a cui si ha accesso: un clic su una tabella prepara nell'editor `SELECT * FROM <tabella> LIMIT 1;` e ne mostra le colonne (tipo, chiavi, commenti).
- Query nei segnalibri: una query salvata con un nome per una connessione si riesegue dal menu **Bookmarked queries**, solo su quella connessione. Un segnalibro può essere una [maschera](#maschere) con segnaposto `${NOME}` per i valori che cambiano. I segnalibri si possono [esportare](#esportare-le-query-nei-segnalibri) in un file JSON e [importare](#importare-le-query-nei-segnalibri) in un'altra connessione o installazione.
- Sono ammesse solo istruzioni di lettura (`SELECT`, `WITH … SELECT`, `UNION`, `SHOW`, `DESCRIBE`/`DESC`, `EXPLAIN SELECT`). Ogni query passa da un validatore basato sul parsing.
- Alla connessione vengono controllati i privilegi dell'account database per database: un database che l'account può modificare viene rifiutato finché non lo si accetta in [modalità attenzione](#modalità-attenzione).
- L'esecuzione avviene fuori dal thread della GUI, con indicatore di attività, timeout e un pulsante **Stop** (Interrompi) lampeggiante che compare solo quando una query dura più di un secondo.
- Tabella dei risultati non modificabile:
  - `NULL` è distinto dalla stringa vuota;
  - colonne ridimensionabili;
  - copia di celle o righe in formato tabulato, incollabile in Excel e LibreOffice Calc;
  - esportazione del risultato in Excel (`.xlsx`), CSV o JSON.
- Il limite di righe (predefinito 1.000, massimo 10.000) è applicato durante il recupero dei dati.
- **Pagine**: quando una query `SELECT`/`WITH` restituisce più righe del limite di righe, le prime righe si vedono subito ("Results limited to the first N rows"), poi le righe vengono contate con `SELECT COUNT(*) FROM (<query>) AS querylean_count` e compaiono **«** **‹** "Page N of M" (Pagina N di M) **›** **»** a destra della riga sotto i risultati (il totale è nel tooltip). Una pagina contiene tante righe quanto il limite di righe. Il conteggio si esegue solo se il risultato è stato troncato. Ogni altra pagina si legge con `SELECT * FROM (<query>) AS querylean_page LIMIT <limite> OFFSET <n>`; la prima pagina è il risultato già caricato. Entrambe le istruzioni passano dal validatore di sola lettura e girano solo sulla sessione che ha eseguito la query; le pagine spariscono con una nuova query, un altro database attivo o una disconnessione. I numeri di riga proseguono da una pagina all'altra; la copia e **Export** prendono la pagina mostrata. Senza `ORDER BY` MySQL non garantisce l'ordine delle righe tra le pagine. Una query che non può essere una tabella derivata (per esempio `SELECT *` su una join con due colonne con lo stesso nome) non ha pagine: il messaggio spiega il motivo. `SHOW`, `DESCRIBE` ed `EXPLAIN` non hanno pagine.
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

La barra in alto contiene, nell'ordine: **Run** (Esegui, ▶), **Save query** (Salva query, ☆) e **Bookmarked queries** (Query nei segnalibri, menu a tendina), attivi solo da connessi, **Export** (Esporta, menu a tendina, attivo quando c'è un risultato), **Connect**/**Disconnect** (Connetti/Disconnetti), **Connections** (Connessioni, menu a tendina) e **About** (Informazioni: versione, autore, licenza). Lo stato della connessione è in basso a destra. L'interfaccia è in inglese. A sinistra, per tutta l'altezza della finestra, c'è la barra **Tables** (Tabelle).

Mentre una query è in esecuzione, sotto i risultati compaiono una barra di attività e il testo della query. Se dopo un secondo la query è ancora in corso, accanto alla barra di attività compare un pulsante rosso **Stop** (Interrompi, ■) che lampeggia fino alla fine della query: un clic la interrompe. Le query veloci non lo mostrano mai.

1. **Connections** → **New connection…** (Connessioni → Nuova connessione…): compila nome (facoltativo), host, porta, database (oppure spunta "All the databases the account can access", Tutti i database a cui l'account ha accesso), username, password e i timeout, poi usa **Test connection** (Test connessione) e **Save** (Salva). Salvare non apre la connessione (vedi [Connessioni](#connessioni)).
2. **Connect** apre la connessione attiva, quella con la spunta nel menu **Connections**: lo stato passa da *Disconnected* (Disconnesso) a *Connecting* (Connessione in corso) e poi a *Connected* (Connesso) o *Connection error* (Errore di connessione). Se la password non è nel portachiavi, viene richiesta.
3. Scrivi la query, aiutato dall'[autocompletamento](#autocompletamento), e premi **Run** oppure `Ctrl/Cmd+Invio`. In alternativa fai clic su una tabella nella barra laterale (vedi [Barra delle tabelle](#barra-delle-tabelle)). Sotto i risultati, su una sola riga, compaiono "Query executed:" (Query eseguita:) seguito dalla query appena eseguita, poi righe e tempo e, quando c'è più di una pagina, i pulsanti delle pagine a destra (vedi sotto). Oltre i 160 caratteri la query è troncata con "…"; il testo completo è nel tooltip del messaggio. Durante l'esecuzione la stessa riga mostra "Running:" (In esecuzione:) seguito dalla query.
4. Seleziona celle o righe e premi `Ctrl/Cmd+C`. Il menu contestuale offre anche le varianti "con intestazioni" e "righe intere".
5. Per salvare il risultato su file apri il menu **Export** e scegli il formato (vedi [Esportazione](#esportazione)).

### Connessioni

Il pulsante **Connections** (Connessioni) apre un menu con **New connection…** (Nuova connessione…) e, sotto, le connessioni salvate in ordine alfabetico. Ogni connessione è mostrata con il suo nome oppure, se il nome è vuoto, come `<utente>@<host>/<database>` (`<utente>@<host>/*` per tutti i database). La connessione attiva ha la spunta.

Ogni voce ha un sottomenu:

- **Connect** (Connetti): la rende attiva e si connette. Se si è già connessi a un'altra, quella viene chiusa prima.
- **Edit…** (Modifica…): apre la finestra di compilazione con i valori salvati. Se è la connessione in uso, le modifiche valgono dalla prossima connessione.
- **Delete…** (Elimina…): chiede conferma, poi cancella il file della connessione e le sue query nei segnalibri. Se è quella in uso, la chiude.

In fondo, **Export bookmarked queries…** esporta i segnalibri delle connessioni salvate e **Import bookmarked queries…** (Importa le query nei segnalibri) li importa da un file esportato (vedi [Esportare le query nei segnalibri](#esportare-le-query-nei-segnalibri) e [Importare le query nei segnalibri](#importare-le-query-nei-segnalibri)).

Il pulsante **Connect** (Connetti) della barra usa la connessione attiva; se non ne esiste nessuna, apre **New connection…**. Una connessione appena salvata diventa attiva se in quel momento non si è connessi.

Ogni connessione è un file JSON a sé (vedi [File locali](#file-locali)) e non contiene mai la password.

Una connessione con almeno un database accettato in **Caution mode** (modalità attenzione) compare nel menu come "<nome> (caution mode)" (vedi [Modalità attenzione](#modalità-attenzione)).

### Tutti i database

Nella finestra della connessione il campo **Database** può essere sostituito dalla casella "All the databases the account can access" (Tutti i database a cui l'account ha accesso):

- con un database (casella spenta) la connessione usa solo quel database, come nelle versioni precedenti: la barra laterale mostra solo quello, già espanso, e il controllo dei privilegi considera solo quello;
- con la casella attiva la connessione comprende tutti i database elencati da `SHOW DATABASES` (solo quelli a cui l'account ha accesso). Il campo **Database** diventa facoltativo: se compilato, è il database attivo alla connessione;
- il **database attivo** è quello a cui si riferiscono i nomi non qualificati (`SELECT * FROM users`). È in grassetto nella barra laterale e lo stato in basso a destra lo mostra come "db: <nome>". Un clic su un database (o su una sua tabella), oppure **Use as active database** (Usa come database attivo) nel suo menu contestuale, lo rende attivo. L'applicazione lo cambia con il comando di protocollo MySQL `COM_INIT_DB`, non con SQL dall'editor (`USE` non è una query di lettura e resta vietato); le riconnessioni lo mantengono;
- senza un database attivo MySQL rifiuta i nomi non qualificati ("No database selected"): fai prima clic su un database, oppure scrivi `db.tabella`;
- con tutti i database le query preparate dalla barra laterale qualificano sempre la tabella (`` SELECT * FROM `shop`.`orders` LIMIT 1; ``), quindi funzionano qualunque sia il database attivo;
- l'autocompletamento propone i database dopo `FROM`/`JOIN` (inseriti con il loro punto), le tabelle dopo `db.` e le colonne dopo `db.tabella.`; tabelle e colonne di un database vengono lette quando lo si espande, lo si rende attivo o servono all'autocompletamento.

### Barra delle tabelle

Dopo la connessione la barra **Tables** (Tabelle) mostra un albero: i database (quello configurato, oppure tutti quelli accessibili), le loro tabelle e viste (`SHOW FULL TABLES`, solo quelle a cui l'account ha accesso) e le colonne. Le viste sono in corsivo e in fondo c'è il numero di tabelle (o di database).

I nomi dei database mostrano l'accesso in scrittura dell'account: in **verde** quelli che può solo leggere, in **rosa** con un'icona di avviso arancione (⚠) quelli che può modificare (accettati in [modalità attenzione](#modalità-attenzione)). Il tooltip elenca i privilegi. L'accesso si calcola dai grant letti alla connessione, anche per i database che compaiono dopo un aggiornamento.

- Un **clic** su una tabella (anche un doppio clic, oppure `Invio` sulla voce selezionata) sostituisce il contenuto dell'editor con `SELECT * FROM <tabella> LIMIT 1;`. La query **non viene eseguita**: premi **Run** per lanciarla. Il testo precedente si recupera con `Ctrl/Cmd+Z`.
- **Colonne**: lo stesso clic espande la tabella e ne mostra le colonne in ordine, con il tipo a destra; la sola freccia la apre o la chiude senza toccare l'editor. Le colonne della chiave primaria sono in grassetto con un'etichetta gialla "P"; il tooltip mostra la definizione completa (tipo, `NULL`/`NOT NULL`, chiave, default, extra, commento).
- Un doppio clic su una colonna, oppure `Invio`, sostituisce il contenuto dell'editor con `SELECT <colonna> FROM <tabella> LIMIT 1;`, senza eseguirla e annullabile con `Ctrl/Cmd+Z`. Un clic singolo su una colonna non tocca l'editor.
- **Shift + doppio clic** su una colonna (oppure `Shift+Invio`) la aggiunge alle colonne della query preparata: `SELECT * FROM <tabella> LIMIT 1;` diventa `SELECT <colonna> …`, poi `SELECT <colonna>, <altra colonna> …`. Una colonna già presente non viene ripetuta; se nell'editor c'è un altro testo (una query su un'altra tabella o scritta a mano), viene sostituito da una nuova `SELECT <colonna> FROM <tabella> LIMIT 1;`. Ogni aggiunta si annulla con `Ctrl/Cmd+Z`.
- Il menu contestuale (clic destro) offre **Prepare SELECT** (Prepara la SELECT, sulle tabelle), **Prepare SELECT of the column** (Prepara la SELECT della colonna) e **Add to the SELECT** (Aggiungi alla SELECT, sulle colonne), e **Copy name** (Copia il nome).
- **Filter tables…** (Filtra le tabelle…) in alto mostra solo le tabelle il cui nome, o il nome del loro database, contiene il testo (senza distinzione tra maiuscole e minuscole); la riga in fondo indica allora "N of M tables" (N di M tabelle).
- Il nome della tabella è sempre tra backtick, con gli eventuali backtick interni raddoppiati, quindi funzionano anche nomi con spazi o parole riservate.
- Il pulsante ⟳ ricarica database e tabelle, per esempio dopo la creazione di una tabella. Alla disconnessione l'albero si svuota.
- La lettura dell'elenco passa dal validatore, rispetta il timeout delle query e mostra al massimo 10.000 voci. Un errore (per esempio permessi insufficienti) viene mostrato nella barra, senza chiudere la connessione.
- Le colonne di un database vengono lette una volta, insieme alle sue tabelle, con una sola query su `information_schema.COLUMNS` (passando dal validatore, al massimo 10.000 colonne); le tabelle rimaste fuori, o il cui elenco non è riuscito, vengono lette su richiesta con `SHOW FULL COLUMNS FROM <tabella>` quando si espandono o servono all'autocompletamento. Una tabella di cui non si possono leggere le colonne mostra "No columns available." (Nessuna colonna disponibile; il motivo è nel tooltip).

### Autocompletamento

L'editor propone ciò che ha senso nel punto del cursore, come i principali strumenti per database:

- `Ctrl+Spazio` apre le proposte (su macOS con il tasto fisico **Control**: `Cmd+Spazio` è di Spotlight). Se c'è una sola proposta, viene inserita subito. `Ctrl/Cmd+Invio` continua a eseguire la query.
- L'elenco si apre anche da solo mentre si scrive: subito dopo un `.` e dopo la prima lettera del nome di una tabella o di una colonna (due lettere dove sono possibili solo parole chiave). Si chiude quando la parola è completa, quando si scrive uno spazio o un segno di punteggiatura, oppure con `Esc`.
- `Invio` o `Tab` inseriscono la proposta selezionata, le frecce e `PagSu`/`PagGiù` si muovono nell'elenco, anche un clic inserisce. L'inserimento sostituisce tutta la parola sotto il cursore e si annulla con un solo `Ctrl/Cmd+Z`.
- Cosa viene proposto dipende dalla posizione:
  - all'inizio: `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `EXPLAIN`;
  - dopo `FROM`/`JOIN`, `DESCRIBE` e `SHOW COLUMNS FROM`: tabelle, viste e le query `WITH` dello statement;
  - dopo una tabella: le varianti di `JOIN`, `ON`, `WHERE`, `GROUP BY`, `ORDER BY`, `LIMIT`…;
  - in `SELECT`, `WHERE`, `ON`, `GROUP BY`, `ORDER BY`, `HAVING` e negli argomenti delle funzioni: le colonne delle tabelle dello statement (anche quelle scritte dopo il cursore, quindi `SELECT | FROM users u` funziona), gli alias, poi funzioni e parole chiave;
  - dopo `alias.` o `tabella.`: solo le colonne di quella tabella; dopo `database.`: le sue tabelle;
  - dopo un valore o una colonna: operatori e clausole (`AND`, `OR`, `IN`, `LIKE`, `IS NULL`, `AS`, `ORDER BY`…).
- Ogni proposta ha un'etichetta con il tipo (`P` chiave primaria, `c` colonna, `T` tabella, `V` vista, `a` alias, `f` funzione, `k` parola chiave) e, a destra, il tipo e la tabella di una colonna. Il tooltip di una colonna ne mostra la definizione completa.
- Il confronto ignora maiuscole e minuscole: prima i nomi che iniziano con il testo scritto, poi quelli con una parola (dopo `_`) che inizia con esso, poi tabelle e colonne che lo contengono.
- Il nome di una colonna presente in più tabelle dello statement viene inserito qualificato (`u.id`). I nomi con spazi, parole riservate o caratteri speciali vengono inseriti tra backtick; le parole chiave seguono il maiuscolo/minuscolo del testo scritto (`sel` → `select`, `SEL` → `SELECT`); le funzioni vengono inserite con le parentesi e il cursore all'interno.
- Non viene proposto nulla dentro stringhe, commenti, numeri, dopo `AS` e dopo `LIMIT`. Le parole che il validatore rifiuta (`INSERT`, `UPDATE`, `DELETE`, …) e le funzioni vietate non vengono mai proposte.
- Le colonne delle sottoquery nel `FROM` e delle query `WITH` non sono note, quindi dopo il loro alias non viene proposto nulla.

### Query nei segnalibri

Una query nei segnalibri appartiene a **una connessione salvata** e al database a cui punta (`<utente>@<host>:<porta>/<database>`, oppure `/*` con tutti i database).

- **Save query** (Salva query) salva la selezione oppure, senza selezione, tutto il contenuto dell'editor. Chiede un nome (al massimo 100 caratteri) e salva la query per la connessione aperta. Un segnalibro esistente con lo stesso nome (senza distinzione tra maiuscole e minuscole) viene sostituito dopo una conferma. Si possono salvare solo query accettate dal validatore: una query di scrittura viene rifiutata già a questo punto.
- Il menu **Bookmarked queries** (Query nei segnalibri) elenca, in ordine alfabetico, solo le query della connessione aperta; il testo della query è nel tooltip. Un clic mette la query nell'editor (annullabile con `Ctrl/Cmd+Z`) e la esegue subito, passando dal validatore come ogni altra query.
- **Bookmarked queries** → **Delete** (Elimina) cancella un segnalibro, dopo una conferma.
- Un segnalibro non viene mai eseguito su un'altra connessione: il menu mostra solo quelli della connessione aperta e, prima di eseguirne uno, il thread del database controlla che la sessione aperta punti allo stesso utente, host, porta e database. Un'altra connessione salvata che punta allo stesso database ha i suoi segnalibri.
- Se una connessione viene modificata per puntare a un altro host, porta, database o utente, i suoi vecchi segnalibri non vengono più mostrati; tornano se si ripristinano i valori precedenti.
- I segnalibri sono salvati in un file JSON per connessione (vedi [File locali](#file-locali)).

### Maschere

Una **maschera** è una query nei segnalibri con segnaposto `${NOME}` al posto dei valori che cambiano, per esempio:

```sql
SELECT * FROM orders WHERE year = ${YEAR};
SELECT * FROM call_answered WHERE cli = '${DIGITS}' AND connection_time = '${CONNECTION_DATETIME}';
SELECT * FROM documents WHERE code IN (${CODES}) AND importDateTime >= '${IMPORT_DATE_TIME}';
```

- **Scrivere i segnaposto**: scrivili nell'editor, oppure parti da una query che già funziona: seleziona un valore (`2026`, `'3391234567'`, parte di una stringa, oppure una lista come `12, 15, 31`) e scegli **Make placeholder…** (Crea segnaposto…, `Ctrl+Shift+P`, anche nel menu contestuale dell'editor). Il nome proposto è la colonna confrontata (`cli = '…'` → `CLI`); il valore diventa l'esempio e il predefinito, e il tipo viene riconosciuto. Un solo annulla ripristina il valore.
- **Più valori insieme**: **Make placeholder…** senza selezione apre **Make placeholders** (Crea segnaposto), con tutti i valori della query che possono diventare segnaposto (numeri e stringhe fuori dai commenti; una lista di valori in `IN (…)` diventa un solo segnaposto lista). I valori confrontati con una colonna partono spuntati, gli altri (come `LIMIT 100`) no; ogni riga mostra il valore, il nome proposto (modificabile), il tipo e la riga, e l'anteprima mostra la query risultante. Lo stesso nome su più valori dello stesso tipo forma un solo segnaposto. Un solo annulla ripristina tutti i valori.
- **Nomi**: lettere, cifre e `_`, senza iniziare con una cifra. Lo stesso segnaposto usato due volte prende un solo valore. Nell'editor i segnaposto sono evidenziati; nei commenti vengono ignorati, tra backtick (un nome di tabella o colonna) non sono ammessi.
- **Tipi**: Integer (intero), Decimal (decimale), Text (testo), Date (data), Time (ora), Date-time (data e ora), Boolean (booleano). Un segnaposto può essere una **lista** (per `IN (${CODES})`): valori separati da virgola, oppure uno per riga.
- **I valori non diventano mai SQL**: fuori dagli apici un valore diventa un letterale tipizzato (un numero controllato, `TRUE`/`FALSE` oppure una stringa con escape), dentro gli apici (`'${DIGITS}'`) contenuto di stringa con escape. Un valore come `2026 OR 1=1` per un Integer viene rifiutato e `x' OR 'a'='a` per un Text resta dentro la stringa: la struttura della query non cambia mai.
- **Salvataggio**: **Save query** su una query con segnaposto apre **Save mask** (Salva maschera): nome e, per ogni segnaposto, tipo, lista, valore predefinito e descrizione. L'anteprima mostra la query compilata con i predefiniti: deve essere una query di lettura, altrimenti **Save** resta disattivato.
- **Esecuzione**: nel menu una maschera ha l'icona `${}` e il nome termina con "…" (le query nei segnalibri senza segnaposto hanno l'icona di un foglio blu e si eseguono subito); sceglierla apre **Run mask** (Esegui maschera), con un campo per segnaposto: calendario per date e date-ora, editor dell'ora, TRUE/FALSE per i booleani, un riquadro con un valore per riga per le liste. Ogni valore è obbligatorio. I campi partono dai **valori usati l'ultima volta, evidenziati in giallo** finché non vengono cambiati, altrimenti dai predefiniti (**Defaults**, Predefiniti, li ripristina tutti). Sotto, la query compilata viene controllata a ogni modifica: **Run** si attiva solo con valori validi e una query di lettura. La query compilata va nell'editor (annullabile) e si esegue come un segnalibro, solo sulla sua connessione e passando dal validatore.
- **Modificare una maschera**: il nome in cima a **Run mask** si può modificare; il nuovo nome (non vuoto e diverso da quello di un altro segnalibro della connessione) viene salvato quando la maschera viene eseguita o aperta nell'editor, mentre **Cancel** (Annulla) mantiene quello vecchio. **Open in editor** (Apri nell'editor) nella stessa finestra carica la maschera con i suoi segnaposto, senza eseguirla; **Save query** con lo stesso nome la sostituisce e conserva gli ultimi valori dei segnaposto che ha ancora. **Run** su una query con segnaposto nell'editor viene rifiutato con l'elenco dei segnaposto da sostituire, mostrato sia in rosso sotto i risultati sia nella finestra **Placeholders to fill in** (Segnaposto da compilare).
- Le maschere, con i loro ultimi valori, sono salvate con gli altri segnalibri della connessione (file dei segnalibri versione 2; i file delle versioni precedenti vengono letti senza modifiche).

### Esportare le query nei segnalibri

**Connections** → **Export bookmarked queries…** (Esporta le query nei segnalibri, anche senza connessione) oppure **Bookmarked queries** → **Export…** (Esporta) apre **Export bookmarked queries**, con le query nei segnalibri e le maschere di **tutte le connessioni salvate**:

- una riga per segnalibro, con quello che li distingue: nome, tipo (**Query** oppure **Mask**, maschera), connessione, target `<utente>@<host>:<porta>/<database>`, segnaposto e la query su una riga (completa nel tooltip). Due segnalibri con lo stesso nome su connessioni diverse sono righe distinte;
- ogni riga parte selezionata; il filtro mostra solo le righe che contengono il testo scritto (nome, connessione, target o query), **Select all** (Seleziona tutto) e **Select none** (Deseleziona tutto) agiscono sulle righe visibili. **Export…** si attiva quando almeno una riga è selezionata e chiede il nome del file (`querylean-bookmarks.json` come predefinito);
- **Include the last values used in masks** (Includi gli ultimi valori usati nelle maschere) è disattivata come predefinito: quei valori possono essere dati reali.

Sono elencati solo i segnalibri del target attuale di ogni connessione (quelli che mostra il suo menu). La connessione serve solo a scegliere: **il file contiene solo le query e le maschere**, senza host, porta, utente, database né password, così si può condividere con utenti che eseguono le query sui propri server (per esempio un database locale di sviluppo) con le proprie credenziali. Lo stesso segnalibro salvato per più connessioni viene scritto una volta sola. Il file è scritto con permessi 0600. Il formato, letto dall'[importazione](#importare-le-query-nei-segnalibri) di un'altra installazione di QueryLean:

```json
{
  "format": "querylean-bookmarks",
  "format_version": 1,
  "exported_at": "2026-11-08T09:30:00+00:00",
  "exported_by": {"application": "querylean", "version": "…"},
  "bookmarks": [
    {"name": "Users", "kind": "query", "sql": "SELECT * FROM users"},
    {"name": "Orders by year", "kind": "mask",
     "sql": "SELECT * FROM orders WHERE year = ${YEAR}",
     "placeholders": [{"name": "YEAR", "type": "integer", "list": false,
                       "default": "2025", "description": ""}],
     "last_values": {"YEAR": "2024"}}
  ]
}
```

Ogni segnalibro ha gli stessi campi dei file dei segnalibri, senza la connessione (`last_values` solo se richiesto): chi lo importa sceglie la connessione per cui salvarlo. `format_version` cambia solo con modifiche incompatibili.

### Importare le query nei segnalibri

**Connections** → **Import bookmarked queries…** (Importa le query nei segnalibri, anche senza connessione) oppure **Bookmarked queries** → **Import…** (Importa) chiede un file scritto dall'esportazione, poi apre **Import bookmarked queries**:

- **Import into** (Importa in) sceglie la connessione salvata (viene proposta quella aperta o quella attiva): i segnalibri si salvano per il suo target attuale e si eseguono sul suo database con le sue credenziali. Il file non sceglie mai un server;
- una riga per segnalibro del file, con nome, tipo, stato, segnaposto e la query su una riga. Lo stato lo confronta con i segnalibri già salvati per la connessione scelta: **New** (nuovo), **Already saved** (già salvato: stesso nome, query e segnaposto, non si scrive niente) oppure **Name in use** (nome in uso: un segnalibro diverso con lo stesso nome);
- **When the name is in use** (se il nome è in uso): **Import it with a new name** (importalo con un nuovo nome, predefinito: "Users (2)", "Users (3)", …), **Replace the saved query** (sostituisci la query salvata, che conserva gli ultimi valori della maschera salvata se il file non ne ha) oppure **Skip it** (saltalo). Due segnalibri del file con lo stesso nome vengono importati entrambi, il secondo con un nuovo nome;
- il filtro, **Select all** e **Select none** funzionano come nell'esportazione; **Import the last values used in masks** (Importa gli ultimi valori usati nelle maschere) è proposta, e selezionata, solo se il file li contiene.

Il file è trattato come non fidato: deve essere un file regolare con un'esportazione (`format` `querylean-bookmarks`) con un `format_version` conosciuto (un file scritto da un QueryLean più recente viene rifiutato), di al massimo 5 MB e 10.000 segnalibri. Le voci non valide vengono scartate e contate, i campi sconosciuti ignorati. Come nel salvataggio dall'editor, **si importano solo query di lettura**: la query, o la maschera compilata con i suoi predefiniti, deve passare il validatore di sola lettura, altrimenti la riga mostra **Refused** (rifiutata) con il motivo (nel tooltip) e non si può selezionare. Le query vengono validate di nuovo a ogni esecuzione.

### Regole di esecuzione

- Se nell'editor c'è del testo selezionato, viene eseguita **solo la selezione**.
- Senza selezione viene eseguito **l'intero contenuto** dell'editor.
- Un editor vuoto (o con soli spazi) non esegue nulla.
- È ammessa **una sola istruzione**; un `;` finale è tollerato. Con più istruzioni la query viene rifiutata: per eseguirne una, selezionala.
- Una query che non è di lettura (per esempio `UPDATE`, `DELETE`, `INSERT`), o che il validatore rifiuta per un altro motivo, non viene inviata al server: oltre al messaggio rosso sotto i risultati, una finestra **Read queries only** (Solo query di lettura) spiega che vengono eseguite solo query di lettura e perché la query è stata rifiutata. In modalità attenzione elenca anche i database che l'account potrebbe modificare. La finestra non blocca l'applicazione e compare solo quando una query viene rifiutata, mai alla connessione.

### Copia

Le celle copiate sono separate da tabulazioni e le righe da a capo. La selezione viene copiata come rettangolo, e le celle non selezionate al suo interno restano vuote. Un `NULL` diventa una cella vuota, mentre tabulazioni e a capo dentro i valori diventano spazi, così la griglia resta allineata. I valori binari non UTF-8 sono mostrati in esadecimale (`0x…`, troncati a 64 byte).

### Esportazione

**Export** (Esporta) salva su file il risultato mostrato nella tabella, con le intestazioni delle colonne. Il pulsante apre un menu:

- **Excel (.xlsx)**, **CSV (.csv)**, **JSON (.json)**: la finestra di salvataggio propone solo quel formato. Se il nome non ha la sua estensione, viene aggiunta.
- **Export…** (Esporta…): la finestra di salvataggio propone tutti i formati. Decide l'estensione del nome (`.xlsx`, `.csv`, `.json`) oppure, se manca, il formato selezionato nella finestra.

- Si esportano **le righe già caricate** (la pagina mostrata, vedi Pagine), cioè al massimo il limite di righe impostato: la query non viene rieseguita. Se il risultato era troncato, il messaggio finale lo ricorda.
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
- rimuove `NO_BACKSLASH_ESCAPES`, `ANSI_QUOTES` e `ANSI` dal `sql_mode` di sessione, così il server interpreta le stringhe come il validatore (`"…"` è sempre una stringa, mai un nome), poi rilegge il `sql_mode`: se uno dei primi due è ancora attivo, o non si riesce a leggere, la connessione viene chiusa.

> L'applicazione **non** promette una modalità read-only assoluta basata solo sulla GUI. Ad esempio, una funzione memorizzata (stored function) richiamata in una `SELECT` potrebbe modificare dati se l'account ne avesse i privilegi (la sessione READ ONLY blocca le scritture sulle tabelle permanenti, non su quelle temporanee). Per questo il vincolo deve essere garantito dall'account MySQL.

### Controllo dei privilegi

A ogni connessione, compresi **Test connection** (Test connessione) e le riconnessioni trasparenti, l'applicazione esegue `SHOW GRANTS` e ne analizza il risultato in modo fail-closed:

- i privilegi di lettura sono solo `USAGE`, `SELECT`, `SHOW VIEW` e `SHOW DATABASES`; qualsiasi altro privilegio (`INSERT`, `ALL PRIVILEGES`, `EXECUTE`, `PROXY`, `WITH GRANT OPTION`, privilegi dinamici come `BACKUP_ADMIN`, …) rende l'account "con privilegi di scrittura";
- i privilegi su colonne (`UPDATE (col)`) contano come gli altri;
- l'assegnazione di ruoli (`` GRANT `ruolo` TO … ``), righe non riconosciute o un errore di `SHOW GRANTS` rendono l'account "non verificato", e viene trattato come uno con privilegi di scrittura;
- le righe `REVOKE` (revoche parziali) tolgono soltanto privilegi e vengono ignorate;
- ogni privilegio oltre la lettura vale per il database del suo grant: `db.*`, `db.tabella`, `PROCEDURE db.nome`. I nomi di database nei grant seguono i caratteri jolly di MySQL (`%`, `_`, con `\` come escape) e si confrontano senza distinzione tra maiuscole e minuscole, quindi non coprono mai meno database del server. I grant globali (`*.*`), gli oggetti fuori da un database (`PROXY`) e gli account non verificati valgono per **tutti** i database. `information_schema` non è mai modificabile.

Il controllo riguarda i database della connessione: quello configurato, oppure tutti quelli elencati da `SHOW DATABASES`. Un database che l'account può modificare e che non è stato accettato in [modalità attenzione](#modalità-attenzione) viene rifiutato, con un messaggio che elenca i database e i loro privilegi. Le scritture consentite solo su altri database non contano. Nel log finiscono solo i nomi dei privilegi, mai le righe dei grant (su MariaDB possono contenere l'hash della password).

### Modalità attenzione

La **Caution mode** (modalità attenzione) si accetta **database per database**, nella finestra **New connection…**/**Edit…**:

- **Test connection** elenca in rosso i database della connessione che l'account può modificare, ciascuno con i suoi privilegi e una casella ("shop — INSERT, UPDATE"). Spunta ogni database che accetti; la scelta viene salvata con la connessione e resta valida nei test successivi. Cambiare host, porta, username, database o la casella "tutti i database" toglie la spunta a tutti i database: l'accettazione vale solo per il server e l'account per cui è stata data, quindi va ripetuto il test e vanno rispuntati;
- un database modificabile non spuntato fa rifiutare la connessione. Se i privilegi cambiano (un nuovo database, un nuovo grant), la connessione viene rifiutata finché non si accettano i nuovi database con un nuovo test;
- **non cambia nient'altro**: vale lo stesso validatore (solo query di lettura) e la sessione deve essere confermata READ ONLY, altrimenti la connessione viene chiusa;
- mentre si è connessi, lo stato in basso a destra mostra in rosso "CAUTION: write access (<database>)" (ATTENZIONE: accesso in scrittura), il messaggio di connessione elenca i database e i loro privilegi e nella barra laterale quei database sono in rosa con un'icona di avviso (quelli di sola lettura sono in verde);
- per tutta la sessione le parti grigie della finestra (sfondo di barra degli strumenti, barra laterale e barra di stato, margini) diventano rosa, come promemoria costante che l'account può modificare qualche database; editor e tabelle mantengono i loro colori. La tinta segue il tema del sistema (rosa tenue con i temi chiari, rosa scuro con quelli scuri) e sparisce alla disconnessione;
- le connessioni salvate in modalità attenzione dalla versione 1.7 o precedenti la mantengono per il loro database.

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

### Testo dal server

Nomi di database, tabelle e colonne, commenti, messaggi di errore e valori delle celle arrivano dal server e vengono mostrati **alla lettera**: tooltip, righe di stato e finestre non li interpretano mai come HTML, quindi il markup salvato nel database (immagini, link, tabelle) compare come testo e non viene mai interpretato. I nomi dei database si confrontano con i grant esattamente come li restituisce il server (spazi compresi).

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
| Query nei segnalibri, un file `<id connessione>.json` per connessione (permessi 0600) | `~/.config/querylean/bookmarks/` | `~/Library/Application Support/querylean/bookmarks/` |
| Log (rotazione 1 MB × 3) | `~/.local/state/querylean/log/` | `~/Library/Logs/querylean/` |

Le versioni fino alla 1.2 avevano una sola connessione dentro `config.json`. Al primo avvio della nuova versione viene salvata come prima connessione, e la sua password nel portachiavi resta valida.

Agli utenti non vengono mai mostrati stack trace: i dettagli tecnici finiscono nel log, senza segreti.

## Timeout e interruzione

- Il **timeout di connessione** è passato al driver (`connection_timeout`).
- Il **timeout di esecuzione** funziona così:
  - prima di ogni query viene impostato `MAX_EXECUTION_TIME` di sessione, che il server applica alle `SELECT`;
  - un watchdog lato client, scaduto il timeout più 2 secondi, invia `KILL QUERY` da una connessione separata. Questo copre anche `SHOW`/`EXPLAIN` e i server che non supportano `MAX_EXECUTION_TIME`, come MariaDB.
- **Stop** (il pulsante lampeggiante sotto i risultati) invia `KILL QUERY` sulla stessa connessione separata.
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
  bookmarks/    query nei segnalibri per connessione (QueryBookmark, BookmarkStore) e maschere (MaskTemplate, Placeholder, PlaceholderType), esportazione (BookmarkExport, BookmarkEntry)
  completion/   autocompletamento: scanner tollerante, analisi dello statement, proposte (CompletionEngine)
  security/     password nel portachiavi (SecretStore astratta, KeyringSecretStore)
  export/       esportazione Excel/CSV/JSON (ResultExporter astratta)
  database/     errors/, connection/, execution/, schema/ (tabelle e colonne), privileges/ (controllo SHOW GRANTS), validation/ (validatore a stadi)
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
- Non sono supportati: TLS/SSH tunnel configurabili da GUI, cronologia, paginazione.
- Le query nei segnalibri si importano in una connessione alla volta.
- L'esportazione salva solo le righe caricate (al massimo 10.000): per esportarne di più serve uno strumento come `mysqldump` o `mysql --batch`.
- `SHOW` è ammesso solo nelle forme riconosciute dal parser; le altre vengono rifiutate.
- Colonne, tabelle e alias il cui nome è una parola di scrittura (`update`, `delete`, `insert`, …) vengono rifiutati anche se quotati o qualificati; i nomi che contengono soltanto una di queste parole (`updated_at`, `delete_flag`) sono ammessi. Viene rifiutata anche la funzione di stringa `INSERT()`. Le parole dentro stringhe e commenti non vengono controllate.
- Sequenze `--` non seguite da spazio fuori dalle stringhe (es. `1--1`) vengono rifiutate per evitare ambiguità con i commenti: scrivi `1 - -1`.
- Il supporto a MariaDB non è garantito: `MAX_EXECUTION_TIME` non esiste e si usa solo il watchdog.
- Con tutti i database, le query nei segnalibri e la barra laterale si riferiscono all'intero server: un segnalibro con nomi non qualificati viene eseguito sul database attivo del momento.

## Licenza

QueryLean è distribuito con [licenza MIT](LICENSE). I pacchetti contengono anche componenti di terze parti, ciascuno con la propria licenza: vedi [Licenze di terze parti](#licenze-di-terze-parti).
