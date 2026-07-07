"""
HtmlTemplateHighlighter — syntax highlighting for the Custom HTML widget editor.

Colours HTML tags / attributes / strings / comments, and — most usefully — the
``{{ variable }}`` placeholders: green when the name matches a known metric/dimension
column, red when it doesn't (typo / not selected). Call ``set_known_vars()`` whenever the
selected metrics/dimensions change so the green/red feedback stays accurate.
"""
from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


def _fmt(color: str, *, bold: bool = False, italic: bool = False, bg: str | None = None) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    if bg:
        f.setBackground(QColor(bg))
    return f


class HtmlTemplateHighlighter(QSyntaxHighlighter):
    """Highlights HTML + ``{{column}}`` placeholders in the Custom HTML template editor."""

    def __init__(self, document, known_vars=None):
        super().__init__(document)
        self._known: set[str] = {v for v in (known_vars or set()) if v}

        self._f_tag     = _fmt("#1a6fa8", bold=True)                  # <tag> name + < > /
        self._f_attr    = _fmt("#8e44ad")                            # attribute names
        self._f_str     = _fmt("#1e8449")                            # "attr values"
        self._f_comment = _fmt("#8aa0b4", italic=True)               # <!-- comments -->
        self._f_var_ok  = _fmt("#0e6655", bold=True, bg="#d1f2eb")    # {{known column}}
        self._f_var_bad = _fmt("#c0392b", bold=True, bg="#fdecea")    # {{unknown}}

        self._re_tag     = QRegularExpression(r"</?\s*[A-Za-z][\w:-]*")
        self._re_tagend  = QRegularExpression(r"/?>")
        self._re_attr    = QRegularExpression(r"([A-Za-z_:][\w:.-]*)\s*=")
        self._re_str     = QRegularExpression(r"\"[^\"]*\"|'[^']*'")
        self._re_comment = QRegularExpression(r"<!--.*?-->")
        self._re_var     = QRegularExpression(r"\{\{\s*([^}]+?)\s*\}\}")

    def set_known_vars(self, names) -> None:
        new = {str(n) for n in (names or set()) if n}
        if new != self._known:
            self._known = new
            self.rehighlight()

    def _apply(self, text: str, regex: QRegularExpression, fmt: QTextCharFormat, group: int = 0) -> None:
        it = regex.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(group), m.capturedLength(group), fmt)

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt override)
        self._apply(text, self._re_str, self._f_str)
        self._apply(text, self._re_tag, self._f_tag)
        self._apply(text, self._re_tagend, self._f_tag)
        self._apply(text, self._re_attr, self._f_attr, group=1)
        self._apply(text, self._re_comment, self._f_comment)
        # Placeholders last so they win, coloured by whether the name is a known column.
        it = self._re_var.globalMatch(text)
        while it.hasNext():
            m = it.next()
            name = m.captured(1).strip()
            fmt = self._f_var_ok if name in self._known else self._f_var_bad
            self.setFormat(m.capturedStart(0), m.capturedLength(0), fmt)
