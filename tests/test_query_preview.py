"""Tests of the query preview of the dialogs."""

from PySide6.QtGui import QFontDatabase

from querylean.ui.dialogs.query_preview import QueryPreview


class TestQueryPreview:
    """Read only, monospaced, limited height."""

    def test_preview(self, qtbot):
        preview = QueryPreview(100)
        qtbot.addWidget(preview)
        assert preview.isReadOnly()
        fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        assert preview.font().family() == fixed.family()
        assert preview.maximumHeight() == 100
        assert QueryPreview().maximumHeight() == QueryPreview.DEFAULT_MAX_HEIGHT
