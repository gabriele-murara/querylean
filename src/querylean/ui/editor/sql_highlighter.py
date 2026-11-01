"""Basic SQL syntax highlighting."""

from __future__ import annotations

import re

from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)


class SqlHighlighter(QSyntaxHighlighter):
    """Highlights keywords, strings, numbers and comments (including
    multi-line)."""

    __WORDS = "ADD ALL AND ANY AS ASC BETWEEN BINARY BY CASE CAST COLLATE "
    __WORDS += "CREATE CROSS CURRENT_DATE CURRENT_TIME CURRENT_TIMESTAMP "
    __WORDS += "DATABASE DATABASES DEFAULT DELETE DESC DESCRIBE DISTINCT DIV "
    __WORDS += "DROP ELSE END ESCAPE EXCEPT EXISTS EXPLAIN FALSE FOR FROM "
    __WORDS += "FULL GROUP HAVING IF IN INDEX INNER INSERT INTERSECT INTERVAL "
    __WORDS += "INTO IS JOIN KEY LATERAL LEFT LIKE LIMIT MOD NATURAL NOT NULL "
    __WORDS += "OFFSET ON OR ORDER OUTER OVER PARTITION RECURSIVE REGEXP "
    __WORDS += "RIGHT ROLLUP ROW ROWS SELECT SET SHOW STATUS STRAIGHT_JOIN "
    __WORDS += "TABLE TABLES THEN TRUE UNION UNIQUE UPDATE USING VALUES "
    __WORDS += "VARIABLES VIEW WHEN WHERE WINDOW WITH XOR"
    KEYWORDS = __WORDS.split()

    __IN_COMMENT = 1
    __KEYWORD_RE = re.compile(
        r"\b(?:{})\b".format("|".join(KEYWORDS)), re.IGNORECASE
    )
    __NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b")
    # Strings, quoted identifiers and line comments, in order of appearance.
    __SPAN = r"'(?:\\.|''|[^'\\])*'?"
    __SPAN += r"|\"(?:\\.|\"\"|[^\"\\])*\"?"
    __SPAN += r"|`(?:``|[^`])*`?"
    __SPAN += r"|#.*$|--(?:\s.*)?$|/\*"
    __SPAN_RE = re.compile(__SPAN)

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self.__keyword = SqlHighlighter.__make_format("#0033b3", bold=True)
        self.__string = SqlHighlighter.__make_format("#067d17")
        self.__number = SqlHighlighter.__make_format("#1750eb")
        self.__comment = SqlHighlighter.__make_format("#8c8c8c", italic=True)
        self.__plain = QTextCharFormat()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt API)
        for match in SqlHighlighter.__KEYWORD_RE.finditer(text):
            self.setFormat(
                match.start(), match.end() - match.start(), self.__keyword
            )
        for match in SqlHighlighter.__NUMBER_RE.finditer(text):
            self.setFormat(
                match.start(), match.end() - match.start(), self.__number
            )

        self.setCurrentBlockState(0)
        pos = 0
        if self.previousBlockState() == SqlHighlighter.__IN_COMMENT:
            pos = self.__comment_to_end(text, 0, continuing=True)
        while pos < len(text):
            match = SqlHighlighter.__SPAN_RE.search(text, pos)
            if not match:
                break
            token = match.group()
            if token == "/*":
                pos = self.__comment_to_end(
                    text, match.start(), continuing=False
                )
                continue
            if token[0] == "`":
                fmt = self.__plain  # quoted identifiers are not highlighted
            elif token[0] in "#-":
                fmt = self.__comment
            else:
                fmt = self.__string
            self.setFormat(match.start(), len(token), fmt)
            pos = match.end()

    def __comment_to_end(
        self, text: str, start: int, *, continuing: bool
    ) -> int:
        """Format a /* */ comment from ``start``; return the end position."""
        end = text.find("*/", start if continuing else start + 2)
        if end < 0:
            self.setCurrentBlockState(SqlHighlighter.__IN_COMMENT)
            self.setFormat(start, len(text) - start, self.__comment)
            return len(text)
        self.setFormat(start, end + 2 - start, self.__comment)
        return end + 2

    @staticmethod
    def __make_format(
        color: str, *, bold: bool = False, italic: bool = False
    ) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        fmt.setFontItalic(italic)
        return fmt
