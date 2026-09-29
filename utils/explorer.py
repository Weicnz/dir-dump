from __future__ import annotations

import os
import re
import subprocess
import urllib.parse
from typing import Optional

import win32com.client
import win32gui

EXPLORER_CLASS_NAMES = {"CabinetWClass", "ExploreWClass"}
DIALOG_CLASS_NAME = "#32770"
# 文件对话框里承载 Shell 文件视图的子窗口类；普通对话框不会有，据此区分
SHELL_VIEW_CLASS_NAMES = {"ShellTabWindowClass", "DUIViewWndClassName"}
# 形如 "C:\..." 或 "\\server\..." 的本地/网络路径
_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")
_ADDRESS_PREFIXES = ("Address:", "Address :", "地址:", "地址：")


def _descendants(hwnd: int) -> list[int]:
    """枚举窗口的全部后代窗口（EnumChildWindows 会递归）。"""
    result: list[int] = []

    def _collect(child: int, _param) -> bool:
        result.append(child)
        return True

    try:
        win32gui.EnumChildWindows(hwnd, _collect, None)
    except Exception:
        pass
    return result


def is_file_dialog(hwnd: int) -> bool:
    """判断窗口是否为（打开/另存为类）文件对话框：类名 #32770 且含 Shell 文件视图。"""
    try:
        if win32gui.GetClassName(hwnd) != DIALOG_CLASS_NAME:
            return False
    except Exception:
        return False
    for child in _descendants(hwnd):
        try:
            if win32gui.GetClassName(child) in SHELL_VIEW_CLASS_NAMES:
                return True
        except Exception:
            continue
    return False


def _extract_path(text: str) -> Optional[str]:
    """从窗口文本中解析出真实存在的目录路径，否则返回 None。"""
    if not text:
        return None
    text = text.strip()
    for prefix in _ADDRESS_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    if _PATH_RE.match(text) and os.path.isdir(text):
        return text
    return None


def get_file_dialog_path(hwnd: int) -> Optional[str]:
    """尽力读取文件对话框当前所在文件夹；读不到返回 None。"""
    for child in _descendants(hwnd):
        try:
            class_name = win32gui.GetClassName(child)
        except Exception:
            continue
        if class_name not in ("ToolbarWindow32", "Edit", "ComboBoxEx32"):
            continue
        try:
            text = win32gui.GetWindowText(child)
        except Exception:
            continue
        path = _extract_path(text)
        if path:
            print(f"[explorer] dialog path={path!r}")
            return path
    return None


def is_supported_foreground() -> bool:
    """前台是否为资源管理器窗口或文件对话框。"""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return False
    class_name = win32gui.GetClassName(hwnd)
    if class_name in EXPLORER_CLASS_NAMES:
        print(f"[explorer] foreground class={class_name!r} is_explorer=True")
        return True
    result = is_file_dialog(hwnd)
    print(f"[explorer] foreground class={class_name!r} is_file_dialog={result}")
    return result


def get_active_path() -> Optional[str]:
    """前台窗口对应的当前目录：资源管理器窗口用其打开目录，
    文件对话框用其当前所在文件夹（读不到则返回 None，仅按收藏推荐）。"""
    hwnd = win32gui.GetForegroundWindow()
    if hwnd:
        try:
            class_name = win32gui.GetClassName(hwnd)
        except Exception:
            class_name = ""
        if class_name == DIALOG_CLASS_NAME and is_file_dialog(hwnd):
            return get_file_dialog_path(hwnd)
    return get_active_explorer_path()


def _url_to_path(url: str) -> Optional[str]:
    if url.startswith("file:///"):
        path = urllib.parse.unquote(url[8:])
        path = path.replace("/", "\\")
        return path
    return None


def get_active_explorer_path() -> Optional[str]:
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        windows = shell.Windows()
    except Exception:
        return None

    foreground_hwnd = win32gui.GetForegroundWindow()
    candidates: list[str] = []

    for i in range(windows.Count):
        try:
            window = windows.Item(i)
        except Exception:
            continue
        if window is None:
            continue
        try:
            hwnd = window.HWND
        except Exception:
            continue
        if hwnd != foreground_hwnd:
            continue
        try:
            location_url = window.LocationURL
        except Exception:
            location_url = ""
        if location_url:
            path = _url_to_path(location_url)
            if path:
                candidates.append(path)

    if candidates:
        return candidates[0]

    for i in range(windows.Count):
        try:
            window = windows.Item(i)
        except Exception:
            continue
        if window is None:
            continue
        try:
            location_url = window.LocationURL
        except Exception:
            continue
        if location_url:
            path = _url_to_path(location_url)
            if path:
                candidates.append(path)
    return candidates[0] if candidates else None


def open_in_explorer(path: str) -> None:
    if not path:
        return
    normalized = os.path.normpath(path)
    try:
        os.startfile(normalized)
    except Exception:
        try:
            subprocess.Popen(["explorer", normalized])
        except Exception:
            pass
