from __future__ import annotations

import os
import pathlib
import time
from typing import Any

from .base import DirectoryItem, DirectoryStrategy

# 最近该时长内使用过的目录，按权重加分（不做绝对优先，避免压过高频目录）
RECENT_BOOST_SEC = 600   # 10 分钟
RECENT_BOOST_WEIGHT = 3  # 相当于额外 N 次触发


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

        # 统计每个目录的历史打开频次（同路径取最大次数，路径保留原始写法）
        history = config.get("history", [])
        freq: dict[str, tuple[int, float, str]] = {}
        for entry in history:
            p = entry.get("path", "")
            if not p:
                continue
            norm = os.path.normcase(os.path.normpath(p))
            count = int(entry.get("count", 1) or 1)
            t = float(entry.get("time", 0) or 0)
            prev = freq.get(norm)
            if prev is None or count > prev[0] or (count == prev[0] and t > prev[1]):
                freq[norm] = (count, t, p)

        if config.get("include_parent", True) and current_dir:
            parent = pathlib.Path(current_dir).parent
            if str(parent) != str(current_dir):
                add(DirectoryItem(name="..", path=str(parent), category="parent"))

        cur_norm = ""
        prefix = ""
        if current_dir:
            cur_norm = os.path.normcase(os.path.normpath(current_dir))
            prefix = cur_norm if cur_norm.endswith(os.sep) else cur_norm + os.sep

        now = time.time()

        def rank_key(entry: tuple[int, float, str]) -> tuple[int, float]:
            """排序主键：加权得分 = 频次 + 近期权重；同分再比最近时间。
            10 分钟内用过加 RECENT_BOOST_WEIGHT 分，但不绝对压过更高频的目录。"""
            count, t, _orig = entry
            recent = RECENT_BOOST_WEIGHT if (now - t) <= RECENT_BOOST_SEC else 0
            return (count + recent, t)

        # 推荐当前目录下的“深层子目录”（层级 >= 2）：直接子目录在当前目录中已可见，故排除
        if config.get("include_frequent_dirs", True) and current_dir:
            max_dirs = int(config.get("max_frequent_dirs", 8))
            candidates: list[tuple[int, float, str]] = []
            for norm, (count, t, orig) in freq.items():
                if norm == cur_norm or not norm.startswith(prefix):
                    continue
                if os.sep not in norm[len(prefix):]:
                    continue  # 直接子目录，不再推荐
                if not os.path.isdir(orig):
                    continue
                candidates.append((count, t, orig))
            candidates.sort(key=rank_key, reverse=True)
            for _count, _t, orig in candidates[:max_dirs]:
                add(
                    DirectoryItem(
                        name=os.path.basename(os.path.normpath(orig)),
                        path=orig,
                        category="frequent",
                    )
                )

        # 补充推荐：不在当前目录下的历史高频目录，按访问频次排序
        if config.get("include_global_dirs", True) and current_dir:
            max_global = int(config.get("max_global_dirs", 4))
            if max_global > 0:
                global_candidates: list[tuple[int, float, str]] = []
                for norm, (count, t, orig) in freq.items():
                    if norm == cur_norm or norm.startswith(prefix):
                        continue
                    if not os.path.isdir(orig):
                        continue
                    global_candidates.append((count, t, orig))
                global_candidates.sort(key=rank_key, reverse=True)
                for _count, _t, orig in global_candidates[:max_global]:
                    add(
                        DirectoryItem(
                            name=os.path.basename(os.path.normpath(orig)),
                            path=orig,
                            category="global",
                        )
                    )

        if config.get("include_siblings", False) and current_dir:
            max_siblings = int(config.get("max_siblings", 3))
            recent_days = max(1, int(config.get("recent_days", 5)))
            cutoff = time.time() - recent_days * 86400
            parent = pathlib.Path(current_dir).parent
            scored: list[tuple[float, pathlib.Path]] = []
            try:
                for child in parent.iterdir():
                    if not child.is_dir() or str(child) == str(current_dir):
                        continue
                    norm = os.path.normcase(os.path.normpath(str(child)))
                    last_used = freq.get(norm, (0, 0.0, ""))[1]
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

        if config.get("include_favorites", True):
            for fav in config.get("favorites", []):
                name = fav.get("name", "")
                path = fav.get("path", "")
                if name and path:
                    add(
                        DirectoryItem(
                            name=name,
                            path=path,
                            category="favorite",
                            icon=fav.get("icon"),
                            color=fav.get("color"),
                        )
                    )

        # 应用“自动识别路径”的自定义样式（颜色/图案），不覆盖已有的手动设置
        styles = config.get("path_styles") or {}
        if styles:
            for item in items:
                style = styles.get(os.path.normcase(os.path.normpath(item.path)))
                if not style:
                    continue
                if not item.color:
                    item.color = style.get("color")
                if not item.icon:
                    item.icon = style.get("icon")

        return items
