"""The "Informazioni su QueryLean" dialog."""

from __future__ import annotations

import html
import platform

import PySide6
from PySide6.QtCore import Qt, qVersion
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from querylean.app.app_info import AppInfo
from querylean.ui.icons.toolbar_icons import ToolbarIcons


class AboutDialog(QDialog):
    """Shows product name, version, description, author, license and the
    versions of the runtime components."""

    __ICON_SIZE = 64
    __MIN_HEIGHT = 400

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Informazioni su {AppInfo.DISPLAY_NAME}")
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
        )

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
        e = html.escape
        runtime = (
            f"Python {platform.python_version()} · Qt {qVersion()} · "
            f"PySide6 {PySide6.__version__}"
        )
        return (
            f"<h2>{e(AppInfo.DISPLAY_NAME)}</h2>"
            f"<p><b>Versione {e(AppInfo.version())}</b></p>"
            f"<p>{e(AppInfo.DESCRIPTION)}</p>"
            "<p>Esegue solo istruzioni di lettura (SELECT, SHOW, DESCRIBE, "
            "EXPLAIN). La password è conservata nel portachiavi di sistema.</p>"
            f"<p>Autore: {e(AppInfo.AUTHOR)}<br>"
            f"© {e(AppInfo.COPYRIGHT_YEAR)} {e(AppInfo.AUTHOR)} · "
            f"Licenza {e(AppInfo.LICENSE)}</p>"
            f"<p><small>{e(runtime)}</small></p>"
        )
