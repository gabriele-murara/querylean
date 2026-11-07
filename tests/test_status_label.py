"""Tests of the outcome line of the dialogs."""

from PySide6.QtCore import Qt

from querylean.ui.dialogs.status_label import StatusLabel


class TestStatusLabel:
    """Plain text, colours."""

    def test_plain_text_and_colours(self, qtbot):
        label = StatusLabel()
        qtbot.addWidget(label)
        assert label.textFormat() == Qt.TextFormat.PlainText
        assert label.wordWrap()
        label.show_status(True, "<b>ok</b>")
        assert label.text() == "<b>ok</b>"
        assert StatusLabel.OK_COLOR in label.styleSheet()
        label.show_status(False, "no")
        assert StatusLabel.ERROR_COLOR in label.styleSheet()
        label.show_neutral("wait")
        assert label.styleSheet() == ""
        assert label.text() == "wait"
