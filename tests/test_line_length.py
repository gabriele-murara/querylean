"""Physical line length of the sources, comments and pragmas included."""

from pathlib import Path


class TestLineLength:
    """``ruff`` does not count a trailing ``# noqa`` against the limit;
    the coding rules do (80 columns everywhere, shell scripts and the
    PyInstaller spec too)."""

    LIMIT = 80
    ROOT = Path(__file__).resolve().parent.parent
    FOLDERS = ("src", "tests", "packaging")
    PATTERNS = ("*.py", "*.sh", "*.spec")

    def test_lines_fit(self) -> None:
        too_long = []
        for folder in TestLineLength.FOLDERS:
            for pattern in TestLineLength.PATTERNS:
                for path in sorted(
                    (TestLineLength.ROOT / folder).rglob(pattern)
                ):
                    lines = path.read_text(encoding="utf-8").splitlines()
                    for number, line in enumerate(lines, 1):
                        if len(line) > TestLineLength.LIMIT:
                            relative = path.relative_to(TestLineLength.ROOT)
                            too_long.append("{}:{}".format(relative, number))
        assert too_long == []

    def test_sources_are_found(self) -> None:
        spec = TestLineLength.ROOT / "packaging" / "querylean.spec"
        assert spec.is_file()
        assert list((TestLineLength.ROOT / "packaging").rglob("*.sh"))
