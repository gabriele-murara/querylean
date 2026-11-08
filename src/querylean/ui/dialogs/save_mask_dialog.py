"""Dialog to save a query with placeholders as a mask."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

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


class SaveMaskDialog(QDialog):
    """Name of the mask and, for each placeholder of the query, its type,
    whether it takes a list of values, its default value and a
    description.

    The preview shows the query compiled with the defaults; it must be
    accepted by the validator as a read query, otherwise "Save" stays
    disabled. ``MaskTemplate`` raises ``MaskError`` for a query whose
    placeholders cannot be parsed: build the dialog only for valid
    masks.
    """

    TITLE = "Save mask"
    __COLUMNS = ("Placeholder", "Type", "List", "Default", "Description")
    __NAME, __TYPE, __LIST, __DEFAULT, __DESCRIPTION = range(5)
    __DEFAULT_WIDTH = 190

    def __init__(
        self,
        sql: str,
        known: Mapping[str, Placeholder] | None = None,
        *,
        name: str = "",
        validator: ReadOnlyValidator | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(SaveMaskDialog.TITLE)
        self.setMinimumWidth(720)
        self.__template = MaskTemplate(sql)
        self.__validator = validator or ReadOnlyValidator()
        known = known or {}

        self.__name = QLineEdit(name)
        self.__name.setMaxLength(QueryBookmark.MAX_NAME_LENGTH)
        self.__name.setPlaceholderText("Name shown in Bookmarked queries")

        names = self.__template.names
        self.__table = QTableWidget(len(names), len(SaveMaskDialog.__COLUMNS))
        self.__table.setHorizontalHeaderLabels(list(SaveMaskDialog.__COLUMNS))
        self.__table.verticalHeader().setVisible(False)
        header = self.__table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            SaveMaskDialog.__DESCRIPTION, QHeaderView.ResizeMode.Stretch
        )
        # Room for a date-time or a short list.
        header.setSectionResizeMode(
            SaveMaskDialog.__DEFAULT, QHeaderView.ResizeMode.Interactive
        )
        self.__table.setColumnWidth(
            SaveMaskDialog.__DEFAULT, SaveMaskDialog.__DEFAULT_WIDTH
        )
        self.__rows: dict[
            str, tuple[QComboBox, QCheckBox, QLineEdit, QLineEdit]
        ]
        self.__rows = {}
        for row, placeholder_name in enumerate(names):
            self.__add_row(row, known.get(placeholder_name), placeholder_name)

        self.__preview = QueryPreview(120)
        self.__status = StatusLabel()

        hint = "Each placeholder is replaced by a value of its type: "
        hint += "numbers and booleans as they are, everything else as an "
        hint += "escaped string. A list takes comma-separated values (for "
        hint += "IN (…)). The preview uses the default values."
        hint_label = QLabel(hint)
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet(StatusLabel.HINT_STYLE)

        buttons = QDialogButtonBox()
        self.__save_button: QPushButton = buttons.addButton(
            "Save", QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Name *", self.__name)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.__table)
        layout.addWidget(hint_label)
        layout.addWidget(QLabel("Preview"))
        layout.addWidget(self.__preview)
        layout.addWidget(self.__status)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(buttons)
        layout.addLayout(bottom)

        self.__name.textChanged.connect(self.refresh)
        self.refresh()

    # -------------------------------------------------------------- widgets
    @property
    def name_edit(self) -> QLineEdit:
        """Name of the mask."""
        return self.__name

    @property
    def table(self) -> QTableWidget:
        """One row per placeholder."""
        return self.__table

    @property
    def preview(self) -> QueryPreview:
        """Query compiled with the default values."""
        return self.__preview

    @property
    def status(self) -> StatusLabel:
        """Outcome of the check of the preview."""
        return self.__status

    @property
    def save_button(self) -> QPushButton:
        """ "Save" button (enabled only for a valid mask)."""
        return self.__save_button

    def type_box(self, name: str) -> QComboBox:
        """Type selector of the placeholder ``name``."""
        return self.__rows[name][0]

    def list_box(self, name: str) -> QCheckBox:
        """ "List" checkbox of the placeholder ``name``."""
        return self.__rows[name][1]

    def default_edit(self, name: str) -> QLineEdit:
        """Default value of the placeholder ``name``."""
        return self.__rows[name][2]

    def description_edit(self, name: str) -> QLineEdit:
        """Description of the placeholder ``name``."""
        return self.__rows[name][3]

    # --------------------------------------------------------------- values
    def mask_name(self) -> str:
        """Name entered, on one line."""
        return QueryBookmark.clean_name(self.__name.text())

    def placeholders(self) -> tuple[Placeholder, ...]:
        """Placeholders as defined in the table, in order."""
        result = []
        for name in self.__template.names:
            type_box, list_box, default, description = self.__rows[name]
            result.append(
                Placeholder(
                    name,
                    type_box.currentData(),
                    default=default.text(),
                    description=description.text().strip(),
                    is_list=list_box.isChecked(),
                )
            )
        return tuple(result)

    def is_valid(self) -> bool:
        """True when the mask can be saved."""
        return self.__save_button.isEnabled()

    def refresh(self, *_: object) -> None:
        """Compile the preview with the defaults and check it."""
        placeholders = {p.name: p for p in self.placeholders()}
        defaults = {name: p.default for name, p in placeholders.items()}
        try:
            compiled = self.__template.compile(placeholders, defaults)
        except MaskError as exc:
            self.__preview.setPlainText("")
            self.__set_status(False, exc.message)
            return
        self.__preview.setPlainText(compiled)
        result = self.__validator.validate(compiled)
        if not result.ok:
            msg = "The mask is not a read query: {}"
            self.__set_status(False, msg.format(result.reason))
            return
        if not self.mask_name():
            self.__set_status(False, "Enter a name for the mask.")
            return
        self.__set_status(True, "Read query: the mask can be saved.")

    # ------------------------------------------------------------ internals
    def __add_row(self, row: int, known: Placeholder | None, name: str) -> None:
        placeholder = known or Placeholder(name)
        item = QTableWidgetItem("${{{}}}".format(name))
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.__table.setItem(row, SaveMaskDialog.__NAME, item)
        type_box = QComboBox()
        for kind in PlaceholderType:
            type_box.addItem(kind.label, kind)
        type_box.setCurrentIndex(list(PlaceholderType).index(placeholder.kind))
        list_box = QCheckBox()
        list_box.setChecked(placeholder.is_list)
        list_box.setToolTip("Several comma-separated values, for IN (…)")
        default = QLineEdit(placeholder.default)
        description = QLineEdit(placeholder.description)
        description.setMaxLength(Placeholder.MAX_DESCRIPTION_LENGTH)
        self.__table.setCellWidget(row, SaveMaskDialog.__TYPE, type_box)
        self.__table.setCellWidget(row, SaveMaskDialog.__LIST, list_box)
        self.__table.setCellWidget(row, SaveMaskDialog.__DEFAULT, default)
        self.__table.setCellWidget(
            row, SaveMaskDialog.__DESCRIPTION, description
        )
        type_box.currentIndexChanged.connect(self.refresh)
        list_box.toggled.connect(self.refresh)
        default.textChanged.connect(self.refresh)
        self.__rows[name] = (type_box, list_box, default, description)

    def __set_status(self, ok: bool, message: str) -> None:
        self.__status.show_status(ok, message)
        self.__save_button.setEnabled(ok)
