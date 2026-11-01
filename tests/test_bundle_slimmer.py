"""Tests of the bundle slimming rules applied by the PyInstaller spec."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


class TestBundleSlimmer:
    """Drop patterns, links to removed files, required Linux libraries."""

    ROOT = Path(__file__).resolve().parents[1]

    @pytest.fixture
    def slimmer(self) -> type:
        path = self.ROOT / "packaging" / "bundle_slimmer.py"
        spec = importlib.util.spec_from_file_location("bundle_slimmer", path)
        module: ModuleType = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.BundleSlimmer

    def test_drops_unused_qt_files_and_keeps_the_rest(self, slimmer):
        toc = [
            ("PySide6/Qt/translations/qt_it.qm", "/x", "DATA"),
            ("PySide6/Qt/plugins/platforms/libqvnc.so", "/x", "BINARY"),
            ("PySide6/Qt/plugins/imageformats/libqjpeg.so", "/x", "BINARY"),
            ("PySide6/Qt/plugins/imageformats/libqsvg.so", "/x", "BINARY"),
            ("PySide6/Qt/plugins/platforms/libqxcb.so", "/x", "BINARY"),
            ("PySide6/Qt/lib/libQt6Network.so.6", "/x", "BINARY"),
            ("PySide6/Qt/lib/QtNetwork.framework/QtNetwork", "/x", "BINARY"),
        ]
        kept = [entry[0] for entry in slimmer.drop_unused(toc)]
        assert kept == [
            "PySide6/Qt/plugins/imageformats/libqsvg.so",
            "PySide6/Qt/plugins/platforms/libqxcb.so",
        ]

    def test_drops_only_links_to_removed_files(self, slimmer):
        framework = "PySide6/Qt/lib/QtGui.framework"
        toc = [
            # Top-level link to a dropped library.
            (
                "libQt6Network.so.6",
                "PySide6/Qt/lib/libQt6Network.so.6",
                "SYMLINK",
            ),
            ("libQt6Core.so.6", "PySide6/Qt/lib/libQt6Core.so.6", "SYMLINK"),
            # macOS framework: links pointing to other links.
            ("{}/QtGui".format(framework), "Versions/Current/QtGui", "SYMLINK"),
            ("{}/Versions/Current".format(framework), "A", "SYMLINK"),
            ("{}/Versions/A/QtGui".format(framework), "/x", "BINARY"),
        ]
        removed = {"PySide6/Qt/lib/libQt6Network.so.6"}
        kept = [e[0] for e in slimmer.drop_links_to_removed(toc, removed)]
        assert kept == [entry[0] for entry in toc[1:]]

    @pytest.mark.skipif(
        not sys.platform.startswith("linux"), reason="Linux only"
    )
    def test_missing_xcb_library_fails_the_build(self, slimmer):
        complete = [
            (name, "/x", "BINARY") for name in slimmer.REQUIRED_LINUX_LIBRARIES
        ]
        slimmer.check_required_libraries(complete)
        with pytest.raises(RuntimeError, match="libxcb-cursor.so.0"):
            slimmer.check_required_libraries(complete[1:])
