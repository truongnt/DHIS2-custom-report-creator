"""Shared, app-wide display format for metadata items: ``(DE) Name``.

Every list that shows data elements / attributes / indicators / program indicators uses
these helpers so the format and the per-type prefix colour are identical everywhere:
  - `code_for(item)`   → "DE" | "PA" | "I" | "PI"
  - `plain_label(item)`→ "(DE) Cases"   (for item-view models + combo boxes)
  - `html_label(item)` → '(<span style="color:#e74c3c;font-weight:700">DE</span>) Cases'
  - `TypePrefixDelegate` paints the "(CODE)" prefix of an item-view row in its type colour.
"""
from __future__ import annotations

import re

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem,
)

# Short code per type, and its prefix colour (readable on light + selection backgrounds).
TYPE_COLORS: dict[str, str] = {
    "DE": "#e74c3c",   # data element      — red
    "PA": "#27ae60",   # program attribute — green
    "I":  "#8e44ad",   # indicator         — purple
    "PI": "#e67e22",   # program indicator — orange
}

# Flattened `kind` labels (Metadata Library) → short code.
_KIND_LABEL_TO_CODE = {
    "Data Element": "DE", "Tracker DE": "DE",
    "Tracked Attribute": "PA",
    "Indicator": "I",
    "Program Indicator": "PI",
}


def code_for(item: dict) -> str:
    """Best-effort short code for a metadata item dict from any source."""
    kind = item.get("kind", "")
    if kind in TYPE_COLORS:
        return kind
    if kind in _KIND_LABEL_TO_CODE:
        return _KIND_LABEL_TO_CODE[kind]
    if item.get("is_pi"):
        return "PI"
    if item.get("is_tea"):
        return "PA"
    typ = item.get("type", "")
    if typ == "indicator":
        return "PI" if item.get("prog_uid") else "I"
    # tracker_option / tracker_numeric / aggregate all render under DE
    return "DE"


def plain_label(item: dict) -> str:
    """`(DE) Name` — used for item-view models and combo boxes (colour via delegate)."""
    return f"({code_for(item)}) {item.get('name') or item.get('uid', '')}"


def html_label(item: dict, name_color: str | None = None) -> str:
    """Rich-text label with a colour-coded prefix, for QLabel-based rows/chips."""
    code = code_for(item)
    color = TYPE_COLORS.get(code, "#555")
    name = _escape(item.get("name") or item.get("uid", ""))
    name_part = f'<span style="color:{name_color}">{name}</span>' if name_color else name
    return (f'<span style="color:{color};font-weight:700">({code})</span> {name_part}')


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


_PREFIX_RE = re.compile(r"^(\s*✓?\s*)\((DE|PA|I|PI)\)\s*(.*)$", re.S)


class TypePrefixDelegate(QStyledItemDelegate):
    """Paints an item whose DisplayRole text is ``(CODE) Name`` (optionally with a leading
    ✓) with the ``(CODE)`` prefix in its type colour. Attach to a QListView / QComboBox view.
    """

    def paint(self, painter, option, index):
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        m = _PREFIX_RE.match(text)
        if not m:
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""                                  # we draw the text ourselves
        widget = opt.widget
        style = widget.style() if widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)

        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        lead, code, rest = m.group(1), m.group(2), m.group(3)
        color = TYPE_COLORS.get(code, "#555")
        name_color = "#ffffff" if selected else "#1e2d3d"
        doc = QTextDocument()
        doc.setDefaultFont(opt.font)
        doc.setHtml(
            f'{_escape(lead)}'
            f'<span style="color:{color};font-weight:700">({code})</span> '
            f'<span style="color:{name_color}">{_escape(rest)}</span>')
        painter.save()
        r = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, widget)
        painter.translate(r.left(), r.top() + max(0, (r.height() - doc.size().height()) / 2))
        doc.drawContents(painter)
        painter.restore()

    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        return QSize(sh.width(), max(sh.height(), 20))
