"""GUI tests of the "Make placeholders" dialog."""

from querylean.bookmarks.mask_template import MaskTemplate
from querylean.ui.dialogs.make_placeholders_dialog import (
    MakePlaceholdersDialog,
)


class TestMakePlaceholdersDialog:
    """Rows per value, preview, name checks."""

    SQL = "SELECT * FROM t WHERE year = 2026 AND cli = '339' LIMIT 5"

    def make(self, qtbot) -> MakePlaceholdersDialog:
        dialog = MakePlaceholdersDialog(
            self.SQL, MaskTemplate.candidates(self.SQL)
        )
        qtbot.addWidget(dialog)
        return dialog

    def test_rows_and_preview(self, qtbot):
        dialog = self.make(qtbot)
        assert dialog.table.rowCount() == 3
        assert dialog.table.item(0, 1).text() == "2026"
        assert dialog.table.item(0, 3).text() == "Integer"
        assert dialog.table.item(1, 1).text() == "'339'"
        assert dialog.table.item(2, 4).text() == "1"
        assert dialog.name_edit(1).text() == "CLI"
        assert dialog.is_valid()
        expected = "SELECT * FROM t WHERE year = ${YEAR} AND cli = ${CLI} "
        expected += "LIMIT 5"
        assert dialog.preview.toPlainText() == expected
        assert dialog.result_sql() == expected
        assert [p.name for p in dialog.result_placeholders()] == [
            "YEAR",
            "CLI",
        ]
        dialog.use_box(2).setChecked(True)
        dialog.name_edit(2).setText("ROWS")
        assert dialog.result_sql().endswith("LIMIT ${ROWS}")

    def test_invalid_choices_disable_the_button(self, qtbot):
        dialog = self.make(qtbot)
        dialog.name_edit(0).setText("1YEAR")
        assert not dialog.is_valid()
        assert "1YEAR" in dialog.status.text()
        assert dialog.preview.toPlainText() == self.SQL
        dialog.name_edit(0).setText("X")
        dialog.name_edit(1).setText("X")
        assert not dialog.is_valid()
        assert "different types" in dialog.status.text()
        dialog.use_box(0).setChecked(False)
        assert dialog.is_valid()
        dialog.use_box(1).setChecked(False)
        assert not dialog.is_valid()
        assert dialog.status.text() == "Choose at least one value."
        dialog.accept()
        assert dialog.result() != MakePlaceholdersDialog.DialogCode.Accepted
        assert not dialog.ok_button.isEnabled()
        dialog.use_box(0).setChecked(True)
        dialog.ok_button.click()
        assert dialog.result() == MakePlaceholdersDialog.DialogCode.Accepted

    def test_same_name_and_type_make_one_placeholder(self, qtbot):
        sql = "SELECT 1 FROM t WHERE a = 1 OR b = 2"
        dialog = MakePlaceholdersDialog(sql, MaskTemplate.candidates(sql))
        qtbot.addWidget(dialog)
        dialog.use_box(0).setChecked(False)  # the 1 after SELECT
        dialog.name_edit(1).setText("N")
        dialog.name_edit(2).setText("N")
        assert dialog.is_valid()
        assert dialog.result_sql().endswith("a = ${N} OR b = ${N}")
        assert len(dialog.result_placeholders()) == 1
