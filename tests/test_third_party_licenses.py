"""Tests of the third-party license notices generated for the bundle."""

from __future__ import annotations

import importlib.util
import os
import sysconfig
import zipfile
from pathlib import Path
from types import ModuleType

import PySide6
import pytest
import sqlglot
from mysql.connector import cursor as mysql_cursor

from querylean.app.bundle_resources import BundleResources


class TestThirdPartyLicenses:
    """Attribution of bundled files and content of the generated notices."""

    ROOT = Path(__file__).resolve().parents[1]
    VENDORED = ROOT / "packaging" / "licenses"

    @pytest.fixture
    def module(self) -> ModuleType:
        path = self.ROOT / "packaging" / "third_party_licenses.py"
        spec = importlib.util.spec_from_file_location("tpl", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @pytest.fixture
    def notices(self, module, tmp_path):
        return module.ThirdPartyLicenses(
            self.ROOT, self.VENDORED, tmp_path / "out"
        )

    @staticmethod
    def entry(path: Path | str) -> tuple[str, str, str]:
        return (Path(path).name, str(path), "DATA")

    def test_vendored_license_texts_are_present(self):
        expected = {
            "LGPL-3.0.txt": "GNU LESSER GENERAL PUBLIC LICENSE",
            "GPL-3.0.txt": "GNU GENERAL PUBLIC LICENSE",
            "Apache-2.0.txt": "Apache License",
            "ICU-73.txt": "UNICODE, INC. LICENSE AGREEMENT",
        }
        for name, title in expected.items():
            text = (self.VENDORED / name).read_text(encoding="utf-8")
            assert title in text[:400], name

    def test_notices_cover_python_packages_qt_and_gpl_sources(self, notices):
        qt_core = next(Path(PySide6.__file__).parent.glob("QtCore.*"))
        stdlib = sysconfig.get_paths()["stdlib"]
        notices.collect(
            [
                self.entry(sqlglot.__file__),
                self.entry(mysql_cursor.__file__),
                self.entry(qt_core),
                self.entry(os.path.join(stdlib, "os.py")),
                self.entry(self.ROOT / "src" / "querylean" / "__init__.py"),
                ("relative", "PySide6/Qt/lib/x", "SYMLINK"),
            ]
        )
        toc = notices.write()
        names = {Path(dest).name for dest, _src, _kind in toc}
        assert BundleResources.THIRD_PARTY_LICENSES in names
        assert "LICENSE" in names
        text = Path(
            next(src for dest, src, _ in toc if dest.endswith(".txt"))
        ).read_text(encoding="utf-8")
        for expected in (
            "sqlglot",
            "mysql-connector-python",
            "PySide6_Essentials",
            "GNU LESSER GENERAL PUBLIC LICENSE",
            "https://download.qt.io/official_releases/",
            "pyinstaller",
        ):
            assert expected in text
        assert "- querylean " not in text.lower()

        archive = next(src for dest, src, _ in toc if dest.endswith(".zip"))
        with zipfile.ZipFile(archive) as zipped:
            members = zipped.namelist()
        assert "mysql/connector/cursor.py" in members
        assert any(m.endswith("/LICENSE.txt") for m in members)

    def test_file_without_known_origin_fails_the_build(self, notices, tmp_path):
        stray = tmp_path / "libunknown.so.1"
        stray.write_bytes(b"\0")
        notices.collect([self.entry(stray)])
        assert notices.unknown
        with pytest.raises(RuntimeError, match="libunknown"):
            notices.write()

    def test_source_zip_is_reproducible(self, module, tmp_path):
        archives = []
        for name in ("a", "b"):
            notices = module.ThirdPartyLicenses(
                self.ROOT, self.VENDORED, tmp_path / name
            )
            notices.collect([self.entry(mysql_cursor.__file__)])
            toc = notices.write()
            archives.append(
                next(src for dest, src, _ in toc if dest.endswith(".zip"))
            )
        assert Path(archives[0]).read_bytes() == Path(archives[1]).read_bytes()
