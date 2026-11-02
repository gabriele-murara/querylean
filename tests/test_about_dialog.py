"""GUI tests of the about dialog."""

import sys

from querylean.app.app_info import AppInfo
from querylean.app.bundle_resources import BundleResources
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

    def test_mentions_third_party_licenses_without_bundle(self):
        assert not BundleResources.third_party_licenses().is_file()
        html_text = AboutDialog.third_party_html()
        assert "third-party" in html_text
        assert BundleResources.THIRD_PARTY_LICENSES in html_text
        assert "<a " not in html_text

    def test_links_third_party_licenses_in_bundle(self, monkeypatch, tmp_path):
        notices = tmp_path / BundleResources.LICENSES_DIR
        notices.mkdir()
        (notices / BundleResources.THIRD_PARTY_LICENSES).write_text("x")
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        html_text = AboutDialog.third_party_html()
        assert '<a href="file://' in html_text
        assert BundleResources.THIRD_PARTY_LICENSES in html_text
