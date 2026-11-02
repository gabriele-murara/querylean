"""Tests of the atomic, private file replacement."""

import os
import stat

import pytest

from querylean.files.private_file import PrivateFile


class TestPrivateFile:
    """Replacement on success, cleanup on failure, 0600 permissions."""

    def test_replaces_target_with_private_mode(self, tmp_path):
        target = tmp_path / "out.csv"
        target.write_text("old")
        with PrivateFile.replace(target, ".csv") as tmp:
            assert tmp.parent == tmp_path and tmp.suffix == ".csv"
            # A writer that recreates the file with a wider mode.
            tmp.unlink()
            tmp.write_text("new")
            os.chmod(tmp, 0o644)
        assert target.read_text() == "new"
        assert stat.S_IMODE(os.stat(target).st_mode) == PrivateFile.MODE
        assert sorted(tmp_path.iterdir()) == [target]

    def test_failure_keeps_target_and_removes_temporary(self, tmp_path):
        target = tmp_path / "out.json"
        target.write_text("old")
        with (
            pytest.raises(RuntimeError),
            PrivateFile.replace(target) as tmp,
        ):
            tmp.write_text("partial")
            raise RuntimeError("writer failed")
        assert target.read_text() == "old"
        assert sorted(tmp_path.iterdir()) == [target]

    def test_missing_directory_raises(self, tmp_path):
        with (
            pytest.raises(FileNotFoundError),
            PrivateFile.replace(tmp_path / "missing" / "x.txt"),
        ):
            pass
