"""
html_template_gallery.py — Pick a previously generated 'image → HTML' template.

Shows saved templates as a matrix/grid of image thumbnails (config.html_template_library).
Selecting one returns its HTML so the editor can load it without calling the API again.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

import config.html_template_library as htl

_COLS = 3
_THUMB_W = 200
_THUMB_H = 130


class HtmlTemplateGallery(QDialog):
    """Grid of saved templates. `self.result_html` is set when the user picks one."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_html: str | None = None
        self.setWindowTitle("HTML templates")
        self.resize(720, 540)

        outer = QVBoxLayout(self)
        hdr = QLabel("Pick a saved template to load it into the editor (no API call).")
        hdr.setStyleSheet("color:#5a7a9a;font-size:11px;")
        outer.addWidget(hdr)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        outer.addWidget(self._scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        outer.addLayout(btn_row)

        self._rebuild()

    def _rebuild(self) -> None:
        items = htl.load_index()
        host = QWidget()
        if not items:
            lay = QVBoxLayout(host)
            empty = QLabel("No templates yet.\nUse '🤖 Generate from image…' to create one.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color:#9bb3c4;font-size:13px;padding:40px;")
            lay.addWidget(empty)
            self._scroll.setWidget(host)
            return

        grid = QGridLayout(host)
        grid.setSpacing(12)
        for i, entry in enumerate(items):
            grid.addWidget(self._card(entry), i // _COLS, i % _COLS)
        # keep cards top-left aligned
        grid.setRowStretch((len(items) // _COLS) + 1, 1)
        self._scroll.setWidget(host)

    def _card(self, entry: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            "QFrame{border:1px solid #c0cdd8;border-radius:6px;background:#ffffff;}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        thumb = QLabel()
        thumb.setFixedSize(_THUMB_W, _THUMB_H)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet("border:1px solid #e1e8ee;background:#f7fafc;")
        pix = QPixmap(str(htl.image_path(entry)))
        if not pix.isNull():
            thumb.setPixmap(pix.scaled(_THUMB_W, _THUMB_H, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation))
        else:
            thumb.setText("(no image)")
        lay.addWidget(thumb)

        name = QLabel(entry.get("name", "Template"))
        name.setStyleSheet("font-size:11px;font-weight:bold;color:#1e2d3d;border:none;")
        name.setWordWrap(True)
        lay.addWidget(name)

        meta = QLabel(f"{entry.get('created_at', '')} · {_short(entry.get('model', ''))}")
        meta.setStyleSheet("font-size:9px;color:#7a93a8;border:none;")
        lay.addWidget(meta)

        row = QHBoxLayout()
        use_btn = QPushButton("Use")
        use_btn.setStyleSheet(
            "QPushButton{font-size:10px;padding:3px 10px;border:1px solid #1a6fa8;"
            "border-radius:4px;background:#eaf3fa;color:#1a6fa8;}"
            "QPushButton:hover{background:#d6e9f7;}")
        use_btn.clicked.connect(lambda _=False, e=entry: self._use(e))
        row.addWidget(use_btn)
        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet(
            "QPushButton{font-size:10px;padding:3px 10px;border:1px solid #d0808a;"
            "border-radius:4px;background:#fdecea;color:#c0392b;}"
            "QPushButton:hover{background:#fad7d3;}")
        del_btn.clicked.connect(lambda _=False, e=entry: self._delete(e))
        row.addWidget(del_btn)
        lay.addLayout(row)
        return card

    def _use(self, entry: dict) -> None:
        self.result_html = entry.get("html", "")
        self.accept()

    def _delete(self, entry: dict) -> None:
        if QMessageBox.question(
                self, "Delete template",
                f"Delete \"{entry.get('name', '')}\"?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        htl.delete_template(entry.get("id", ""))
        self._rebuild()


def _short(model: str) -> str:
    m = (model or "").lower()
    if "opus" in m:
        return "Opus"
    if "sonnet" in m:
        return "Sonnet"
    if "haiku" in m:
        return "Haiku"
    return model or "AI"
