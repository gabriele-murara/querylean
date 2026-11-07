"""Main window: toolbar, SQL editor, result panel and status bar."""

from __future__ import annotations

import base64
import html
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from querylean.app.app_info import AppInfo
from querylean.bookmarks.mask_error import MaskError
from querylean.bookmarks.mask_template import MaskTemplate
from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.completion.completion_engine import CompletionEngine
from querylean.completion.schema_model import SchemaModel
from querylean.config.app_config import AppConfig
from querylean.config.config_error import ConfigError
from querylean.config.config_manager import ConfigManager
from querylean.config.connection_config import ConnectionConfig
from querylean.config.connection_profile import ConnectionProfile
from querylean.config.connection_store import ConnectionStore
from querylean.database.connection.connection_manager import (
    ConnectionManager,
)
from querylean.database.execution.query_executor import QueryExecutor
from querylean.database.execution.query_result import QueryResult
from querylean.database.privileges.account_check import AccountCheck
from querylean.database.schema.column_info import ColumnInfo
from querylean.database.schema.table_info import TableInfo
from querylean.database.validation.read_only_validator import (
    ReadOnlyValidator,
)
from querylean.export.export_report import ExportReport
from querylean.export.result_exporter import ResultExporter
from querylean.export.result_exporters import ResultExporters
from querylean.log.log_manager import LogManager
from querylean.security.keyring_secret_store import KeyringSecretStore
from querylean.security.secret_storage_error import SecretStorageError
from querylean.security.secret_store import SecretStore
from querylean.ui.dialogs.about_dialog import AboutDialog
from querylean.ui.dialogs.connection_dialog import ConnectionDialog
from querylean.ui.dialogs.fill_mask_dialog import FillMaskDialog
from querylean.ui.dialogs.save_mask_dialog import SaveMaskDialog
from querylean.ui.editor.sql_editor import SqlEditor
from querylean.ui.icons.toolbar_icons import ToolbarIcons
from querylean.ui.main.bookmarks_menu import BookmarksMenu
from querylean.ui.main.caution_palette import CautionPalette
from querylean.ui.main.connection_state import ConnectionState
from querylean.ui.main.connections_menu import ConnectionsMenu
from querylean.ui.main.stop_button import StopButton
from querylean.ui.results.results_table import ResultsTable
from querylean.ui.safe_text import SafeText
from querylean.ui.sidebar.table_sidebar import TableSidebar
from querylean.ui.worker.db_thread import DbThread
from querylean.ui.worker.db_worker import DbWorker
from querylean.ui.worker.export_thread import ExportThread


class MainWindow(QMainWindow):
    """Toolbar (run, save query, bookmarked queries, export, connect,
    connections, about); below it
    the table side bar on the left and, on the right, editor and result
    panel separated by a resizable splitter; connection state at the bottom
    right.

    Several connections can be saved (``ConnectionStore``); one at a time is
    active, and it is the one "Connect" opens. Passwords stay in the
    keychain or, for the session, in memory, keyed by MySQL account
    (``user@host:port``): connections to the same account share it.

    Bookmarked queries belong to one saved connection and its target
    (``user@host:port/database``): the menu offers, and the worker runs,
    only those of the open session. A mask (bookmark with placeholders)
    opens ``FillMaskDialog`` and runs the query compiled with its values;
    text with placeholders is never run from the editor."""

    # Delay after the query timeout before the watchdog sends KILL QUERY: lets
    # the server-side MAX_EXECUTION_TIME act first.
    WATCHDOG_GRACE_MS = 2000
    __MAX_RUNNING_PREVIEW = 160
    __SIDEBAR_WIDTH = 220
    __ERROR_STYLE = "color: #c62828;"
    # Shown next to the state while connected in caution mode.
    CAUTION_LABEL = "CAUTION: write access"
    # Databases named in the state line before "…".
    __CAUTION_NAMES = 3
    CAUTION_COLOR = "#c62828"
    READ_ONLY_NOTICE_TITLE = "Read queries only"
    PLACEHOLDER_NOTICE_TITLE = "Placeholders to fill in"
    # Bookmark messages, formatted with a name or a validator reason.
    __NOT_AVAILABLE = "The bookmarked query “{}” is not available for this "
    __NOT_AVAILABLE += "connection."
    __NOT_READ = "Only read queries can be bookmarked. {}"
    # Error kind of a query refused by the validator.
    __REJECTED_KIND = "rejected"
    SAVE_QUERY_TEXT = "Save query"
    __SAVE_QUERY_TIP = "Bookmark the selection or the whole query for the "
    __SAVE_QUERY_TIP += "current connection"
    __log = LogManager.get_logger(__name__)

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        secrets: SecretStore | None = None,
        db: DbThread | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(AppInfo.DISPLAY_NAME)
        self.__config_manager = config_manager or ConfigManager()
        self.__secrets = secrets or KeyringSecretStore()
        self.__db = db or DbThread()
        self.__app_config: AppConfig = self.__config_manager.load()
        self.__profiles: list[ConnectionProfile] = (
            self.__config_manager.connections.load_all()
        )
        # Session passwords by account key (never written anywhere).
        self.__passwords: dict[str, str] = {}
        # True between the disconnection and the connection of a switch to
        # another saved connection.
        self.__switching = False
        self.__state = ConnectionState.DISCONNECTED
        # Write access of the account to the databases of the open session.
        self.__check: AccountCheck | None = None
        # Dialog shown when a query is refused because it is not a read.
        self.__read_only_notice: QMessageBox | None = None
        self.__placeholder_notice: QMessageBox | None = None
        # Saved connection and settings of the open session: bookmarks are
        # read and run only for them.
        self.__session_id = ""
        self.__session_config: ConnectionConfig | None = None
        self.__bookmarks: list[QueryBookmark] = []
        self.__validator = ReadOnlyValidator()
        # Tables and columns of the open session (side bar, completion) and
        # the tables whose columns are being read.
        self.__schema = SchemaModel()
        # Requests in progress: tables by database, columns by (database,
        # table) (case insensitive), and the database being activated.
        self.__pending_tables: set[str] = set()
        self.__pending_columns: set[tuple[str, str]] = set()
        self.__pending_database = ""
        self.__running = False
        self.__closed = False
        # Result shown in the table (exported by "Export").
        self.__result: QueryResult | None = None
        self.__export_thread: ExportThread | None = None
        self.__export_source: QueryResult | None = None
        # Remembered for the session only.
        self.__export_dir = Path.home()
        self.__export_filter = ResultExporters.all()[0].name_filter

        self.__build_toolbar()
        self.__build_body()
        self.__connect_worker()

        self.__watchdog = QTimer(self)
        self.__watchdog.setSingleShot(True)
        self.__watchdog.timeout.connect(self.__on_watchdog)

        self.__restore_geometry()
        self.__ensure_active()
        self.__load_password()
        self.__set_state(ConnectionState.DISCONNECTED)

    # --------------------------------------------------------------- properties
    @property
    def config_manager(self) -> ConfigManager:
        """Configuration persistence."""
        return self.__config_manager

    @property
    def secrets(self) -> SecretStore:
        """Password storage."""
        return self.__secrets

    @property
    def db(self) -> DbThread:
        """Database thread."""
        return self.__db

    @property
    def worker(self) -> DbWorker:
        """Database worker."""
        return self.__db.worker

    @property
    def app_config(self) -> AppConfig:
        """Current configuration."""
        return self.__app_config

    @app_config.setter
    def app_config(self, value: AppConfig) -> None:
        self.__app_config = value

    @property
    def connections(self) -> list[ConnectionProfile]:
        """Saved connections, sorted by display name."""
        return list(self.__profiles)

    @property
    def active_connection(self) -> ConnectionProfile | None:
        """Connection used by "Connect" (None when nothing is saved)."""
        return self.__profile(self.__app_config.active_connection)

    @property
    def password(self) -> str:
        """Session password of the active connection ("" when unknown)."""
        profile = self.active_connection
        if profile is None:
            return ""
        return self.__passwords.get(MainWindow.__account(profile.config), "")

    @password.setter
    def password(self, value: str) -> None:
        profile = self.active_connection
        if profile is not None:
            self.__remember_session(profile.config, value)

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self.__state

    @property
    def caution_active(self) -> bool:
        """True while connected with an account that can change some
        database of the session (accepted in caution mode)."""
        return (
            self.__state == ConnectionState.CONNECTED
            and self.__check is not None
            and self.__check.caution
        )

    @property
    def read_only_notice(self) -> QMessageBox | None:
        """Notice shown the last time a query was refused because it is
        not a read query, if any."""
        return self.__read_only_notice

    @property
    def placeholder_notice(self) -> QMessageBox | None:
        """Notice shown the last time a query was not run because it
        still contains placeholders, if any."""
        return self.__placeholder_notice

    @property
    def account_check(self) -> AccountCheck | None:
        """Write access of the account to the databases of the open
        session."""
        return self.__check

    @property
    def all_databases(self) -> bool:
        """True when the open session covers all the databases."""
        config = self.__session_config
        return config is not None and config.all_databases

    @property
    def session_target(self) -> str:
        """``user@host:port/database`` of the open (or opening) session;
        empty when disconnected."""
        if self.__session_config is None:
            return ""
        return QueryBookmark.target_of(self.__session_config)

    @property
    def schema(self) -> SchemaModel:
        """Tables and columns of the open session."""
        return self.__schema

    @property
    def bookmarks(self) -> list[QueryBookmark]:
        """Bookmarked queries of the open session."""
        return list(self.__bookmarks)

    @property
    def running(self) -> bool:
        """True while a query is executing."""
        return self.__running

    @property
    def exporting(self) -> bool:
        """True while an export file is being written."""
        return self.__export_thread is not None

    @property
    def closed(self) -> bool:
        """True once the window has been closed and resources released."""
        return self.__closed

    @property
    def editor(self) -> SqlEditor:
        """SQL editor."""
        return self.__editor

    @property
    def results(self) -> ResultsTable:
        """Result table."""
        return self.__results

    @property
    def splitter(self) -> QSplitter:
        """Splitter between editor and result panel."""
        return self.__splitter

    @property
    def sidebar(self) -> TableSidebar:
        """Side bar with the databases, tables and columns of the session."""
        return self.__sidebar

    @property
    def sidebar_splitter(self) -> QSplitter:
        """Splitter between the side bar and editor/results."""
        return self.__sidebar_splitter

    @property
    def state_label(self) -> QLabel:
        """Connection state indicator."""
        return self.__state_label

    @property
    def rows_label(self) -> QLabel:
        """Number of loaded rows."""
        return self.__rows_label

    @property
    def time_label(self) -> QLabel:
        """Execution time."""
        return self.__time_label

    @property
    def limit_label(self) -> QLabel:
        """Truncation notice."""
        return self.__limit_label

    @property
    def message_label(self) -> QLabel:
        """Status and error messages."""
        return self.__message_label

    @property
    def running_label(self) -> QLabel:
        """Query currently running."""
        return self.__running_label

    @property
    def progress(self) -> QProgressBar:
        """Activity indicator."""
        return self.__progress

    @property
    def connections_action(self) -> QAction:
        """ "Connections" toolbar entry: opens the connections menu."""
        return self.__connections_action

    @property
    def connections_menu(self) -> ConnectionsMenu:
        """Menu with "New connection…" and the saved connections."""
        return self.__connections_menu

    @property
    def export_action(self) -> QAction:
        """ "Export" toolbar entry: opens the export menu."""
        return self.__export_action

    @property
    def export_menu(self) -> QMenu:
        """Export menu: one entry per format, then "Export…"."""
        return self.__export_menu

    @property
    def connect_action(self) -> QAction:
        """ "Connect"/"Disconnect" action."""
        return self.__connect_action

    @property
    def save_query_action(self) -> QAction:
        """ "Save query" action (bookmarks the query)."""
        return self.__save_query_action

    @property
    def bookmarks_action(self) -> QAction:
        """ "Bookmarked queries" action."""
        return self.__bookmarks_action

    @property
    def bookmarks_menu(self) -> BookmarksMenu:
        """Menu of the bookmarked queries of the open session."""
        return self.__bookmarks_menu

    @property
    def execute_action(self) -> QAction:
        """ "Run" action."""
        return self.__execute_action

    @property
    def stop_button(self) -> StopButton:
        """Blinking "Stop" button of the result panel, shown only while a
        query runs for a while."""
        return self.__stop_button

    @property
    def stop_action(self) -> QAction:
        """ "Stop" action."""
        return self.__stop_action

    def toolbar_actions(self) -> tuple[QAction, ...]:
        """Toolbar actions in display order."""
        return (
            self.__execute_action,
            self.__save_query_action,
            self.__bookmarks_action,
            self.__export_action,
            self.__connect_action,
            self.__connections_action,
            self.__about_action,
        )

    # ------------------------------------------------------------------ actions
    def show_about(self) -> None:
        """Open the "About QueryLean" dialog."""
        AboutDialog(self).exec()

    def show_message(
        self, text: str, *, error: bool = False, tooltip: str = ""
    ) -> None:
        """Show a status (or error) message in the result panel."""
        self.__message_label.setStyleSheet(
            MainWindow.__ERROR_STYLE if error else ""
        )
        self.__message_label.setText(text)
        self.__message_label.setToolTip(
            SafeText.tooltip(tooltip) if tooltip else ""
        )

    @staticmethod
    def query_preview(sql: str) -> str:
        """``sql`` on one line (whitespace runs collapsed), cut with "…"
        when longer than the preview limit."""
        single_line = " ".join(sql.split())
        limit = MainWindow.__MAX_RUNNING_PREVIEW
        if len(single_line) <= limit:
            return single_line
        return "{}…".format(single_line[: limit - 1])

    def new_connection(self) -> ConnectionProfile | None:
        """Open the dialog for a new connection and save it."""
        return self.__edit(None)

    def edit_connection(self, profile_id: str) -> ConnectionProfile | None:
        """Open the dialog on the saved connection ``profile_id``."""
        profile = self.__profile(profile_id)
        return None if profile is None else self.__edit(profile)

    def save_connection(
        self,
        config: ConnectionConfig,
        password: str,
        *,
        profile_id: str | None = None,
        remember: bool = True,
    ) -> ConnectionProfile | None:
        """Save ``config`` as a new connection, or over ``profile_id``, and
        its password (keychain when ``remember``, otherwise session only).
        Returns None when the file cannot be written."""
        previous = self.__profile(profile_id) if profile_id else None
        profile = ConnectionProfile(
            profile_id or ConnectionStore.new_id(), config.copy()
        )
        try:
            self.__config_manager.connections.save(profile)
        except ConfigError as exc:
            self.__warn("Connections", str(exc))
            return None
        self.__profiles = self.__config_manager.connections.load_all()
        self.__remember_session(config, password)
        msg = "Connection “{}” saved.".format(profile.display_name)
        error = False
        if remember:
            try:
                self.__secrets.set_password(
                    MainWindow.__account(config), password
                )
                msg += " Password saved in the keyring."
            except SecretStorageError as exc:
                msg = "{} {}".format(msg, exc)
                error = True
            if previous is not None:
                self.__forget_password(previous.config)
        else:
            msg += " The password will be kept for this session only."
        in_use = self.__state in (
            ConnectionState.CONNECTED,
            ConnectionState.CONNECTING,
        )
        is_active = profile.profile_id == self.__app_config.active_connection
        if not in_use or self.active_connection is None:
            self.__set_active(profile.profile_id)
        elif is_active:
            msg += " Reconnect to apply the changes."
        self.__refresh_connections()
        self.show_message(msg, error=error)
        return profile

    def delete_connection(
        self, profile_id: str, *, confirm: bool = True
    ) -> bool:
        """Delete the saved connection ``profile_id`` (after confirmation),
        disconnecting first when it is in use. Returns True when deleted."""
        profile = self.__profile(profile_id)
        if profile is None:
            return False
        if confirm:
            msg = "Delete the connection “{}”?"
            if not self.__confirm(
                "Delete connection", msg.format(profile.display_name)
            ):
                return False
        is_active = profile_id == self.__app_config.active_connection
        if is_active and self.__state == ConnectionState.CONNECTED:
            self.worker.disconnect_requested.emit()
        try:
            self.__config_manager.connections.delete(profile_id)
        except ConfigError as exc:
            self.__warn("Connections", str(exc))
            return False
        self.__profiles = [
            p for p in self.__profiles if p.profile_id != profile_id
        ]
        self.__forget_password(profile.config)
        try:
            self.__config_manager.bookmarks.delete_all(profile_id)
        except ConfigError as exc:
            self.__log.warning("Bookmarks of a deleted connection: {}", exc)
        if is_active:
            self.__app_config.active_connection = ""
            self.__ensure_active()
            self.__save_config()
        self.__refresh_connections()
        msg = "Connection “{}” deleted.".format(profile.display_name)
        self.show_message(msg)
        return True

    def connect_to(self, profile_id: str) -> None:
        """Make ``profile_id`` the active connection and connect to it,
        closing the current connection first."""
        profile = self.__profile(profile_id)
        if profile is None or self.__running:
            return
        if self.__state == ConnectionState.CONNECTING:
            return
        is_active = profile_id == self.__app_config.active_connection
        if is_active and self.__state == ConnectionState.CONNECTED:
            return
        if not self.__ready_to_connect(profile):
            return
        if self.__state == ConnectionState.CONNECTED:
            self.__switching = True
            self.worker.disconnect_requested.emit()
        self.__set_active(profile_id)
        # Reloaded: completing it may have saved new settings.
        profile = self.__profile(profile_id)
        if profile is not None:
            self.__start_connect(profile)

    def toggle_connection(self) -> None:
        """Connect the active connection, or disconnect when connected. With
        no saved connection, open "New connection"."""
        if self.__state == ConnectionState.CONNECTED:
            self.worker.disconnect_requested.emit()
            return
        profile = self.active_connection
        if profile is None:
            profile = self.new_connection()
            if profile is None:
                return
        if self.__ready_to_connect(profile):
            profile = self.__profile(profile.profile_id)
            if profile is not None:
                self.__start_connect(profile)

    def execute_query(self) -> None:
        """Run the selection, or the whole editor content when nothing is
        selected. Text with placeholders is refused (red message and
        ``placeholder_notice``)."""
        if self.__running:
            return
        sql = self.__editor.query_text()
        if not sql.strip():
            return
        if MaskTemplate.has_placeholders(sql):
            msg = "The query contains placeholders{}: replace them with "
            msg += "values before running it."
            msg = msg.format(MainWindow.__placeholder_list(sql))
            self.show_message(msg, error=True)
            self.__show_placeholder_notice(msg)
            return
        self.__start_query(sql)

    def save_bookmark(
        self,
        name: str | None = None,
        *,
        confirm: bool = True,
        placeholders: tuple[Placeholder, ...] | None = None,
    ) -> QueryBookmark | None:
        """Save the selection, or the whole editor content, as a bookmarked
        query of the open session. Without ``name`` the user is asked for
        one; an existing bookmark with that name is replaced (after
        confirmation). Only queries accepted by the validator are saved.

        A query with ``${NAME}`` placeholders is saved as a mask: the
        "Save mask" dialog asks for the name and the placeholder types and
        defaults, unless ``placeholders`` is given. The mask compiled with
        its defaults must be a read query."""
        if self.__running:
            return None
        if self.__state != ConnectionState.CONNECTED:
            self.show_message(ConnectionManager.NOT_CONNECTED, error=True)
            return None
        sql = self.__editor.query_text().strip()
        if not sql:
            self.show_message("Write a query to bookmark it.", error=True)
            return None
        if MaskTemplate.has_placeholders(sql):
            definition = self.__define_mask(sql, name, placeholders)
            if definition is None:
                return None
            name, placeholders = definition
        else:
            placeholders = ()
            validation = self.__validator.validate(sql)
            if not validation.ok:
                self.show_message(
                    MainWindow.__NOT_READ.format(validation.reason),
                    error=True,
                )
                return None
        if name is None:
            name, ok = QInputDialog.getText(
                self,
                MainWindow.SAVE_QUERY_TEXT,
                SafeText.html(
                    "Name of the query for “{}”:".format(
                        self.__session_display_name()
                    )
                ),
            )
            if not ok:
                return None
        name = QueryBookmark.clean_name(name)
        if not name:
            self.show_message("Query not saved: no name.", error=True)
            return None
        if len(name) > QueryBookmark.MAX_NAME_LENGTH:
            msg = "Query not saved: the name is longer than {} characters."
            self.show_message(
                msg.format(QueryBookmark.MAX_NAME_LENGTH), error=True
            )
            return None
        store = self.__config_manager.bookmarks
        target = self.session_target
        existing = store.find(self.__session_id, target, name)
        if existing is not None and confirm:
            if not self.__confirm(
                MainWindow.SAVE_QUERY_TEXT,
                "Replace the bookmarked query “{}”?".format(existing.name),
            ):
                return None
        if existing is not None:
            name = existing.name
        # A mask saved again keeps the last values of the placeholders it
        # still has.
        last_values = existing.last_values if existing is not None else {}
        bookmark = QueryBookmark(name, sql, target, placeholders, last_values)
        try:
            store.add(self.__session_id, bookmark)
        except ConfigError as exc:
            self.__warn(MainWindow.SAVE_QUERY_TEXT, str(exc))
            return None
        self.__reload_bookmarks()
        msg = (
            "Mask saved as “{}” for “{}”."
            if placeholders
            else ("Query saved as “{}” for “{}”.")
        )
        self.show_message(msg.format(name, self.__session_display_name()))
        return bookmark

    def __define_mask(
        self,
        sql: str,
        name: str | None,
        placeholders: tuple[Placeholder, ...] | None,
    ) -> tuple[str, tuple[Placeholder, ...]] | None:
        """Name and placeholders of the mask ``sql`` (from the "Save mask"
        dialog unless ``placeholders`` is given), checked: the mask
        compiled with the defaults must be a read query."""
        try:
            template = MaskTemplate(sql)
        except MaskError as exc:
            self.show_message(
                "Mask not saved. {}".format(exc.message), error=True
            )
            return None
        if placeholders is None:
            dialog = SaveMaskDialog(
                sql,
                self.__editor.placeholders(),
                name=name or "",
                validator=self.__validator,
                parent=self,
            )
            if dialog.exec() != SaveMaskDialog.DialogCode.Accepted:
                return None
            name, placeholders = dialog.mask_name(), dialog.placeholders()
        defined = {p.name: p for p in placeholders}
        try:
            compiled = template.compile(
                defined, {key: p.default for key, p in defined.items()}
            )
        except MaskError as exc:
            self.show_message(
                "Mask not saved. {}".format(exc.message), error=True
            )
            return None
        validation = self.__validator.validate(compiled)
        if not validation.ok:
            self.show_message(
                MainWindow.__NOT_READ.format(validation.reason), error=True
            )
            return None
        ordered = tuple(defined[key] for key in template.names)
        return (name or ""), ordered

    @staticmethod
    def __placeholder_list(sql: str) -> str:
        """`` (${A}, ${B})`` for the placeholders of ``sql`` (empty when
        they cannot be parsed)."""
        try:
            names = MaskTemplate(sql).names
        except MaskError:
            return ""
        return " ({})".format(", ".join("${{{}}}".format(n) for n in names))

    def run_bookmark(self, name: str) -> None:
        """Put the bookmarked query ``name`` of the open session in the
        editor (undoable) and run it. Bookmarks of other connections are
        never run.

        A mask first opens the "Run mask" dialog: the query compiled with
        the values entered there is run like a bookmark (target check and
        validator), and the values are remembered for the next time. From
        the dialog the mask can also be opened in the editor instead."""
        if self.__running:
            return
        if self.__state != ConnectionState.CONNECTED:
            self.show_message(ConnectionManager.NOT_CONNECTED, error=True)
            return
        target = self.session_target
        bookmark = self.__config_manager.bookmarks.find(
            self.__session_id, target, name
        )
        if bookmark is None or bookmark.target != target:
            self.show_message(
                MainWindow.__NOT_AVAILABLE.format(name), error=True
            )
            self.__reload_bookmarks()
            return
        if bookmark.is_mask:
            self.__run_mask(bookmark)
            return
        self.__editor.replace_query(bookmark.sql)
        self.__start_query(bookmark.sql, bookmark.target)

    def __run_mask(self, mask: QueryBookmark) -> None:
        """Ask the values of ``mask``, then run the compiled query."""
        try:
            dialog = FillMaskDialog(
                mask,
                validator=self.__validator,
                taken_names=[b.name for b in self.__bookmarks],
                parent=self,
            )
        except MaskError as exc:
            self.show_message(exc.message, error=True)
            return
        result = dialog.exec()
        if result not in (
            FillMaskDialog.EDIT_RESULT,
            FillMaskDialog.DialogCode.Accepted,
        ):
            return
        if dialog.is_renamed():
            renamed = self.__rename_mask(mask, dialog.mask_name())
            if renamed is None:
                return
            mask = renamed
        if result == FillMaskDialog.EDIT_RESULT:
            self.open_mask(mask)
            return
        sql = dialog.compiled_sql()
        if not sql:
            return
        try:
            self.__config_manager.bookmarks.remember_values(
                self.__session_id, mask.target, mask.name, dialog.values()
            )
        except ConfigError as exc:
            # The run does not depend on it: only the next proposal.
            self.__log.warning("Values of the mask not saved: {}", exc)
        else:
            self.__reload_bookmarks()
        self.__editor.replace_query(sql)
        self.__start_query(sql, mask.target)

    def __rename_mask(
        self, mask: QueryBookmark, name: str
    ) -> QueryBookmark | None:
        """Rename ``mask``; None (and a warning) when it cannot be."""
        try:
            renamed = self.__config_manager.bookmarks.rename(
                self.__session_id, mask.target, mask.name, name
            )
        except ConfigError as exc:
            self.__warn(BookmarksMenu.TITLE, str(exc))
            return None
        self.__reload_bookmarks()
        if renamed is None:
            self.show_message(
                MainWindow.__NOT_AVAILABLE.format(mask.name), error=True
            )
        return renamed

    def open_mask(self, mask: QueryBookmark) -> None:
        """Load ``mask`` in the editor with its placeholders (to change it
        and save it again), without running it."""
        self.__editor.replace_query(mask.sql)
        self.__editor.remember_placeholders(mask.placeholders)
        msg = "Mask “{}” loaded in the editor{}: save it again to keep "
        msg += "the changes."
        self.show_message(
            msg.format(mask.name, MainWindow.__placeholder_list(mask.sql))
        )

    def delete_bookmark(self, name: str, *, confirm: bool = True) -> bool:
        """Delete the bookmarked query ``name`` of the open session (after
        confirmation). Returns True when deleted."""
        if not self.__session_id:
            return False
        if confirm:
            if not self.__confirm(
                "Delete bookmark",
                "Delete the bookmarked query “{}”?".format(name),
            ):
                return False
        try:
            deleted = self.__config_manager.bookmarks.remove(
                self.__session_id, self.session_target, name
            )
        except ConfigError as exc:
            self.__warn("Delete bookmark", str(exc))
            return False
        self.__reload_bookmarks()
        if deleted:
            self.show_message("Bookmarked query “{}” deleted.".format(name))
        return deleted

    def __start_query(self, sql: str, target: str | None = None) -> None:
        """Send ``sql`` to the worker; with ``target`` (a bookmark) the
        worker runs it only on a session for that target."""
        if self.__state != ConnectionState.CONNECTED:
            self.show_message(ConnectionManager.NOT_CONNECTED, error=True)
            return
        cfg = self.__active_config()
        self.__running = True
        self.__update_actions()
        self.__progress.show()
        self.__stop_button.start()
        self.__rows_label.clear()
        self.__time_label.clear()
        self.__limit_label.clear()
        preview = MainWindow.query_preview(sql)
        self.__running_label.setText("Running: {}".format(preview))
        self.__running_label.show()
        self.show_message("Running the query…")
        self.__watchdog.start(
            cfg.query_timeout * 1000 + MainWindow.WATCHDOG_GRACE_MS
        )
        if target is None:
            self.worker.query_requested.emit(
                sql, cfg.row_limit, cfg.query_timeout
            )
        else:
            self.worker.bookmark_requested.emit(
                sql, target, cfg.row_limit, cfg.query_timeout
            )

    def stop_query(self) -> None:
        """Interrupt the running query."""
        if self.__running:
            self.show_message("Stopping the query…")
            self.__stop_action.setEnabled(False)
            self.worker.cancel_query(QueryExecutor.CANCEL_BY_USER)

    def refresh_tables(self) -> None:
        """Reload databases, tables and columns of the side bar (only when
        connected)."""
        if self.__state != ConnectionState.CONNECTED:
            return
        active = self.__schema.database
        self.__schema.clear()
        self.__schema.database = active
        self.__pending_tables.clear()
        self.__pending_columns.clear()
        config = self.__session_config
        if config is not None and config.all_databases:
            self.__sidebar.set_loading(TableSidebar.LOADING_DATABASES)
            self.worker.databases_requested.emit(self.__timeout())
            return
        database = config.database if config is not None else active
        self.__schema.set_databases([database])
        self.__sidebar.set_loading()
        self.__sidebar.set_write_access(self.__write_access([database]))
        # Showing the single database expands it, which requests its tables.
        self.__sidebar.set_databases([database], database)

    def load_tables(self, database: str) -> None:
        """Read the tables (and all the columns) of ``database`` unless they
        are known or already being read."""
        if self.__state != ConnectionState.CONNECTED or not database:
            return
        tables = self.__schema.tables_of(database)
        if tables is not None:
            self.__sidebar.set_tables(tables, database)
            return
        key = database.casefold()
        if key in self.__pending_tables:
            return
        self.__pending_tables.add(key)
        wire = self.__wire(database)
        self.worker.tables_requested.emit(wire, self.__timeout())
        self.worker.columns_requested.emit(wire, self.__timeout())

    def load_columns(self, database: str, table: str) -> None:
        """Read the columns of ``table`` in ``database`` (for the side bar
        and the completion) unless they are known or already being read."""
        if self.__state != ConnectionState.CONNECTED:
            return
        database = database or self.__schema.database
        key = (database.casefold(), table.casefold())
        if key in self.__pending_columns or self.__schema.has_columns(
            table, database
        ):
            return
        self.__pending_columns.add(key)
        self.worker.table_columns_requested.emit(
            self.__wire(database), table, self.__timeout()
        )

    def select_database(self, database: str) -> None:
        """Make ``database`` the active one (only when the session covers
        all the databases): unqualified names in queries refer to it."""
        if (
            self.__state != ConnectionState.CONNECTED
            or not self.all_databases
            or not database
            or database == self.__schema.database
            or database == self.__pending_database
        ):
            return
        self.__pending_database = database
        self.worker.database_requested.emit(database)

    def use_column(self, table: TableInfo, column: str) -> None:
        """Put ``SELECT column FROM table LIMIT 1;`` in the editor,
        replacing its content (undoable). The query is not executed."""
        self.__prepare(table.column_statement(column))

    def add_column(self, table: TableInfo, column: str) -> None:
        """Add ``column`` to the preview query of ``table`` in the editor
        (``SELECT *`` becomes ``SELECT column``). When the editor holds
        another text, start ``SELECT column FROM table LIMIT 1;``. A column
        already selected is not repeated."""
        current = table.selected_columns(self.__editor.toPlainText())
        if current is None:
            columns = [column]
        elif column in current:
            columns = current
        else:
            columns = [*current, column]
        self.__prepare(table.columns_statement(columns))

    def use_table(self, table: TableInfo) -> None:
        """Put the preview query of ``table`` in the editor, replacing its
        content (undoable with Ctrl/Cmd+Z). The query is not executed.
        When the editor already holds it (e.g. the second click of a double
        click) nothing changes, so one undo still restores the old text."""
        self.__prepare(table.select_statement)

    def __prepare(self, statement: str) -> None:
        """Replace the editor text with ``statement`` (no new undo step when
        it is already there, e.g. on the second click of a double click)."""
        self.__editor.hide_completion()
        if self.__editor.toPlainText() != statement:
            self.__editor.replace_query(statement)
        self.__editor.setFocus()

    def export_results(self, exporter: ResultExporter | None = None) -> None:
        """Ask for a file name and export the displayed result.

        With ``exporter`` the dialog offers only that format; without it
        ("Export…") every format is offered and the extension decides."""
        if not self.__can_export():
            return
        path = self.__ask_export_path(exporter)
        if path is not None:
            self.export_to(path, exporter)

    def export_to(
        self, path: Path, exporter: ResultExporter | None = None
    ) -> None:
        """Export the displayed result to ``path`` in a background thread.
        The format follows the extension unless ``exporter`` is given."""
        if not self.__can_export() or self.__result is None:
            return
        exporter = exporter or ResultExporters.for_path(path)
        if exporter is None:
            self.show_message(
                "Unsupported format: use .xlsx, .csv or .json.", error=True
            )
            return
        result = self.__result
        thread = ExportThread(exporter, path, result.columns, result.rows, self)
        thread.exported.connect(self.__on_exported)
        thread.export_failed.connect(self.__on_export_failed)
        self.__export_thread = thread
        self.__export_source = result
        self.__update_actions()
        self.show_message("Exporting to {}…".format(path))
        thread.start()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Save window geometry and configuration, then release database
        resources."""
        if self.__closed:
            event.accept()
            return
        self.__closed = True
        self.__watchdog.stop()
        if self.__export_thread is not None:
            # Let the file be completed: an interrupted export leaves only a
            # temporary file behind.
            self.__export_thread.wait()
        ui = self.__app_config.ui
        ui.window_geometry = MainWindow.__encode(self.saveGeometry())
        ui.splitter_state = MainWindow.__encode(self.__splitter.saveState())
        ui.sidebar_state = MainWindow.__encode(
            self.__sidebar_splitter.saveState()
        )
        try:
            self.__config_manager.save(self.__app_config)
        except ConfigError as exc:
            self.__log.warning(
                "Saving the configuration on close failed: {}", exc
            )
        self.__db.shutdown()
        event.accept()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        # A theme change replaces the application palette: tint it again.
        if event.type() == QEvent.Type.ApplicationPaletteChange:
            self.__apply_palette()

    # ---------------------------------------------------------- UI construction
    def __build_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setObjectName("main-toolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)

        # Connection state shown at the bottom right, as a permanent status bar
        # widget.
        self.__state_label = QLabel()
        self.__state_label.setContentsMargins(6, 0, 6, 0)
        # Markup built here; names and databases inside are escaped.
        self.__state_label.setTextFormat(Qt.TextFormat.RichText)
        status_bar = QStatusBar(self)
        status_bar.setSizeGripEnabled(True)
        status_bar.addPermanentWidget(self.__state_label)
        self.setStatusBar(status_bar)

        # Order: Run, Save query, Bookmarked queries, Export,
        # Connect/Disconnect, Connections, About.
        self.__connect_icon = ToolbarIcons.connect()
        self.__disconnect_icon = ToolbarIcons.disconnect()
        self.__execute_action = QAction(ToolbarIcons.play(), "Run", self)
        self.__execute_action.setToolTip(
            "Run the selection or the whole query (Ctrl/Cmd+Enter)"
        )
        self.__execute_action.triggered.connect(self.execute_query)
        self.__stop_action = QAction(ToolbarIcons.stop(), "Stop", self)
        self.__stop_action.setToolTip("Stop the running query")
        self.__stop_action.setEnabled(False)
        self.__stop_action.triggered.connect(self.stop_query)
        self.__save_query_action = QAction(
            ToolbarIcons.star(), MainWindow.SAVE_QUERY_TEXT, self
        )
        self.__save_query_action.setToolTip(MainWindow.__SAVE_QUERY_TIP)
        self.__save_query_action.triggered.connect(lambda: self.save_bookmark())
        self.__bookmarks_action = QAction(
            ToolbarIcons.bookmarks(), BookmarksMenu.TITLE, self
        )
        self.__bookmarks_action.setToolTip(
            "Run a query bookmarked for the current connection"
        )
        self.__bookmarks_menu = BookmarksMenu(self)
        self.__bookmarks_menu.run_requested.connect(self.run_bookmark)
        self.__bookmarks_menu.delete_requested.connect(self.delete_bookmark)
        self.__bookmarks_action.setMenu(self.__bookmarks_menu)
        self.__export_action = QAction(ToolbarIcons.export(), "Export", self)
        self.__export_action.setToolTip(
            "Export the result to Excel, CSV or JSON"
        )
        self.__export_menu = QMenu("Export", self)
        for exporter in ResultExporters.all():
            entry = self.__export_menu.addAction(
                "{} ({})".format(exporter.label, exporter.extension)
            )
            entry.triggered.connect(
                lambda _checked=False, e=exporter: self.export_results(e)
            )
        self.__export_menu.addSeparator()
        export_any = self.__export_menu.addAction("Export…")
        export_any.triggered.connect(lambda: self.export_results())
        self.__export_action.setMenu(self.__export_menu)
        self.__connect_action = QAction(self.__connect_icon, "Connect", self)
        self.__connect_action.triggered.connect(self.toggle_connection)
        self.__connections_action = QAction(
            ToolbarIcons.settings(), "Connections", self
        )
        self.__connections_action.setToolTip(
            "Create, edit, delete or choose a MySQL connection"
        )
        self.__connections_menu = ConnectionsMenu(self)
        self.__connections_menu.new_requested.connect(self.new_connection)
        self.__connections_menu.connect_requested.connect(self.connect_to)
        self.__connections_menu.edit_requested.connect(self.edit_connection)
        self.__connections_menu.delete_requested.connect(self.delete_connection)
        self.__connections_action.setMenu(self.__connections_menu)
        self.__about_action = QAction(ToolbarIcons.about(), "About", self)
        self.__about_action.setToolTip("About {}".format(AppInfo.DISPLAY_NAME))
        self.__about_action.setMenuRole(QAction.MenuRole.AboutRole)
        self.__about_action.triggered.connect(self.show_about)
        for action in self.toolbar_actions():
            toolbar.addAction(action)
        # A click on "Export" or "Connections" opens the menu directly.
        for action in (
            self.__bookmarks_action,
            self.__export_action,
            self.__connections_action,
        ):
            button = toolbar.widgetForAction(action)
            if isinstance(button, QToolButton):
                button.setPopupMode(
                    QToolButton.ToolButtonPopupMode.InstantPopup
                )

        quit_action = QAction(self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

    def __build_body(self) -> None:
        self.__editor = SqlEditor()
        self.__editor.execute_requested.connect(self.execute_query)
        self.__editor.completion_engine = CompletionEngine(self.__schema)
        self.__editor.columns_needed.connect(self.load_columns)
        self.__editor.tables_needed.connect(self.load_tables)

        self.__results = ResultsTable()
        self.__rows_label = QLabel()
        self.__time_label = QLabel()
        self.__limit_label = QLabel()
        self.__limit_label.setStyleSheet("color: #ef6c00; font-weight: bold;")
        self.__progress = QProgressBar()
        self.__progress.setRange(0, 0)  # indeterminate
        self.__progress.setMaximumWidth(120)
        self.__progress.setMaximumHeight(14)
        self.__progress.setTextVisible(False)
        self.__progress.hide()
        # Not in the toolbar: it appears, blinking, next to the progress bar
        # only when a query takes a while.
        self.__stop_button = StopButton(self.__stop_action)
        self.__message_label = QLabel()
        # Messages contain SQL: "<" must never be read as rich text.
        self.__message_label.setTextFormat(Qt.TextFormat.PlainText)
        self.__message_label.setWordWrap(True)
        self.__message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.__running_label = QLabel()
        self.__running_label.setTextFormat(Qt.TextFormat.PlainText)
        self.__running_label.setStyleSheet("color: palette(placeholder-text);")
        self.__running_label.hide()

        info = QHBoxLayout()
        info.addWidget(self.__stop_button)
        info.addWidget(self.__progress)
        info.addWidget(self.__rows_label)
        info.addWidget(self.__time_label)
        info.addWidget(self.__limit_label)
        info.addStretch(1)

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 4, 0, 0)
        panel_layout.addWidget(self.__results, 1)
        panel_layout.addLayout(info)
        panel_layout.addWidget(self.__running_label)
        panel_layout.addWidget(self.__message_label)

        self.__splitter = QSplitter(Qt.Orientation.Vertical)
        self.__splitter.setObjectName("editor-results-splitter")
        self.__splitter.addWidget(self.__editor)
        self.__splitter.addWidget(panel)
        self.__splitter.setStretchFactor(0, 2)
        self.__splitter.setStretchFactor(1, 3)
        self.__splitter.setChildrenCollapsible(False)

        self.__sidebar = TableSidebar()
        self.__sidebar.table_chosen.connect(self.use_table)
        self.__sidebar.refresh_requested.connect(self.refresh_tables)
        self.__sidebar.set_schema(self.__schema)
        self.__sidebar.columns_requested.connect(self.load_columns)
        self.__sidebar.tables_requested.connect(self.load_tables)
        self.__sidebar.database_selected.connect(self.select_database)
        self.__sidebar.column_chosen.connect(self.use_column)
        self.__sidebar.column_added.connect(self.add_column)

        # Side bar on the left, for the whole height below the toolbar.
        self.__sidebar_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.__sidebar_splitter.setObjectName("sidebar-splitter")
        self.__sidebar_splitter.addWidget(self.__sidebar)
        self.__sidebar_splitter.addWidget(self.__splitter)
        self.__sidebar_splitter.setStretchFactor(0, 0)
        self.__sidebar_splitter.setStretchFactor(1, 1)
        self.__sidebar_splitter.setChildrenCollapsible(False)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.__sidebar_splitter)
        self.setCentralWidget(container)
        self.resize(1000, 700)
        self.__sidebar_splitter.setSizes(
            [MainWindow.__SIDEBAR_WIDTH, 1000 - MainWindow.__SIDEBAR_WIDTH]
        )

    def __connect_worker(self) -> None:
        worker = self.worker
        worker.connected.connect(self.__on_connected)
        worker.connect_failed.connect(self.__on_connect_failed)
        worker.disconnected.connect(self.__on_disconnected)
        worker.query_finished.connect(self.__on_query_finished)
        worker.query_failed.connect(self.__on_query_failed)
        worker.tables_loaded.connect(self.__on_tables_loaded)
        worker.tables_failed.connect(self.__on_tables_failed)
        worker.columns_loaded.connect(self.__on_columns_loaded)
        worker.columns_failed.connect(self.__on_columns_failed)
        worker.table_columns_loaded.connect(self.__on_table_columns_loaded)
        worker.table_columns_failed.connect(self.__on_table_columns_failed)
        worker.databases_loaded.connect(self.__on_databases_loaded)
        worker.databases_failed.connect(self.__on_databases_failed)
        worker.database_changed.connect(self.__on_database_changed)
        worker.database_failed.connect(self.__on_database_failed)

    # ------------------------------------------------------------------ state
    def __set_state(self, state: ConnectionState) -> None:
        self.__state = state
        if state != ConnectionState.CONNECTED:
            self.__check = None
            self.__schema.clear()
            self.__pending_tables.clear()
            self.__pending_columns.clear()
            self.__pending_database = ""
            self.__editor.hide_completion()
        if state in (ConnectionState.DISCONNECTED, ConnectionState.ERROR):
            self.__session_id = ""
            self.__session_config = None
            self.__set_bookmarks([])
        text = "<b style='color:{}'>●</b> {}".format(state.color, state.label)
        if self.caution_active and self.__check is not None:
            names = self.__check.write_databases
            shown = ", ".join(names[: MainWindow.__CAUTION_NAMES])
            if len(names) > MainWindow.__CAUTION_NAMES:
                shown = "{}, …".format(shown)
            text = "{} · <b style='color:{}'>{} ({})</b>".format(
                text,
                MainWindow.CAUTION_COLOR,
                MainWindow.CAUTION_LABEL,
                html.escape(shown),
            )
        profile = self.active_connection
        if profile is not None and state in (
            ConnectionState.CONNECTED,
            ConnectionState.CONNECTING,
        ):
            text = "{} · {}".format(text, html.escape(profile.display_name))
        if state == ConnectionState.CONNECTED and self.__schema.database:
            text = "{} · db: <b>{}</b>".format(
                text, html.escape(self.__schema.database)
            )
        self.__state_label.setText(text)
        self.__apply_palette()
        if state != ConnectionState.CONNECTED:
            self.__sidebar.show_message(TableSidebar.NOT_CONNECTED)
        self.__update_actions()
        self.__refresh_connections()

    def __apply_palette(self) -> None:
        """Pink window background while the account is not read-only, the
        inherited palette otherwise."""
        if self.caution_active:
            base = QApplication.palette(self)
            self.setPalette(CautionPalette.tinted(base))
        else:
            # An empty palette clears the explicit roles: back to the
            # application palette.
            self.setPalette(QPalette())

    def __update_actions(self) -> None:
        connected = self.__state == ConnectionState.CONNECTED
        busy = self.__state == ConnectionState.CONNECTING
        self.__connect_action.setText("Disconnect" if connected else "Connect")
        self.__connect_action.setIcon(
            self.__disconnect_icon if connected else self.__connect_icon
        )
        self.__connect_action.setEnabled(not busy and not self.__running)
        self.__connections_action.setEnabled(not busy and not self.__running)
        self.__execute_action.setEnabled(connected and not self.__running)
        self.__save_query_action.setEnabled(connected and not self.__running)
        self.__bookmarks_action.setEnabled(connected and not self.__running)
        self.__stop_action.setEnabled(self.__running)
        self.__export_action.setEnabled(
            self.__can_export() and not self.__running
        )

    def __can_export(self) -> bool:
        return (
            self.__result is not None
            and bool(self.__result.columns)
            and self.__export_thread is None
        )

    # ---------------------------------------------------------------- bookmarks
    def __reload_bookmarks(self) -> None:
        """Read the bookmarks of the open session again."""
        if not self.__session_id or self.__session_config is None:
            self.__set_bookmarks([])
            return
        self.__set_bookmarks(
            self.__config_manager.bookmarks.load(
                self.__session_id, self.session_target
            )
        )

    def __set_bookmarks(self, bookmarks: list[QueryBookmark]) -> None:
        self.__bookmarks = list(bookmarks)
        self.__bookmarks_menu.set_bookmarks(self.__bookmarks)

    def __session_display_name(self) -> str:
        profile = self.__profile(self.__session_id)
        return profile.display_name if profile is not None else ""

    # -------------------------------------------------------------- connections
    def __profile(self, profile_id: str | None) -> ConnectionProfile | None:
        for profile in self.__profiles:
            if profile.profile_id == profile_id:
                return profile
        return None

    def __active_config(self) -> ConnectionConfig:
        profile = self.active_connection
        return profile.config if profile is not None else ConnectionConfig()

    def __ensure_active(self) -> None:
        """Keep the active identifier pointing to a saved connection."""
        if self.active_connection is None:
            first = self.__profiles[0].profile_id if self.__profiles else ""
            if first != self.__app_config.active_connection:
                self.__app_config.active_connection = first

    def __set_active(self, profile_id: str) -> None:
        if profile_id != self.__app_config.active_connection:
            self.__app_config.active_connection = profile_id
            self.__save_config()
        self.__set_state(self.__state)

    def __refresh_connections(self) -> None:
        self.__connections_menu.set_connections(
            self.__profiles,
            self.__app_config.active_connection,
            connected=self.__state == ConnectionState.CONNECTED,
        )

    def __edit(
        self, profile: ConnectionProfile | None
    ) -> ConnectionProfile | None:
        config = profile.config if profile else ConnectionConfig()
        dialog = ConnectionDialog(
            config,
            self.__password_for(config) if profile else "",
            self.worker,
            keyring_available=self.__secrets.is_available(),
            title=(
                ConnectionDialog.EDIT_TITLE
                if profile
                else ConnectionDialog.NEW_TITLE
            ),
            parent=self,
        )
        if dialog.exec() != ConnectionDialog.DialogCode.Accepted:
            return None
        return self.save_connection(
            dialog.config(),
            dialog.password_value(),
            profile_id=profile.profile_id if profile else None,
            remember=dialog.remember_password.isChecked(),
        )

    def __ready_to_connect(self, profile: ConnectionProfile) -> bool:
        """Complete configuration and known password (asked if needed)."""
        if not profile.config.is_complete():
            self.show_message(
                "Incomplete connection: fill in the required fields.",
                error=True,
            )
            edited = self.edit_connection(profile.profile_id)
            if edited is None or not edited.config.is_complete():
                return False
            profile = edited
        if self.__password_for(profile.config):
            return True
        if self.__ask_password(profile.config):
            return True
        self.show_message(
            "Connection cancelled: no password entered.", error=True
        )
        return False

    def __start_connect(self, profile: ConnectionProfile) -> None:
        cfg = profile.config
        self.__set_state(ConnectionState.CONNECTING)
        self.__session_id = profile.profile_id
        self.__session_config = cfg.copy()
        self.__set_bookmarks([])
        msg = "Connecting to {}:{}/{}…"
        self.show_message(msg.format(cfg.host, cfg.port, cfg.database))
        self.worker.connect_requested.emit(cfg.copy(), self.__password_for(cfg))

    # ----------------------------------------------------------------- password
    @staticmethod
    def __account(config: ConnectionConfig) -> str:
        return SecretStore.account_key(
            config.username, config.host, config.port
        )

    def __remember_session(self, config: ConnectionConfig, value: str) -> None:
        LogManager.register_secret(value)
        self.__passwords[MainWindow.__account(config)] = value

    def __password_for(self, config: ConnectionConfig) -> str:
        """Session password of the account of ``config``, read from the
        keychain the first time."""
        key = MainWindow.__account(config)
        if key not in self.__passwords:
            try:
                stored = self.__secrets.get_password(key) or ""
            except SecretStorageError as exc:
                self.show_message(str(exc), error=True)
                return ""
            if stored:
                self.__remember_session(config, stored)
        return self.__passwords.get(key, "")

    def __forget_password(self, config: ConnectionConfig) -> None:
        """Drop the password of an account no saved connection uses any
        more, from the session and from the keychain."""
        key = MainWindow.__account(config)
        if any(MainWindow.__account(p.config) == key for p in self.__profiles):
            return
        self.__passwords.pop(key, None)
        try:
            self.__secrets.delete_password(key)
        except SecretStorageError as exc:
            self.__log.warning("Cannot delete the stored password: {}", exc)

    def __load_password(self) -> None:
        profile = self.active_connection
        if profile is not None and profile.config.username:
            self.__password_for(profile.config)

    def __ask_password(self, config: ConnectionConfig) -> bool:
        password, ok = QInputDialog.getText(
            self,
            "Password",
            SafeText.html(
                "Password for {}@{}:".format(config.username, config.host)
            ),
            QLineEdit.EchoMode.Password,
        )
        if ok and password:
            self.__remember_session(config, password)
            return True
        return False

    def __save_config(self) -> None:
        try:
            self.__config_manager.save(self.__app_config)
        except ConfigError as exc:
            self.__warn("Configuration", str(exc))

    # --------------------------------------------------------- worker responses
    def __on_watchdog(self) -> None:
        if self.__running:
            self.__log.info(
                "Watchdog: query exceeded its timeout, sending KILL QUERY"
            )
            self.worker.cancel_query(QueryExecutor.CANCEL_BY_TIMEOUT)

    def __on_connected(self, check: AccountCheck | None) -> None:
        session = self.__session_config or self.__active_config()
        self.__check = check
        self.__schema.clear()
        self.__schema.database = session.database
        self.__set_state(ConnectionState.CONNECTED)
        msg = "Connected to {}:{}/{}.".format(
            session.host, session.port, session.scope_label()
        )
        if self.caution_active and check is not None:
            caution = "{} Caution mode: the account can change data in {}. "
            caution += "Only read queries are allowed, but double-check what "
            caution += "you run."
            self.show_message(caution.format(msg, check.describe()), error=True)
        else:
            self.show_message(msg)
        self.__reload_bookmarks()
        self.__editor.setFocus()
        self.refresh_tables()

    def __on_connect_failed(self, message: str) -> None:
        self.__set_state(ConnectionState.ERROR)
        self.show_message(message, error=True)

    def __on_disconnected(self) -> None:
        if self.__switching:
            # Closed to open another connection: stay "connecting".
            self.__switching = False
            return
        if self.__closed or self.__state == ConnectionState.ERROR:
            return  # keep showing the error that caused the disconnection
        self.__set_state(ConnectionState.DISCONNECTED)
        self.show_message("Disconnected.")

    def __finish_run(self) -> None:
        self.__watchdog.stop()
        self.__running = False
        self.__progress.hide()
        self.__stop_button.finish()
        self.__running_label.clear()
        self.__running_label.hide()
        self.__update_actions()

    def __on_query_finished(self, result: QueryResult) -> None:
        self.__result = result
        self.__finish_run()
        self.__results.set_result(result.columns, result.rows)
        self.__rows_label.setText("{} rows".format(len(result.rows)))
        elapsed_ms = result.elapsed * 1000
        self.__time_label.setText("· {:.0f} ms".format(elapsed_ms))
        if result.truncated:
            msg = "· Results limited to the first {} rows"
            self.__limit_label.setText(msg.format(result.row_limit))
        preview = MainWindow.query_preview(result.statement)
        if result.columns:
            msg = "Query executed: {}"
        else:
            msg = "Query executed (no tabular result): {}"
        # The full statement is in the tooltip when the preview is cut.
        cut = preview != " ".join(result.statement.split())
        full = result.statement if cut else ""
        self.show_message(msg.format(preview), tooltip=full)

    def __on_query_failed(self, message: str, kind: str) -> None:
        self.__finish_run()
        self.show_message(message, error=True)
        if kind == MainWindow.__REJECTED_KIND:
            self.__show_read_only_notice(message)
        elif kind == "not_connected":
            self.__set_state(ConnectionState.DISCONNECTED)
        elif kind == "connection_lost":
            self.__set_state(ConnectionState.ERROR)
            self.worker.disconnect_requested.emit()

    def __show_read_only_notice(self, reason: str) -> None:
        """Tell the user, in a dialog, that the query was not run because
        only read queries are allowed (also with an account that can change
        data). Window-modal but not blocking."""
        if self.__read_only_notice is not None:
            self.__read_only_notice.close()
        text = "The query was not run: {} runs only read queries "
        text += "(SELECT, SHOW, DESCRIBE, EXPLAIN)."
        info = reason
        check = self.__check
        if self.caution_active and check is not None:
            extra = "\n\nThe account could change data in {}, but "
            extra += "queries that write or change data are always refused."
            info += extra.format(check.describe())
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        # Validator reasons and database names: never rendered as HTML.
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setWindowTitle(MainWindow.READ_ONLY_NOTICE_TITLE)
        box.setText(text.format(AppInfo.DISPLAY_NAME))
        box.setInformativeText(info)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        self.__read_only_notice = box
        box.open()

    def __show_placeholder_notice(self, text: str) -> None:
        """Repeat in a dialog that the query was not run because of its
        placeholders. Window-modal but not blocking."""
        if self.__placeholder_notice is not None:
            self.__placeholder_notice.close()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        # Placeholder names come from the editor: never rendered as HTML.
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setWindowTitle(MainWindow.PLACEHOLDER_NOTICE_TITLE)
        box.setText(text)
        self.__placeholder_notice = box
        box.open()

    def __timeout(self) -> int:
        return self.__active_config().query_timeout

    def __write_access(self, databases: list[str]) -> dict[str, str] | None:
        """Privileges beyond reading of each writable database in
        ``databases`` (also those created after the connection), from the
        grants read at connection; None when unknown."""
        if self.__check is None:
            return None
        check = AccountCheck(self.__check.privileges, databases)
        return {name: check.reason(name) for name in check.write_databases}

    def __wire(self, database: str) -> str:
        """Database as sent to the worker: empty (the default database of
        the session) unless the session covers all the databases."""
        return database if self.all_databases else ""

    def __local(self, wire: str) -> str:
        """Database of a worker response (empty means the configured
        one)."""
        if wire:
            return wire
        config = self.__session_config
        return config.database if config is not None else ""

    def __on_databases_loaded(self, databases: list[str]) -> None:
        if self.__state != ConnectionState.CONNECTED:
            return  # stale: the session was closed meanwhile
        self.__schema.set_databases(databases)
        self.__sidebar.set_write_access(self.__write_access(databases))
        self.__sidebar.set_databases(databases, self.__schema.database)
        if self.__schema.database:
            self.load_tables(self.__schema.database)
        self.__editor.refresh_completion()

    def __on_databases_failed(self, message: str) -> None:
        if self.__state == ConnectionState.CONNECTED:
            self.__sidebar.set_error(message)

    def __on_database_changed(self, database: str) -> None:
        if self.__pending_database == database:
            self.__pending_database = ""
        if self.__state != ConnectionState.CONNECTED:
            return
        self.__schema.database = database
        self.__sidebar.set_active_database(database)
        self.__set_state(self.__state)
        self.show_message("Active database: {}.".format(database))
        self.load_tables(database)
        self.__editor.refresh_completion()

    def __on_database_failed(self, database: str, message: str) -> None:
        if self.__pending_database == database:
            self.__pending_database = ""
        if self.__state == ConnectionState.CONNECTED:
            self.show_message(message, error=True)

    def __on_tables_loaded(self, wire: str, tables: list[TableInfo]) -> None:
        database = self.__local(wire)
        self.__pending_tables.discard(database.casefold())
        # A response that arrives after a disconnection is stale.
        if self.__state == ConnectionState.CONNECTED:
            self.__schema.set_tables(tables, database)
            self.__sidebar.set_tables(tables, database)
            self.__editor.refresh_completion()

    def __on_tables_failed(self, wire: str, message: str) -> None:
        database = self.__local(wire)
        self.__pending_tables.discard(database.casefold())
        if self.__state == ConnectionState.CONNECTED:
            # Remembered as empty, so they are not requested again.
            self.__schema.set_tables([], database)
            self.__sidebar.set_tables_error(database, message)

    def __on_columns_loaded(
        self, wire: str, columns: dict[str, tuple[ColumnInfo, ...]]
    ) -> None:
        if self.__state != ConnectionState.CONNECTED:
            return  # stale: the session was closed meanwhile
        self.__schema.set_all_columns(columns, self.__local(wire))
        self.__sidebar.refresh_columns()
        self.__editor.refresh_completion()

    def __on_columns_failed(self, wire: str, message: str) -> None:
        # Columns are then read table by table, when needed.
        self.__log.info("Columns not listed at once: {}", message)

    def __on_table_columns_loaded(
        self, wire: str, table: str, columns: tuple[ColumnInfo, ...]
    ) -> None:
        database = self.__local(wire)
        self.__pending_columns.discard((database.casefold(), table.casefold()))
        if self.__state != ConnectionState.CONNECTED:
            return
        self.__schema.set_columns(table, columns, database)
        self.__sidebar.refresh_columns()
        self.__editor.refresh_completion()

    def __on_table_columns_failed(
        self, wire: str, table: str, message: str
    ) -> None:
        database = self.__local(wire)
        self.__pending_columns.discard((database.casefold(), table.casefold()))
        if self.__state != ConnectionState.CONNECTED:
            return
        # Remembered as empty, so they are not requested again and again.
        self.__schema.set_columns(table, (), database)
        self.__sidebar.set_columns_error(table, message, database)

    # ------------------------------------------------------------------- export
    def __ask_export_path(
        self, fixed: ResultExporter | None = None
    ) -> Path | None:
        """File chosen in the save dialog, with the extension of the format
        added when missing; None when cancelled. With ``fixed`` only that
        format is offered and its extension is always enforced."""
        exporters = [fixed] if fixed is not None else ResultExporters.all()
        current = fixed or (
            ResultExporters.for_name_filter(self.__export_filter)
            or exporters[0]
        )
        start = self.__export_dir / "result{}".format(current.extension)
        name, selected = QFileDialog.getSaveFileName(
            self,
            "Export result",
            str(start),
            ";;".join(e.name_filter for e in exporters),
            current.name_filter,
        )
        if not name:
            return None
        path = Path(name)
        chosen = fixed or ResultExporters.for_name_filter(selected) or current
        if fixed is not None:
            missing = path.suffix.lower() != fixed.extension
        else:
            missing = ResultExporters.for_path(path) is None
        if missing:
            path = path.with_name("{}{}".format(path.name, chosen.extension))
            # The dialog confirmed the overwrite of the name without the
            # extension only.
            if path.exists() and not self.__confirm_overwrite(path):
                return None
        self.__export_filter = (
            ResultExporters.for_path(path) or chosen
        ).name_filter
        self.__export_dir = path.parent
        return path

    def __confirm_overwrite(self, path: Path) -> bool:
        return self.__confirm(
            "Export result",
            "The file {} already exists. Replace it?".format(path.name),
        )

    def __confirm(self, title: str, text: str) -> bool:
        """Yes/No question; ``text`` (names, paths) is never rendered as
        HTML."""
        answer = QMessageBox.question(self, title, SafeText.html(text))
        return answer == QMessageBox.StandardButton.Yes

    def __warn(self, title: str, text: str) -> None:
        """Warning dialog; ``text`` is never rendered as HTML."""
        QMessageBox.warning(self, title, SafeText.html(text))

    def __finish_export(self) -> QueryResult | None:
        thread = self.__export_thread
        source = self.__export_source
        self.__export_thread = None
        self.__export_source = None
        if thread is not None:
            thread.wait()
            thread.deleteLater()
        self.__update_actions()
        return source

    def __on_exported(self, report: ExportReport) -> None:
        source = self.__finish_export()
        parts = ["Exported {} rows to {}.".format(report.rows, report.path)]
        if source is not None and source.truncated:
            msg = "The result was limited to the first {} rows: the others "
            msg += "are not in the file."
            parts.append(msg.format(source.row_limit))
        if report.shortened_cells:
            msg = "{} cells exceeded the Excel limit and were "
            msg += "truncated."
            parts.append(msg.format(report.shortened_cells))
        self.show_message(" ".join(parts))

    def __on_export_failed(self, message: str) -> None:
        self.__finish_export()
        self.show_message(message, error=True)

    # ----------------------------------------------------------------- geometry
    def __restore_geometry(self) -> None:
        ui = self.__app_config.ui
        try:
            if ui.window_geometry:
                self.restoreGeometry(
                    QByteArray(base64.b64decode(ui.window_geometry))
                )
            if ui.splitter_state:
                self.__splitter.restoreState(
                    QByteArray(base64.b64decode(ui.splitter_state))
                )
            if ui.sidebar_state:
                self.__sidebar_splitter.restoreState(
                    QByteArray(base64.b64decode(ui.sidebar_state))
                )
        except (ValueError, TypeError):
            self.__log.warning("Invalid window geometry: ignored")

    @staticmethod
    def __encode(data: QByteArray) -> str:
        return base64.b64encode(bytes(data.data())).decode("ascii")
