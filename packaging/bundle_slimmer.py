"""Removal of what QueryLean never loads from the PyInstaller bundle."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


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

    TOC entries are ``(dest, source, kind)`` tuples; for ``SYMLINK`` entries
    ``source`` is the link target, relative to the directory of ``dest``.
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
    # System libraries the Qt xcb platform plugin needs (Linux). They are
    # bundled only when installed on the build machine: without them the
    # application does not start on systems that lack them.
    REQUIRED_LINUX_LIBRARIES = (
        "libxcb-cursor.so.0",
        "libxcb-icccm.so.4",
        "libxcb-image.so.0",
        "libxcb-keysyms.so.1",
        "libxcb-render-util.so.0",
        "libxcb-shape.so.0",
        "libxcb-util.so.1",
        "libxcb-xkb.so.1",
        "libxkbcommon-x11.so.0",
    )
    __NEEDED = re.compile(r"\(NEEDED\).*\[(.+)\]")

    @staticmethod
    def drop_unused(toc: list[tuple]) -> list[tuple]:
        """Entries of ``toc`` that do not match any drop pattern."""
        patterns = [re.compile(p) for p in BundleSlimmer.DROP_PATTERNS]
        kept = []
        for entry in toc:
            dest = entry[0].replace(os.sep, "/")
            if not any(p.search(dest) for p in patterns):
                kept.append(entry)
        return kept

    @staticmethod
    def drop_links_to_removed(
        toc: list[tuple], removed: set[str]
    ) -> list[tuple]:
        """Drop the SYMLINK entries of ``toc`` that point to a ``removed``
        destination (e.g. the top-level links PyInstaller adds to dropped Qt
        libraries). Links pointing to other links, as inside macOS
        frameworks (``Versions/Current``), are kept."""
        removed = {BundleSlimmer.__normalize(path) for path in removed}
        kept = []
        for entry in toc:
            if entry[2] == "SYMLINK":
                base = os.path.dirname(entry[0])
                target = os.path.join(base, entry[1])
                if BundleSlimmer.__normalize(target) in removed:
                    continue
            kept.append(entry)
        return kept

    @staticmethod
    def prune_orphan_libraries(binaries: list[tuple]) -> list[tuple]:
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
    def check_required_libraries(binaries: list[tuple]) -> None:
        """Linux only: raise ``RuntimeError`` when a library listed in
        ``REQUIRED_LINUX_LIBRARIES`` is not in the bundle."""
        if not sys.platform.startswith("linux"):
            return
        names = {Path(entry[0]).name for entry in binaries}
        missing = [
            name
            for name in BundleSlimmer.REQUIRED_LINUX_LIBRARIES
            if name not in names
        ]
        if missing:
            msg = "Libraries needed by the Qt xcb plugin are not installed "
            msg += "on the build machine (see packaging/build_linux_*.sh): {}"
            raise RuntimeError(msg.format(", ".join(missing)))

    @staticmethod
    def __normalize(path: str) -> str:
        return os.path.normpath(path).replace(os.sep, "/")

    @staticmethod
    def __needed(path: str) -> list[str]:
        result = subprocess.run(
            ["readelf", "-d", str(path)],
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
            check=False,
        )
        return BundleSlimmer.__NEEDED.findall(result.stdout)
