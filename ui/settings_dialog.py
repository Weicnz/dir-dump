from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.config_manager import ConfigManager
from strategies.base import DirectoryStrategy
from utils.patterns import list_patterns, pattern_path, patterns_dir


class StrategyOptionsWidget(QWidget):
    def __init__(self, strategy: DirectoryStrategy, config: dict[str, Any]) -> None:
        super().__init__()
        self._strategy = strategy
        self._config = dict(config)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel(f"<b>{self._strategy.display_name}</b>")
        layout.addWidget(title)

        self.enabled_cb = QCheckBox("启用此策略")
        self.enabled_cb.setChecked(self._config.get("enabled", True))
        layout.addWidget(self.enabled_cb)

        bool_options = [
            ("include_parent", "包含上级目录 (..)"),
            ("include_siblings", "包含同级目录"),
            ("include_frequent_dirs", "推荐常访问的深层子目录（层级≥2，按频次排序）"),
            ("include_global_dirs", "补充推荐全局高频目录"),
            ("include_favorites", "包含收藏夹"),
        ]
        self._bool_checkboxes: dict[str, QCheckBox] = {}
        for key, label in bool_options:
            cb = QCheckBox(label)
            cb.setChecked(self._config.get(key, True))
            self._bool_checkboxes[key] = cb
            layout.addWidget(cb)

        int_options = [
            ("recent_days", "最近使用天数 (3-7)"),
            ("max_frequent_dirs", "深层子目录最大数量"),
            ("max_global_dirs", "全局高频目录最大数量 (0=不推荐)"),
            ("max_siblings", "同级目录最大数量"),
        ]
        self._int_spins: dict[str, QSpinBox] = {}
        int_group = QGroupBox("数量限制")
        int_layout = QVBoxLayout(int_group)
        for key, label in int_options:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            spin = QSpinBox()
            if key == "recent_days":
                spin.setRange(1, 30)
                spin.setValue(int(self._config.get(key, 5)))
            elif key == "max_global_dirs":
                spin.setRange(0, 50)
                spin.setValue(int(self._config.get(key, 4)))
            else:
                spin.setRange(1, 50)
                spin.setValue(int(self._config.get(key, 8)))
            self._int_spins[key] = spin
            row.addWidget(spin)
            int_layout.addLayout(row)
        layout.addWidget(int_group)

        layout.addStretch()

    def get_config(self) -> dict[str, Any]:
        result = dict(self._config)
        result["enabled"] = self.enabled_cb.isChecked()
        for key, cb in self._bool_checkboxes.items():
            result[key] = cb.isChecked()
        for key, spin in self._int_spins.items():
            result[key] = spin.value()
        return result


class FavoritesWidget(QWidget):
    """常用路径管理：手动收藏 + 自动识别路径，按路径字母排序，支持颜色与图案。"""

    def __init__(
        self,
        favorites: list[dict[str, Any]],
        auto_paths: list[str] | None = None,
        auto_styles: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        super().__init__()
        self._favorites: list[dict[str, Any]] = [
            {
                "name": str(f.get("name", "") or ""),
                "path": str(f.get("path", "") or ""),
                "color": f.get("color") or None,
                "icon": f.get("icon") or None,
            }
            for f in favorites
            if isinstance(f, dict)
        ]
        self._auto_styles: dict[str, dict[str, Any]] = {}
        for key, val in (auto_styles or {}).items():
            if isinstance(val, dict):
                self._auto_styles[self._norm(str(key))] = {
                    "color": val.get("color") or None,
                    "icon": val.get("icon") or None,
                }

        manual_norms = {self._norm(f["path"]) for f in self._favorites}
        autos = [
            p for p in (auto_paths or []) if p and self._norm(p) not in manual_norms
        ]
        # 每行：(来源, 数据)；manual 时为收藏 dict，auto 时为路径字符串
        self._entries: list[tuple[str, Any]] = [("manual", f) for f in self._favorites]
        self._entries += [("auto", p) for p in autos]
        self._sort_entries()

        self._build_ui()
        self._refresh_table()

    @staticmethod
    def _norm(path: str) -> str:
        return os.path.normcase(os.path.normpath(path))

    def _path_of(self, entry: tuple[str, Any]) -> str:
        kind, value = entry
        return value["path"] if kind == "manual" else value

    def _sort_entries(self) -> None:
        self._entries.sort(key=lambda e: self._path_of(e).lower())

    def _auto_style(self, path: str) -> dict[str, Any]:
        return self._auto_styles.setdefault(
            self._norm(path), {"color": None, "icon": None}
        )

    def _color_of(self, entry: tuple[str, Any]) -> str | None:
        kind, value = entry
        if kind == "manual":
            return value.get("color")
        return self._auto_styles.get(self._norm(value), {}).get("color")

    def _icon_of(self, entry: tuple[str, Any]) -> str | None:
        kind, value = entry
        if kind == "manual":
            return value.get("icon")
        return self._auto_styles.get(self._norm(value), {}).get("icon")

    def _set_color(self, entry: tuple[str, Any], color: str | None) -> None:
        kind, value = entry
        if kind == "manual":
            value["color"] = color
        else:
            self._auto_style(value)["color"] = color

    def _set_icon(self, entry: tuple[str, Any], icon: str | None) -> None:
        kind, value = entry
        if kind == "manual":
            value["icon"] = icon
        else:
            self._auto_style(value)["icon"] = icon

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        hint = QLabel(f"图案库目录：{patterns_dir()}（可自行放入 png/svg 图片）")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["路径", "来源", "颜色", "图案"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        # 隐藏了竖直表头后原生左边框可能不绘制，改用显式边框保证四边完整
        self.table.setFrameShape(QFrame.NoFrame)
        self.table.setStyleSheet(
            "QTableWidget { border: 1px solid #8f8f8f; }"
        )
        self.table.setMinimumHeight(240)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._sync_controls)
        layout.addWidget(self.table, 1)

        btns = QHBoxLayout()
        add_btn = QPushButton("添加路径…")
        add_btn.clicked.connect(self._add_path)
        self.remove_btn = QPushButton("删除选中")
        self.remove_btn.clicked.connect(self._remove_selected)
        btns.addWidget(add_btn)
        btns.addWidget(self.remove_btn)
        btns.addStretch()
        layout.addLayout(btns)

        edit_group = QGroupBox("选中项设置")
        edit_layout = QHBoxLayout(edit_group)

        edit_layout.addWidget(QLabel("颜色"))
        self.color_btn = QPushButton("设置颜色…")
        self.color_btn.clicked.connect(self._pick_color)
        self.auto_color_btn = QPushButton("自动")
        self.auto_color_btn.clicked.connect(self._clear_color)
        edit_layout.addWidget(self.color_btn)
        edit_layout.addWidget(self.auto_color_btn)

        edit_layout.addSpacing(12)
        edit_layout.addWidget(QLabel("图案"))
        self.icon_combo = QComboBox()
        self.icon_combo.setIconSize(QSize(22, 22))
        self.icon_combo.addItem(QIcon(), "无", None)
        for name in list_patterns():
            self.icon_combo.addItem(QIcon(pattern_path(name) or ""), name, name)
        self.icon_combo.currentIndexChanged.connect(self._on_icon_changed)
        edit_layout.addWidget(self.icon_combo)

        self.icon_preview = QLabel("无")
        self.icon_preview.setFixedSize(30, 30)
        self.icon_preview.setFrameShape(QFrame.StyledPanel)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        edit_layout.addWidget(self.icon_preview)
        edit_layout.addStretch()

        layout.addWidget(edit_group)

    def _current_row(self) -> int:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _select_row(self, row: int) -> None:
        if 0 <= row < self.table.rowCount():
            self.table.selectRow(row)

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            kind, _ = entry
            path = self._path_of(entry)
            path_item = QTableWidgetItem(path)
            path_item.setToolTip(path)
            self.table.setItem(row, 0, path_item)

            source = QTableWidgetItem("手动" if kind == "manual" else "自动")
            source.setToolTip(
                "手动添加的常用路径"
                if kind == "manual"
                else "根据访问频次自动识别的路径"
            )
            self.table.setItem(row, 1, source)

            color = self._color_of(entry)
            color_item = QTableWidgetItem(color or "自动")
            if color:
                qcolor = QColor(color)
                if qcolor.isValid():
                    color_item.setBackground(QBrush(qcolor))
                    color_item.setForeground(
                        QBrush(
                            QColor(255, 255, 255)
                            if qcolor.lightness() < 128
                            else QColor(0, 0, 0)
                        )
                    )
            self.table.setItem(row, 2, color_item)
            self.table.setItem(row, 3, QTableWidgetItem(self._icon_of(entry) or "无"))
        self._sync_controls()

    def _sync_controls(self) -> None:
        row = self._current_row()
        enabled = 0 <= row < len(self._entries)
        self.color_btn.setEnabled(enabled)
        self.auto_color_btn.setEnabled(enabled)
        self.icon_combo.setEnabled(enabled)
        # 自动识别的路径不能在此删除
        self.remove_btn.setEnabled(enabled and self._entries[row][0] == "manual")
        if not enabled:
            self._update_preview(None)
            return
        entry = self._entries[row]
        self.color_btn.setText(self._color_of(entry) or "设置颜色…")
        icon = self._icon_of(entry)
        index = self.icon_combo.findData(icon) if icon else 0
        self.icon_combo.blockSignals(True)
        self.icon_combo.setCurrentIndex(index if index >= 0 else 0)
        self.icon_combo.blockSignals(False)
        self._update_preview(icon)

    def _update_preview(self, icon: str | None) -> None:
        if not icon:
            self.icon_preview.clear()
            self.icon_preview.setText("无")
            return
        path = pattern_path(icon)
        if path:
            pixmap = QIcon(path).pixmap(24, 24)
            if not pixmap.isNull():
                self.icon_preview.setPixmap(pixmap)
                return
        self.icon_preview.clear()
        self.icon_preview.setText("?")

    def _add_path(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择常用路径")
        if not directory:
            return
        path = os.path.normpath(directory)
        norm = self._norm(path)
        if any(self._norm(self._path_of(e)) == norm for e in self._entries):
            return
        fav = {
            "name": os.path.basename(path),
            "path": path,
            "color": None,
            "icon": None,
        }
        self._favorites.append(fav)
        self._entries.append(("manual", fav))
        self._sort_entries()
        self._refresh_table()

    def _remove_selected(self) -> None:
        row = self._current_row()
        if not (0 <= row < len(self._entries)):
            return
        kind, value = self._entries[row]
        if kind != "manual":
            return
        self._favorites.remove(value)
        self._entries.pop(row)
        self._refresh_table()

    def _pick_color(self) -> None:
        row = self._current_row()
        if not (0 <= row < len(self._entries)):
            return
        entry = self._entries[row]
        initial = QColor(52, 101, 164)
        current = self._color_of(entry)
        if current:
            parsed = QColor(current)
            if parsed.isValid():
                initial = parsed
        color = QColorDialog.getColor(initial, self, "选择颜色")
        if color.isValid():
            self._set_color(entry, color.name())
            self._refresh_table()
            self._select_row(row)

    def _clear_color(self) -> None:
        row = self._current_row()
        if 0 <= row < len(self._entries):
            self._set_color(self._entries[row], None)
            self._refresh_table()
            self._select_row(row)

    def _on_icon_changed(self) -> None:
        row = self._current_row()
        if not (0 <= row < len(self._entries)):
            return
        self._set_icon(self._entries[row], self.icon_combo.currentData())
        self._refresh_table()
        self._select_row(row)

    def get_favorites(self) -> list[dict[str, Any]]:
        self._favorites.sort(key=lambda f: f["path"].lower())
        return self._favorites

    def get_path_styles(self) -> dict[str, dict[str, Any]]:
        return {
            norm: {"color": style.get("color"), "icon": style.get("icon")}
            for norm, style in self._auto_styles.items()
            if style.get("color") or style.get("icon")
        }


class SettingsDialog(QDialog):
    def __init__(
        self,
        config: ConfigManager,
        strategies: list[DirectoryStrategy],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("目录跳转工具 - 设置")
        self.resize(680, 640)
        self._config = config
        self._strategies = strategies
        self._strategy_widgets: dict[str, StrategyOptionsWidget] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        strategy_tab = QWidget()
        strategy_layout = QVBoxLayout(strategy_tab)
        for strategy in self._strategies:
            cfg = self._config.get_strategy(strategy.name)
            widget = StrategyOptionsWidget(strategy, cfg)
            self._strategy_widgets[strategy.name] = widget
            strategy_layout.addWidget(widget)
        strategy_layout.addStretch()
        tabs.addTab(strategy_tab, "推荐策略")

        history_paths = [
            str(entry.get("path", ""))
            for entry in self._config.get_history()
            if entry.get("path")
        ]
        self._favorites_widget = FavoritesWidget(
            self._config.get_favorites(),
            history_paths,
            self._config.get_path_styles(),
        )
        tabs.addTab(self._favorites_widget, "常用路径")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply(self) -> None:
        for name, widget in self._strategy_widgets.items():
            self._config.set_strategy(name, widget.get_config())
        self._config.set_favorites(self._favorites_widget.get_favorites())
        self._config.set_path_styles(self._favorites_widget.get_path_styles())
        self._config.save()
