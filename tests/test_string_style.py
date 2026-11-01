"""Enforces the string formatting rules of CLAUDE.md on the whole code base.

- no f-strings;
- no implicit concatenation of adjacent string literals;
- no ``+`` between a string literal and another value;
- no ``%`` formatting, logger calls included.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path


class TestStringStyle:
    """Every string is built with ``str.format`` and ``+=`` of literals."""

    __ROOT = Path(__file__).resolve().parents[1]
    __SOURCES = ("src", "tests", "packaging")
    __LOG_METHODS = frozenset(
        {"debug", "info", "warning", "error", "critical", "exception"}
    )
    __PERCENT = re.compile(r"%(\(\w+\))?[-+ 0#]*\d*(\.\d+)?[sdrifxXeEgG]")
    __SKIP = frozenset({tokenize.NL, tokenize.COMMENT})

    @staticmethod
    def files() -> list[Path]:
        """Python sources of the project, PyInstaller spec included."""
        found: list[Path] = []
        for folder in TestStringStyle.__SOURCES:
            base = TestStringStyle.__ROOT / folder
            found += sorted(base.rglob("*.py"))
            found += sorted(base.rglob("*.spec"))
        return found

    @staticmethod
    def is_text(node: ast.AST) -> bool:
        """True for a string literal or an f-string."""
        if isinstance(node, ast.JoinedStr):
            return True
        return isinstance(node, ast.Constant) and isinstance(node.value, str)

    @staticmethod
    def implicit_concatenations(source: str) -> list[int]:
        """Lines where two string literals are adjacent."""
        lines: list[int] = []
        previous = None
        readline = io.StringIO(source).readline
        for token in tokenize.generate_tokens(readline):
            if token.type in TestStringStyle.__SKIP:
                continue
            if token.type == tokenize.STRING and previous == tokenize.STRING:
                lines.append(token.start[0])
            previous = token.type
        return lines

    @staticmethod
    def violations(path: Path) -> list[str]:
        """Human readable violations found in ``path``."""
        source = path.read_text(encoding="utf-8")
        found: list[str] = []
        for line in TestStringStyle.implicit_concatenations(source):
            found.append("{}: implicit concatenation".format(line))
        for node in ast.walk(ast.parse(source)):
            line = getattr(node, "lineno", 0)
            if isinstance(node, ast.JoinedStr):
                found.append("{}: f-string".format(line))
            elif isinstance(node, ast.BinOp):
                sides = (node.left, node.right)
                text = any(TestStringStyle.is_text(s) for s in sides)
                if isinstance(node.op, ast.Add) and text:
                    found.append("{}: '+' concatenation".format(line))
                elif isinstance(node.op, ast.Mod) and (
                    TestStringStyle.is_text(node.left)
                ):
                    found.append("{}: '%' formatting".format(line))
            elif TestStringStyle.is_percent_log_call(node):
                found.append("{}: '%' placeholder in a log call".format(line))
        return sorted(set(found), key=lambda item: int(item.split(":")[0]))

    @staticmethod
    def is_percent_log_call(node: ast.AST) -> bool:
        """True for ``log.info("... %s ...", value)`` style calls."""
        if not isinstance(node, ast.Call) or not node.args:
            return False
        func = node.func
        if not isinstance(func, ast.Attribute):
            return False
        if func.attr not in TestStringStyle.__LOG_METHODS:
            return False
        first = node.args[0]
        if not TestStringStyle.is_text(first) or isinstance(
            first, ast.JoinedStr
        ):
            return False
        return bool(TestStringStyle.__PERCENT.search(first.value))

    def test_strings_follow_the_coding_style(self) -> None:
        found: list[str] = []
        for path in TestStringStyle.files():
            name = path.relative_to(TestStringStyle.__ROOT)
            for violation in TestStringStyle.violations(path):
                found.append("{}:{}".format(name, violation))
        assert found == []

    def test_detector_finds_every_forbidden_form(self, tmp_path: Path) -> None:
        sample = tmp_path / "sample.py"
        code = 'a = f"x{1}"\n'
        code += 'b = ("x" "y")\n'
        code += 'c = "x" + a\n'
        code += 'd = "%s" % a\n'
        code += 'log.info("value %s", a)\n'
        code += 'e = "ok {}"\n'
        code += 'e += "fine"\n'
        code += "e = e.format(a)\n"
        sample.write_text(code, encoding="utf-8")
        found = TestStringStyle.violations(sample)
        assert [item.split(":")[0] for item in found] == [
            "1",
            "2",
            "3",
            "4",
            "5",
        ]
