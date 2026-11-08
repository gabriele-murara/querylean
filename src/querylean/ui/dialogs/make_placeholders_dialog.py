"""Dialog to choose the values of a query that become placeholders."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
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
from querylean.bookmarks.value_candidate import ValueCandidate
from querylean.ui.dialogs.query_preview import QueryPreview
from querylean.ui.dialogs.status_label import StatusLabel
from querylean.ui.safe_text import SafeText


class MakePlaceholdersDialog(QDialog):
    """Every value of the query that could become a placeholder, one per
    row: whether to replace it, the value, the placeholder name (suggested
    from the compared column, editable), the detected type and the line.

    Values compared with a column start checked, the others (``LIMIT``,
    function arguments, …) unchecked. The preview shows the query with
    the chosen placeholders; "Make placeholders" stays disabled until at
    least one value is chosen and every name is valid. The same name on
    several values makes them one placeholder, so their types must match.
    """

    TITLE = "Make placeholders"
    __COLUMNS = ("Use", "Value", "Placeholder", "Type", "Line")
    __USE, __VALUE, __NAME, __TYPE, __LINE = range(5)
    __MAX_VALUE_TEXT = 60
    __NAME_WIDTH = 210

    def __init__(
        self,
        sql: str,
        candidates: tuple[ValueCandidate, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(MakePlaceholdersDialog.TITLE)
        self.setMinimumWidth(640)
        self.__sql = sql
        self.__candidates = tuple(candidates)
        self.__result_sql = sql
        self.__result_placeholders: tuple[Placeholder, ...] = ()
        self.__rows: list[tuple[QCheckBox, QLineEdit]] = []

        intro = QLabel(
            "Choose the values to replace with ${NAME} placeholders."
        )
        intro.setTextFormat(Qt.TextFormat.PlainText)

        self.__table = QTableWidget(
            len(self.__candidates), len(MakePlaceholdersDialog.__COLUMNS)
        )
        self.__table.setHorizontalHeaderLabels(
            list(MakePlaceholdersDialog.__COLUMNS)
        )
        self.__table.verticalHeader().setVisible(False)
        header = self.__table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            MakePlaceholdersDialog.__VALUE, QHeaderView.ResizeMode.Stretch
        )
        # Room for names such as IMPORT_DATE_TIME.
        header.setSectionResizeMode(
            MakePlaceholdersDialog.__NAME, QHeaderView.ResizeMode.Interactive
        )
        self.__table.setColumnWidth(
            MakePlaceholdersDialog.__NAME, MakePlaceholdersDialog.__NAME_WIDTH
        )
        for row, candidate in enumerate(self.__candidates):
            self.__add_row(row, candidate)

        self.__preview = QueryPreview()
        self.__status = StatusLabel()

        buttons = QDialogButtonBox()
        self.__ok_button: QPushButton = buttons.addButton(
            MakePlaceholdersDialog.TITLE, QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.__table)
        layout.addWidget(QLabel("Preview"))
        layout.addWidget(self.__preview)
        layout.addWidget(self.__status)
        layout.addWidget(buttons)

        self.refresh()

    # -------------------------------------------------------------- widgets
    @property
    def table(self) -> QTableWidget:
        """One row per value."""
        return self.__table

    @property
    def preview(self) -> QueryPreview:
        """Query with the chosen placeholders."""
        return self.__preview

    @property
    def status(self) -> StatusLabel:
        """Why the placeholders cannot be made (empty when they can)."""
        return self.__status

    @property
    def ok_button(self) -> QPushButton:
        """ "Make placeholders" button."""
        return self.__ok_button

    def use_box(self, row: int) -> QCheckBox:
        """ "Use" checkbox of ``row``."""
        return self.__rows[row][0]

    def name_edit(self, row: int) -> QLineEdit:
        """Placeholder name of ``row``."""
        return self.__rows[row][1]

    # --------------------------------------------------------------- values
    def result_sql(self) -> str:
        """Query with the chosen placeholders."""
        return self.__result_sql

    def result_placeholders(self) -> tuple[Placeholder, ...]:
        """Placeholders made, in order of the text."""
        return self.__result_placeholders

    def choices(self) -> list[tuple[int, int, str]]:
        """``(start, end, name)`` of each chosen value."""
        return [
            (candidate.start, candidate.end, name.text().strip())
            for candidate, (use, name) in zip(
                self.__candidates, self.__rows, strict=True
            )
            if use.isChecked()
        ]

    def is_valid(self) -> bool:
        """True when the placeholders can be made."""
        return self.__ok_button.isEnabled()

    def refresh(self, *_: object) -> None:
        """Rebuild the preview and check the choices."""
        self.__result_sql = self.__sql
        self.__result_placeholders = ()
        choices = self.choices()
        error = self.__check(choices)
        if error is None:
            try:
                sql, placeholders = MaskTemplate.make_placeholders(
                    self.__sql, choices
                )
            except MaskError as exc:
                error = exc.message
            else:
                self.__result_sql = sql
                self.__result_placeholders = placeholders
        self.__preview.setPlainText(self.__result_sql)
        self.__status.show_status(False, error or "")
        self.__ok_button.setEnabled(error is None)

    def accept(self) -> None:
        """Close with ``Accepted`` only when the choices are valid."""
        if self.is_valid():
            super().accept()

    # ------------------------------------------------------------ internals
    def __check(self, choices: list[tuple[int, int, str]]) -> str | None:
        """Reason why ``choices`` cannot be applied, None when they can."""
        if not choices:
            return "Choose at least one value."
        kinds: dict[str, tuple[object, bool]] = {}
        for candidate, (use, name_edit) in zip(
            self.__candidates, self.__rows, strict=True
        ):
            if not use.isChecked():
                continue
            name = name_edit.text().strip()
            if not Placeholder.is_valid_name(name):
                return Placeholder.INVALID_NAME.format(name)
            placeholder = candidate.placeholder
            kind = (placeholder.kind, placeholder.is_list)
            if kinds.setdefault(name, kind) != kind:
                msg = "${{{}}} is used for values of different types: "
                msg += "give them different names."
                return msg.format(name)
        return None

    def __add_row(self, row: int, candidate: ValueCandidate) -> None:
        placeholder = candidate.placeholder
        use = QCheckBox()
        use.setChecked(candidate.compared)
        use.setToolTip("Replace this value with a placeholder")
        name = QLineEdit(placeholder.name)
        name.setMaxLength(Placeholder.MAX_NAME_LENGTH)
        value = QTableWidgetItem(
            SafeText.one_line(
                candidate.text, MakePlaceholdersDialog.__MAX_VALUE_TEXT
            )
        )
        value.setToolTip(SafeText.tooltip(candidate.text))
        kind = placeholder.kind.label
        if placeholder.is_list:
            kind = "{} list".format(kind)
        line = self.__sql.count("\n", 0, candidate.start) + 1
        items = (
            (MakePlaceholdersDialog.__VALUE, value),
            (MakePlaceholdersDialog.__TYPE, QTableWidgetItem(kind)),
            (MakePlaceholdersDialog.__LINE, QTableWidgetItem(str(line))),
        )
        for column, item in items:
            # Read only; the item text is never rendered as HTML.
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.__table.setItem(row, column, item)
        self.__table.setCellWidget(row, MakePlaceholdersDialog.__USE, use)
        self.__table.setCellWidget(row, MakePlaceholdersDialog.__NAME, name)
        use.toggled.connect(self.refresh)
        name.textChanged.connect(self.refresh)
        self.__rows.append((use, name))
