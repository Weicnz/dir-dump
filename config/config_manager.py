import json
import os
import pathlib
import time
from typing import Any

CONFIG_FILE = pathlib.Path(__file__).resolve().parent.parent / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "strategies": {
        "current_dir": {
            "enabled": True,
            "include_parent": True,
            "include_siblings": True,
            "include_recent_subdirs": True,
            "include_common_dirs": True,
            "include_favorites": True,
            "recent_days": 5,
            "max_siblings": 3,
            "max_recent_subdirs": 8,
        }
    },
    "favorites": [
        {"name": "Desktop", "path": str(pathlib.Path.home() / "Desktop")},
        {"name": "Documents", "path": str(pathlib.Path.home() / "Documents")},
        {"name": "Downloads", "path": str(pathlib.Path.home() / "Downloads")},
        {"name": "Pictures", "path": str(pathlib.Path.home() / "Pictures")},
    ],
    "history": [],
    "wheel": {
        "radius": 150,
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
        return self._data.get("favorites", [])

    def set_favorites(self, favorites: list[dict[str, str]]) -> None:
        self._data["favorites"] = favorites

    def get_history(self) -> list[dict[str, Any]]:
        return self._data.get("history", [])

    def add_history(self, path: str) -> None:
        history = self._data.setdefault("history", [])
        now = time.time()
        norm = os.path.normcase(os.path.normpath(path))
        history = [h for h in history if os.path.normcase(os.path.normpath(h.get("path", ""))) != norm]
        history.insert(0, {"path": path, "time": now})
        if len(history) > HISTORY_MAX_ENTRIES:
            history = history[:HISTORY_MAX_ENTRIES]
        self._data["history"] = history
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
