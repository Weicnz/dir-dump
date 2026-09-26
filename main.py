from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

import pythoncom
from PySide6.QtCore import QObject, QPoint, QThread, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from config.config_manager import ConfigManager
from strategies import get_registry
from ui.wheel_menu import WheelMenu
from ui.settings_dialog import SettingsDialog
from utils.explorer import get_active_explorer_path, is_explorer_foreground, open_in_explorer

WH_MOUSE_LL = 14
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MOUSEMOVE = 0x0200
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

LowLevelMouseProc = ctypes.WINFUNCTYPE(
    wintypes.LPARAM, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, LowLevelMouseProc, wintypes.HINSTANCE, wintypes.DWORD
]
user32.CallNextHookEx.restype = wintypes.LPARAM
user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetMessageW.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = wintypes.LPARAM
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class MouseHook(QThread):
    rightButtonDown = Signal(int, int)
    rightButtonUp = Signal(int, int)
    mouseMoved = Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self._hook: wintypes.HHOOK | None = None
        self._proc: LowLevelMouseProc | None = None
        self._suppress_right: bool = False
        self._reinjecting: bool = False
        self._running = False
        self._thread_id: int = 0

    def run(self) -> None:
        self._running = True
        self._thread_id = kernel32.GetCurrentThreadId()

        def _hook_proc(nCode: int, wParam: int, lParam: int) -> int:
            if nCode >= 0:
                if self._reinjecting and wParam in (WM_RBUTTONDOWN, WM_RBUTTONUP):
                    return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
                info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                x, y = info.pt.x, info.pt.y
                if wParam == WM_RBUTTONDOWN:
                    fg = is_explorer_foreground()
                    if fg:
                        self._suppress_right = True
                        self.rightButtonDown.emit(x, y)
                        return 1
                    else:
                        self._suppress_right = False
                elif wParam == WM_RBUTTONUP:
                    if self._suppress_right:
                        self._suppress_right = False
                        self.rightButtonUp.emit(x, y)
                        return 1
                elif wParam == WM_MOUSEMOVE:
                    self.mouseMoved.emit(x, y)
            return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

        self._proc = LowLevelMouseProc(_hook_proc)
        module = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, module, 0)
        if not self._hook:
            print("[hook] failed to install")
            return

        print("[hook] installed in thread")

        msg = wintypes.MSG()
        while self._running:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0:
                break
            if ret == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
        self._proc = None
        print("[hook] thread stopped")

    def reinject_right_click(self, x: int, y: int) -> None:
        self._reinjecting = True
        user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, x, y, 0, 0)
        user32.mouse_event(MOUSEEVENTF_RIGHTUP, x, y, 0, 0)
        QTimer.singleShot(150, self._clear_reinjecting)

    def _clear_reinjecting(self) -> None:
        self._reinjecting = False

    def stop(self) -> None:
        self._running = False
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        self.wait(2000)


class WheelController(QObject):
    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._registry = get_registry()
        self._wheel: WheelMenu | None = None
        self._active = False

    def show_wheel(self, x: int, y: int) -> None:
        print(f"[wheel] show_wheel called at ({x},{y})")
        if self._wheel is not None:
            self.hide_wheel()

        current_dir = get_active_explorer_path()
        items: list = []
        for strategy in self._registry.all():
            cfg = self._config.get_strategy(strategy.name)
            if not cfg.get("enabled", True):
                continue
            cfg_with_favs = dict(cfg)
            cfg_with_favs["favorites"] = self._config.get_favorites()
            cfg_with_favs["history"] = self._config.get_history()
            items.extend(strategy.get_recommendations(current_dir, cfg_with_favs))

        if not items:
            self._active = False
            return

        self._wheel = WheelMenu(
            items=items[:12],
            center_pos=QPoint(x, y),
            radius=self._config.wheel_radius,
            inner_radius=self._config.wheel_inner_radius,
        )
        self._wheel.show()
        self._active = True

    def update_highlight(self, x: int, y: int) -> None:
        if self._wheel is not None and self._active:
            self._wheel.highlight_at(QPoint(x, y))

    def commit_and_hide(self, x: int, y: int) -> bool:
        selected = False
        if self._wheel is not None and self._active:
            path = self._wheel.commit()
            if path:
                open_in_explorer(path)
                self._config.add_history(path)
                selected = True
        self.hide_wheel()
        return selected

    def hide_wheel(self) -> None:
        if self._wheel is not None:
            self._wheel.close()
            self._wheel = None
        self._active = False


class App(QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)
        pythoncom.CoInitialize()
        self._config = ConfigManager()
        self._controller = WheelController(self._config)
        self._hook = MouseHook()

        self._hook.rightButtonDown.connect(self._on_right_down)
        self._hook.rightButtonUp.connect(self._on_right_up)
        self._hook.mouseMoved.connect(self._on_mouse_move)

        self._tray = self._create_tray()
        self._hook.start()

    def _create_tray(self) -> QSystemTrayIcon:
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("目录跳转工具")

        menu = QMenu()
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

        reload_action = QAction("重新加载配置", self)
        reload_action.triggered.connect(self._config.load)
        menu.addAction(reload_action)

        menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)

        tray.setContextMenu(menu)
        tray.show()
        return tray

    def _on_right_down(self, x: int, y: int) -> None:
        QTimer.singleShot(0, lambda: self._show_wheel_safe(x, y))

    def _show_wheel_safe(self, x: int, y: int) -> None:
        try:
            self._controller.show_wheel(x, y)
        except Exception as e:
            print(f"[wheel] show error: {e}")

    def _on_right_up(self, x: int, y: int) -> None:
        def _do() -> None:
            selected = self._controller.commit_and_hide(x, y)
            if not selected:
                self._hook.reinject_right_click(x, y)
        QTimer.singleShot(0, _do)

    def _on_mouse_move(self, x: int, y: int) -> None:
        self._controller.update_highlight(x, y)

    def _open_settings(self) -> None:
        strategies = self._controller._registry.all()
        dialog = SettingsDialog(self._config, strategies)
        if dialog.exec():
            dialog.apply()

    def quit_app(self) -> None:
        self._hook.stop()
        self.quit()


def main() -> int:
    app = App(sys.argv)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
