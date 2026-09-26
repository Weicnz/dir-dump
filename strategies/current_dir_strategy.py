from __future__ import annotations

import os
import pathlib
import time
from typing import Any

from .base import DirectoryItem, DirectoryStrategy

COMMON_DIRS = [
    ("Desktop", pathlib.Path.home() / "Desktop"),
    ("Documents", pathlib.Path.home() / "Documents"),
    ("Downloads", pathlib.Path.home() / "Downloads"),
    ("Pictures", pathlib.Path.home() / "Pictures"),
    ("Music", pathlib.Path.home() / "Music"),
    ("Videos", pathlib.Path.home() / "Videos"),
]


class CurrentDirStrategy(DirectoryStrategy):
    @property
    def name(self) -> str:
        return "current_dir"

    @property
    def display_name(self) -> str:
        return "基于当前目录推荐"

    def get_recommendations(
        self, current_dir: str | None, config: dict[str, Any]
    ) -> list[DirectoryItem]:
        items: list[DirectoryItem] = []
        seen: set[str] = set()

        def add(item: DirectoryItem) -> None:
            norm = os.path.normcase(os.path.normpath(item.path))
            if norm in seen:
                return
            seen.add(norm)
            items.append(item)

        recent_days = max(1, int(config.get("recent_days", 5)))
        cutoff = time.time() - recent_days * 86400
        history = config.get("history", [])

        history_by_path: dict[str, float] = {}
        for entry in history:
            p = entry.get("path", "")
            t = float(entry.get("time", 0))
            if p:
                history_by_path[os.path.normcase(os.path.normpath(p))] = t

        if config.get("include_parent", True) and current_dir:
            parent = pathlib.Path(current_dir).parent
            if str(parent) != str(current_dir):
                add(DirectoryItem(name="..", path=str(parent), category="parent"))

        if config.get("include_recent_subdirs", True) and current_dir:
            max_recent = int(config.get("max_recent_subdirs", 8))
            scored: list[tuple[float, pathlib.Path]] = []
            try:
                for child in pathlib.Path(current_dir).iterdir():
                    if not child.is_dir():
                        continue
                    norm = os.path.normcase(os.path.normpath(str(child)))
                    last_used = history_by_path.get(norm, 0.0)
                    try:
                        mtime = child.stat().st_mtime
                    except OSError:
                        mtime = 0.0
                    score = max(last_used, mtime)
                    if score >= cutoff or last_used > 0:
                        scored.append((score, child))
            except OSError:
                scored = []
            scored.sort(key=lambda x: x[0], reverse=True)
            for _, sub in scored[:max_recent]:
                add(
                    DirectoryItem(
                        name=sub.name, path=str(sub), category="recent"
                    )
                )

        if config.get("include_siblings", True) and current_dir:
            max_siblings = int(config.get("max_siblings", 3))
            parent = pathlib.Path(current_dir).parent
            scored: list[tuple[float, pathlib.Path]] = []
            try:
                for child in parent.iterdir():
                    if not child.is_dir() or str(child) == str(current_dir):
                        continue
                    norm = os.path.normcase(os.path.normpath(str(child)))
                    last_used = history_by_path.get(norm, 0.0)
                    try:
                        mtime = child.stat().st_mtime
                    except OSError:
                        mtime = 0.0
                    score = max(last_used, mtime)
                    if score >= cutoff or last_used > 0:
                        scored.append((score, child))
            except OSError:
                scored = []
            scored.sort(key=lambda x: x[0], reverse=True)
            for _, sib in scored[:max_siblings]:
                add(DirectoryItem(name=sib.name, path=str(sib), category="sibling"))

        if config.get("include_common_dirs", True):
            for name, path in COMMON_DIRS:
                if path.exists():
                    add(DirectoryItem(name=name, path=str(path), category="common"))

        if config.get("include_favorites", True):
            for fav in config.get("favorites", []):
                name = fav.get("name", "")
                path = fav.get("path", "")
                if name and path:
                    add(DirectoryItem(name=name, path=path, category="favorite"))

        return items
