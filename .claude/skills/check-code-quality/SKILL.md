---
name: check-code-quality
description: Controllo completo del codice di QueryLean (src, tests, packaging) per trovare e correggere codice duplicato, funzioni non utilizzate, regole di coding di CLAUDE.md non rispettate, commenti e docstring non aggiornati e falle di sicurezza. Usare quando l'utente chiede un audit, una revisione generale o /check-code-quality.
---

# /check-code-quality

Controlla **tutto** il codice del progetto (`src/`, `tests/`, `packaging/`, script
shell e workflow CI) per individuare e **correggere**:

1. codice duplicato;
2. funzioni non utilizzate;
3. regole di coding non rispettate;
4. commenti / docstring non aggiornati;
5. falle di sicurezza.

Le regole di riferimento sono quelle di `CLAUDE.md` (stile, invarianti, sicurezza):
rileggilo prima di iniziare, perché è la fonte di verità e può essere cambiato
dall'ultima esecuzione.

## Vincoli (sempre validi)

- **Mai** modificare, ricreare, rinominare o cancellare `.version`: si legge e basta.
  Se una correzione sembra richiederlo, fermati e chiedi.
- **Mai** leggere, stampare o includere `.env`.
- Niente commit, tag, merge o push: le modifiche restano nel working tree.
- Non aggiungere funzionalità né cambiare comportamento visibile all'utente: si
  correggono difetti, si toglie codice morto, si aggiorna la documentazione. Se una
  correzione cambia il comportamento (anche per sicurezza), descrivila e chiedi
  prima di applicarla, a meno che non sia una falla evidente.
- Non rilassare il validatore read-only né le barriere di sicurezza per far passare
  un test.

## Procedura

### 0. Punto di partenza

```bash
cat .version                       # solo lettura: versione su cui si lavora
git status --short                 # modifiche già presenti (non vanno perse)
git log --oneline -5
.venv/bin/ruff check src tests packaging
.venv/bin/ruff format --check src tests packaging
.venv/bin/pytest -q
```

Annota lo stato iniziale (numero di test, errori di lint già presenti) per poterlo
confrontare alla fine. Se ci sono modifiche non committate, lavora sopra di esse
senza scartarle.

### 1. Codice duplicato

- Cerca blocchi ripetuti tra classi diverse e nella stessa classe: costruzione di
  dialog e `QMessageBox`, gestione degli errori `ConfigError`/`DatabaseError`,
  quoting e escape (`MySqlIdentifier`, `MySqlLiteral`, `MaskTemplate`), scansione
  di stringhe/commenti (`MySqlLexer`, `SqlScanner`, `MaskTemplate.__regions`),
  messaggi utente identici scritti più volte, helper dei test.
- Strumenti utili: `grep -rn` sulle righe sospette; confronto dei metodi con lo
  stesso nome o la stessa firma; per i messaggi,
  `grep -rhoE '"[^"]{25,}"' src | sort | uniq -c | sort -rn | head`.
- Correggi estraendo in un metodo `@staticmethod` della classe del dominio giusto
  (regola "nessuna funzione a livello di modulo"), o riusando l'helper esistente.
- **Eccezione voluta**: il lexer del validatore (`MySqlLexer`) e lo scanner
  tollerante dell'autocompletamento (`SqlScanner`) sono separati per scelta
  (vedi `CLAUDE.md`): non unificarli.

### 2. Funzioni non utilizzate

- Per ogni metodo, property, costante di classe e classe definita in `src/`
  verifica che sia usata altrove (in `src/` o, per l'API pubblica pensata per i
  test, in `tests/`). Un modo rapido: estrai i nomi con `ast` in uno script
  temporaneo nella scratchpad (senza `print`: scrivi l'esito su file o usa
  `sys.stdout.write`), poi `grep -rnw` di ciascun nome.
- Attenzione ai falsi positivi: override Qt (`keyPressEvent`, `rowCount`, …), slot
  collegati per nome, `__eq__`/`__hash__`/`__repr__`, entry point
  (`Application.run`, `[project.gui-scripts]`), metodi chiamati da
  `packaging/querylean.spec`, attributi letti dai test.
- Codice usato **solo** dai test: valuta se è API di test legittima (accessor dei
  widget per pytest-qt) o codice morto; in quest'ultimo caso rimuovilo insieme ai
  test che lo coprono.
- Controlla anche import inutilizzati, fake in `tests/fakes/` e fixture in
  `tests/support/` non più usati.

### 3. Regole di coding (`CLAUDE.md` → "Stile del codice")

Verifica una per una, su `src`, `tests` e `packaging`:

- una sola classe per file `.py`, nome del file = classe in snake_case
  (eccezioni: `__init__.py` solo docstring, `__main__.py`, `conftest.py`,
  `packaging/launcher.py`);
- nessuna funzione, variabile o alias di tipo a livello di modulo;
- attributi d'istanza `self.__nome` esposti con `@property`; metodi interni
  `__metodo`; value object immutabili senza setter;
- package per responsabilità (una classe nel package del suo dominio);
- stringhe: niente f-string, `%`, `+` tra stringhe, concatenazione implicita;
  testi lunghi con `+=` e `.format()` alla fine (`tests/test_string_style.py` ne
  copre una parte, non tutto: controlla anche a mano i casi multi-riga);
- logger del progetto con segnaposto `{}`, mai `%s`, mai `print`;
- righe ≤ 80 colonne anche in docstring, commenti, script shell e `.spec`; mai
  `# noqa: E501`;
- testi rivolti all'utente, docstring, commenti e log in inglese;
- test: una classe `Test…` per file, fixture come metodi, fake in `tests/fakes/`
  (una classe per file), basi in `tests/support/`;
- override Qt con `# noqa: N802`.

Per le regole non coperte dai test, valuta se aggiungere un controllo
automatico in un test esistente (es. `tests/test_string_style.py`), senza
inventare regole nuove.

### 4. Commenti e docstring

- Ogni docstring di modulo, classe e metodo pubblico deve descrivere il
  comportamento **attuale**: parametri, valori di ritorno, eccezioni sollevate,
  segnali emessi. Confrontale con il codice, soprattutto per le classi toccate
  negli ultimi commit (`git log --stat -10`).
- Cerca riferimenti a cose che non esistono più: nomi di metodi/classi/segnali
  (`grep -rnw` su ogni identificatore citato tra backtick), versioni ("fino alla
  1.x", "fase successiva"), comportamenti cambiati, TODO superati.
- Verifica anche la documentazione: `CLAUDE.md` (architettura e invarianti),
  `README.md` e `README_ITA.md`. I due README devono restare **allineati** (stesse
  sezioni, stesso contenuto): ogni correzione va su entrambi.
- Nessun numero di versione scritto fuori da `.version` (anche nei commenti).

### 5. Falle di sicurezza

Controlla gli invarianti di sicurezza di `CLAUDE.md` e cerca regressioni:

- **Sola lettura**: ogni query arriva al server solo tramite `QueryExecutor`
  (validatore incluso); nessun SQL fuori dal validatore; i segnalibri e le
  maschere passano da `bookmark_requested`; il testo inviato è quello originale.
  Il validatore resta fail-closed (eccezioni = rifiuto).
- **Maschere**: un valore non diventa mai SQL (letterali tipizzati, escape dentro
  gli apici), niente segnaposto per nomi o SQL libero, `${` malformato = errore.
- **Identificatori e letterali** nelle query costruite dall'app solo tramite
  `MySqlIdentifier.quote` / `MySqlLiteral.quote`.
- **Opzioni di connessione**: niente `MULTI_STATEMENTS`/`LOCAL_FILES`,
  `use_pure=True`, sessione READ ONLY verificata, `NO_BACKSLASH_ESCAPES` rimosso,
  controllo dei grant fail-closed.
- **Segreti**: password mai in file, log, messaggi, `repr`; registrata con
  `LogManager.register_secret()`; righe dei grant mai nel log.
- **File**: configurazioni, segnalibri ed export scritti con
  `PrivateFile`/`PrivateJsonFile` (0600, atomici); file danneggiati mai
  sovrascritti; input dei JSON trattato come non fidato (`from_dict`).
- **Testo non fidato nei widget**: tooltip con `SafeText.tooltip`, `QLabel` con
  testo variabile in `PlainText`, `QMessageBox` con escape o `PlainText`, celle
  Excel sempre stringa.
- **Thread**: nessuna operazione di database nel thread GUI.
- **Packaging/CI**: nessun segreto nei workflow, versioni pinnate, nessun
  download non verificato, `.env` escluso dal bundle.

Per ogni falla trovata aggiungi un test che la riproduce (che fallisce prima della
correzione) e poi correggi.

### 6. Verifica finale

```bash
.venv/bin/ruff format src tests packaging
.venv/bin/ruff check src tests packaging
.venv/bin/ruff format --check src tests packaging
.venv/bin/pytest -q
.venv/bin/python -m querylean --smoke-test
git diff --stat
```

Tutto deve essere pulito e i test non devono diminuire (salvo test di codice morto
rimosso, da dichiarare). Se una correzione tocca la GUI, verificala anche con uno
screenshot offscreen (`QT_QPA_PLATFORM=offscreen`, `widget.grab().save(...)`) da
uno script nella scratchpad.

## Rapporto all'utente

Alla fine rispondi in italiano con un riepilogo per categoria (le cinque sopra):

- per ogni problema: file e riga (`percorso:riga`), cosa non andava, come è stato
  corretto;
- problemi trovati ma **non** corretti (perché cambierebbero il comportamento,
  richiedono una decisione o sono fuori perimetro), con una proposta;
- esito di lint, test (numero prima/dopo) e smoke test;
- ricorda che le modifiche non sono committate.

Se una categoria non ha problemi, dillo esplicitamente invece di ometterla.
