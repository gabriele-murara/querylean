"""Consistency of application metadata."""

import tomllib
from pathlib import Path

from querylean.app.app_info import AppInfo


class TestAppInfo:
    """``AppInfo`` must agree with ``pyproject.toml``."""

    def test_version_matches_pyproject(self):
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        assert data["project"]["version"] == AppInfo.VERSION
        assert data["project"]["name"] == AppInfo.NAME
