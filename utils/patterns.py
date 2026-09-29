from __future__ import annotations

import pathlib
import shutil

from utils.paths import app_dir, resource_dir

# 本地图案库目录：可直接往里放 png/svg/jpg/ico 等图片文件
PATTERNS_DIR = app_dir() / "patterns"
# 打包时内置的示例图案（只读），首次运行会释放到 PATTERNS_DIR
BUNDLED_PATTERNS_DIR = resource_dir() / "patterns"
PATTERN_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".ico", ".svg", ".webp"}


def _copy_bundled() -> None:
    src = BUNDLED_PATTERNS_DIR
    if src == PATTERNS_DIR or not src.is_dir():
        return
    for item in src.iterdir():
        if item.is_file() and item.suffix.lower() in PATTERN_EXTS:
            try:
                shutil.copy2(item, PATTERNS_DIR / item.name)
            except OSError:
                pass


def patterns_dir() -> pathlib.Path:
    """返回图案库目录（不存在则创建，并释放内置示例图案）。"""
    if not PATTERNS_DIR.exists():
        PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
        _copy_bundled()
    return PATTERNS_DIR


def list_patterns() -> list[str]:
    """返回图案库中的图片文件名（按名称不区分大小写排序）。"""
    directory = patterns_dir()
    try:
        names = [
            p.name
            for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in PATTERN_EXTS
        ]
    except OSError:
        names = []
    return sorted(names, key=str.lower)


def pattern_path(name: str | None) -> str | None:
    """把图案文件名解析为绝对路径；不存在返回 None。"""
    if not name:
        return None
    candidate = patterns_dir() / name
    return str(candidate) if candidate.is_file() else None
