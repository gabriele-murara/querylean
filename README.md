# QueryLean

*English · [Italiano](README_ITA.md)*

A minimal desktop client for **running read-only queries** against a MySQL database.
It is inspired by DBeaver, but deliberately reduced to the essentials: one connection, a SQL
editor and a table of copyable results.

## Features

- A single MySQL connection, configured from the GUI. The connection can be tested before saving it.
- The password is kept in the operating system keychain, never in plain text.
- SQL editor with:
  - line numbers;
  - highlighting of keywords, strings, numbers and comments;
  - execution with `Ctrl+Enter` (Linux) or `Cmd+Enter` (macOS).
- Only read statements are allowed (`SELECT`, `WITH … SELECT`, `UNION`, `SHOW`, `DESCRIBE`/`DESC`, `EXPLAIN SELECT`). Every query goes through a parser-based validator.
- Queries run outside the GUI thread, with an activity indicator, a **Stop** button and timeouts.
- Read-only results table:
  - `NULL` is distinct from the empty string;
  - resizable columns;
  - copy of cells or rows as tab-separated text, ready to paste into Excel and LibreOffice Calc;
  - export of the result to Excel (`.xlsx`), CSV or JSON.
- The row limit (default 1,000, maximum 10,000) is enforced while fetching the data.
- Window and splitter sizes are remembered between sessions.
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

The toolbar contains, in order: **Esegui** (Run, ▶), **Interrompi** (Stop, enabled only while a query runs), **Esporta** (Export, drop-down menu, enabled when there is a result), **Connetti**/**Disconnetti** (Connect/Disconnect), **Configurazione** (Configuration) and **Informazioni** (About: version, author, license). The connection state is shown at the bottom right. The user interface is in Italian.

1. **Configuration**: fill in host, port, database, username, password and timeouts, then use **Test connessione** (Test connection) and **Salva configurazione** (Save configuration). Saving does not open the connection.
2. **Connect**: the state goes from *Disconnesso* (Disconnected) to *Connessione in corso* (Connecting) and then to *Connesso* (Connected) or *Errore di connessione* (Connection error). If the password is not in the keychain, it is asked for.
3. Write the query and press **Run** or `Ctrl/Cmd+Enter`.
4. Select cells or rows and press `Ctrl/Cmd+C`. The context menu also offers the "with headers" and "whole rows" variants.
5. To save the result to a file open the **Export** menu and choose the format (see [Export](#export)).

### Execution rules

- If text is selected in the editor, **only the selection** is run.
- Without a selection, **the whole content** of the editor is run.
- An empty editor (or one with only whitespace) runs nothing.
- **Only one statement** is allowed; a trailing `;` is tolerated. With several statements the query is rejected: to run one of them, select it.

### Copy

Copied cells are separated by tabs and rows by newlines. The selection is copied as a rectangle, and unselected cells inside it stay empty. A `NULL` becomes an empty cell, while tabs and newlines inside values become spaces, so the grid stays aligned. Binary values that are not valid UTF-8 are shown in hexadecimal (`0x…`, truncated to 64 bytes).

### Export

**Esporta** (Export) saves the result shown in the table to a file, with the column headers. The button opens a menu:

- **Excel (.xlsx)**, **CSV (.csv)**, **JSON (.json)**: the save dialog offers only that format. If the name lacks its extension, it is added.
- **Esporta…** (Export…): the save dialog offers every format. The extension of the name (`.xlsx`, `.csv`, `.json`) decides or, when missing, the format selected in the dialog.

- **The rows already loaded** are exported, that is at most the configured row limit: the query is not run again. If the result was truncated, the final message says so.
- The file is written in a separate thread, so the window stays usable. It is first written to a temporary file in the same folder and then renamed: an existing file is replaced only by a complete export.
- The file is readable only by your user (permissions `0600`), because it may contain confidential data.
- Exporting is still possible after disconnecting.

| Format | Content |
| --- | --- |
| Excel (`.xlsx`) | One sheet, "Risultato" (Result), with a bold, frozen header row. Numbers, booleans, dates and date-times are native Excel values. Text never becomes a formula, even when it starts with `=`. Values Excel would alter stay text: integers and DECIMAL values with more than 15 significant digits, dates before 1900, `TIME` values. `NULL` and the empty string are both empty cells. Control characters Excel does not allow become `�`; cells longer than 32,767 characters are cut and the final message counts them |
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

1. **MySQL account with minimal privileges (primary barrier).** The application assumes the account has only `SELECT` privileges. It never tries to create users or change permissions.
2. **Application validator (additional barrier)**, in `src/querylean/database/validation/` (`ReadOnlyValidator`). It is fail-closed: if a query cannot be classified with certainty, it is rejected. It works on three levels:
   - **MySQL lexer**: recognizes strings, identifiers and comments with the server's rules. It rejects multiple statements, executable comments `/*! … */`, hints `/*+ … */`, `--` not followed by whitespace (in MySQL that is not a comment), `:=` assignments, and unterminated strings and comments.
   - **Words and functions**: outside strings and comments it blocks reserved write words (`INSERT`, `UPDATE`, `DELETE`, `INTO`, `LOCK`, `CALL`, `LOAD`, …) and functions with side effects (`GET_LOCK`, `LOAD_FILE`, …).
   - **sqlglot parser**: requires exactly one statement of an allowed type, with no DML/DDL nodes, `SELECT … INTO` or `FOR UPDATE`/`LOCK IN SHARE MODE`.

   The original text is sent to the server, never regenerated SQL.

On top of these two barriers, the connection:

- is opened **without** the `CLIENT_MULTI_STATEMENTS` flag and with `LOCAL INFILE` disabled;
- sets `SET SESSION TRANSACTION READ ONLY`;
- removes `NO_BACKSLASH_ESCAPES` from the session `sql_mode`, so the server interprets strings the same way as the validator.

> The application does **not** promise an absolute read-only mode based on the GUI alone. For example, a stored function called in a `SELECT` could modify data if the account had the privileges to do so. This is why the constraint must be guaranteed by the MySQL account.

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
- It **never** appears in the configuration file or in the logs, which go through a redaction filter.
- Plain-text (`keyrings.alt`) or "fail" keyring backends are treated as unavailable. In that case the password is kept in memory only, for the session.
- If the keychain is locked or denies access, a message is shown and the password is asked for when connecting.

### Local files

| File | Linux | macOS |
| --- | --- | --- |
| Configuration (permissions 0600) | `~/.config/querylean/config.json` | `~/Library/Application Support/querylean/config.json` |
| Log (rotation 1 MB × 3) | `~/.local/state/querylean/log/` | `~/Library/Logs/querylean/` |

Users are never shown stack traces: technical details go to the log, without secrets.

## Timeouts and cancellation

- The **connection timeout** is passed to the driver (`connection_timeout`).
- The **execution timeout** works like this:
  - before every query the session `MAX_EXECUTION_TIME` is set, which the server applies to `SELECT`;
  - a client-side watchdog, once the timeout plus 2 seconds has expired, sends `KILL QUERY` from a separate connection. This also covers `SHOW`/`EXPLAIN` and servers that do not support `MAX_EXECUTION_TIME`, such as MariaDB.
- **Stop** sends `KILL QUERY` over the same separate connection.
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
  security/     password in the keychain (abstract SecretStore, KeyringSecretStore)
  export/       Excel/CSV/JSON export (abstract ResultExporter)
  database/     errors/, connection/, execution/, validation/ (staged validator)
  ui/           main/, dialogs/, editor/, icons/, results/, worker/ (QThread thread)
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

- One connection and one query at a time, one statement per execution.
- Not supported: TLS/SSH tunnels configurable from the GUI, autocompletion, history, pagination.
- The export saves only the loaded rows (at most 10,000): to export more, use a tool such as `mysqldump` or `mysql --batch`.
- `SHOW` is allowed only in the forms recognized by the parser; the others are rejected.
- Reserved write words used as column names must be quoted (`` `update` ``) or qualified (`t.update`), as MySQL requires.
- `--` sequences not followed by whitespace outside strings (e.g. `1--1`) are rejected to avoid ambiguity with comments: write `1 - -1`.
- MariaDB support is not guaranteed: `MAX_EXECUTION_TIME` does not exist there, so only the watchdog is used.

## License

QueryLean is distributed under the [MIT License](LICENSE). The packages also contain third-party components, each with its own license: see [Third-party licenses](#third-party-licenses).
