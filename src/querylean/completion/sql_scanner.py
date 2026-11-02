"""Tolerant tokenizer for SQL being edited."""

from __future__ import annotations

from querylean.completion.scan_token import ScanToken


class SqlScanner:
    """Splits SQL text into tokens following MySQL's rules for strings,
    quoted identifiers and comments, without ever failing: unterminated
    strings and comments simply run to the end of the text.

    Unlike the validator lexer it accepts any input, because it works on
    text that is still being written.
    """

    __IDENTIFIER_EXTRA = "_$"
    __MULTI_SYMBOLS = ("<=>", "<=", ">=", "<>", "!=", "||", "&&", ":=")

    @staticmethod
    def is_identifier_char(ch: str) -> bool:
        """True for characters of an unquoted identifier."""
        return ch.isalnum() or ch in SqlScanner.__IDENTIFIER_EXTRA

    @staticmethod
    def scan(text: str) -> list[ScanToken]:
        """Every token of ``text``, comments included, in order."""
        tokens: list[ScanToken] = []
        i, n = 0, len(text)
        while i < n:
            ch = text[i]
            nxt = text[i + 1] if i + 1 < n else ""
            if ch.isspace():
                i += 1
            elif ch == "#" or (
                ch == "-"
                and nxt == "-"
                and (i + 2 >= n or text[i + 2].isspace())
            ):
                end = text.find("\n", i)
                end = n if end < 0 else end
                tokens.append(
                    ScanToken(ScanToken.COMMENT, text[i:end], i, closed=False)
                )
                i = end
            elif ch == "/" and nxt == "*":
                end = text.find("*/", i + 2)
                closed = end >= 0
                end = end + 2 if closed else n
                tokens.append(
                    ScanToken(ScanToken.COMMENT, text[i:end], i, closed=closed)
                )
                i = end
            elif ch in "'\"":
                i = SqlScanner.__quoted(text, i, ScanToken.STRING, tokens)
            elif ch == "`":
                i = SqlScanner.__quoted(text, i, ScanToken.QUOTED, tokens)
            elif ch == "@":
                j = i + 1
                if j < n and text[j] == "@":
                    j += 1
                while j < n and (
                    SqlScanner.is_identifier_char(text[j]) or text[j] == "."
                ):
                    j += 1
                tokens.append(ScanToken(ScanToken.VARIABLE, text[i:j], i))
                i = j
            elif ch.isdigit() or (ch == "." and nxt.isdigit()):
                i = SqlScanner.__number_or_word(text, i, tokens)
            elif SqlScanner.is_identifier_char(ch):
                j = i
                while j < n and SqlScanner.is_identifier_char(text[j]):
                    j += 1
                tokens.append(ScanToken(ScanToken.WORD, text[i:j], i))
                i = j
            else:
                symbol = ch
                for candidate in SqlScanner.__MULTI_SYMBOLS:
                    if text.startswith(candidate, i):
                        symbol = candidate
                        break
                tokens.append(ScanToken(ScanToken.SYMBOL, symbol, i))
                i += len(symbol)
        return tokens

    @staticmethod
    def __quoted(
        text: str, start: int, kind: str, tokens: list[ScanToken]
    ) -> int:
        """Scan a string or quoted identifier opened at ``start``. Doubled
        delimiters, and backslash escapes in strings, stay inside it."""
        quote = text[start]
        i, n = start + 1, len(text)
        while i < n:
            ch = text[i]
            if ch == "\\" and kind == ScanToken.STRING:
                i += 2
            elif ch == quote:
                if i + 1 < n and text[i + 1] == quote:
                    i += 2
                else:
                    tokens.append(ScanToken(kind, text[start : i + 1], start))
                    return i + 1
            else:
                i += 1
        tokens.append(ScanToken(kind, text[start:], start, closed=False))
        return n

    @staticmethod
    def __number_or_word(text: str, start: int, tokens: list[ScanToken]) -> int:
        """Numbers (``1``, ``1.5``, ``.5``, ``1e3``, ``0x1F``); a run that
        also has other letters (``1abc``) is an identifier, as in MySQL."""
        i, n = start, len(text)
        while i < n and (
            SqlScanner.is_identifier_char(text[i])
            or (
                text[i] == "."
                and i + 1 < n
                and text[i + 1].isdigit()
                and "." not in text[start:i]
            )
            or (
                text[i] in "+-"
                and i > start
                and text[i - 1] in "eE"
                and text[start : i - 1].replace(".", "").isdigit()
            )
        ):
            i += 1
        word = text[start:i]
        kind = (
            ScanToken.NUMBER
            if SqlScanner.__is_number(word)
            else (ScanToken.WORD)
        )
        tokens.append(ScanToken(kind, word, start))
        return i

    @staticmethod
    def __is_number(word: str) -> bool:
        lower = word.lower()
        if lower.startswith("0x"):
            return all(c in "0123456789abcdef" for c in lower[2:])
        if lower.startswith("0b") and lower[2:]:
            return all(c in "01" for c in lower[2:])
        mantissa, _, exponent = lower.partition("e")
        if exponent and not exponent.lstrip("+-").isdigit():
            return False
        return mantissa.replace(".", "", 1).isdigit() or mantissa == "."
