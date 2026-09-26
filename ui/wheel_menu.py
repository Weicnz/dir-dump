from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QBrush
from PySide6.QtWidgets import QWidget

from strategies.base import DirectoryItem

CATEGORY_COLORS = {
    "parent": QColor(70, 130, 180, 220),
    "sibling": QColor(60, 179, 113, 220),
    "recent": QColor(255, 165, 0, 220),
    "common": QColor(147, 112, 219, 220),
    "favorite": QColor(220, 20, 60, 220),
    "other": QColor(100, 100, 100, 220),
}


class WheelMenu(QWidget):
    itemSelected = Signal(str)

    def __init__(
        self,
        items: list[DirectoryItem],
        center_pos: QPoint,
        radius: int = 150,
        inner_radius: int = 50,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._items = items
        self._radius = radius
        self._inner_radius = inner_radius
        self._highlighted: Optional[int] = None
        self._seg_paths: list[QPainterPath] = []

        size = (radius + 10) * 2
        self.setFixedSize(size, size)
        self._center = QPoint(size // 2, size // 2)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.move(center_pos.x() - size // 2, center_pos.y() - size // 2)

    @property
    def item_count(self) -> int:
        return len(self._items)

    def _build_seg_paths(self) -> None:
        self._seg_paths.clear()
        n = self.item_count
        if n == 0:
            return
        sweep = 360.0 / n
        rect = QRectF(
            self._center.x() - self._radius,
            self._center.y() - self._radius,
            self._radius * 2,
            self._radius * 2,
        )
        for i in range(n):
            seg_start = 90.0 - sweep / 2 - i * sweep
            path = QPainterPath()
            path.moveTo(self._center)
            path.arcTo(rect, seg_start, sweep)
            path.closeSubpath()
            self._seg_paths.append(path)

    def showEvent(self, event) -> None:
        self._build_seg_paths()
        super().showEvent(event)

    def highlight_at(self, global_pos: QPoint) -> None:
        if not self._seg_paths:
            self._build_seg_paths()
        local = self.mapFromGlobal(global_pos)
        dx = local.x() - self._center.x()
        dy = local.y() - self._center.y()
        dist = math.hypot(dx, dy)
        if dist < self._inner_radius:
            idx = None
        else:
            idx = None
            pointf = QPointF(local)
            for i, path in enumerate(self._seg_paths):
                if path.contains(pointf):
                    idx = i
                    break
        if idx != self._highlighted:
            self._highlighted = idx
            self.update()

    def clear_highlight(self) -> None:
        if self._highlighted is not None:
            self._highlighted = None
            self.update()

    def commit(self) -> Optional[str]:
        if self._highlighted is not None and 0 <= self._highlighted < self.item_count:
            return self._items[self._highlighted].path
        return None

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        n = self.item_count
        if n == 0:
            self._seg_paths.clear()
            painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
            painter.setBrush(QBrush(QColor(40, 40, 40, 200)))
            painter.drawEllipse(self._center, self._inner_radius, self._inner_radius)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                QRectF(0, 0, self.width(), self.height()),
                Qt.AlignCenter,
                "无可用目录",
            )
            return

        if not self._seg_paths:
            self._build_seg_paths()

        for i, path in enumerate(self._seg_paths):
            base_color = CATEGORY_COLORS.get(self._items[i].category, CATEGORY_COLORS["other"])
            if i == self._highlighted:
                color = base_color.lighter(140)
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(255, 255, 255, 230), 2))
            else:
                color = QColor(base_color.red(), base_color.green(), base_color.blue(), 180)
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
            painter.drawPath(path)

        painter.setBrush(QBrush(QColor(30, 30, 30, 230)))
        painter.setPen(QPen(QColor(255, 255, 255, 180), 2))
        painter.drawEllipse(self._center, self._inner_radius, self._inner_radius)

        painter.setPen(QColor(220, 220, 220))
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(
            QRectF(
                self._center.x() - self._inner_radius,
                self._center.y() - self._inner_radius,
                self._inner_radius * 2,
                self._inner_radius * 2,
            ),
            Qt.AlignCenter,
            "取消",
        )

        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))

        sweep = 360.0 / n
        start = -90.0 - sweep / 2
        label_radius = (self._inner_radius + self._radius) / 2
        for i, item in enumerate(self._items):
            seg_mid = math.radians(start + i * sweep + sweep / 2)
            lx = self._center.x() + label_radius * math.cos(seg_mid)
            ly = self._center.y() + label_radius * math.sin(seg_mid)

            name = item.name
            max_chars = 12
            if len(name) > max_chars:
                name = name[: max_chars - 1] + "…"

            text_rect = QRectF(lx - 60, ly - 12, 120, 24)
            painter.drawText(text_rect, Qt.AlignCenter, name)
