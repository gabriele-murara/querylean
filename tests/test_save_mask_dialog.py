"""GUI tests of the "Save mask" dialog."""

from querylean.bookmarks.placeholder import Placeholder
from querylean.bookmarks.placeholder_type import PlaceholderType
from querylean.ui.dialogs.save_mask_dialog import SaveMaskDialog


class TestSaveMaskDialog:
    """Rows per placeholder, defaults from the editor, preview check."""

    SQL = "SELECT * FROM calls WHERE cli = '${DIGITS}' AND y = ${YEAR} "
    SQL += "AND c IN (${CODES})"

    def make(self, qtbot, known=None, name="") -> SaveMaskDialog:
        dialog = SaveMaskDialog(self.SQL, known, name=name)
        qtbot.addWidget(dialog)
        return dialog

    def test_rows_start_from_the_known_placeholders(self, qtbot):
        dialog = self.make(
            qtbot,
            {
                "YEAR": Placeholder(
                    "YEAR", PlaceholderType.INTEGER, default="2026"
                )
            },
        )
        assert dialog.table.rowCount() == 3
        assert dialog.table.item(1, 0).text() == "${YEAR}"
        assert dialog.type_box("YEAR").currentData() is PlaceholderType.INTEGER
        assert dialog.default_edit("YEAR").text() == "2026"
        assert dialog.type_box("DIGITS").currentData() is PlaceholderType.TEXT

    def test_save_needs_name_and_valid_defaults(self, qtbot):
        dialog = self.make(qtbot)
        assert not dialog.is_valid()  # no defaults yet
        dialog.default_edit("DIGITS").setText("339")
        dialog.default_edit("YEAR").setText("2026")
        dialog.type_box("YEAR").setCurrentIndex(
            list(PlaceholderType).index(PlaceholderType.INTEGER)
        )
        dialog.list_box("CODES").setChecked(True)
        dialog.default_edit("CODES").setText("a, b")
        assert not dialog.is_valid()
        assert "name" in dialog.status.text()
        dialog.name_edit.setText("  Calls  by number ")
        assert dialog.is_valid()
        assert dialog.mask_name() == "Calls by number"
        preview = dialog.preview.toPlainText()
        assert "cli = '339'" in preview and "IN ('a', 'b')" in preview
        dialog.default_edit("YEAR").setText("2026 OR 1=1")
        assert not dialog.is_valid()
        assert "${YEAR}" in dialog.status.text()

    def test_placeholders_result(self, qtbot):
        dialog = self.make(qtbot, name="M")
        dialog.default_edit("DIGITS").setText("1")
        dialog.description_edit("DIGITS").setText(" Caller ")
        placeholders = dialog.placeholders()
        assert [p.name for p in placeholders] == ["DIGITS", "YEAR", "CODES"]
        assert placeholders[0].description == "Caller"
        assert placeholders[0].default == "1"
