"""GUI tests of the about dialog."""

from querylean.app.app_info import AppInfo
from querylean.ui.dialogs.about_dialog import AboutDialog


class TestAboutDialog:
    """Product name, version, author, license and runtime versions."""

    def test_shows_product_information(self, qtbot):
        dialog = AboutDialog()
        qtbot.addWidget(dialog)
        text = dialog.text.text()
        for expected in (
            AppInfo.DISPLAY_NAME,
            AppInfo.version(),
            AppInfo.AUTHOR,
            AppInfo.LICENSE,
            "Python",
            "Qt",
        ):
            assert expected in text
        assert AppInfo.DISPLAY_NAME in dialog.windowTitle()

    def test_closes_with_ok(self, qtbot):
        dialog = AboutDialog()
        qtbot.addWidget(dialog)
        dialog.show()
        dialog.accept()
        assert dialog.result() == AboutDialog.DialogCode.Accepted
