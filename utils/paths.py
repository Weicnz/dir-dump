from __future__ import annotations

import pathlib
import sys


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> pathlib.Path:
    """可写数据目录：打包后为 exe 所在目录，开发时为项目根目录。"""
    if _is_frozen():
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parent.parent


def resource_dir() -> pathlib.Path:
    """只读资源目录：打包后为解压出的临时目录，开发时为项目根目录。"""
    if _is_frozen():
        base = getattr(sys, "_MEIPASS", None)
        return pathlib.Path(base) if base else pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parent.parent
