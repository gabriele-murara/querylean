# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec (onedir mode).
# Usage: pyinstaller --noconfirm packaging/querylean.spec
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
APP_NAME = "querylean"

hiddenimports = (
    # Authentication plugins are loaded at runtime.
    collect_submodules("mysql.connector.plugins")
    + collect_submodules("mysql.connector.locales")
    # SecretService (Linux), macOS Keychain.
    + collect_submodules("keyring.backends")
    + ["sqlglot.dialects.mysql"]
)
datas = collect_data_files("mysql.connector")

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter",
        "unittest",
        "pytest",
        "PySide6.QtNetwork",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtSql",
        "PySide6.QtTest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    strip=False,
    upx=False,
    # Architecture of the interpreter running the build.
    target_arch=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="QueryLean.app",
        icon=None,
        bundle_identifier="computer.murara.querylean",
        info_plist={
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
        },
    )
