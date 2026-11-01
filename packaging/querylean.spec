# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec (onedir mode).
# Usage: pyinstaller --noconfirm packaging/querylean.spec
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

sys.path.insert(0, SPECPATH)
from bundle_slimmer import BundleSlimmer  # noqa: E402
from third_party_licenses import ThirdPartyLicenses  # noqa: E402

ROOT = Path(SPECPATH).parent
APP_NAME = "querylean"
# The version is read only from .version, which is also bundled so that the
# application can read it at runtime (VersionFile).
VERSION_FILE = ROOT / ".version"
VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()


hiddenimports = (
    # Authentication plugins are loaded at runtime.
    collect_submodules("mysql.connector.plugins")
    + collect_submodules("mysql.connector.locales")
    # SecretService (Linux), macOS Keychain.
    + collect_submodules("keyring.backends")
    + ["sqlglot.dialects.mysql"]
)
datas = collect_data_files("mysql.connector") + [(str(VERSION_FILE), ".")]

excludes = [
    "tkinter",
    "unittest",
    "pytest",
    # Build tooling, never imported at runtime.
    "setuptools",
    "pkg_resources",
    "distutils",
    # C extension of mysql-connector: QueryLean always uses use_pure=True.
    "_mysql_connector",
    "mysql.connector.connection_cext",
    "mysql.connector.cursor_cext",
    "PySide6.QtDBus",
    "PySide6.QtNetwork",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtSql",
    "PySide6.QtTest",
    # Optional openpyxl accelerators and extras: the xlsx export needs none
    # of them.
    "numpy",
    "pandas",
    "PIL",
    "lxml",
]
if sys.platform == "darwin":
    # SecretService (and its cryptography dependency) is Linux only.
    excludes += ["secretstorage", "jeepney", "cryptography"]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
# Remove what QueryLean never loads (see packaging/bundle_slimmer.py).
collected = {e[0] for e in a.binaries + a.datas}
a.binaries = BundleSlimmer.prune_orphan_libraries(
    BundleSlimmer.drop_unused(a.binaries)
)
a.datas = BundleSlimmer.drop_unused(a.datas)
# PyInstaller lists the symlinks to libraries among the datas.
removed = collected - {e[0] for e in a.binaries + a.datas}
a.binaries = BundleSlimmer.drop_links_to_removed(a.binaries, removed)
a.datas = BundleSlimmer.drop_links_to_removed(a.datas, removed)
BundleSlimmer.check_required_libraries(a.binaries)

# License notices of every bundled third-party component (fails the build
# when a file has no known license).
notices = ThirdPartyLicenses(
    ROOT, ROOT / "packaging" / "licenses", Path(workpath) / "licenses"
)
notices.collect(a.binaries + a.datas + a.pure + a.scripts)
a.datas += notices.write()
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
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
        },
    )
