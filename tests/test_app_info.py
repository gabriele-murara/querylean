"""Consistency of application metadata and of the version source."""

import importlib
import re
import tomllib
from pathlib import Path

from querylean.app.app_info import AppInfo
from querylean.app.application import Application
from querylean.app.version_file import VersionFile


class TestAppInfo:
    """``AppInfo`` must agree with ``pyproject.toml``; the version must come
    only from ``.version``."""

    ROOT = Path(__file__).resolve().parents[1]

    def pyproject(self) -> dict:
        text = (self.ROOT / "pyproject.toml").read_text(encoding="utf-8")
        return tomllib.loads(text)

    def test_version_comes_from_version_file(self):
        expected = (self.ROOT / ".version").read_text(encoding="utf-8").strip()
        assert VersionFile.path() == self.ROOT / ".version"
        assert AppInfo.version() == expected
        assert AppInfo.version() != VersionFile.UNKNOWN

    def test_pyproject_reads_version_file(self):
        data = self.pyproject()
        assert "version" not in data["project"]
        assert "version" in data["project"]["dynamic"]
        dynamic = data["tool"]["setuptools"]["dynamic"]["version"]
        assert dynamic == {"file": ".version"}
        assert data["project"]["name"] == AppInfo.NAME

    def test_gui_script_points_to_the_entry_point(self):
        scripts = self.pyproject()["project"]["gui-scripts"]
        module_name, _, attribute = scripts[AppInfo.NAME].partition(":")
        target = importlib.import_module(module_name)
        for part in attribute.split("."):
            target = getattr(target, part)
        assert target is Application.run

    def test_author_matches_pyproject(self):
        data = self.pyproject()
        assert data["project"]["authors"][0]["name"] == AppInfo.AUTHOR

    def test_no_hardcoded_version_elsewhere(self):
        version = re.escape(AppInfo.version())
        pattern = re.compile(r"(?<![\d.]){}(?![\d.])".format(version))
        sources = [
            *self.ROOT.joinpath("src").rglob("*.py"),
            *self.ROOT.joinpath("packaging").iterdir(),
            self.ROOT / "pyproject.toml",
            *self.ROOT.joinpath(".github").rglob("*.yml"),
        ]
        offenders = [
            str(path.relative_to(self.ROOT))
            for path in sources
            if path.is_file()
            and pattern.search(path.read_text(encoding="utf-8"))
        ]
        assert offenders == []

    def test_missing_or_invalid_file_is_unknown(self, tmp_path):
        assert VersionFile.parse(tmp_path / "absent") == VersionFile.UNKNOWN
        bad = tmp_path / ".version"
        bad.write_text("not a version\n", encoding="utf-8")
        assert VersionFile.parse(bad) == VersionFile.UNKNOWN
        bad.write_text("1.2.3-rc1\n", encoding="utf-8")
        assert VersionFile.parse(bad) == "1.2.3-rc1"
