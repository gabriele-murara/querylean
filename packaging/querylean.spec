# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec (onedir mode).
# Usage: pyinstaller --noconfirm packaging/querylean.spec
import os
import re
import subprocess
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

sys.path.insert(0, SPECPATH)
from third_party_licenses import ThirdPartyLicenses  # noqa: E402

ROOT = Path(SPECPATH).parent
APP_NAME = "querylean"
# The version is read only from .version, which is also bundled so that the
# application can read it at runtime (VersionFile).
VERSION_FILE = ROOT / ".version"
VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()


class BundleSlimmer:
    """Removes from the bundle what QueryLean never loads.

    - Qt translations: the application does not install a QTranslator.
    - Qt plugins for embedded/remote targets (EGLFS, linuxfb, VNC, Vulkan
      display, evdev input, TUIO), image formats other than SVG and the GTK3
      platform theme (it alone pulls in GTK, cairo, pango and ATK).
    - The Qt libraries used only by those plugins.
    - On Linux, the system libraries no remaining binary depends on.

    Kept on purpose: xcb and Wayland (desktop sessions), offscreen and
    minimal (smoke test, CI), the XDG portal theme, SVG support.
    """

    __PLATFORMS = r"PySide6/Qt/plugins/platforms/libq(eglfs|linuxfb"
    __PLATFORMS += r"|minimalegl|vnc|vkkhrdisplay)\.so$"
    __QT_LIBS = r"PySide6/Qt/lib/libQt6(EglFSDeviceIntegration"
    __QT_LIBS += r"|EglFsKmsSupport|Network)\.so"
    DROP_PATTERNS = [
        r"PySide6/Qt/translations/",
        __PLATFORMS,
        r"PySide6/Qt/plugins/(egldeviceintegrations|generic)/",
        r"PySide6/Qt/plugins/imageformats/(?!libqsvg\.(so|dylib)$)",
        r"PySide6/Qt/plugins/platformthemes/libqgtk3\.so$",
        __QT_LIBS,
        # macOS equivalent of libQt6Network.
        r"PySide6/Qt/lib/QtNetwork\.framework/",
    ]
    __NEEDED = re.compile(r"\(NEEDED\).*\[(.+)\]")

    @staticmethod
    def drop_unused(toc):
        """Entries of ``toc`` that do not match any drop pattern."""
        patterns = [re.compile(p) for p in BundleSlimmer.DROP_PATTERNS]
        kept = []
        for entry in toc:
            dest = entry[0].replace(os.sep, "/")
            if not any(p.search(dest) for p in patterns):
                kept.append(entry)
        return kept

    @staticmethod
    def drop_dangling_symlinks(toc, bundled):
        """Drop the SYMLINK entries of ``toc`` whose target is not among the
        ``bundled`` destinations (e.g. the top-level links PyInstaller adds
        to dropped Qt libraries)."""
        return [
            entry
            for entry in toc
            if entry[2] != "SYMLINK"
            or os.path.normpath(
                os.path.join(os.path.dirname(entry[0]), entry[1])
            )
            in bundled
        ]

    @staticmethod
    def prune_orphan_libraries(binaries):
        """Linux only: drop top-level shared libraries (collected from the
        system) that no other kept binary needs any more. Python extension
        modules and every library in a subdirectory are kept as roots."""
        if not sys.platform.startswith("linux"):
            return binaries
        needed_by = {}
        for dest, src, _kind in binaries:
            needed_by[dest] = BundleSlimmer.__needed(src)
        top_level = {
            Path(dest).name: dest
            for dest, _src, kind in binaries
            if kind == "BINARY"
            and "/" not in dest.replace(os.sep, "/")
            and not dest.startswith("libpython")
        }
        reachable = set()
        queue = [d for d in needed_by if d not in top_level.values()]
        queue += [d for d in top_level.values() if d.startswith("libpython")]
        seen = set(queue)
        while queue:
            for name in needed_by.get(queue.pop(), ()):
                dest = top_level.get(name)
                if dest and dest not in seen:
                    seen.add(dest)
                    reachable.add(dest)
                    queue.append(dest)
        return [
            entry
            for entry in binaries
            if entry[0] not in top_level.values() or entry[0] in reachable
        ]

    @staticmethod
    def __needed(path):
        result = subprocess.run(
            ["readelf", "-d", str(path)],
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
            check=False,
        )
        return BundleSlimmer.__NEEDED.findall(result.stdout)


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
a.binaries = BundleSlimmer.prune_orphan_libraries(
    BundleSlimmer.drop_unused(a.binaries)
)
a.datas = BundleSlimmer.drop_unused(a.datas)
# PyInstaller lists the symlinks to libraries among the datas.
bundled = {e[0] for e in a.binaries + a.datas if e[2] != "SYMLINK"}
a.binaries = BundleSlimmer.drop_dangling_symlinks(a.binaries, bundled)
a.datas = BundleSlimmer.drop_dangling_symlinks(a.datas, bundled)

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
