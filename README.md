# QueryLean

*English · [Italiano](README_ITA.md)*

A minimal desktop client for **running read-only queries** against a MySQL database.
It is inspired by DBeaver, but deliberately reduced to the essentials: saved connections, one
at a time, a SQL editor and a table of copyable results.

## Features

- Several saved MySQL connections, each with an optional name, managed from the **Connections** menu. One is used at a time, and the connection can be tested before saving it.
- The password is kept in the operating system keychain, never in plain text.
- SQL editor with:
  - line numbers;
  - highlighting of keywords, strings, numbers and comments;
  - execution with `Ctrl+Enter` (Linux) or `Cmd+Enter` (macOS);
  - [autocompletion](#autocompletion) of tables, columns, aliases, keywords and functions with `Ctrl+Space`, also opening by itself while typing.
- A connection uses one database or [all the databases](#all-the-databases) the account can access.
- Side bar with databases, tables and views you have access to: a click on a table prepares `SELECT * FROM <table> LIMIT 1;` in the editor and shows its columns (type, keys, comments).
- Bookmarked queries: a query saved with a name for one connection can be run again from the **Bookmarked queries** menu, only on that connection.
- Only read statements are allowed (`SELECT`, `WITH … SELECT`, `UNION`, `SHOW`, `DESCRIBE`/`DESC`, `EXPLAIN SELECT`). Every query goes through a parser-based validator.
- On connection the account privileges are checked database by database: a database the account can change is refused until you accept it in [caution mode](#caution-mode).
- Queries run outside the GUI thread, with an activity indicator, timeouts and a blinking **Stop** button that appears only when a query takes more than a second.
- Read-only results table:
  - `NULL` is distinct from the empty string;
  - resizable columns;
  - copy of cells or rows as tab-separated text, ready to paste into Excel and LibreOffice Calc;
  - export of the result to Excel (`.xlsx`), CSV or JSON.
- The row limit (default 1,000, maximum 10,000) is enforced while fetching the data.
- Window, splitter and side bar sizes are remembered between sessions.
- No telemetry, no cloud services, no local database.

## Supported platforms

| Platform | Package | Status |
| --- | --- | --- |
| Linux x86_64 (Ubuntu 22.04+ or equivalents with glibc ≥ 2.35) | AppImage | Built and smoke-tested in CI |
| macOS Apple Silicon (arm64), macOS 12+ | `.dmg` | Built and smoke-tested in CI (`macos-15` runner) |
| macOS Intel (x86_64), macOS 12+ | `.dmg` | Built and smoke-tested in CI (`macos-15-intel` runner) |

macOS compatibility should be considered confirmed only once the corresponding CI pipeline passes. Windows is not supported.

## Technology stack

| Component | Choice | Reason |
| --- | --- | --- |
| Language | Python 3.11+ | SQL logic that is easy to maintain |
| GUI | PySide6-Essentials (Qt 6) | Native GUI on Linux and macOS. The *Essentials* package leaves out WebEngine and the other unneeded modules, so the packages are smaller |
| Driver | mysql-connector-python (pure Python implementation) | Needs no installed MySQL client. Gives control over multi-statements and LOCAL INFILE |
| SQL parser | sqlglot (MySQL dialect) | Pure Python parser, used as the second layer of the validator |
| Secrets | keyring | Secret Service on Linux, Keychain on macOS |
| Excel export | openpyxl | Writes `.xlsx` files without Excel or LibreOffice; pure Python, MIT license |
| Packaging | PyInstaller → AppImage / `.deb` / `.app` + `.dmg` | End users do not have to install any runtime |
| Tests | pytest, pytest-qt | |

## Installation (end users)

- **Ubuntu/Lubuntu 24.04 (`.deb`)**: `sudo apt install ./querylean-<version>-amd64.deb`. QueryLean appears in the applications menu (Development section) and can also be started from a terminal with `querylean`. Remove it with `sudo apt remove querylean`.
- **Linux (AppImage)**: download `querylean-<version>-x86_64.AppImage`, make it executable (`chmod +x`) and run it. It needs FUSE 2: the package is `libfuse2t64` on Ubuntu/Lubuntu 24.04 and `libfuse2` on 22.04. Alternatively, run `./querylean-….AppImage --appimage-extract-and-run`.
- **macOS**: open the `.dmg` and drag *QueryLean* into *Applications*. The package is not signed with a Developer ID certificate (see [Signing and notarization](#signing-and-notarization-macos)): on first launch use *right-click → Open*, or run `xattr -dr com.apple.quarantine "/Applications/QueryLean.app"`.

### System requirements

- **Linux**: a keychain service compatible with *Secret Service* (GNOME Keyring, KWallet ≥ 5.97 or KeePassXC with the integration enabled) to store the password. Without a keychain the application still works, but the password must be entered again at every start. The basic graphics libraries (`libegl1`, `libgl1`, `libxkbcommon0`, `libfontconfig1`) are also needed; they are normally already present on an Ubuntu desktop.
- **macOS**: no additional requirements; the system Keychain is used.

## Usage

The toolbar contains, in order: **Run** (▶), **Save query** (☆) and **Bookmarked queries** (drop-down menu), both enabled only while connected, **Export** (drop-down menu, enabled when there is a result), **Connect**/**Disconnect**, **Connections** (drop-down menu) and **About** (version, author, license). The connection state is shown at the bottom right. The user interface is in English. On the left, for the whole height of the window, there is the **Tables** side bar.

While a query runs, an activity bar and the text of the query appear below the results. If the query is still running after one second, a red **Stop** button (■) appears next to the activity bar and blinks until the query ends: a click interrupts it. Quick queries never show it.

1. **Connections** → **New connection…**: fill in name (optional), host, port, database (or check "All the databases the account can access"), username, password and timeouts, then use **Test connection** and **Save**. Saving does not open the connection (see [Connections](#connections)).
2. **Connect** opens the active connection, the one checked in the **Connections** menu: the state goes from *Disconnected* to *Connecting* and then to *Connected* or *Connection error*. If the password is not in the keychain, it is asked for.
3. Write the query, helped by the [autocompletion](#autocompletion), and press **Run** or `Ctrl/Cmd+Enter`. Alternatively click a table in the side bar (see [Table side bar](#table-side-bar)). Below the results you see rows and time, then "Query executed:" followed by the query just executed, on one line. Beyond 160 characters the query is cut with "…"; the full text is in the message tooltip.
4. Select cells or rows and press `Ctrl/Cmd+C`. The context menu also offers the "with headers" and "whole rows" variants.
5. To save the result to a file open the **Export** menu and choose the format (see [Export](#export)).

### Connections

The **Connections** button opens a menu with **New connection…** and, below it, the saved connections in alphabetical order. Each connection is shown with its name or, when the name is empty, as `<user>@<host>/<database>` (`<user>@<host>/*` for all the databases). The active connection is checked.

Each item has a sub-menu:

- **Connect**: makes it active and connects. If another connection is open, it is closed first.
- **Edit…**: opens the form with the saved values. If it is the connection in use, the changes apply from the next connection.
- **Delete…**: asks for confirmation, then deletes the connection file and its bookmarked queries. If it is the one in use, it is closed.

The toolbar **Connect** button uses the active connection; if none exists, it opens **New connection…**. A connection that has just been saved becomes active if you are not connected at that moment.

Each connection is a JSON file of its own (see [Local files](#local-files)) and never contains the password.

A connection with at least one database accepted in caution mode is shown in the menu as "<name> (caution mode)" (see [Caution mode](#caution-mode)).

### All the databases

In the connection form the **Database** field can be replaced by the checkbox "All the databases the account can access":

- with a database (checkbox off) the connection uses only that database, as in previous versions: the side bar shows it alone, already expanded, and the privilege check considers only it;
- with the checkbox on the connection covers every database listed by `SHOW DATABASES` (only those the account can access). The **Database** field becomes optional: if filled in, it is the active database at connection;
- the **active database** is the one unqualified names refer to (`SELECT * FROM users`). It is shown in bold in the side bar, and the state at the bottom right shows it as "db: <name>". A click on a database (or on one of its tables), or **Use as active database** in its context menu, makes it active. The application changes it with the MySQL protocol command `COM_INIT_DB`, not with SQL from the editor (`USE` is not a read query and stays forbidden); reconnections keep it;
- without an active database MySQL refuses unqualified names ("No database selected"): click a database first, or write `db.table`;
- with all the databases the queries prepared by the side bar always qualify the table (`` SELECT * FROM `shop`.`orders` LIMIT 1; ``), so they work whatever the active database is;
- the autocompletion proposes the databases after `FROM`/`JOIN` (inserted with their dot), the tables after `db.` and the columns after `db.table.`; the tables and columns of a database are read when it is expanded, made active or needed by the completion.

### Table side bar

After connecting, the **Tables** side bar shows a tree: databases (the configured one, or all the accessible ones), their tables and views (`SHOW FULL TABLES`, only those the account can access) and the columns. Views are in italics and the number of tables (or of databases) is shown at the bottom.

The database names show the write access of the account: **green** for the databases it can only read, **pink** with an orange warning icon (⚠) for those it can change (accepted in [caution mode](#caution-mode)). The tooltip lists the privileges. The access is computed from the grants read at connection, also for databases that appear after a reload.

- A **click** on a table (also a double click, or `Enter` on the selected one) replaces the editor content with `SELECT * FROM <table> LIMIT 1;`. The query is **not executed**: press **Run** to start it. The previous text can be restored with `Ctrl/Cmd+Z`.
- **Columns**: the same click expands the table and shows its columns in order, with the type on the right; the arrow alone expands or collapses it without touching the editor. Primary key columns are in bold with a yellow "P" badge; the tooltip shows the full definition (type, `NULL`/`NOT NULL`, key, default, extra, comment).
- A double click on a column, or `Enter`, replaces the editor content with `SELECT <column> FROM <table> LIMIT 1;`, not executed and undoable with `Ctrl/Cmd+Z`. A single click on a column does not touch the editor.
- **Shift + double click** on a column (or `Shift+Enter`) adds it to the columns of the prepared query: `SELECT * FROM <table> LIMIT 1;` becomes `SELECT <column> …`, then `SELECT <column>, <other column> …`. A column already in the list is not repeated; if the editor holds another text (a query on another table or written by hand), a new `SELECT <column> FROM <table> LIMIT 1;` replaces it. Each addition is undone with `Ctrl/Cmd+Z`.
- The context menu (right click) offers **Prepare SELECT** (tables), **Prepare SELECT of the column** and **Add to the SELECT** (columns), and **Copy name**.
- **Filter tables…** at the top shows only the tables whose name, or whose database name, contains the text (case insensitive); the bottom line then shows "N of M tables".
- The table name is always between backticks, with any inner backticks doubled, so names with spaces or reserved words work too.
- The ⟳ button reloads databases and tables, for example after a table has been created. On disconnection the tree is emptied.
- Reading the list goes through the validator, respects the query timeout and shows at most 10,000 items. An error (for example missing privileges) is shown in the side bar, without closing the connection.
- The columns of a database are read once, when its tables are, with a single query on `information_schema.COLUMNS` (through the validator, at most 10,000 columns); the tables left out, or whose listing failed, are read on demand with `SHOW FULL COLUMNS FROM <table>` when they are expanded or needed by the completion. A table whose columns cannot be read shows "No columns available." (the reason is in the tooltip).

### Autocompletion

The editor proposes what fits at the cursor, as in the major database tools:

- `Ctrl+Space` opens the proposals (on macOS with the physical **Control** key: `Cmd+Space` belongs to Spotlight). If only one proposal fits, it is inserted at once. `Ctrl/Cmd+Enter` still runs the query.
- The list also opens by itself while typing: right after a `.` and after the first letter of a table or column name (two letters where only keywords fit). It closes when the word is complete, when a space or punctuation is typed, or with `Esc`.
- `Enter` or `Tab` insert the selected proposal, the arrows and `PageUp`/`PageDown` move in the list, a click also inserts. The insertion replaces the whole word under the cursor and is undone with a single `Ctrl/Cmd+Z`.
- What is proposed depends on the position:
  - at the start: `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `EXPLAIN`;
  - after `FROM`/`JOIN`, `DESCRIBE` and `SHOW COLUMNS FROM`: tables, views and the `WITH` queries of the statement;
  - after a table: `JOIN` variants, `ON`, `WHERE`, `GROUP BY`, `ORDER BY`, `LIMIT`…;
  - in `SELECT`, `WHERE`, `ON`, `GROUP BY`, `ORDER BY`, `HAVING` and in function arguments: the columns of the tables of the statement (also those written after the cursor, so `SELECT | FROM users u` works), the aliases, then functions and keywords;
  - after `alias.` or `table.`: only the columns of that table; after `database.`: its tables;
  - after a value or a column: operators and clauses (`AND`, `OR`, `IN`, `LIKE`, `IS NULL`, `AS`, `ORDER BY`…).
- Each proposal shows a badge with its kind (`P` primary key, `c` column, `T` table, `V` view, `a` alias, `f` function, `k` keyword) and, on the right, the type and the table of a column. The tooltip of a column shows its full definition.
- Matching ignores case: first the names that start with the typed text, then those with a word (after `_`) that starts with it, then tables and columns that contain it.
- A column name present in more than one table of the statement is inserted qualified (`u.id`). Names with spaces, reserved words or special characters are inserted between backticks; keywords follow the case of the typed text (`sel` → `select`, `SEL` → `SELECT`); functions are inserted with their parentheses and the cursor inside.
- Nothing is proposed inside strings, comments, numbers, after `AS` and after `LIMIT`. Words that the validator rejects (`INSERT`, `UPDATE`, `DELETE`, …) and forbidden functions are never proposed.
- The columns of subqueries in `FROM` and of `WITH` queries are not known, so after their alias nothing is proposed.

### Bookmarked queries

A bookmarked query belongs to **one saved connection** and to the database it points to (`<user>@<host>:<port>/<database>`, or `/*` with all the databases).

- **Save query** saves the selection or, without a selection, the whole editor content. It asks for a name (at most 100 characters) and saves the query for the open connection. An existing bookmark with the same name (case insensitive) is replaced after confirmation. Only queries accepted by the validator can be saved: a write query is refused already at this step.
- The **Bookmarked queries** menu lists, in alphabetical order, only the queries of the open connection; the query text is in the tooltip. A click puts the query in the editor (undoable with `Ctrl/Cmd+Z`) and runs it at once, through the validator like any other query.
- **Bookmarked queries** → **Delete** deletes a bookmark, after confirmation.
- A bookmark is never run on another connection: the menu shows only those of the open connection, and before running one the database thread checks that the open session points to the same user, host, port and database. Another saved connection pointing to the same database has its own bookmarks.
- If a connection is edited to point to another host, port, database or user, its old bookmarks are no longer shown; they come back if the previous values are restored.
- The bookmarks are stored in a JSON file per connection (see [Local files](#local-files)).

### Execution rules

- If text is selected in the editor, **only the selection** is run.
- Without a selection, **the whole content** of the editor is run.
- An empty editor (or one with only whitespace) runs nothing.
- **Only one statement** is allowed; a trailing `;` is tolerated. With several statements the query is rejected: to run one of them, select it.
- A query that is not a read (for example `UPDATE`, `DELETE`, `INSERT`), or that the validator rejects for any other reason, is not sent to the server: besides the red message below the results, a **Read queries only** dialog explains that only read queries are run and why the query was refused. In caution mode it also lists the databases the account could change. The dialog does not block the application and appears only when a query is refused, never on connection.

### Copy

Copied cells are separated by tabs and rows by newlines. The selection is copied as a rectangle, and unselected cells inside it stay empty. A `NULL` becomes an empty cell, while tabs and newlines inside values become spaces, so the grid stays aligned. Binary values that are not valid UTF-8 are shown in hexadecimal (`0x…`, truncated to 64 bytes).

### Export

**Export** saves the result shown in the table to a file, with the column headers. The button opens a menu:

- **Excel (.xlsx)**, **CSV (.csv)**, **JSON (.json)**: the save dialog offers only that format. If the name lacks its extension, it is added.
- **Export…**: the save dialog offers every format. The extension of the name (`.xlsx`, `.csv`, `.json`) decides or, when missing, the format selected in the dialog.

- **The rows already loaded** are exported, that is at most the configured row limit: the query is not run again. If the result was truncated, the final message says so.
- The file is written in a separate thread, so the window stays usable. It is first written to a temporary file in the same folder and then renamed: an existing file is replaced only by a complete export.
- The file is readable only by your user (permissions `0600`), because it may contain confidential data.
- Exporting is still possible after disconnecting.

| Format | Content |
| --- | --- |
| Excel (`.xlsx`) | One sheet, "Result", with a bold, frozen header row. Numbers, booleans, dates and date-times are native Excel values. Text never becomes a formula, even when it starts with `=`. Values Excel would alter stay text: integers and DECIMAL values with more than 15 significant digits, dates before 1900, `TIME` values. `NULL` and the empty string are both empty cells. Control characters Excel does not allow become `�`; cells longer than 32,767 characters are cut and the final message counts them |
| CSV (`.csv`) | UTF-8, comma separator, header row. Fields are quoted only when needed, and newlines inside values are kept. `NULL` becomes an empty field, as in the copy |
| JSON (`.json`) | UTF-8, an array with one object per row, keyed by column name. `NULL` becomes `null`, while integers, floating-point numbers and booleans stay numbers and booleans. DECIMAL values become strings, so that no digit is lost. Repeated column names get a suffix (`id`, `id_2`) |

In every format binary values are written in full (UTF-8 text or hexadecimal `0x…`, without the 64-byte cut of the table), dates in ISO format and `TIME` values as `hh:mm:ss[.ffffff]`.

### Settings

| Setting | Default | Range |
| --- | --- | --- |
| Connection timeout | 5 s | 1–3600 s |
| Query timeout | 30 s | 1–3600 s |
| Maximum rows | 1000 | 1–10,000 |

## Security

### Read-only: two barriers

1. **MySQL account with minimal privileges (primary barrier).** On every connection the application reads the account privileges with `SHOW GRANTS` and refuses the connection if the account is not provably read-only (see [Privilege check](#privilege-check)). It never tries to create users or change permissions.
2. **Application validator (additional barrier)**, in `src/querylean/database/validation/` (`ReadOnlyValidator`). It is fail-closed: if a query cannot be classified with certainty, it is rejected. It works on three levels:
   - **MySQL lexer**: recognizes strings, identifiers and comments with the server's rules. It rejects multiple statements, executable comments `/*! … */`, hints `/*+ … */`, `--` not followed by whitespace (in MySQL that is not a comment), `:=` assignments, and unterminated strings and comments.
   - **Words and functions**: outside strings and comments it blocks the words of write, modify and administration statements (`INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `TRUNCATE`, `CREATE`, `DROP`, `ALTER`, `GRANT`, `INTO`, `LOCK`, `CALL`, `LOAD`, `PREPARE`, `EXECUTE`, `COMMIT`, `FLUSH`, `KILL`, …) wherever they appear: unquoted, qualified (`t.update`) or as quoted identifiers (`` `delete` ``). Only `REPLACE(…)` and `TRUNCATE(…)` are allowed, as read-only functions. Functions with side effects (`GET_LOCK`, `LOAD_FILE`, …) are blocked too.
   - **sqlglot parser**: requires exactly one statement of an allowed type, with no DML/DDL nodes, `SELECT … INTO` or `FOR UPDATE`/`LOCK IN SHARE MODE`.

   The original text is sent to the server, never regenerated SQL.

On top of these two barriers, the connection:

- is opened **without** the `CLIENT_MULTI_STATEMENTS` flag and with `LOCAL INFILE` disabled;
- sets `SET SESSION TRANSACTION READ ONLY` and reads back `@@SESSION.transaction_read_only` (`tx_read_only` on older servers): if the server does not confirm a read-only session, the connection is closed;
- removes `NO_BACKSLASH_ESCAPES` from the session `sql_mode`, so the server interprets strings the same way as the validator.

> The application does **not** promise an absolute read-only mode based on the GUI alone. For example, a stored function called in a `SELECT` could modify data if the account had the privileges to do so (the READ ONLY session blocks writes to permanent tables, not to temporary ones). This is why the constraint must be guaranteed by the MySQL account.

### Privilege check

On every connection, including **Test connection** and transparent reconnections, the application runs `SHOW GRANTS` and analyzes the result fail-closed:

- read privileges are only `USAGE`, `SELECT`, `SHOW VIEW` and `SHOW DATABASES`; any other privilege (`INSERT`, `ALL PRIVILEGES`, `EXECUTE`, `PROXY`, `WITH GRANT OPTION`, dynamic privileges such as `BACKUP_ADMIN`, …) makes the account "with write privileges";
- column privileges (`UPDATE (col)`) count like the others;
- role grants (`` GRANT `role` TO … ``), unrecognized lines or a failure of `SHOW GRANTS` make the account "not verified", and it is treated like one with write privileges;
- `REVOKE` lines (partial revokes) only remove privileges and are ignored;
- each privilege beyond reading applies to the database of its grant: `db.*`, `db.table`, `PROCEDURE db.name`. Database names in grants follow the MySQL wildcards (`%`, `_`, escaped with `\`) and match case-insensitively, so they never cover fewer databases than the server. Global grants (`*.*`), objects outside a database (`PROXY`) and unverified accounts apply to **every** database. `information_schema` is never writable.

The check covers the databases of the connection: the configured one, or all those listed by `SHOW DATABASES`. A database the account can change and that was not accepted in [caution mode](#caution-mode) is refused, with a message listing the databases and their privileges. Writes allowed only on other databases do not matter. The log records only the privilege names, never the grant lines (on MariaDB they can contain the password hash).

### Caution mode

**Caution mode** is accepted **database by database**, in the **New connection…**/**Edit…** form:

- **Test connection** lists, in red, the databases of the connection that the account can change, each with its privileges and a checkbox ("shop — INSERT, UPDATE"). Check every database you accept; the choice is saved with the connection and survives new tests;
- a writable database left unchecked makes the connection refused. If the privileges change (a new database, a new grant), the connection is refused until you accept the new databases with a new test;
- **nothing else changes**: the same validator applies (only read queries) and the session must be confirmed READ ONLY, otherwise the connection is closed;
- while connected, the state at the bottom right shows "CAUTION: write access (<databases>)" in red, the connection message lists the databases and their privileges, and in the side bar those databases are pink with a warning icon (the read-only ones are green);
- for the whole session the grey parts of the window (toolbar, side bar and status bar background, margins) turn pink, a constant reminder that the account can change some database; editor and tables keep their colors. The tint follows the system theme (a soft pink on light themes, a dark rose on dark ones) and disappears on disconnection;
- connections saved with caution mode by version 1.7 or earlier keep it for their database.

With a read-only account caution mode has no visible effect. Use it only when a SELECT-only account is not available.

### Setting up a read-only MySQL account

```sql
-- Run as an administrator. Replace name, host and password.
CREATE USER 'report_ro'@'%' IDENTIFIED BY 'a-strong-password';

-- SELECT only, only on the database you need:
GRANT SELECT ON database_name.* TO 'report_ro'@'%';

-- Alternatively, even more restrictive: single tables or dedicated views
-- GRANT SELECT ON database_name.report_view TO 'report_ro'@'%';

-- Optional: resource limits
ALTER USER 'report_ro'@'%' WITH MAX_USER_CONNECTIONS 3;
```

Recommendations:

- Never grant `ALL`, `SUPER`, `FILE`, `PROCESS`, `EXECUTE`, `CREATE ROUTINE` or global privileges (`*.*`).
- Restrict the host (`'report_ro'@'10.0.0.%'`) whenever possible.
- To limit the visible columns or rows, create **dedicated views** and grant `SELECT` only on them.
- Do not use `root` or administrative accounts. The application does not need them.

### Password

- It is stored in the operating system keychain under the service `querylean` with the key `user@host:port`. On Linux you can check it with `secret-tool search service querylean`.
- The key belongs to the MySQL account, not to the connection: several connections to the same account (for example to different databases) share the password. When the last connection using an account is deleted, its password is removed from the keychain.
- It is read from the keychain only when needed, that is when connecting or editing.
- It **never** appears in the configuration or connection files, or in the logs, which go through a redaction filter.
- Plain-text (`keyrings.alt`) or "fail" keyring backends are treated as unavailable. In that case the password is kept in memory only, for the session.
- If the keychain is locked or denies access, a message is shown and the password is asked for when connecting.

### Local files

| File | Linux | macOS |
| --- | --- | --- |
| Configuration: active connection, window (permissions 0600) | `~/.config/querylean/config.json` | `~/Library/Application Support/querylean/config.json` |
| Saved connections, one `<id>.json` file each (permissions 0600) | `~/.config/querylean/connections/` | `~/Library/Application Support/querylean/connections/` |
| Bookmarked queries, one `<connection id>.json` file per connection (permissions 0600) | `~/.config/querylean/bookmarks/` | `~/Library/Application Support/querylean/bookmarks/` |
| Log (rotation 1 MB × 3) | `~/.local/state/querylean/log/` | `~/Library/Logs/querylean/` |

Versions up to 1.2 had a single connection inside `config.json`. On the first start of the new version it is saved as the first connection, and its password in the keychain stays valid.

Users are never shown stack traces: technical details go to the log, without secrets.

## Timeouts and cancellation

- The **connection timeout** is passed to the driver (`connection_timeout`).
- The **execution timeout** works like this:
  - before every query the session `MAX_EXECUTION_TIME` is set, which the server applies to `SELECT`;
  - a client-side watchdog, once the timeout plus 2 seconds has expired, sends `KILL QUERY` from a separate connection. This also covers `SHOW`/`EXPLAIN` and servers that do not support `MAX_EXECUTION_TIME`, such as MariaDB.
- **Stop** (the blinking button below the results) sends `KILL QUERY` over the same separate connection.
- Known limits:
  - `KILL QUERY` requires the user to be allowed to terminate their own queries, which is always permitted on one's own sessions;
  - if the server is unreachable, the cancellation request fails after the connection timeout. The GUI stays responsive anyway, because the query runs in a separate thread;
  - a query for which only the transfer of results can be interrupted may end with a short delay.
- **Row limit**: at most *N+1* rows are read with an unbuffered cursor. If more exist, the session is closed without downloading the rest of the result set and reopened transparently for the next query.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"          # runtime + pytest, pytest-qt, ruff
python -m querylean              # run from the sources
ruff check src tests packaging   # lint, lines of at most 80 columns
ruff format src tests packaging  # formatting
pytest                           # unit + GUI (offscreen); integration if configured
```

On Ubuntu you need `python3-venv` and, for the GUI tests, the libraries listed in the requirements.

### Structure

Each file contains a single class; the full coding style rules are in `CLAUDE.md`.

```
src/querylean/
  app/          startup (Application), metadata (AppInfo), smoke test
  log/          application logger, rotating log, secret redaction
  config/       configuration model and JSON persistence
  bookmarks/    bookmarked queries per connection (QueryBookmark, BookmarkStore)
  completion/   autocompletion: tolerant scanner, statement analysis, proposals (CompletionEngine)
  security/     password in the keychain (abstract SecretStore, KeyringSecretStore)
  export/       Excel/CSV/JSON export (abstract ResultExporter)
  database/     errors/, connection/, execution/, schema/ (tables and columns), privileges/ (SHOW GRANTS check), validation/ (staged validator)
  ui/           main/, dialogs/, editor/, icons/, results/, sidebar/, worker/ (QThread thread)
tests/          one Test… class per file; fakes/ (test doubles), support/ (bases), integration/
packaging/      PyInstaller spec, AppImage/.deb/DMG scripts, desktop file, icon,
                third-party license generator, licenses/ (vendored license texts)
.github/workflows/ci.yml     lint, tests, artifact builds
```

### Integration tests

They are non-destructive tests against a dedicated test database, never against real databases.

```bash
sudo mysql < tests/integration/setup_test_db.sql   # creates querylean_test and the querylean_ro user (SELECT only)
QUERYLEAN_TEST_HOST=127.0.0.1 QUERYLEAN_TEST_USER=querylean_ro QUERYLEAN_TEST_PASSWORD=querylean_ro_password \
QUERYLEAN_TEST_DATABASE=querylean_test pytest tests/integration -v
```

They check allowed queries, types and `NULL`, the row limit, timeouts, cancellation, rejection of writes by the validator and, bypassing the validator, the server-side block (privileges and READ ONLY session). Without the `QUERYLEAN_TEST_*` variables they are skipped. In CI they use a `mysql:8.0` service container.

## Packaging

Builds must run on the target platform: PyInstaller does not cross-compile.

### Version

The QueryLean version is read **only** from the `.version` file in the project root (a single line). To change it, edit that file. It is read by:

- `pyproject.toml`, as a dynamic version;
- the build scripts, for the artifact names;
- the PyInstaller spec, which bundles it and uses it for `Info.plist` on macOS;
- the application at runtime, for the **About** window and the log.

After a change, when running from the sources, run `pip install -e .` again so that the package metadata reports the new version too.

The scripts share `packaging/common.sh`, which reads the version from `.version` and runs PyInstaller. `PYTHON=.venv/bin/python` selects the interpreter.

### Package size

The spec (`BundleSlimmer`, in `packaging/bundle_slimmer.py`) removes from the bundle what QueryLean never loads:

| Removed | Reason | Approximate saving (Linux bundle) |
|---|---|---|
| mysql-connector C extension (`_mysql_connector` and its copy of OpenSSL) | `use_pure=True` is always used; Python's `ssl` module uses the system OpenSSL included in the bundle, which is smaller | ~28 MB |
| Qt GTK3 theme and the libraries it pulls in (GTK, cairo, pango, ATK, …) | not needed: without it, Qt uses its own style | ~20 MB |
| Qt translations | the app does not install a `QTranslator` | ~7 MB |
| Qt plugins for embedded or remote systems (EGLFS, linuxfb, VNC, evdev, …), image formats other than SVG, `QtNetwork`, Python `QtDBus` | never used by a desktop app | ~6 MB |
| setuptools and pkg_resources | build tools | ~1 MB |
| On macOS: secretstorage, jeepney, cryptography | only needed by the Linux keychain | ~14 MB |

On Linux, after filtering, system libraries that no remaining binary uses are removed automatically (`readelf -d`).

Result on Linux x86_64: bundle from 191 to 133 MB, AppImage from 70 to 50 MB, `.deb` from 54 to 39 MB. The Excel export (openpyxl) adds about 0.5 MB.

`numpy`, `pandas`, `PIL` and `lxml`, which openpyxl uses only when present, are excluded from the bundle.

What remains and why:

- **ICU (~38 MB)**: required by `libQt6Core`; it can be neither removed nor replaced with the system one (Ubuntu 24.04 ships a different version).
- **cryptography (~14 MB, Linux only)**: required by `secretstorage` for the keychain.
- **Qt Core/Gui/Widgets, Python, OpenSSL**: essential.
- **Symbol stripping**: it would save only ~3% and would invalidate the signature on macOS, so it is not enabled.

The smoke test checks that `ssl`, `hashlib` and, on Linux, the Secret Service backend are present in the package, and writes a test file in every export format. This way an over-eager exclusion makes CI fail instead of silently disabling TLS or the keychain.

### Third-party licenses

Every package also contains the third-party components it bundles (Qt, PySide6, Python, mysql-connector-python, ICU, OpenSSL, the Ubuntu system libraries and the Python packages). During the build, `packaging/third_party_licenses.py`, called by the spec, generates `licenses/THIRD_PARTY_LICENSES.txt` inside the bundle:

- **Attribution:** each bundled file is attributed to its origin and its license is taken from there:
  - the Python package that installed it (license files in the `dist-info`);
  - on Linux, the Ubuntu package that owns it (`dpkg`, file `/usr/share/doc/<package>/copyright`);
  - the Python interpreter (`LICENSE.txt` of the standard library).
- **Missing texts:** for the components that ship no license text (PySide6 and shiboken6, ICU bundled with Qt, OpenSSL bundled with Python on macOS) the official texts kept in `packaging/licenses/` are used (LGPL-3.0, GPL-3.0, ICU 73, Apache-2.0).
- **Content:** the file contains the list of components with version and license, where to get the source code (Qt and PySide6 releases, PyPI, Ubuntu packages on Launchpad) and the full license texts.
- **mysql-connector-python source code:** the connector is GPLv2 (with the Universal FOSS Exception) and is bundled only as bytecode, so its source code is included as well (`licenses/mysql-connector-python-<ver>-source.zip`).
- **Fail-closed:** if a bundled file has no known origin, the build fails. A new dependency can never be distributed without its license.

Where to find the notices:

- `.deb`: `/usr/share/doc/querylean/THIRD_PARTY_LICENSES.txt`;
- DMG: next to the application, together with `LICENSE.txt`;
- AppImage: inside the bundle (`usr/lib/querylean/_internal/licenses/`).

The **About** window links to the file. In packaged builds, the smoke test fails if the file is missing.

### Linux (AppImage)

```bash
pip install -e ".[build]"
packaging/build_linux_appimage.sh     # → dist/querylean-<ver>-x86_64.AppImage
```

The script downloads `appimagetool` (version pinned in the script) and the AppImage runtime into `build/`; on later runs it reuses them. Without FUSE, use `APPIMAGE_EXTRACT_AND_RUN=1`. For maximum compatibility, build on the oldest distribution you want to support (Ubuntu 22.04).

Build requirements on Linux (AppImage and `.deb`):

```bash
sudo apt install curl file desktop-file-utils \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
  libxcb-shape0 libxcb-util1 libxcb-xkb1 libxkbcommon-x11-0
```

The `libxcb-*` and `libxkbcommon-x11-0` libraries are needed by Qt's xcb plugin and are bundled only if they are installed on the build machine: without them the build fails, so as not to produce a package that does not start on systems lacking them. `desktop-file-utils` is needed by `appimagetool`.

### Ubuntu/Lubuntu 24.04 (.deb)

```bash
pip install -e ".[build]"
packaging/build_linux_deb.sh          # → dist/querylean-<ver>-amd64.deb
```

The build must run on Ubuntu 24.04 (or a derivative such as Lubuntu): the bundle requires glibc ≥ 2.38. The package installs:

- the PyInstaller bundle in `/opt/querylean`;
- the launcher `/usr/bin/querylean`;
- the menu entry and the icon;
- the licenses in `/usr/share/doc/querylean/copyright` (DEP-5 format) and the third-party notices in `/usr/share/doc/querylean/THIRD_PARTY_LICENSES.txt`.

Qt, Python and the other libraries are included in the bundle. The only declared dependencies are `libc6 (>= 2.38)`, `libegl1`, `libgl1` and `libxcb1`, derived from the libraries the bundle loads from the system. The keychain (`gnome-keyring` or `keepassxc`) and the Wayland libraries are *Recommends*.

The package version is derived from `.version`: `-` becomes `~` and the revision `-1` is appended (`X.Y.Z-dev` → `X.Y.Z~dev-1`), so a development version sorts before the final release.

### macOS (.app + .dmg)

```bash
pip install -e ".[build]"
packaging/build_macos_dmg.sh          # → dist/querylean-<ver>-<arch>.dmg
```

The architecture is that of the Python interpreter used. You therefore get two separate builds: arm64 on Apple Silicon and x86_64 on Intel. The disk image also contains `LICENSE.txt` and `THIRD_PARTY_LICENSES.txt`.

#### Signing and notarization (macOS)

The script applies an *ad-hoc* signature, which is enough for local testing. To distribute without Gatekeeper warnings you need an Apple Developer account and a *Developer ID Application* certificate:

```bash
CODESIGN_IDENTITY="Developer ID Application: Name (TEAMID)" packaging/build_macos_dmg.sh
xcrun notarytool submit dist/querylean-*.dmg --apple-id … --team-id … --password … --wait
xcrun stapler staple dist/querylean-*.dmg
```

A signature valid for notarization also requires the hardened runtime (`codesign --options runtime`). Without a certificate the package works, but the user has to authorize it manually (see Installation).

### CI/CD

`.github/workflows/ci.yml` runs these steps:

- `ruff`;
- unit, GUI and integration tests on Ubuntu 22.04 with MySQL 8 in a service container;
- builds of the AppImage (Ubuntu 22.04), the `.deb` (Ubuntu 24.04) and the arm64 and x86_64 DMGs, each with a smoke test (`--smoke-test`, which also checks the third-party licenses);
- the `.deb` is installed with `apt`, checked and then removed;
- publication of the packages as build artifacts;
- on `vX.Y.Z` tags, creation of the GitHub release (see below).

The CI runs on pushes to `main` and to `release-*` branches, on tags `v*` and on pull requests.

### Release

The release flow is:

1. From `develop`, create the `release-X.Y.Z` branch, where `X.Y.Z` is the current version without `-dev`.
2. On that branch, change `.version` to `X.Y.Z` and push the branch: the CI builds and checks all packages.
3. Merge `release-X.Y.Z` into `main` and tag `main` with `vX.Y.Z`, then push the tag.
4. On the tag, the `release` job of the CI:
   - checks that the tag matches `.version`;
   - waits for all packages to be built and smoke-tested;
   - creates the GitHub release with the AppImage, the `.deb`, the two DMGs, the third-party licenses of the AppImage and the `SHA256SUMS` file;
   - marks it as a pre-release if the tag contains a hyphen (e.g. `vX.Y.Z-rc1`).

To verify a download: `sha256sum -c SHA256SUMS --ignore-missing`.

## Limitations of this version

- One open connection and one query at a time, one statement per execution.
- Not supported: TLS/SSH tunnels configurable from the GUI, history, pagination.
- The export saves only the loaded rows (at most 10,000): to export more, use a tool such as `mysqldump` or `mysql --batch`.
- `SHOW` is allowed only in the forms recognized by the parser; the others are rejected.
- Columns, tables and aliases whose name is a write word (`update`, `delete`, `insert`, …) are rejected even when quoted or qualified; names that only contain such a word (`updated_at`, `delete_flag`) are allowed. The `INSERT()` string function is rejected too. Words inside strings and comments are not checked.
- `--` sequences not followed by whitespace outside strings (e.g. `1--1`) are rejected to avoid ambiguity with comments: write `1 - -1`.
- MariaDB support is not guaranteed: `MAX_EXECUTION_TIME` does not exist there, so only the watchdog is used.
- With all the databases, the bookmarked queries and the side bar refer to the whole server: a bookmark with unqualified names runs on the active database of the moment.

## License

QueryLean is distributed under the [MIT License](LICENSE). The packages also contain third-party components, each with its own license: see [Third-party licenses](#third-party-licenses).
