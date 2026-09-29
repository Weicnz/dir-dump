import json
import os
import pathlib
import time
from typing import Any

from utils.paths import app_dir

# 打包成 exe 后写到 exe 同目录（便携），开发时写到项目根目录
CONFIG_FILE = app_dir() / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "strategies": {
        "current_dir": {
            "enabled": True,
            "include_parent": True,
            "include_siblings": False,
            "include_frequent_dirs": True,
            "include_global_dirs": True,
            "include_favorites": True,
            "recent_days": 5,
            "max_siblings": 3,
            "max_frequent_dirs": 8,
            "max_global_dirs": 4,
        }
    },
    "favorites": [],
    "path_styles": {},
    "history": [],
    "wheel": {
        "radius": 200,
        "inner_radius": 50,
    },
}

HISTORY_MAX_ENTRIES = 100


class ConfigManager:
    def __init__(self, config_path: str | os.PathLike[str] | None = None) -> None:
        self._path = pathlib.Path(config_path) if config_path else CONFIG_FILE
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        exists = self._path.exists()
        if exists:
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        else:
            self._data = {}
        self._merge_defaults()
        if not exists:
            self.save()

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def _merge_defaults(self) -> None:
        for key, value in DEFAULT_CONFIG.items():
            if key not in self._data:
                self._data[key] = value
            elif isinstance(value, dict):
                self._data[key] = self._deep_merge(value, self._data.get(key, {}))

    @staticmethod
    def _deep_merge(default: dict, override: dict) -> dict:
        result = dict(default)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = ConfigManager._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get_strategy(self, name: str) -> dict[str, Any]:
        strategies = self._data.get("strategies", {})
        return strategies.get(name, {})

    def set_strategy(self, name: str, config: dict[str, Any]) -> None:
        if "strategies" not in self._data:
            self._data["strategies"] = {}
        self._data["strategies"][name] = config

    def get_favorites(self) -> list[dict[str, str]]:
        raw = self._data.get("favorites", [])
        if not isinstance(raw, list):
            return []
        result = [self._normalize_favorite(f) for f in raw if isinstance(f, dict)]
        result = [f for f in result if f["name"] and f["path"]]
        result.sort(key=lambda f: f["path"].lower())
        return result

    def set_favorites(self, favorites: list[dict[str, str]]) -> None:
        if not isinstance(favorites, list):
            favorites = []
        cleaned = [
            self._normalize_favorite(f) for f in favorites if isinstance(f, dict)
        ]
        cleaned = [f for f in cleaned if f["name"] and f["path"]]
        # 按路径字母排序后保存
        cleaned.sort(key=lambda f: f["path"].lower())
        self._data["favorites"] = cleaned

    @staticmethod
    def _normalize_favorite(fav: dict[str, Any]) -> dict[str, str | None]:
        return {
            "name": str(fav.get("name", "") or ""),
            "path": str(fav.get("path", "") or ""),
            "color": fav.get("color") or None,
            "icon": fav.get("icon") or None,
        }

    def get_path_styles(self) -> dict[str, dict[str, Any]]:
        """自动识别路径的自定义样式覆盖：{规范化路径: {color, icon}}。"""
        raw = self._data.get("path_styles", {})
        if not isinstance(raw, dict):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for key, val in raw.items():
            if not isinstance(val, dict):
                continue
            norm = os.path.normcase(os.path.normpath(str(key)))
            color = val.get("color") or None
            icon = val.get("icon") or None
            if color or icon:
                result[norm] = {"color": color, "icon": icon}
        return result

    def set_path_styles(self, styles: dict[str, Any]) -> None:
        cleaned: dict[str, dict[str, Any]] = {}
        if isinstance(styles, dict):
            for key, val in styles.items():
                if not isinstance(val, dict):
                    continue
                norm = os.path.normcase(os.path.normpath(str(key)))
                color = val.get("color") or None
                icon = val.get("icon") or None
                if color or icon:
                    cleaned[norm] = {"color": color, "icon": icon}
        self._data["path_styles"] = cleaned

    def get_history(self) -> list[dict[str, Any]]:
        return self._data.get("history", [])

    def add_history(self, path: str) -> None:
        history = self._data.setdefault("history", [])
        now = time.time()
        norm = os.path.normcase(os.path.normpath(path))
        count = 0
        rest: list[dict[str, Any]] = []
        for h in history:
            if os.path.normcase(os.path.normpath(h.get("path", ""))) == norm:
                count = max(count, int(h.get("count", 1) or 1))
            else:
                rest.append(h)
        rest.insert(0, {"path": path, "time": now, "count": count + 1})
        if len(rest) > HISTORY_MAX_ENTRIES:
            rest = rest[:HISTORY_MAX_ENTRIES]
        self._data["history"] = rest
        try:
            self.save()
        except OSError:
            pass

    @property
    def wheel_radius(self) -> int:
        return self._data.get("wheel", {}).get("radius", 150)

    @property
    def wheel_inner_radius(self) -> int:
        return self._data.get("wheel", {}).get("inner_radius", 50)

    @property
    def raw(self) -> dict[str, Any]:
        return self._data
