from __future__ import annotations

import html
import math
import os
from pathlib import PureWindowsPath
from typing import Optional

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTextDocument,
)
from PySide6.QtWidgets import QWidget

from strategies.base import DirectoryItem
from ui.theme import (
    WHEEL_HOVER_ALPHA,
    WHEEL_RANK_COLORS,
    WHEEL_RANK_LEVELS,
)
from utils.patterns import pattern_path

GROW = 14          # 悬浮时扇形向外放大的像素
MARGIN = 16        # 轮盘外圈到窗口边缘的留白（需容纳放大）
HINT_MAX_W = 560   # 白条内容最大宽度（像素），超出则换行
HINT_VPAD = 5      # 白条上下留白
HINT_FONT_PT = 9   # 白条字号
HINT_PADDING = 12  # 白条内左右留白
HINT_SIBLINGS = 5  # 白条内同级目录展示条数（含目标本身）
HINT_TAIL_SEGS = 3  # 判定“尾部相同”时比较的末段数（含条目名 + 最近两级上级）


def _path_parts(path: str) -> tuple[str, ...]:
    """把路径拆成各层片段（含盘符/根），用于比较目录结构。"""
    return PureWindowsPath(os.path.normpath(path)).parts


def _first_diff_segment(
    group_parts: list[tuple[str, ...]], parts: tuple[str, ...]
) -> Optional[str]:
    """在“尾部相同”的一组路径中，取出该路径最靠前的差异段；
    整条路径都相同时返回 None。"""
    limit = min(len(p) for p in group_parts)
    i = 0
    while i < limit:
        base = os.path.normcase(group_parts[0][i])
        if all(os.path.normcase(p[i]) == base for p in group_parts):
            i += 1
            continue
        break
    if i >= len(parts):
        return None
    return parts[i].rstrip("\\/") or None


ICON_SIZE = 18  # 扇形内“图案”图标尺寸（像素）


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
        self._grow_paths: list[QPainterPath] = []
        # _seg_indices[k] = 第 k 个扇形对应的 _items 下标（按绘制顺序重排）
        self._seg_indices: list[int] = []
        self._seg_mids: list[float] = []  # 第 k 个扇形的中心角（屏幕角度，度）
        self._seg_widths: list[float] = []  # 第 k 个扇形的角度跨度（度）
        self._icon_cache: dict[str, Optional[QPixmap]] = {}
        self._sibling_cache: dict[str, list[str]] = {}

        half = radius + MARGIN
        self._half = half
        # 窗口宽高随最长白条文本自适应，保证白条能以正常字号完整显示
        hint_font = QFont()
        hint_font.setPointSize(HINT_FONT_PT)
        self._hint_font = hint_font
        prefixes = self._ambiguity_prefixes()
        self._hint_html = [
            self._hint_html_for(it, prefixes[i]) for i, it in enumerate(items)
        ]
        max_text_w = 0.0
        max_text_h = 0.0
        for markup in self._hint_html:
            doc = QTextDocument()
            doc.setDocumentMargin(0)
            doc.setDefaultFont(hint_font)
            doc.setHtml(markup)
            doc.setTextWidth(HINT_MAX_W)
            max_text_w = max(max_text_w, min(doc.idealWidth(), HINT_MAX_W))
            max_text_h = max(max_text_h, doc.size().height())
        width = int(max(half * 2, max_text_w + 2 * HINT_PADDING))
        height = int(half * 2 + max_text_h + 2 * HINT_VPAD)
        self.setFixedSize(width, height)
        self._center = QPoint(width // 2, half)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # 分层（半透明）窗口默认不提供光标，Windows 上指针会“透明/消失”，显式指定
        self.setCursor(Qt.ArrowCursor)

        self.move(center_pos.x() - self._center.x(), center_pos.y() - self._center.y())

    @property
    def item_count(self) -> int:
        return len(self._items)

    def _layout(self) -> list[tuple[int, float, float]]:
        """计算各扇形的角度范围（屏幕角度，度，0=右/90=下/180=左/270=上）。

        唯一顺序契约：条目索引即优先级，索引 0 的扇形中心固定在正上方
        （270°），随后按索引递增沿顺时针方向等宽铺满整圈。
        """
        n = self.item_count
        if n == 0:
            return []
        step = 360.0 / n
        first_start = 270.0 - step / 2
        return [
            (i, first_start + i * step, first_start + (i + 1) * step)
            for i in range(n)
        ]

    def _rank_for_index(self, item_idx: int) -> int:
        """条目索引 -> 优先级档（0 = 最高）；用于颜色深浅阶梯。"""
        n = len(self._items)
        if n <= 1:
            return 0
        return min(WHEEL_RANK_LEVELS - 1, item_idx * WHEEL_RANK_LEVELS // n)

    def _build_seg_paths(self) -> None:
        self._seg_paths.clear()
        self._grow_paths.clear()
        self._seg_indices.clear()
        self._seg_mids.clear()
        self._seg_widths.clear()

        r = float(self._radius)
        gr = r + GROW
        rect = QRectF(self._center.x() - r, self._center.y() - r, r * 2, r * 2)
        grect = QRectF(self._center.x() - gr, self._center.y() - gr, gr * 2, gr * 2)

        for idx, phi_start, phi_end in self._layout():
            sweep = max(phi_end - phi_start, 0.01)

            path = QPainterPath()
            path.moveTo(self._center)
            path.arcTo(rect, -phi_end, sweep)
            path.closeSubpath()
            self._seg_paths.append(path)

            grow = QPainterPath()
            grow.moveTo(self._center)
            grow.arcTo(grect, -phi_end, sweep)
            grow.closeSubpath()
            self._grow_paths.append(grow)

            self._seg_indices.append(idx)
            self._seg_mids.append((phi_start + phi_end) / 2)
            self._seg_widths.append(sweep)

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

        idx: Optional[int] = None
        if dist >= self._inner_radius:
            pointf = QPointF(local)
            # 若仍落在当前高亮扇形的放大区域内则保持，避免放大后闪烁
            if (
                self._highlighted is not None
                and self._highlighted < len(self._grow_paths)
                and self._grow_paths[self._highlighted].contains(pointf)
            ):
                idx = self._highlighted
            else:
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
        if (
            self._highlighted is not None
            and 0 <= self._highlighted < len(self._seg_indices)
        ):
            return self._items[self._seg_indices[self._highlighted]].path
        return None

    @staticmethod
    def _elide(name: str, avail: float, fm: QFontMetrics) -> str:
        if not name or fm.horizontalAdvance(name) <= avail:
            return name
        result = name
        while result and fm.horizontalAdvance(result + "…") > avail:
            result = result[:-1]
        return (result + "…") if result else "…"

    def _icon_pixmap(self, name: str) -> Optional[QPixmap]:
        """从本地图案库加载图标（带缓存）；无效返回 None。"""
        if name in self._icon_cache:
            return self._icon_cache[name]
        pixmap: Optional[QPixmap] = None
        path = pattern_path(name)
        if path:
            icon = QIcon(path)
            if not icon.isNull():
                pixmap = icon.pixmap(24, 24)
                if pixmap.isNull():
                    pixmap = None
        self._icon_cache[name] = pixmap
        return pixmap

    def _feather_brush(self, color: QColor, outer_r: float) -> QBrush:
        """外沿渐变虚化：以轮盘中心为圆心、扇形外沿为半径的径向渐变画刷。"""
        grad = QRadialGradient(QPointF(self._center), max(outer_r, 1.0))
        fade = QColor(color)
        fade.setAlpha(int(color.alpha() * 0.9))
        clear = QColor(color)
        clear.setAlpha(0)
        grad.setColorAt(0.00, color)
        grad.setColorAt(0.90, color)
        grad.setColorAt(0.92, fade)
        grad.setColorAt(1.00, clear)
        return QBrush(grad)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        n = self.item_count
        if n == 0:
            self._seg_paths.clear()
            self._grow_paths.clear()
            painter.setPen(QPen(QColor(170, 225, 255, 190), 2))
            painter.setBrush(QBrush(QColor(24, 40, 88, 200)))
            painter.drawEllipse(self._center, self._inner_radius, self._inner_radius)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                QRectF(0, 0, self.width(), self._half * 2),
                Qt.AlignCenter,
                "无可用目录",
            )
            return

        if not self._seg_paths:
            self._build_seg_paths()

        for k, item_idx in enumerate(self._seg_indices):
            base = QColor(WHEEL_RANK_COLORS[self._rank_for_index(item_idx)])
            is_h = k == self._highlighted
            path = self._grow_paths[k] if is_h else self._seg_paths[k]
            outer_r = self._radius + (GROW if is_h else 0)
            if is_h:
                # 悬浮：保持档位色相、提到全实，配合外扩与亮白描边凸显
                fill = QColor(base.red(), base.green(), base.blue(), WHEEL_HOVER_ALPHA)
                stroke = QColor(255, 255, 255, 245)
                width = 2
            else:
                # 非悬浮：直接用档位色（深浅/虚实已编码优先级）
                fill = QColor(base)
                stroke = QColor(255, 255, 255, 120)
                width = 1
            # 填充与描边都随半径向外渐变虚化，外沿不出现硬边
            painter.setBrush(self._feather_brush(fill, outer_r))
            painter.setPen(QPen(self._feather_brush(stroke, outer_r), width))
            painter.drawPath(path)

        # 中心“取消”圆（半透明深蓝，青蓝色描边）
        painter.setBrush(QBrush(QColor(24, 40, 88, 200)))
        painter.setPen(QPen(QColor(170, 225, 255, 190), 2))
        painter.drawEllipse(self._center, self._inner_radius, self._inner_radius)
        painter.setPen(QColor(200, 228, 255))
        cancel_font = QFont()
        cancel_font.setPointSize(12)
        painter.setFont(cancel_font)
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

        # 各扇形标签：放不下时省略；悬浮时用底部白条显示完整路径
        for k, item_idx in enumerate(self._seg_indices):
            item = self._items[item_idx]
            is_h = k == self._highlighted
            label_radius = (
                self._inner_radius + (self._radius + GROW if is_h else self._radius)
            ) / 2
            seg_mid = math.radians(self._seg_mids[k])
            lx = self._center.x() + label_radius * math.cos(seg_mid)
            ly = self._center.y() + label_radius * math.sin(seg_mid)

            font = QFont()
            font.setPointSize(10 if is_h else 9)
            font.setBold(True)
            painter.setFont(font)
            fm = QFontMetrics(font)

            avail = 2 * math.pi * label_radius * (self._seg_widths[k] / 360.0) - 10
            display = self._elide(item.name, avail, fm)

            painter.setPen(QColor(255, 255, 255))
            painter.drawText(QRectF(lx - 70, ly - 12, 140, 24), Qt.AlignCenter, display)

            # 自定义“图案”：在标签内侧画一个小图标
            if item.icon:
                pixmap = self._icon_pixmap(item.icon)
                if pixmap is not None:
                    iradius = label_radius - 26
                    ix = self._center.x() + iradius * math.cos(seg_mid)
                    iy = self._center.y() + iradius * math.sin(seg_mid)
                    painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(
                        QPointF(ix, iy), ICON_SIZE / 2 + 3, ICON_SIZE / 2 + 3
                    )
                    painter.drawPixmap(
                        QRectF(
                            ix - ICON_SIZE / 2,
                            iy - ICON_SIZE / 2,
                            ICON_SIZE,
                            ICON_SIZE,
                        ),
                        pixmap,
                        QRectF(pixmap.rect()),
                    )

        self._draw_hint(painter)

    def _sibling_window(self, parent: str, name: str) -> list[str]:
        """取同一父目录下的目录名（字母序），以目标为中心取一小段窗口。"""
        entries = self._sibling_cache.get(parent)
        if entries is None:
            try:
                entries = [
                    e
                    for e in os.listdir(parent)
                    if os.path.isdir(os.path.join(parent, e))
                ]
            except OSError:
                entries = []
            entries.sort(key=str.lower)
            self._sibling_cache[parent] = entries
        key = name.lower()
        index = next((i for i, e in enumerate(entries) if e.lower() == key), None)
        if index is None:
            return [name]
        count = min(HINT_SIBLINGS, len(entries))
        start = max(0, min(index - count // 2, len(entries) - count))
        return entries[start : start + count]

    def _ambiguity_prefixes(self) -> list[Optional[str]]:
        """对“尾部相同”（条目名 + 最近两级上级相同）的多个条目，给出各自
        用于区分的最靠前差异段（如 code / wp）；无需区分时为 None。"""
        if not self._items:
            return []
        parts_list = [_path_parts(it.path) for it in self._items]
        groups: dict[tuple[str, ...], list[int]] = {}
        for i, parts in enumerate(parts_list):
            tail = tuple(os.path.normcase(p) for p in parts[-HINT_TAIL_SEGS:])
            groups.setdefault(tail, []).append(i)

        prefixes: list[Optional[str]] = [None] * len(self._items)
        for idxs in groups.values():
            if len(idxs) < 2:
                continue
            group_parts = [parts_list[i] for i in idxs]
            for i in idxs:
                prefixes[i] = _first_diff_segment(group_parts, parts_list[i])
        return prefixes

    def _hint_html_for(self, item: DirectoryItem, prefix: Optional[str] = None) -> str:
        """白条内容（树状）：上级路径一行（淡化，不参与连接），同级目录用
        ├─/└─ 逐行连接并左对齐，目标一行不淡化且名称加粗。
        当存在“尾部相同”的其它条目时，prefix 为差异首段，加在上级路径最前面。"""
        norm = os.path.normpath(item.path)
        name = os.path.basename(norm) or norm
        parent = os.path.dirname(norm)

        ancestors: list[str] = []
        cur = parent
        while cur and len(ancestors) < 2:
            base = os.path.basename(cur)
            if not base:
                ancestors.append(cur)
                break
            ancestors.append(base)
            nxt = os.path.dirname(cur)
            if nxt == cur:
                break
            cur = nxt
        ancestors.reverse()

        key = name.lower()
        siblings = self._sibling_window(parent, name)
        lines = []
        # 上级路径单独一行（淡化），不参与树状连接；有歧义时最前面补差异首段
        if ancestors:
            head_parts = ([prefix, ".."] if prefix else []) + ancestors
            head = "&nbsp;&gt;&nbsp;".join(html.escape(a) for a in head_parts)
            lines.append(f'<span style="color:#8a8a8a">{head}</span>')
        # 同级目录：树状连接，一行一个，左对齐；目标不淡化且名称加粗
        for i, sname in enumerate(siblings):
            branch = "└─" if i == len(siblings) - 1 else "├─"
            branch_prefix = f'<span style="color:#a6a6a6">{branch}&nbsp;</span>'
            text = html.escape(sname)
            if sname.lower() == key:
                lines.append(f'{branch_prefix}<b style="color:#111111">{text}</b>')
            else:
                lines.append(f'{branch_prefix}<span style="color:#a6a6a6">{text}</span>')
        return "<br>".join(lines)

    def _draw_hint(self, painter: QPainter) -> None:
        idx = self._highlighted
        if idx is None or not (0 <= idx < len(self._seg_indices)):
            return
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setDefaultFont(self._hint_font)
        doc.setHtml(self._hint_html[self._seg_indices[idx]])
        doc.setTextWidth(HINT_MAX_W)

        bar_y = self._half * 2
        bar_h = self.height() - bar_y
        text_w = min(doc.idealWidth(), HINT_MAX_W)
        text_h = doc.size().height()
        bar_w = min(float(self.width()), text_w + 2 * HINT_PADDING)
        bar_x = (self.width() - bar_w) / 2

        painter.setBrush(QBrush(QColor(255, 255, 255, 245)))
        painter.setPen(QPen(QColor(60, 60, 60, 120), 1))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 6, 6)

        painter.save()
        painter.translate(bar_x + HINT_PADDING, bar_y + (bar_h - text_h) / 2)
        doc.drawContents(painter)
        painter.restore()