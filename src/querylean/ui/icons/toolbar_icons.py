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
    __EXPORT = "#00897b"
    __REFRESH = "#546e7a"
    __CONNECT = "#1565c0"
    __DISCONNECT = "#6d4c41"
    __SETTINGS = "#546e7a"
    __ABOUT = "#1565c0"
    __STAR = "#f9a825"
    __BOOKMARKS = "#6a1b9a"
    __WARNING = "#f57c00"

    @staticmethod
    def play() -> QIcon:
        """Green right-pointing triangle ("Run")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_play)

    @staticmethod
    def stop() -> QIcon:
        """Red rounded square ("Stop")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_stop)

    @staticmethod
    def export() -> QIcon:
        """Arrow leaving a tray ("Export")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_export)

    @staticmethod
    def refresh() -> QIcon:
        """Circular arrow ("Aggiorna")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_refresh)

    @staticmethod
    def connect() -> QIcon:
        """Plug and socket joined together ("Connect")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_connect)

    @staticmethod
    def disconnect() -> QIcon:
        """Plug pulled away from its socket ("Disconnect")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_disconnect)

    @staticmethod
    def settings() -> QIcon:
        """Gear ("Connections")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_settings)

    @staticmethod
    def star() -> QIcon:
        """Yellow five-pointed star ("Save query")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_star)

    @staticmethod
    def bookmarks() -> QIcon:
        """Bookmark ribbon ("Bookmarked queries")."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_bookmarks)

    @staticmethod
    def warning() -> QIcon:
        """Orange triangle with "!" (a database the account can change)."""
        return ToolbarIcons.__render(ToolbarIcons.__draw_warning)

    @staticmethod
    def about() -> QIcon:
        """Circle with an "i" ("About")."""
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
    def __draw_export(painter: QPainter) -> None:
        color = QColor(ToolbarIcons.__EXPORT)
        pen = QPen(color, 7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Tray.
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(10, 38),
                    QPointF(10, 54),
                    QPointF(54, 54),
                    QPointF(54, 38),
                ]
            )
        )
        # Arrow shaft and head.
        painter.drawLine(QPointF(32, 42), QPointF(32, 18))
        ToolbarIcons.__fill(painter, ToolbarIcons.__EXPORT)
        painter.drawPolygon(
            QPolygonF([QPointF(18, 22), QPointF(32, 4), QPointF(46, 22)])
        )

    @staticmethod
    def __draw_refresh(painter: QPainter) -> None:
        pen = QPen(QColor(ToolbarIcons.__REFRESH), 7)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Arc of 300 degrees (Qt angles are in 1/16 of a degree), open at
        # the top right where the arrow head sits.
        painter.drawArc(QRectF(12, 12, 40, 40), 60 * 16, 300 * 16)
        ToolbarIcons.__fill(painter, ToolbarIcons.__REFRESH)
        painter.drawPolygon(
            QPolygonF([QPointF(36, 4), QPointF(52, 16), QPointF(34, 24)])
        )

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
    def __draw_star(painter: QPainter) -> None:
        center = QPointF(32, 34)
        outer, inner = 29.0, 12.0
        points = []
        for step in range(10):
            # Start at the top point and go clockwise.
            angle = -math.pi / 2 + math.pi * step / 5
            radius = outer if step % 2 == 0 else inner
            points.append(
                QPointF(
                    center.x() + radius * math.cos(angle),
                    center.y() + radius * math.sin(angle),
                )
            )
        ToolbarIcons.__fill(painter, ToolbarIcons.__STAR)
        painter.drawPolygon(QPolygonF(points))

    @staticmethod
    def __draw_bookmarks(painter: QPainter) -> None:
        # Ribbon with a V notch at the bottom.
        ToolbarIcons.__fill(painter, ToolbarIcons.__BOOKMARKS)
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(14, 4),
                    QPointF(50, 4),
                    QPointF(50, 60),
                    QPointF(32, 44),
                    QPointF(14, 60),
                ]
            )
        )

    @staticmethod
    def __draw_warning(painter: QPainter) -> None:
        ToolbarIcons.__fill(painter, ToolbarIcons.__WARNING)
        painter.drawPolygon(
            QPolygonF([QPointF(32, 4), QPointF(62, 58), QPointF(2, 58)])
        )
        ToolbarIcons.__fill(painter, "white")
        painter.drawRoundedRect(QRectF(28, 20, 8, 22), 3, 3)
        painter.drawEllipse(QRectF(28, 46, 8, 8))

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
