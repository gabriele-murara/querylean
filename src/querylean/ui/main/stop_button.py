"""Blinking "Stop" button shown only while a query runs for a while."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QGraphicsOpacityEffect, QToolButton, QWidget


class StopButton(QToolButton):
    """Tool button bound to the "Stop" action.

    ``start`` shows it after ``appear_delay_ms`` (quick queries end before
    it appears), then it blinks until ``finish`` hides it. Blinking only
    fades it, so it stays readable and clickable.
    """

    APPEAR_DELAY_MS = 1000
    BLINK_MS = 500
    DIM_OPACITY = 0.35
    STYLE = "QToolButton { color: #c62828; font-weight: bold; }"
    __ICON_SIZE = 18

    def __init__(self, action: QAction, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stop-button")
        self.setDefaultAction(action)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        size = StopButton.__ICON_SIZE
        self.setIconSize(QSize(size, size))
        self.setAutoRaise(True)
        self.setStyleSheet(StopButton.STYLE)
        self.__opacity = QGraphicsOpacityEffect(self)
        self.__opacity.setOpacity(1.0)
        self.setGraphicsEffect(self.__opacity)
        self.__appear_delay_ms = StopButton.APPEAR_DELAY_MS
        self.__appear_timer = QTimer(self)
        self.__appear_timer.setSingleShot(True)
        self.__appear_timer.timeout.connect(self.__appear)
        self.__blink_timer = QTimer(self)
        self.__blink_timer.setInterval(StopButton.BLINK_MS)
        self.__blink_timer.timeout.connect(self.__blink)
        self.hide()

    @property
    def appear_delay_ms(self) -> int:
        """Running time after which the button appears."""
        return self.__appear_delay_ms

    @appear_delay_ms.setter
    def appear_delay_ms(self, value: int) -> None:
        self.__appear_delay_ms = max(int(value), 0)

    @property
    def pending(self) -> bool:
        """True while waiting to appear."""
        return self.__appear_timer.isActive()

    @property
    def blinking(self) -> bool:
        """True while shown and blinking."""
        return self.__blink_timer.isActive()

    @property
    def opacity(self) -> float:
        """Current opacity (1 bright, ``DIM_OPACITY`` faded)."""
        return self.__opacity.opacity()

    def start(self) -> None:
        """A query started: appear after the delay."""
        self.finish()
        self.__appear_timer.start(self.__appear_delay_ms)

    def finish(self) -> None:
        """The query ended: hide at once."""
        self.__appear_timer.stop()
        self.__blink_timer.stop()
        self.__opacity.setOpacity(1.0)
        self.hide()

    def __appear(self) -> None:
        self.__opacity.setOpacity(1.0)
        self.show()
        self.__blink_timer.start()

    def __blink(self) -> None:
        bright = self.__opacity.opacity() < 1.0
        self.__opacity.setOpacity(1.0 if bright else StopButton.DIM_OPACITY)
