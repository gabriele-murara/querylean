"""Dialog to choose the bookmarked queries to import and their connection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from querylean.bookmarks.bookmark_import import BookmarkImport
from querylean.bookmarks.bookmark_import_plan import BookmarkImportPlan
from querylean.bookmarks.name_conflict import NameConflict
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.config.connection_profile import ConnectionProfile
from querylean.ui.dialogs.bookmark_table import BookmarkTable
from querylean.ui.dialogs.status_label import StatusLabel


class ImportBookmarksDialog(QDialog):
    """The bookmarks of an export file, one per row (name, type, status,
    placeholders, query on one line), and the saved connection to import
    them into: they are saved for its current target and run with its
    credentials.

    The status compares each bookmark with those already saved for the
    chosen connection (``BookmarkImportPlan.status``); a bookmark refused
    by the validator shows the reason, has no check box and is never
    imported. The other rows are checked at first; filter and "Select
    all"/"Select none" work as in the export dialog. The name conflict
    choice applies to bookmarks named like a different saved one. The last
    values of masks, when the file has them, are imported unless
    unchecked. "Import" stays disabled until a row is checked.
    """

    TITLE = "Import bookmarked queries"
    REFUSED = "Refused"
    __COLUMNS = ("Name", "Type", "Status", "Placeholders", "Query")
    __TYPE, __STATUS, __PLACEHOLDERS, __QUERY = range(1, 5)

    def __init__(
        self,
        source: BookmarkImport,
        profiles: Sequence[ConnectionProfile],
        saved: Mapping[str, Sequence[QueryBookmark]],
        *,
        profile_id: str = "",
        file_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(ImportBookmarksDialog.TITLE)
        self.setMinimumSize(820, 460)
        self.__source = source
        self.__items = source.items
        self.__profiles = tuple(profiles)
        self.__saved = {key: tuple(value) for key, value in saved.items()}

        text = "Choose the bookmarked queries to import and the connection "
        text += "to save them for: they will run on its database with its "
        text += "credentials. Only read queries are imported."
        intro = QLabel(text)
        intro.setTextFormat(Qt.TextFormat.PlainText)
        intro.setWordWrap(True)
        self.__origin = QLabel(self.__origin_text(file_name))
        self.__origin.setTextFormat(Qt.TextFormat.PlainText)
        self.__origin.setWordWrap(True)
        self.__origin.setStyleSheet(StatusLabel.HINT_STYLE)

        self.__connection = QComboBox()
        for profile in self.__profiles:
            self.__connection.addItem(profile.display_name, profile.profile_id)
        index = self.__connection.findData(profile_id)
        self.__connection.setCurrentIndex(max(index, 0))
        self.__target = QLabel()
        self.__target.setTextFormat(Qt.TextFormat.PlainText)
        self.__target.setStyleSheet(StatusLabel.HINT_STYLE)
        self.__conflict = QComboBox()
        for conflict in NameConflict:
            self.__conflict.addItem(conflict.label, conflict)
        form = QFormLayout()
        form.addRow("Import into:", self.__connection)
        form.addRow("", self.__target)
        form.addRow("When the name is in use:", self.__conflict)

        self.__filter = QLineEdit()
        self.__filter.setPlaceholderText("Filter by name or query")
        self.__filter.setClearButtonEnabled(True)
        self.__select_all = QPushButton("Select all")
        self.__select_none = QPushButton("Select none")
        top = QHBoxLayout()
        top.addWidget(self.__filter, 1)
        top.addWidget(self.__select_all)
        top.addWidget(self.__select_none)

        self.__table = BookmarkTable(
            ImportBookmarksDialog.__COLUMNS,
            len(self.__items),
            ImportBookmarksDialog.__QUERY,
        )
        for row, item in enumerate(self.__items):
            bookmark = item.bookmark
            self.__table.set_bookmark_row(
                row,
                bookmark,
                (
                    (
                        ImportBookmarksDialog.__TYPE,
                        BookmarkTable.kind_text(bookmark),
                        "",
                    ),
                    (
                        ImportBookmarksDialog.__PLACEHOLDERS,
                        BookmarkTable.placeholders_text(bookmark),
                        "",
                    ),
                    BookmarkTable.query_cell(
                        ImportBookmarksDialog.__QUERY, bookmark
                    ),
                ),
                checkable=item.importable,
            )

        has_values = any(
            item.importable and item.bookmark.last_values
            for item in self.__items
        )
        self.__last_values = QCheckBox("Import the last values used in masks")
        self.__last_values.setChecked(has_values)
        self.__last_values.setEnabled(has_values)
        self.__status = StatusLabel()

        buttons = QDialogButtonBox()
        self.__import_button: QPushButton = buttons.addButton(
            "Import", QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.__origin)
        layout.addLayout(form)
        layout.addLayout(top)
        layout.addWidget(self.__table, 1)
        layout.addWidget(self.__last_values)
        layout.addWidget(self.__status)
        layout.addWidget(buttons)

        self.__connection.currentIndexChanged.connect(self.show_statuses)
        self.__filter.textChanged.connect(self.apply_filter)
        self.__select_all.clicked.connect(
            lambda: self.__table.set_visible_checked(True)
        )
        self.__select_none.clicked.connect(
            lambda: self.__table.set_visible_checked(False)
        )
        self.__table.itemChanged.connect(self.refresh)
        self.show_statuses()

    # -------------------------------------------------------------- widgets
    @property
    def table(self) -> BookmarkTable:
        """One row per bookmark of the file."""
        return self.__table

    @property
    def connection_box(self) -> QComboBox:
        """Saved connection the bookmarks are imported into."""
        return self.__connection

    @property
    def target_label(self) -> QLabel:
        """Target of the chosen connection."""
        return self.__target

    @property
    def conflict_box(self) -> QComboBox:
        """``NameConflict`` choice."""
        return self.__conflict

    @property
    def filter_edit(self) -> QLineEdit:
        """Text that the visible rows contain."""
        return self.__filter

    @property
    def select_all_button(self) -> QPushButton:
        """Checks the visible rows."""
        return self.__select_all

    @property
    def select_none_button(self) -> QPushButton:
        """Unchecks the visible rows."""
        return self.__select_none

    @property
    def last_values_box(self) -> QCheckBox:
        """Whether the last values of masks are imported."""
        return self.__last_values

    @property
    def origin_label(self) -> QLabel:
        """File, producer and entries left out."""
        return self.__origin

    @property
    def status(self) -> StatusLabel:
        """How many bookmarks are checked."""
        return self.__status

    @property
    def import_button(self) -> QPushButton:
        """ "Import" button."""
        return self.__import_button

    # --------------------------------------------------------------- values
    def profile(self) -> ConnectionProfile | None:
        """Chosen connection (None without saved connections)."""
        index = self.__connection.currentIndex()
        if 0 <= index < len(self.__profiles):
            return self.__profiles[index]
        return None

    def conflict(self) -> NameConflict:
        """What to do with a name already in use."""
        value = self.__conflict.currentData()
        return value if isinstance(value, NameConflict) else NameConflict.SKIP

    def set_conflict(self, conflict: NameConflict) -> None:
        """Choose ``conflict``."""
        self.__conflict.setCurrentIndex(self.__conflict.findData(conflict))

    def selected(self) -> list[QueryBookmark]:
        """Checked bookmarks, in file order, for the target of the chosen
        connection (with their last values only when requested)."""
        profile = self.profile()
        if profile is None:
            return []
        target = QueryBookmark.target_of(profile.config)
        keep = self.__last_values.isChecked()
        return [
            self.__items[row].for_target(target, last_values=keep)
            for row in self.__table.checked_rows()
        ]

    def status_text(self, row: int) -> str:
        """Status shown for ``row``."""
        return self.__table.item(row, ImportBookmarksDialog.__STATUS).text()

    def show_statuses(self, *_: object) -> None:
        """Compare the bookmarks with those of the chosen connection."""
        profile = self.profile()
        saved: tuple[QueryBookmark, ...] = ()
        if profile is not None:
            saved = self.__saved.get(profile.profile_id, ())
            target = QueryBookmark.target_of(profile.config)
            self.__target.setText("Saved for {}".format(target))
        for row, item in enumerate(self.__items):
            if item.importable:
                text = BookmarkImportPlan.status(saved, item.bookmark)
                tooltip = ""
            else:
                text, tooltip = ImportBookmarksDialog.REFUSED, item.refusal
            self.__table.set_text(
                row,
                ImportBookmarksDialog.__STATUS,
                text,
                tooltip,
                enabled=item.importable,
            )
        self.refresh()

    def apply_filter(self, *_: object) -> None:
        """Hide the rows that do not contain the filter text."""
        self.__table.filter_rows(
            self.__filter.text(),
            [
                "{}\n{}".format(item.bookmark.name, item.bookmark.sql)
                for item in self.__items
            ],
        )
        self.refresh()

    def refresh(self, *_: object) -> None:
        """Count the checked rows and enable "Import"."""
        checked = len(self.__table.checked_rows())
        refused = sum(1 for item in self.__items if not item.importable)
        message = "{} of {} bookmarked queries selected."
        if refused:
            message += " {} refused: not read queries."
        message = message.format(checked, len(self.__items), refused)
        self.__status.show_neutral(message)
        self.__import_button.setEnabled(
            checked > 0 and self.profile() is not None
        )

    def accept(self) -> None:
        """Close with ``Accepted`` only when a bookmark is checked."""
        if self.selected():
            super().accept()

    # ------------------------------------------------------------ internals
    def __origin_text(self, file_name: str) -> str:
        parts = []
        if file_name:
            parts.append("File: {}".format(file_name))
        if self.__source.exported_by:
            parts.append("exported by {}".format(self.__source.exported_by))
        if self.__source.exported_at:
            parts.append("on {}".format(self.__source.exported_at))
        text = " ".join(parts)
        if self.__source.invalid:
            skipped = "{} invalid entries of the file left out."
            skipped = skipped.format(self.__source.invalid)
            text = "{}. {}".format(text, skipped) if text else skipped
        return text
