"""The "Informazioni su QueryLean" dialog."""

from __future__ import annotations

import html
import platform

import PySide6
from PySide6.QtCore import Qt, QUrl, qVersion
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from querylean.app.app_info import AppInfo
from querylean.app.bundle_resources import BundleResources
from querylean.ui.icons.toolbar_icons import ToolbarIcons


class AboutDialog(QDialog):
    """Shows product name, version, description, author, license and the
    versions of the runtime components."""

    __ICON_SIZE = 64
    __MIN_HEIGHT = 400

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Informazioni su {}".format(AppInfo.DISPLAY_NAME))
        self.setMinimumHeight(AboutDialog.__MIN_HEIGHT)

        icon = QLabel()
        icon.setPixmap(
            ToolbarIcons.about().pixmap(
                AboutDialog.__ICON_SIZE, AboutDialog.__ICON_SIZE
            )
        )
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.__text = QLabel(AboutDialog.html_text())
        self.__text.setTextFormat(Qt.TextFormat.RichText)
        self.__text.setWordWrap(True)
        self.__text.setMinimumWidth(360)
        self.__text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.__text.setOpenExternalLinks(True)

        body = QHBoxLayout()
        body.addWidget(icon)
        body.addSpacing(12)
        body.addWidget(self.__text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addLayout(body)
        layout.addWidget(buttons)

    @property
    def text(self) -> QLabel:
        """Label holding the product information."""
        return self.__text

    @staticmethod
    def html_text() -> str:
        """Rich text with the product information (all values escaped)."""
        runtime = "Python {} · Qt {} · PySide6 {}"
        runtime = runtime.format(
            platform.python_version(), qVersion(), PySide6.__version__
        )
        text = "<h2>{name}</h2>"
        text += "<p><b>Versione {version}</b></p>"
        text += "<p>{description}</p>"
        text += "<p>Esegue solo istruzioni di lettura (SELECT, SHOW, "
        text += "DESCRIBE, EXPLAIN). La password è conservata nel portachiavi "
        text += "di sistema.</p>"
        text += "<p>Autore: {author}<br>"
        text += "© {year} {author} · Licenza {license}</p>"
        text += "<p>{third_party}</p>"
        text += "<p><small>{runtime}</small></p>"
        e = html.escape
        return text.format(
            name=e(AppInfo.DISPLAY_NAME),
            version=e(AppInfo.version()),
            description=e(AppInfo.DESCRIPTION),
            author=e(AppInfo.AUTHOR),
            year=e(AppInfo.COPYRIGHT_YEAR),
            license=e(AppInfo.LICENSE),
            third_party=AboutDialog.third_party_html(),
            runtime=e(runtime),
        )

    @staticmethod
    def third_party_html() -> str:
        """Note on the bundled third-party components, with a link to their
        licenses when the file is available (packaged builds)."""
        text = "Include componenti di terze parti (Qt, PySide6, "
        text += "mysql-connector-python e altri), ciascuno distribuito con "
        text += "la propria licenza: {}."
        notices = BundleResources.third_party_licenses()
        if not notices.is_file():
            name = html.escape(BundleResources.THIRD_PARTY_LICENSES)
            return text.format("vedi {} nei pacchetti".format(name))
        url = html.escape(QUrl.fromLocalFile(str(notices)).toString())
        link = '<a href="{}">licenze di terze parti</a>'.format(url)
        return text.format(link)
