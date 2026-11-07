"""GUI tests of the "Run mask" dialog."""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QLineEdit,
    QPlainTextEdit,
    QTimeEdit,
)

from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_type import PlaceholderType
from querylean.bookmarks.query_bookmark import QueryBookmark
from querylean.ui.dialogs.fill_mask_dialog import FillMaskDialog


class TestFillMaskDialog:
    """Fields per type, last values in yellow, compiled query check."""

    SQL = "SELECT * FROM calls WHERE cli = '${DIGITS}' AND y = ${YEAR} "
    SQL += "AND c IN (${CODES}) AND d >= ${DAY} AND t < ${AT} "
    SQL += "AND h = ${HOUR} AND ok = ${OK}"
    PLACEHOLDERS = (
        Placeholder("DIGITS", default="339", description="Caller"),
        Placeholder("YEAR", PlaceholderType.INTEGER, default="2026"),
        Placeholder("CODES", default="A, B", is_list=True),
        Placeholder("DAY", PlaceholderType.DATE, default="2026-11-03"),
        Placeholder(
            "AT", PlaceholderType.DATETIME, default="2026-11-03 10:00:00"
        ),
        Placeholder("HOUR", PlaceholderType.TIME, default="10:30"),
        Placeholder("OK", PlaceholderType.BOOLEAN, default="true"),
    )

    def make(self, qtbot, last_values=None) -> FillMaskDialog:
        mask = QueryBookmark(
            "Calls", self.SQL, "t", self.PLACEHOLDERS, last_values
        )
        dialog = FillMaskDialog(mask)
        qtbot.addWidget(dialog)
        return dialog

    def test_fields_follow_the_types(self, qtbot):
        dialog = self.make(qtbot)
        assert isinstance(dialog.field("DIGITS"), QLineEdit)
        assert isinstance(dialog.field("YEAR"), QLineEdit)
        assert isinstance(dialog.field("CODES"), QPlainTextEdit)
        assert isinstance(dialog.field("DAY"), QDateEdit)
        assert dialog.field("DAY").calendarPopup()
        assert isinstance(dialog.field("AT"), QDateTimeEdit)
        assert isinstance(dialog.field("HOUR"), QTimeEdit)
        assert isinstance(dialog.field("OK"), QComboBox)

    def test_defaults_compile_to_a_read_query(self, qtbot):
        dialog = self.make(qtbot)
        assert dialog.values() == {
            "DIGITS": "339",
            "YEAR": "2026",
            "CODES": "A, B",
            "DAY": "2026-11-03",
            "AT": "2026-11-03 10:00:00",
            "HOUR": "10:30:00",
            "OK": "true",
        }
        assert dialog.is_valid()
        expected = "SELECT * FROM calls WHERE cli = '339' AND y = 2026 "
        expected += "AND c IN ('A', 'B') AND d >= '2026-11-03' "
        expected += "AND t < '2026-11-03 10:00:00' AND h = '10:30:00' "
        expected += "AND ok = TRUE"
        assert dialog.compiled_sql() == expected
        assert dialog.preview.toPlainText() == expected
        assert not dialog.legend.isVisible()
        assert not dialog.is_previous("YEAR")

    def test_every_value_is_required_and_checked(self, qtbot):
        dialog = self.make(qtbot)
        dialog.field("DIGITS").setText("")
        assert not dialog.is_valid()
        assert dialog.compiled_sql() == ""
        assert dialog.status.text().startswith("${DIGITS}:")
        dialog.field("DIGITS").setText("339")
        dialog.field("YEAR").setText("2026 OR 1=1")
        assert not dialog.is_valid()
        assert "${YEAR}" in dialog.status.text()
        dialog.field("YEAR").setText("2025")
        dialog.field("CODES").setPlainText("x, y\n")
        assert dialog.is_valid()
        # One value per line keeps the commas.
        dialog.field("CODES").setPlainText("a, b\nc")
        assert "IN ('a, b', 'c')" in dialog.compiled_sql()
        dialog.field("CODES").setPlainText("  \n ")
        assert not dialog.is_valid()

    def test_values_stay_inside_their_strings(self, qtbot):
        dialog = self.make(qtbot)
        dialog.field("DIGITS").setText("x' OR 'a'='a")
        assert dialog.is_valid()
        assert "cli = 'x'' OR ''a''=''a'" in dialog.compiled_sql()

    def test_last_values_are_yellow_until_changed(self, qtbot):
        dialog = self.make(
            qtbot, {"YEAR": "2024", "DAY": "2025-01-31", "OK": "false"}
        )
        dialog.show()
        assert dialog.legend.isVisible()
        assert dialog.value("YEAR") == "2024"
        assert dialog.field("DAY").date() == QDate(2025, 1, 31)
        assert dialog.value("OK") == "false"
        for name in ("YEAR", "DAY", "OK"):
            assert dialog.is_previous(name)
            field = dialog.field(name)
            assert FillMaskDialog.PREVIOUS_BACKGROUND in field.styleSheet()
            assert field.toolTip() == FillMaskDialog.PREVIOUS_TOOLTIP
        assert not dialog.is_previous("DIGITS")
        assert dialog.field("DIGITS").styleSheet() == ""
        dialog.field("YEAR").setText("2023")
        assert not dialog.is_previous("YEAR")
        assert dialog.field("YEAR").styleSheet() == ""
        dialog.field("YEAR").setText("2024")
        assert dialog.is_previous("YEAR")
        dialog.use_defaults()
        assert dialog.value("YEAR") == "2026"
        assert not dialog.is_previous("YEAR")

    def test_run_only_when_valid(self, qtbot):
        dialog = self.make(qtbot)
        dialog.field("YEAR").setText("nope")
        dialog.accept()
        assert dialog.result() != FillMaskDialog.DialogCode.Accepted
        dialog.field("YEAR").setText("1")
        dialog.run_button.click()
        assert dialog.result() == FillMaskDialog.DialogCode.Accepted

    def test_open_in_editor(self, qtbot):
        dialog = self.make(qtbot)
        dialog.edit_button.click()
        assert dialog.result() == FillMaskDialog.EDIT_RESULT

    def test_write_queries_cannot_be_run(self, qtbot):
        mask = QueryBookmark(
            "Bad",
            "SELECT ${Y} INTO OUTFILE '/tmp/x'",
            "t",
            (Placeholder("Y", PlaceholderType.INTEGER, default="1"),),
        )
        dialog = FillMaskDialog(mask)
        qtbot.addWidget(dialog)
        assert not dialog.is_valid()
        assert "Only read queries" in dialog.status.text()
