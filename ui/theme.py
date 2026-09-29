"""应用主题色（单一来源）。

启动窗口 SplashWindow 与轮盘 WheelMenu 共用本模块，避免同一套视觉色在
不同窗口各自硬编码造成主题分叉。主题为青蓝色系：
  #0b4a7a 深青蓝（标题） / #2b6ca3 中青蓝（副标题） / #bfe0ff 淡蓝（柔光）
"""

from __future__ import annotations

from PySide6.QtGui import QColor

# ── 启动窗口主题色 ──────────────────────────────────────────────
SPLASH_TITLE_HEX = "#0b4a7a"
SPLASH_SUBTITLE_HEX = "#2b6ca3"

# 启动窗口柔光背景的径向渐变停靠点 (位置, 颜色)：淡蓝 -> 白、逐渐虚化
SPLASH_GLOW_STOPS: list[tuple[float, QColor]] = [
    (0.00, QColor(191, 224, 255, 255)),  # #bfe0ff
    (0.50, QColor(198, 226, 255, 252)),
    (0.68, QColor(214, 236, 255, 240)),
    (0.82, QColor(230, 242, 255, 215)),
    (0.91, QColor(245, 250, 255, 70)),
    (0.97, QColor(255, 255, 255, 20)),
    (1.00, QColor(255, 255, 255, 0)),
]

# ── 轮盘扇形配色 ──────────────────────────────────────────────────────
# 按优先级分档（item0 最高，在正上方、顺时针递减）：越靠前颜色越深越饱和、
# 填充越实（alpha 越高），靠后的扇形依次变淡，外沿保持同心圆整齐。
# 各档自带非悬浮态 alpha；悬浮时统一改用 WHEEL_HOVER_ALPHA。
WHEEL_RANK_LEVELS = 5
WHEEL_HOVER_ALPHA = 250
WHEEL_RANK_COLORS: list[QColor] = [
    QColor(11, 74, 122, 240),     # 0B4A7A 最深·最实（最高优先级）
    QColor(22, 94, 146, 220),     # 165E92
    QColor(43, 108, 163, 200),    # 2B6CA3 主题主色
    QColor(91, 149, 198, 180),    # 5B95C6
    QColor(156, 203, 230, 155),   # 9CCBE6 最淡（最低优先级）
]
