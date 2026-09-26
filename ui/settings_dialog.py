from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config.config_manager import ConfigManager
from strategies.base import DirectoryStrategy


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
            ("include_recent_subdirs", "包含最近子目录"),
            ("include_common_dirs", "包含常用目录"),
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
            ("max_recent_subdirs", "当前目录子目录最大数量"),
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
    def __init__(self, favorites: list[dict[str, str]]) -> None:
        super().__init__()
        self._favorites = list(favorites)
        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        form = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("名称")
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("路径")
        form.addWidget(self.name_edit)
        form.addWidget(self.path_edit)
        layout.addLayout(form)

        btns = QHBoxLayout()
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add_favorite)
        remove_btn = QPushButton("删除选中")
        remove_btn.clicked.connect(self._remove_selected)
        btns.addWidget(add_btn)
        btns.addWidget(remove_btn)
        btns.addStretch()
        layout.addLayout(btns)

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        for fav in self._favorites:
            item = QListWidgetItem(f"{fav.get('name', '')}  →  {fav.get('path', '')}")
            self.list_widget.addItem(item)

    def _add_favorite(self) -> None:
        name = self.name_edit.text().strip()
        path = self.path_edit.text().strip()
        if not name or not path:
            return
        self._favorites.append({"name": name, "path": path})
        self.name_edit.clear()
        self.path_edit.clear()
        self._refresh_list()

    def _remove_selected(self) -> None:
        row = self.list_widget.currentRow()
        if 0 <= row < len(self._favorites):
            self._favorites.pop(row)
            self._refresh_list()

    def get_favorites(self) -> list[dict[str, str]]:
        return self._favorites


class SettingsDialog(QDialog):
    def __init__(
        self,
        config: ConfigManager,
        strategies: list[DirectoryStrategy],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("目录跳转工具 - 设置")
        self.resize(520, 560)
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

        self._favorites_widget = FavoritesWidget(self._config.get_favorites())
        tabs.addTab(self._favorites_widget, "收藏夹")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply(self) -> None:
        for name, widget in self._strategy_widgets.items():
            self._config.set_strategy(name, widget.get_config())
        self._config.set_favorites(self._favorites_widget.get_favorites())
        self._config.save()
