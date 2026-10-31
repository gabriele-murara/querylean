Di seguito trovi un documento di specifiche tecniche pronto da inviare a un agente AI coder. L'obiettivo è realizzare un client desktop minimale, ispirato a DBeaver, ma progettato esclusivamente per eseguire rapidamente query di lettura su database MySQL.

Ho impostato le specifiche in modo che l'agente possa procedere autonomamente, con requisiti funzionali, scelte tecnologiche, vincoli di sicurezza, interfaccia grafica e criteri di accettazione.

Specifiche tecniche — MySQL Quick Query Desktop Client

# MySQL Quick Query Desktop Client

## Specifiche funzionali e tecniche per lo sviluppo tramite AI Coder

### 1\. Obiettivo del progetto

Realizzare un'applicazione desktop leggera, installabile e avviabile su Linux e macOS, per eseguire rapidamente query SQL di sola lettura su un database MySQL.

L'applicazione deve essere una versione estremamente semplificata di DBeaver, con un'interfaccia essenziale e senza funzionalità avanzate di amministrazione del database.

Il software deve consentire all'utente di:

1. Configurare una singola connessione a un database MySQL tramite GUI.
2. Connettersi al database e verificare la validità della configurazione.
3. Scrivere ed eseguire query SQL di lettura.
4. Visualizzare i risultati in una tabella.
5. Copiare i risultati per utilizzarli in altri strumenti.

**Il principio guida è la semplicità: poche funzionalità, interfaccia immediata, avvio rapido e sicurezza garantita a livello applicativo e di database.**

L'agente AI coder deve implementare un prodotto funzionante, non soltanto un prototipo grafico.

---

### 2\. Piattaforme supportate

L'applicazione deve essere compatibile con:

- Linux, almeno Ubuntu 22.04 LTS e versioni successive compatibili.
- macOS, sia Apple Silicon sia Intel, ove supportato dalle dipendenze selezionate.

Il progetto deve prevedere la generazione di pacchetti eseguibili o installabili per entrambe le piattaforme.

Formati di distribuzione desiderati:

- Linux: AppImage come formato preferenziale.
- macOS: applicazione `.app`, distribuita all'interno di un archivio `.dmg`.

La disponibilità di pacchetti per entrambe le architetture macOS deve essere verificata in base alle tecnologie adottate.

Non deve essere necessario installare Python, Node.js, Java o altri runtime separati per utilizzare l'applicazione, salvo componenti indispensabili esplicitamente documentati.

---

### 3\. Scelta tecnologica

L'agente deve scegliere uno stack tecnologico adatto a un'applicazione desktop minimale, privilegiando affidabilità, facilità di manutenzione e distribuzione.

**Stack consigliato:**

- Linguaggio: Python.
- GUI: PySide6 (Qt).
- Driver MySQL: `mysql-connector-python`.
- Distribuzione: PyInstaller.
- Test: pytest.

Motivazioni:

- Python permette di implementare rapidamente la logica SQL e la gestione delle connessioni.
- PySide6 consente di creare una GUI desktop nativa nell'aspetto e utilizzabile su Linux e macOS.
- PyInstaller permette di distribuire l'applicazione con il runtime necessario.
- Il driver MySQL permette di eseguire query e recuperare i risultati senza richiedere un client MySQL installato separatamente.

L'agente può proporre uno stack alternativo soltanto se offre vantaggi concreti in termini di semplicità, sicurezza o distribuzione multipiattaforma (NO WINDOWS, NO MICROSOFT).

In ogni caso, lo stack scelto deve essere documentato prima di procedere con implementazioni che ne rendano difficile la sostituzione.

---

### 4\. Funzionalità richieste

#### 4.1 Configurazione della connessione

L'applicazione deve prevedere una sola connessione configurabile.

La configurazione deve essere inserita direttamente tramite GUI e deve comprendere i seguenti campi:

| Campo | Obbligatorio | Valore predefinito |
| --- | --- | --- |
| Host | Sì | `localhost` |
| Porta | Sì | `3306` |
| Database | Sì | Vuoto |
| Username | Sì | Vuoto |
| Password | Sì | Vuoto |
| Timeout connessione | Sì | 5 secondi |

I valori predefiniti devono poter essere modificati.

La password deve essere visualizzata come campo mascherato, con un'opzione per mostrarla temporaneamente.

La GUI deve offrire due pulsanti:

- **Test connessione**: verifica che il database sia raggiungibile e che le credenziali siano valide.
- **Salva configurazione**: memorizza i parametri della connessione.

Il salvataggio della configurazione non deve implicare necessariamente una connessione immediata.

Deve essere possibile modificare la configurazione in qualsiasi momento.

Non devono essere supportate connessioni multiple, profili differenti, connessioni preferite o gestione di ambienti multipli.

#### 4.2 Persistenza della configurazione

La configurazione deve essere salvata localmente, in modo da essere disponibile al successivo avvio dell'applicazione.

La configurazione deve includere host, porta, database, username e le eventuali preferenze dell'interfaccia.

La password deve essere gestita separatamente dalla configurazione ordinaria.

Requisiti di sicurezza:

- Non salvare la password in chiaro in file JSON, YAML, INI o equivalenti.
- Utilizzare il portachiavi del sistema operativo per memorizzare la password, tramite un meccanismo compatibile con Linux e macOS.
- Se il portachiavi non è disponibile, non effettuare un salvataggio automatico della password in chiaro.
- Gestire in maniera esplicita gli errori di accesso al portachiavi, consentendo all'utente di inserire nuovamente la password.

Su Linux può essere necessario un servizio di portachiavi compatibile con Secret Service. Tale dipendenza deve essere documentata.

La configurazione non deve contenere dati sensibili nei log.

#### 4.3 Connessione al database

L'applicazione deve permettere di aprire una connessione al database usando i parametri salvati.

Lo stato della connessione deve essere visibile nell'interfaccia:

- Disconnesso.
- Connessione in corso.
- Connesso.
- Errore di connessione.

Se la connessione fallisce, l'utente deve ricevere un messaggio comprensibile.

Esempi:

- Impossibile raggiungere il server MySQL.
- Autenticazione fallita.
- Database inesistente o non accessibile.
- Timeout durante la connessione.

Non devono essere mostrati stack trace all'utente finale.

I dettagli tecnici possono essere registrati in un log locale, escludendo password, segreti e informazioni sensibili.

L'applicazione deve gestire correttamente la chiusura e la riapertura delle connessioni.

Non deve tentare riconnessioni infinite o mantenere connessioni inutilmente aperte.

---

### 5\. Editor SQL

La finestra principale deve includere un editor SQL nel quale l'utente possa digitare o incollare query.

L'editor deve supportare almeno:

- Testo monospaziato.
- Numeri di riga.
- Evidenziazione sintattica SQL di base.
- Selezione e copia del testo.
- Scorciatoia per eseguire la query.
- Visualizzazione della query attualmente in esecuzione.

L'evidenziazione sintattica deve distinguere almeno parole chiave, stringhe, numeri e commenti.

Non sono richiesti autocomplete, suggerimenti intelligenti, completamento dei nomi delle tabelle o analisi avanzata del codice.

La query deve essere eseguibile tramite:

- Pulsante **Esegui**.
- Scorciatoia `Ctrl+Enter` su Linux.
- Scorciatoia `Cmd+Enter` su macOS.

L'esecuzione deve riguardare la query corrente o la selezione dell'editor, secondo le seguenti regole:

1. Se l'utente ha selezionato del testo SQL, eseguire esclusivamente il testo selezionato.
2. Se non è presente una selezione, eseguire il contenuto completo dell'editor.
3. Se il testo è vuoto, non eseguire alcuna operazione.
4. Se la query contiene più istruzioni SQL, rifiutarla in questa versione del prodotto.

La gestione delle selezioni deve essere prevedibile e documentata.

---

### 6\. Sicurezza: esclusivamente query di lettura

Questo requisito è fondamentale.

L'applicazione deve consentire esclusivamente query di lettura.

Sono ammesse le query `SELECT` e le operazioni di lettura compatibili con MySQL che siano state esplicitamente validate.

Non devono essere consentite operazioni che modificano dati, strutture, configurazioni o stato del database.

Esempi di istruzioni da bloccare:

- `INSERT`
- `UPDATE`
- `DELETE`
- `REPLACE`
- `UPSERT`
- `CREATE`
- `ALTER`
- `DROP`
- `TRUNCATE`
- `RENAME`
- `GRANT`
- `REVOKE`
- `CALL`
- `LOAD DATA`
- `SET`
- `USE`
- `LOCK TABLES`
- `UNLOCK TABLES`

Devono essere bloccate anche le istruzioni multiple e i tentativi di aggirare i controlli tramite commenti SQL, spaziature, maiuscole/minuscole o separatori.

#### 6.1 Validazione delle query

Non utilizzare una semplice ricerca testuale della parola `SELECT` come unico controllo di sicurezza.

Implementare un validatore SQL basato su parsing sintattico o su un metodo equivalente sufficientemente robusto da distinguere le istruzioni SQL effettive da commenti e stringhe.

Il validatore deve:

- Accettare soltanto le forme di query di lettura esplicitamente supportate.
- Rifiutare istruzioni multiple.
- Rifiutare istruzioni non riconosciute o ambigue.
- Bloccare istruzioni di modifica anche se precedute da commenti.
- Rifiutare query che includono operazioni non compatibili con la modalità read-only.
- Impedire che il comportamento del driver consenta l'esecuzione di più istruzioni attraverso un'unica richiesta.

Se una query non può essere classificata con sufficiente certezza come query di lettura ammessa, deve essere rifiutata.

La validazione applicativa non deve essere considerata una garanzia di sicurezza sufficiente da sola.

#### 6.2 Protezione a livello MySQL

La connessione deve utilizzare un account MySQL dedicato con privilegi di sola lettura.

L'applicazione deve essere progettata assumendo che l'account configurato abbia esclusivamente i privilegi necessari per leggere i dati richiesti.

Non deve tentare di elevare privilegi, creare utenti o modificare permessi.

La documentazione deve spiegare come predisporre un utente MySQL con privilegi minimi.

L'utente deve essere limitato ai database e agli oggetti necessari.

Dove possibile, devono essere concessi soltanto i privilegi `SELECT` sugli oggetti richiesti.

L'uso di viste dedicate può essere consigliato quando è necessario limitare ulteriormente i dati accessibili.

**Il vincolo di sola lettura deve essere garantito principalmente dai privilegi dell'account MySQL, mentre il validatore SQL costituisce un'ulteriore barriera di sicurezza.**

Il progetto non deve promettere una modalità read-only assoluta basandosi esclusivamente su controlli eseguiti nella GUI.

---

### 7\. Esecuzione delle query

Quando l'utente esegue una query, l'applicazione deve:

1. Verificare che esista una configurazione valida.
2. Verificare che la connessione sia disponibile.
3. Validare la query.
4. Rifiutare l'esecuzione se la query non è ammessa.
5. Eseguire la query su una connessione appropriata.
6. Recuperare i risultati entro limiti definiti.
7. Visualizzare i risultati nella tabella.
8. Mostrare il tempo di esecuzione e il numero di righe restituite.

Le query devono essere eseguite fuori dal thread della GUI, così da non bloccare la finestra durante l'elaborazione.

Durante l'esecuzione:

- Il pulsante Esegui deve essere disabilitato, oppure deve essere previsto un comportamento equivalente che impedisca esecuzioni concorrenti non intenzionali.
- Deve essere visibile un indicatore di attività.
- L'interfaccia deve continuare a rispondere.
- Deve essere possibile interrompere una query quando supportato in modo affidabile dal driver e dalla connessione utilizzata.

Non implementare un sistema complesso di gestione concorrente delle query.

Per questa versione è sufficiente una sola query attiva alla volta.

#### 7.1 Timeout

Prevedere:

- Timeout di connessione configurabile, con valore predefinito di 5 secondi.
- Timeout di esecuzione della query, con valore predefinito di 30 secondi.
- Gestione esplicita dei timeout.

Il timeout di connessione e quello di esecuzione devono essere distinti.

Se il driver non supporta direttamente un timeout affidabile per l'esecuzione, implementare una strategia compatibile con il driver scelto e documentarne i limiti.

L'interruzione della query non deve bloccare indefinitamente la GUI.

---

### 8\. Visualizzazione dei risultati

I risultati devono essere visualizzati in una tabella grafica.

Requisiti:

- Intestazioni con i nomi delle colonne.
- Una riga per ogni record restituito.
- Supporto per valori NULL.
- Supporto per stringhe, numeri, date, booleani e altri tipi restituiti dal driver.
- Ridimensionamento delle colonne.
- Scorrimento orizzontale e verticale.
- Selezione delle celle.
- Copia dei valori selezionati.
- Visualizzazione del numero di righe caricate.

I valori NULL devono essere distinguibili dai valori vuoti.

La tabella non deve essere modificabile.

Non sono richieste funzionalità di modifica diretta delle celle, aggiornamento dei record o inserimento di dati.

#### 8.1 Limite dei risultati

Per evitare un consumo eccessivo di memoria, il numero di righe visualizzate deve essere limitato.

Impostazione predefinita:

**Massimo 1.000 righe visualizzate per query.**

Il limite deve essere configurabile dall'utente, con un massimo consentito di 10.000 righe.

Il limite deve essere applicato durante il recupero dei risultati, non soltanto dopo aver caricato l'intero result set in memoria.

L'applicazione deve indicare chiaramente quando il numero di risultati visualizzati è stato limitato.

Non è necessario implementare paginazione remota, esportazione di dataset completi o streaming avanzato in questa versione.

#### 8.2 Copia dei risultati

Prevedere:

- Copia della cella selezionata.
- Copia delle celle selezionate.
- Copia delle righe selezionate.
- Formato tabulato compatibile con l'incolla in Excel, LibreOffice Calc e strumenti equivalenti.

La copia deve mantenere un formato coerente per righe e colonne.

Non è richiesta l'esportazione in CSV o Excel per la prima versione.

---

### 9\. Interfaccia grafica

L'interfaccia deve essere minimale, pulita e funzionale.

Non deve cercare di replicare integralmente DBeaver.

La finestra principale deve essere organizzata in tre aree.

#### 9.1 Barra superiore

Deve contenere:

- Indicatore dello stato della connessione.
- Pulsante Configurazione.
- Pulsante Connetti/Disconnetti.
- Pulsante Esegui.
- Pulsante Interrompi, quando applicabile.

#### 9.2 Editor SQL

Deve occupare la parte centrale superiore della finestra.

Deve avere dimensioni sufficienti per scrivere e leggere query di lunghezza medio-breve.

#### 9.3 Pannello dei risultati

Deve occupare la parte inferiore della finestra.

Deve contenere:

- Tabella dei risultati.
- Numero di righe restituite.
- Tempo di esecuzione.
- Messaggi di errore o stato.

L'editor e il pannello dei risultati devono essere separati da un divisore ridimensionabile.

La finestra deve ricordare, ove possibile, le dimensioni e la posizione dell'ultima sessione.

La configurazione della connessione deve essere accessibile tramite una finestra separata o un pannello dedicato.

Non devono essere implementati:

- Alberi di navigazione dei database.
- Esplorazione completa di schemi e tabelle.
- Designer grafici di query.
- Gestione di più tab SQL.
- Dashboard.
- Sistema di plugin.
- Gestione di utenti MySQL.
- Strumenti di amministrazione.
- Temi personalizzabili complessi.

La priorità è ridurre al minimo il numero di elementi visivi e i passaggi necessari per eseguire una query.

---

### 10\. Gestione degli errori

Gli errori devono essere gestiti in maniera esplicita.

Categorie principali:

- Parametri di connessione mancanti.
- Connessione fallita.
- Credenziali non valide.
- Database non accessibile.
- Query SQL non valida.
- Query non ammessa dalla modalità read-only.
- Timeout.
- Interruzione dell'esecuzione.
- Errore durante il recupero dei risultati.
- Errore durante la lettura o scrittura della configurazione.
- Errore di accesso al portachiavi del sistema operativo.

Ogni errore deve essere mostrato con un messaggio comprensibile.

Quando possibile, il messaggio deve indicare come risolvere il problema.

Esempio:

"Query non consentita: questa applicazione supporta esclusivamente operazioni di lettura."

Non mostrare informazioni sensibili.

Non registrare password o segreti nei log.

Gli errori tecnici possono essere salvati in un file di log locale con rotazione e dimensione massima limitata.

---

### 11\. Architettura del software

Il codice deve essere organizzato in moduli separati, con responsabilità chiare.

Struttura suggerita:

```
mysql-quick-query/
├── src/
│   └── mysql_quick_query/
│       ├── main.py
│       ├── ui/
│       │   ├── main_window.py
│       │   ├── connection_dialog.py
│       │   ├── sql_editor.py
│       │   └── results_table.py
│       ├── database/
│       │   ├── connection_manager.py
│       │   ├── query_executor.py
│       │   └── readonly_validator.py
│       ├── config/
│       │   ├── config_manager.py
│       │   └── secret_storage.py
│       └── utils/
│           └── logging_config.py
├── tests/
│   ├── test_readonly_validator.py
│   ├── test_connection_manager.py
│   ├── test_query_executor.py
│   └── test_config_manager.py
├── packaging/
├── requirements.txt
├── pyproject.toml
├── README.md
└── LICENSE
```

La struttura è indicativa e può essere adattata, purché venga mantenuta la separazione tra interfaccia, logica applicativa, accesso al database e gestione dei segreti.

Non introdurre livelli architetturali o astrazioni non necessari.

---

### 12\. Prestazioni e affidabilità

L'applicazione deve essere leggera e adatta a un utilizzo quotidiano.

Requisiti:

- Avvio rapido su hardware moderno.
- Nessun servizio server locale obbligatorio.
- Nessun database locale obbligatorio.
- Nessuna dipendenza da servizi cloud.
- Nessuna telemetria.
- Nessun account utente applicativo.
- Nessuna verifica obbligatoria online.
- Una sola connessione configurata.
- Una sola query attiva alla volta.
- Nessun blocco della GUI durante l'esecuzione SQL.
- Gestione efficiente dei risultati entro i limiti stabiliti.

L'applicazione deve funzionare anche quando il computer è offline, purché sia possibile raggiungere il server MySQL attraverso la rete disponibile.

---

### 13\. Test automatici

L'agente deve implementare test automatici per le funzionalità critiche.

#### 13.1 Test del validatore SQL

Verificare che vengano accettate le query di lettura previste:

- `SELECT * FROM users`
- `SELECT id, name FROM users WHERE active = 1`
- `SELECT COUNT(*) FROM orders`
- Query con JOIN.
- Query con sottoquery.
- Query con CTE, se esplicitamente supportate.
- Query con commenti SQL innocui.
- Query con stringhe contenenti parole come `UPDATE` o `DELETE`.

Verificare che vengano rifiutate:

- `INSERT`.
- `UPDATE`.
- `DELETE`.
- `REPLACE`.
- `CREATE`.
- `ALTER`.
- `DROP`.
- `TRUNCATE`.
- `GRANT`.
- `REVOKE`.
- `CALL`.
- Istruzioni multiple separate da `;`.
- Query con commenti utilizzati per tentare di aggirare i controlli.
- Istruzioni non riconosciute.
- Query con più istruzioni nascoste in commenti o stringhe, quando il parser non può determinarne in sicurezza la struttura.

I test devono verificare il comportamento del parser, non limitarsi a cercare parole vietate nel testo.

#### 13.2 Test della GUI

Verificare:

- Apertura della finestra principale.
- Apertura della configurazione.
- Validazione dei campi obbligatori.
- Gestione della connessione fallita.
- Esecuzione di una query valida.
- Visualizzazione dei risultati.
- Visualizzazione degli errori.
- Gestione dei timeout.
- Risposta dell'interfaccia durante una query.
- Copia dei risultati.
- Chiusura corretta dell'applicazione.

#### 13.3 Test del database

Prevedere test d'integrazione eseguibili contro un'istanza MySQL di test.

I test d'integrazione devono verificare sia le query consentite sia il rifiuto delle operazioni non ammesse.

Non eseguire test distruttivi su database reali.

Quando possibile, utilizzare un ambiente MySQL isolato, predisposto automaticamente per i test.

---

### 14\. Packaging e distribuzione

Il progetto deve includere procedure riproducibili per generare i pacchetti destinati alle piattaforme supportate.

#### Linux

Generare un pacchetto AppImage, se compatibile con le dipendenze selezionate.

L'applicazione deve essere avviabile senza installare manualmente Python o le librerie del progetto.

Documentare eventuali dipendenze di sistema necessarie.

#### macOS

Generare un'applicazione `.app` e distribuirla come `.dmg`.

Prevedere la gestione delle dipendenze Qt e MySQL necessarie.

Documentare i requisiti relativi a firma del codice e notarizzazione Apple.

Se non sono disponibili certificati per la firma, documentare chiaramente le limitazioni della distribuzione non firmata e le procedure per i test locali.

Non dichiarare la compatibilità con Apple Silicon e Intel senza averla verificata sulle architetture interessate.

#### Automazione

Configurare una pipeline CI/CD che:

- Esegua i test automatici.
- Verifichi gli errori di linting e i controlli statici previsti.
- Generi gli artefatti per le piattaforme supportate.
- Conservi i pacchetti prodotti come artefatti della build.

Le build macOS devono essere eseguite in un ambiente compatibile con macOS.

---

### 15\. Documentazione

Il repository deve contenere un README che spieghi:

- Scopo dell'applicazione.
- Funzionalità disponibili.
- Piattaforme supportate.
- Requisiti minimi.
- Procedura di installazione.
- Procedura di avvio.
- Modalità di configurazione della connessione.
- Modalità di esecuzione delle query.
- Limiti della versione.
- Gestione della password.
- Procedura per predisporre un account MySQL di sola lettura.
- Procedura per compilare il progetto dai sorgenti.
- Procedura per generare i pacchetti Linux e macOS.
- Limitazioni note.

La documentazione deve essere sufficiente a permettere a uno sviluppatore di compilare e distribuire il software senza dover ricostruire le decisioni progettuali dal codice.

---

### 16\. Funzionalità escluse dalla prima versione

Non implementare:

- Supporto PostgreSQL, SQLite, SQL Server o altri database.
- Connessioni multiple.
- Gestione di più profili.
- Browser visuale di database e tabelle.
- Modifica dei dati.
- Inserimento, aggiornamento o cancellazione di record.
- Creazione o modifica di tabelle.
- Editor visuale di query.
- Autocompletamento SQL avanzato.
- Cronologia persistente delle query.
- Salvataggio di query preferite.
- Gestione degli utenti e dei permessi MySQL.
- Esportazione avanzata.
- Sincronizzazione cloud.
- Collaborazione tra utenti.
- Plugin.
- Sistema di aggiornamento automatico.
- Telemetria.

Queste funzionalità potranno eventualmente essere valutate in versioni successive.

Non devono essere introdotte spontaneamente dall'agente AI coder.

---

### 17\. Criteri di accettazione

Il progetto può essere considerato completato quando tutti i seguenti requisiti sono soddisfatti.

**Configurazione**

- [ ]È possibile inserire una singola configurazione MySQL dalla GUI.
- [ ]È possibile testare la connessione.
- [ ]La configurazione viene salvata e ripristinata al successivo avvio.
- [ ]La password non viene memorizzata in chiaro.
- [ ]È possibile modificare la configurazione.

**Connessione**

- [ ]È possibile connettersi a un server MySQL valido.
- [ ]Gli errori di connessione vengono gestiti correttamente.
- [ ]È possibile disconnettersi e riconnettersi.

**Editor**

- [ ]È possibile scrivere e modificare query SQL.
- [ ]L'editor presenta un'evidenziazione sintattica di base.
- [ ]È possibile eseguire la selezione o l'intero contenuto dell'editor.
- [ ]È possibile avviare una query tramite pulsante o scorciatoia.

**Sicurezza**

- [ ]Le query non ammesse vengono rifiutate prima dell'esecuzione.
- [ ]Le istruzioni multiple vengono rifiutate.
- [ ]Il validatore SQL è coperto da test automatici.
- [ ]La documentazione spiega come utilizzare un account MySQL con privilegi di sola lettura.
- [ ]La connessione non utilizza privilegi amministrativi per impostazione predefinita.
- [ ]Password e segreti non compaiono nei log.

**Risultati**

- [ ]I risultati vengono mostrati in una tabella non modificabile.
- [ ]I valori NULL sono distinguibili dai valori vuoti.
- [ ]È possibile copiare celle e righe.
- [ ]Il limite massimo dei risultati viene applicato durante il recupero dei dati.
- [ ]Vengono mostrati il numero di righe caricate e il tempo di esecuzione.

**Affidabilità**

- [ ]La GUI non si blocca durante l'esecuzione di una query.
- [ ]I timeout vengono gestiti.
- [ ]È possibile interrompere una query, nei limiti delle funzionalità del driver.
- [ ]La chiusura dell'applicazione rilascia correttamente le risorse.

**Distribuzione**

- [ ]Il progetto include istruzioni di compilazione.
- [ ]È disponibile un pacchetto avviabile su Linux.
- [ ]È disponibile un pacchetto avviabile su macOS.
- [ ]Le procedure di build sono documentate e riproducibili.

**Test**

- [ ]I test automatici vengono eseguiti con successo.
- [ ]I test d'integrazione contro MySQL sono disponibili.
- [ ]Non sono presenti errori bloccanti noti.

---

### 18\. Piano di implementazione richiesto all'agente AI coder

Procedere per fasi, mantenendo ogni fase funzionante e verificabile.

**Fase 1 — Struttura e GUI**

- Creare il progetto.
- Configurare le dipendenze.
- Implementare la finestra principale.
- Implementare la finestra di configurazione.
- Verificare l'avvio su Linux e macOS.

**Fase 2 — Connessione MySQL**

- Implementare il connection manager.
- Implementare test di connessione.
- Implementare persistenza della configurazione.
- Implementare l'archiviazione sicura della password.

**Fase 3 — Validazione SQL**

- Selezionare un parser SQL adatto a MySQL.
- Implementare la modalità di sola lettura.
- Definire esplicitamente le istruzioni ammesse.
- Scrivere i test automatici del validatore.
- Verificare che i casi ambigui vengano rifiutati.

**Fase 4 — Esecuzione e risultati**

- Implementare l'esecuzione asincrona.
- Implementare timeout e gestione degli errori.
- Implementare il recupero limitato dei risultati.
- Implementare la tabella.
- Implementare le funzioni di copia.

**Fase 5 — Test e hardening**

- Completare i test unitari.
- Eseguire i test d'integrazione MySQL.
- Verificare la gestione dei segreti.
- Verificare la gestione delle query non ammesse.
- Correggere i problemi rilevati.

**Fase 6 — Distribuzione**

- Configurare il packaging Linux.
- Configurare il packaging macOS.
- Preparare la pipeline CI/CD.
- Verificare l'avvio dei pacchetti generati.
- Completare la documentazione.

Al termine di ogni fase, fornire un riepilogo delle modifiche, dei test eseguiti e degli eventuali problemi residui.

Non considerare una fase completata soltanto perché il codice è stato generato: deve essere verificata attraverso test o prove di esecuzione.

---

### 19\. Istruzioni finali per l'agente

Implementa il progetto seguendo queste specifiche, privilegiando un codice semplice, leggibile, modulare e facile da mantenere.

Non aggiungere funzionalità non richieste.

Non introdurre dipendenze complesse se una soluzione più semplice soddisfa gli stessi requisiti.

Prima di implementare componenti critici, verifica la compatibilità delle librerie scelte con le piattaforme target.

Presta particolare attenzione a:

1. Sicurezza delle query.
2. Gestione sicura della password.
3. Responsività dell'interfaccia.
4. Limitazione del consumo di memoria.
5. Compatibilità Linux/macOS.
6. Riproducibilità delle build.

Non considerare sufficiente il solo blocco delle parole chiave SQL vietate: il controllo deve essere basato sulla struttura delle istruzioni e deve essere affiancato dall'utilizzo di un account MySQL con privilegi minimi.

Se una funzionalità presenta limiti tecnici o non può essere implementata in sicurezza, documenta il problema e proponi la soluzione più semplice che mantenga gli obiettivi del progetto.

**Risultato finale atteso:** un client desktop MySQL minimale, installabile su Linux e macOS, con una sola connessione configurabile, un editor SQL, esecuzione di query di lettura, risultati tabellari copiabili e una modalità di funzionamento sicura per l'utilizzo quotidiano.

