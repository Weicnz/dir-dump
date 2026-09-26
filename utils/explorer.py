from __future__ import annotations

import os
import subprocess
import urllib.parse
from typing import Optional

import win32com.client
import win32gui

EXPLORER_CLASS_NAMES = {"CabinetWClass", "ExploreWClass"}


def is_explorer_foreground() -> bool:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return False
    class_name = win32gui.GetClassName(hwnd)
    result = class_name in EXPLORER_CLASS_NAMES
    print(f"[explorer] foreground class={class_name!r} is_explorer={result}")
    return result


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
