# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件 exe（便携，配置与图案库写在 exe 同目录）。

用法（在项目根目录执行）：
    python -m PyInstaller --noconfirm dir-dump.spec
产物：dist/dir-dump.exe
"""

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    # 内置示例图案，首次运行释放到 exe 同目录的 patterns/
    datas=[("patterns", "patterns")],
    # pywin32 / COM 相关是动态导入，需要显式声明
    hiddenimports=[
        "pythoncom",
        "pywintypes",
        "win32api",
        "win32com",
        "win32com.client",
        "win32com.client.dynamic",
        "win32com.shell",
        "win32gui",
        "win32timezone",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "pynput",
        "numpy",
        "PIL",
        "matplotlib",
        "pandas",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.Qt3DCore",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtDesigner",
        "PySide6.QtHelp",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtWebChannel",
        "PySide6.QtWebSockets",
        "PySide6.QtRemoteObjects",
        "PySide6.QtScxml",
        "PySide6.QtStateMachine",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="dir-dump",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
