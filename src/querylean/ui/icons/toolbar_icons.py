"""Toolbar icons drawn with QPainter."""

from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)


class ToolbarIcons:
    """Factory of the toolbar icons.

    Icons are vector drawings rendered on a transparent pixmap, so they need no
    theme or bundled asset. Qt derives the greyed-out variant used for disabled
    actions automatically.
    """

    SIZE = 64
    __PLAY = "#2e7d32"
    __STOP = "#c62828"
    __CONNECT = "#1565c0"
    __DISCONNECT = "#6d4c41"
    __SETTINGS = "#546e7a"
    __ABOUT = "#1565c0"

    @staticmethod
    def play() -> QIcon:
        """Green right-pointing triangle ("Esegui")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_play)

    @staticmethod
    def stop() -> QIcon:
        """Red rounded square ("Interrompi")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_stop)

    @staticmethod
    def connect() -> QIcon:
        """Plug and socket joined together ("Connetti")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_connect)

    @staticmethod
    def disconnect() -> QIcon:
        """Plug pulled away from its socket ("Disconnetti")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_disconnect)

    @staticmethod
    def settings() -> QIcon:
        """Gear ("Configurazione")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_settings)

    @staticmethod
    def about() -> QIcon:
        """Circle with an "i" ("Informazioni")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_about)

    # ---------------------------------------------------------------- internals
    @staticmethod
    def __render(draw: Callable[[QPainter], None]) -> QIcon:
        pixmap = QPixmap(ToolbarIcons.SIZE, ToolbarIcons.SIZE)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            draw(painter)
        finally:
            painter.end()
        return QIcon(pixmap)

    @staticmethod
    def __fill(painter: QPainter, color: str) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(color)))

    @staticmethod
    def __draw_play(painter: QPainter) -> None:
        ToolbarIcons.__fill(painter, ToolbarIcons.__PLAY)
        painter.drawPolygon(
            QPolygonF([QPointF(16, 8), QPointF(56, 32), QPointF(16, 56)])
        )

    @staticmethod
    def __draw_stop(painter: QPainter) -> None:
        ToolbarIcons.__fill(painter, ToolbarIcons.__STOP)
        painter.drawRoundedRect(QRectF(12, 12, 40, 40), 6, 6)

    @staticmethod
    def __draw_connect(painter: QPainter) -> None:
        ToolbarIcons.__draw_plug(painter, ToolbarIcons.__CONNECT, gap=0)

    @staticmethod
    def __draw_disconnect(painter: QPainter) -> None:
        ToolbarIcons.__draw_plug(painter, ToolbarIcons.__DISCONNECT, gap=12)

    @staticmethod
    def __draw_plug(painter: QPainter, color: str, *, gap: float) -> None:
        """Horizontal plug (left) and socket (right) separated by ``gap``."""
        shift = gap / 2
        cable = QPen(QColor(color), 9)
        cable.setCapStyle(Qt.PenCapStyle.RoundCap)
        # Cables.
        painter.setPen(cable)
        painter.drawLine(QPointF(5, 32), QPointF(14 - shift, 32))
        painter.drawLine(QPointF(50 + shift, 32), QPointF(59, 32))
        ToolbarIcons.__fill(painter, color)
        # Plug body with its two prongs.
        painter.drawRoundedRect(QRectF(10 - shift, 14, 16, 36), 5, 5)
        painter.drawRect(QRectF(26 - shift, 20, 8, 7))
        painter.drawRect(QRectF(26 - shift, 37, 8, 7))
        # Socket body.
        painter.drawRoundedRect(QRectF(34 + shift, 12, 20, 40), 5, 5)

    @staticmethod
    def __draw_settings(painter: QPainter) -> None:
        center = QPointF(32, 32)
        teeth = 8
        outer, inner, hole = 28.0, 20.0, 8.0
        path = QPainterPath()
        steps = teeth * 4
        for step in range(steps + 1):
            angle = 2 * math.pi * step / steps
            radius = outer if step % 4 in (1, 2) else inner
            point = QPointF(
                center.x() + radius * math.cos(angle),
                center.y() + radius * math.sin(angle),
            )
            if step == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        path.closeSubpath()
        path.addEllipse(center, hole, hole)
        path.setFillRule(Qt.FillRule.OddEvenFill)
        ToolbarIcons.__fill(painter, ToolbarIcons.__SETTINGS)
        painter.drawPath(path)

    @staticmethod
    def __draw_about(painter: QPainter) -> None:
        ToolbarIcons.__fill(painter, ToolbarIcons.__ABOUT)
        painter.drawEllipse(QRectF(4, 4, 56, 56))
        painter.setPen(QColor("white"))
        font = QFont()
        font.setBold(True)
        font.setPixelSize(40)
        painter.setFont(font)
        painter.drawText(
            QRectF(4, 4, 56, 56), int(Qt.AlignmentFlag.AlignCenter), "i"
        )
