"""Dialog to fill in the placeholders of a mask and run it."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QDate, QDateTime, Qt, QTime, SignalInstance
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from querylean.bookmarks.bookmark_store import BookmarkStore
from querylean.bookmarks.mask_error import MaskError
from querylean.bookmarks.mask_template import MaskTemplate
from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_type import PlaceholderType
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.database.validation.read_only_validator import (
    ReadOnlyValidator,
)
from querylean.ui.dialogs.query_preview import QueryPreview
from querylean.ui.dialogs.status_label import StatusLabel


class FillMaskDialog(QDialog):
    """One field per placeholder of a mask, the compiled query and the
    outcome of its check.

    A field starts with the value of the last run, highlighted in yellow
    while it is unchanged ("used previously"), or else with the default.
    Every value is required: "Run" stays disabled until all of them are
    valid for their type and the compiled query is accepted by the
    validator. Dates and times use calendar and time editors, booleans a
    selector and lists a box with one value per line (or comma-separated).

    The name of the mask can be changed too (``mask_name``): it must not
    be empty nor the name of another bookmark (``taken_names``); the
    caller renames the mask when the dialog ends with "Run" or "Open in
    editor".

    The dialog ends with ``Accepted`` (run ``compiled_sql()``),
    ``EDIT_RESULT`` (open the mask in the editor) or ``Rejected``.
    """

    TITLE = "Run mask"
    EDIT_RESULT = 2
    PREVIOUS_BACKGROUND = "#fff3b0"
    PREVIOUS_FOREGROUND = "#000000"
    PREVIOUS_TOOLTIP = "Used previously"
    __DATE_FORMAT = "yyyy-MM-dd"
    __TIME_FORMAT = "HH:mm:ss"
    __DATETIME_FORMAT = "yyyy-MM-dd HH:mm:ss"
    __TRUE = "true"
    __FALSE = "false"

    def __init__(
        self,
        mask: QueryBookmark,
        *,
        validator: ReadOnlyValidator | None = None,
        taken_names: Iterable[str] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(FillMaskDialog.TITLE)
        # Names of the other bookmarks, compared ignoring case.
        self.__taken = {
            QueryBookmark.clean_name(name).casefold()
            for name in taken_names
            if not mask.same_name(name)
        }
        self.setMinimumWidth(560)
        self.__mask = mask
        self.__template = MaskTemplate(mask.sql)
        self.__validator = validator or ReadOnlyValidator()
        self.__placeholders = {p.name: p for p in mask.placeholders}
        self.__fields: dict[str, QWidget] = {}
        # Value of each field filled from the last run, as the field
        # renders it: the field is yellow while it still holds it.
        self.__previous: dict[str, str] = {}
        self.__compiled = ""

        self.__name = QLineEdit(mask.name)
        self.__name.setMaxLength(QueryBookmark.MAX_NAME_LENGTH)
        tip = "Name shown in Bookmarked queries: changed when the mask is "
        tip += "run or opened in the editor"
        self.__name.setToolTip(tip)
        font = self.__name.font()
        font.setBold(True)
        self.__name.setFont(font)

        form = QFormLayout()
        form.addRow("Name", self.__name)
        last_values = mask.last_values
        for name in self.__template.names:
            placeholder = self.__placeholders[name]
            field = FillMaskDialog.__make_field(placeholder)
            self.__fields[name] = field
            if name in last_values:
                FillMaskDialog.__set_value(
                    placeholder, field, last_values[name]
                )
                self.__previous[name] = FillMaskDialog.__value_of(field)
            else:
                FillMaskDialog.__set_value(
                    placeholder, field, placeholder.default
                )
            FillMaskDialog.__changed_signal(field).connect(self.refresh)
            form.addRow(FillMaskDialog.__label(placeholder), field)
            if placeholder.description:
                description = QLabel(placeholder.description)
                description.setTextFormat(Qt.TextFormat.PlainText)
                description.setWordWrap(True)
                description.setStyleSheet(StatusLabel.HINT_STYLE)
                form.addRow("", description)

        self.__legend = QLabel(
            "Fields in yellow hold the values used the last time."
        )
        self.__legend.setTextFormat(Qt.TextFormat.PlainText)
        self.__legend.setVisible(bool(self.__previous))

        self.__preview = QueryPreview()
        self.__status = StatusLabel()

        buttons = QDialogButtonBox()
        self.__run_button: QPushButton = buttons.addButton(
            "Run", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.__run_button.setDefault(True)
        self.__defaults_button: QPushButton = buttons.addButton(
            "Defaults", QDialogButtonBox.ButtonRole.ResetRole
        )
        self.__defaults_button.setToolTip("Fill every field with its default")
        self.__edit_button: QPushButton = buttons.addButton(
            "Open in editor", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.__edit_button.setToolTip(
            "Load the mask, with its placeholders, in the editor"
        )
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.__defaults_button.clicked.connect(self.use_defaults)
        self.__edit_button.clicked.connect(self.open_in_editor)
        self.__name.textChanged.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.__legend)
        layout.addWidget(QLabel("Query"))
        layout.addWidget(self.__preview)
        layout.addWidget(self.__status)
        layout.addWidget(buttons)

        self.refresh()
        if self.__fields:
            next(iter(self.__fields.values())).setFocus()

    # -------------------------------------------------------------- widgets
    @property
    def mask(self) -> QueryBookmark:
        """Mask being filled in."""
        return self.__mask

    @property
    def preview(self) -> QueryPreview:
        """Query compiled with the current values."""
        return self.__preview

    @property
    def status(self) -> StatusLabel:
        """Outcome of the check of the values and of the query."""
        return self.__status

    @property
    def legend(self) -> QLabel:
        """Explanation of the yellow fields (shown only with them)."""
        return self.__legend

    @property
    def run_button(self) -> QPushButton:
        """ "Run" button (enabled only for a valid query)."""
        return self.__run_button

    @property
    def defaults_button(self) -> QPushButton:
        """ "Defaults" button."""
        return self.__defaults_button

    @property
    def edit_button(self) -> QPushButton:
        """ "Open in editor" button."""
        return self.__edit_button

    @property
    def name_edit(self) -> QLineEdit:
        """Name of the mask (editable)."""
        return self.__name

    def mask_name(self) -> str:
        """Name entered, on one line."""
        return QueryBookmark.clean_name(self.__name.text())

    def is_renamed(self) -> bool:
        """True when the name entered differs from the saved one."""
        return self.mask_name() != self.__mask.name

    def field(self, name: str) -> QWidget:
        """Input widget of the placeholder ``name``."""
        return self.__fields[name]

    # --------------------------------------------------------------- values
    def value(self, name: str) -> str:
        """Current value of the placeholder ``name``, as text."""
        return FillMaskDialog.__value_of(self.__fields[name])

    def values(self) -> dict[str, str]:
        """Current values, by placeholder name."""
        return {name: self.value(name) for name in self.__fields}

    def is_previous(self, name: str) -> bool:
        """True when the field of ``name`` holds the value of the last
        run."""
        return self.__previous.get(name) == self.value(name)

    def compiled_sql(self) -> str:
        """Query compiled with the current values (empty when invalid)."""
        return self.__compiled

    def is_valid(self) -> bool:
        """True when the query can be run."""
        return self.__run_button.isEnabled()

    def use_defaults(self) -> None:
        """Fill every field with the default of its placeholder."""
        for name, field in self.__fields.items():
            placeholder = self.__placeholders[name]
            FillMaskDialog.__set_value(placeholder, field, placeholder.default)
        self.refresh()

    def refresh(self, *_: object) -> None:
        """Check the name, colour the fields, compile the query and check
        it."""
        for name, field in self.__fields.items():
            FillMaskDialog.__mark(field, self.is_previous(name))
        self.__compiled = ""
        name_error = self.__name_error()
        self.__edit_button.setEnabled(name_error is None)
        if name_error is not None:
            self.__set_status(False, name_error)
            return
        try:
            compiled = self.__template.compile(
                self.__placeholders, self.values()
            )
        except MaskError as exc:
            self.__preview.setPlainText("")
            self.__set_status(False, exc.message)
            return
        self.__preview.setPlainText(compiled)
        result = self.__validator.validate(compiled)
        if not result.ok:
            msg = "Only read queries can be run. {}"
            self.__set_status(False, msg.format(result.reason))
            return
        self.__compiled = compiled
        self.__set_status(True, "Read query: ready to run.")

    def accept(self) -> None:
        """Close with ``Accepted`` only when the query can be run."""
        if self.is_valid():
            super().accept()

    def open_in_editor(self) -> None:
        """Close with ``EDIT_RESULT`` (only with a valid name)."""
        if self.__edit_button.isEnabled():
            self.done(FillMaskDialog.EDIT_RESULT)

    def __name_error(self) -> str | None:
        name = self.mask_name()
        if not name:
            return "Enter a name for the mask."
        if name.casefold() in self.__taken:
            return BookmarkStore.NAME_TAKEN.format(name)
        return None

    # ------------------------------------------------------------ internals
    def __set_status(self, ok: bool, message: str) -> None:
        self.__status.show_status(ok, message)
        self.__run_button.setEnabled(ok)

    @staticmethod
    def __label(placeholder: Placeholder) -> QLabel:
        text = "{} ({} list)" if placeholder.is_list else "{} ({})"
        label = QLabel(
            text.format(placeholder.token, placeholder.kind.label.lower())
        )
        label.setTextFormat(Qt.TextFormat.PlainText)
        return label

    @staticmethod
    def __make_field(placeholder: Placeholder) -> QWidget:
        kind = placeholder.kind
        if placeholder.is_list:
            box = QPlainTextEdit()
            box.setTabChangesFocus(True)
            box.setMaximumHeight(90)
            box.setPlaceholderText(
                "One value per line, or values separated by commas"
            )
            return box
        if kind is PlaceholderType.DATE:
            date = QDateEdit()
            date.setCalendarPopup(True)
            date.setDisplayFormat(FillMaskDialog.__DATE_FORMAT)
            date.setDate(QDate.currentDate())
            return date
        if kind is PlaceholderType.TIME:
            time = QTimeEdit()
            time.setDisplayFormat(FillMaskDialog.__TIME_FORMAT)
            return time
        if kind is PlaceholderType.DATETIME:
            moment = QDateTimeEdit()
            moment.setCalendarPopup(True)
            moment.setDisplayFormat(FillMaskDialog.__DATETIME_FORMAT)
            moment.setDateTime(QDateTime(QDate.currentDate(), QTime(0, 0, 0)))
            return moment
        if kind is PlaceholderType.BOOLEAN:
            choice = QComboBox()
            choice.addItem("TRUE", FillMaskDialog.__TRUE)
            choice.addItem("FALSE", FillMaskDialog.__FALSE)
            return choice
        edit = QLineEdit()
        edit.setPlaceholderText("Required")
        return edit

    @staticmethod
    def __changed_signal(field: QWidget) -> SignalInstance:
        if isinstance(field, QPlainTextEdit):
            return field.textChanged
        if isinstance(field, QDateTimeEdit):
            # Also QDateEdit and QTimeEdit.
            return field.dateTimeChanged
        if isinstance(field, QComboBox):
            return field.currentIndexChanged
        return field.textChanged

    @staticmethod
    def __value_of(field: QWidget) -> str:
        if isinstance(field, QPlainTextEdit):
            return field.toPlainText()
        if isinstance(field, QTimeEdit):
            return field.time().toString(FillMaskDialog.__TIME_FORMAT)
        if isinstance(field, QDateEdit):
            return field.date().toString(FillMaskDialog.__DATE_FORMAT)
        if isinstance(field, QDateTimeEdit):
            return field.dateTime().toString(FillMaskDialog.__DATETIME_FORMAT)
        if isinstance(field, QComboBox):
            return str(field.currentData())
        if isinstance(field, QLineEdit):
            return field.text()
        return ""

    @staticmethod
    def __set_value(
        placeholder: Placeholder, field: QWidget, value: str
    ) -> None:
        if isinstance(field, QPlainTextEdit):
            field.setPlainText(value)
            return
        if isinstance(field, QLineEdit):
            field.setText(value)
            return
        try:
            normalized = placeholder.kind.normalize(value)
        except MaskError:
            return
        if isinstance(field, QTimeEdit):
            # Fractions of a second are not shown by the editor.
            field.setTime(
                QTime.fromString(normalized[:8], FillMaskDialog.__TIME_FORMAT)
            )
        elif isinstance(field, QDateEdit):
            field.setDate(
                QDate.fromString(normalized, FillMaskDialog.__DATE_FORMAT)
            )
        elif isinstance(field, QDateTimeEdit):
            field.setDateTime(
                QDateTime.fromString(
                    normalized[:19], FillMaskDialog.__DATETIME_FORMAT
                )
            )
        elif isinstance(field, QComboBox):
            field.setCurrentIndex(max(0, field.findData(normalized)))

    @staticmethod
    def __mark(field: QWidget, previous: bool) -> None:
        if previous:
            style = "{} {{ background-color: {}; color: {}; }}"
            field.setStyleSheet(
                style.format(
                    field.metaObject().className(),
                    FillMaskDialog.PREVIOUS_BACKGROUND,
                    FillMaskDialog.PREVIOUS_FOREGROUND,
                )
            )
            field.setToolTip(FillMaskDialog.PREVIOUS_TOOLTIP)
        else:
            field.setStyleSheet("")
            field.setToolTip("")
