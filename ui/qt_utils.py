"""Shared Qt utilities for DHIS2 Auto Report."""
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QScrollArea, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

# ── Brand colours ─────────────────────────────────────────────
DHIS2_BLUE  = "#1a6fa8"
SIDEBAR_BG  = "#1e2d3d"
SIDEBAR_FG  = "#ffffff"
PANEL_BG    = "#f7f9fc"
BORDER_CLR  = "#d0dde8"

# ── Global QSS ────────────────────────────────────────────────
APP_QSS = """
QWidget {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
}
QScrollArea { border: none; }
QScrollBar:vertical {
    width: 8px; background: #f0f0f0;
}
QScrollBar::handle:vertical {
    background: #c0cdd8; border-radius: 4px; min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #a0b0c0; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal {
    height: 8px; background: #f0f0f0;
}
QScrollBar::handle:horizontal {
    background: #c0cdd8; border-radius: 4px; min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }

QPushButton {
    border: 1px solid #c0cdd8;
    border-radius: 4px;
    padding: 4px 10px;
    background: white;
    color: #1e2d3d;
}
QPushButton:hover { background: #e8eef5; }
QPushButton:pressed { background: #d0dde8; }
QPushButton:disabled { color: #aaaaaa; background: #f5f5f5; border-color: #e0e0e0; }

QPushButton[class="primary"] {
    background: #1a6fa8; color: white; border: none;
}
QPushButton[class="primary"]:hover { background: #155a8a; }
QPushButton[class="primary"]:pressed { background: #0f4870; }

QPushButton[class="success"] {
    background: #27ae60; color: white; border: none;
}
QPushButton[class="success"]:hover { background: #1e8449; }

QPushButton[class="danger"] {
    background: #e74c3c; color: white; border: none;
}
QPushButton[class="danger"]:hover { background: #c0392b; }

QPushButton[class="outline-primary"] {
    background: transparent; color: #1a6fa8; border: 1px solid #1a6fa8;
}
QPushButton[class="outline-primary"]:hover { background: #e8f0f8; }

QPushButton[class="ghost"] {
    background: transparent; border: none; color: #5a7a9a;
}
QPushButton[class="ghost"]:hover { background: #e8eef5; }

QLineEdit {
    border: 1px solid #c0cdd8;
    border-radius: 4px;
    padding: 4px 8px;
    background: white;
    color: #1e2d3d;
}
QLineEdit:focus { border-color: #1a6fa8; }
QLineEdit:disabled { background: #f5f5f5; color: #aaaaaa; }

QTextEdit, QPlainTextEdit {
    border: 1px solid #c0cdd8;
    border-radius: 4px;
    background: white;
    color: #1e2d3d;
}
QTextEdit:focus { border-color: #1a6fa8; }

QComboBox {
    border: 1px solid #c0cdd8;
    border-radius: 4px;
    padding: 3px 8px;
    background: white;
    color: #1e2d3d;
    min-height: 22px;
}
QComboBox:focus { border-color: #1a6fa8; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    border: 1px solid #c0cdd8;
    background: white;
    selection-background-color: #dbeafe;
    selection-color: #1e2d3d;
}

QCheckBox { color: #1e2d3d; spacing: 6px; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #c0cdd8;
    border-radius: 2px;
    background: white;
}
QCheckBox::indicator:checked {
    background: #1a6fa8;
    border-color: #1a6fa8;
    image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMiAxMiI+PHBhdGggZD0iTTIgNmw0IDQgNC04IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIGZpbGw9Im5vbmUiLz48L3N2Zz4=);
}

QRadioButton { color: #1e2d3d; spacing: 6px; }
QRadioButton::indicator {
    width: 14px; height: 14px;
    border: 1px solid #c0cdd8;
    border-radius: 7px;
    background: white;
}
QRadioButton::indicator:checked {
    background: #1a6fa8;
    border-color: #1a6fa8;
}

QListWidget {
    border: 1px solid #c0cdd8;
    border-radius: 4px;
    background: white;
    color: #1e2d3d;
    outline: none;
}
QListWidget::item { padding: 3px 6px; }
QListWidget::item:selected {
    background: #dbeafe;
    color: #1e2d3d;
}
QListWidget::item:hover { background: #e8eef5; }

QProgressBar {
    border: 1px solid #c0cdd8;
    border-radius: 4px;
    background: #e8eef5;
    height: 8px;
    text-align: center;
    font-size: 9px;
}
QProgressBar::chunk {
    background: #1a6fa8;
    border-radius: 3px;
}

QSplitter::handle { background: #d0dde8; }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical { height: 1px; }

QStatusBar {
    background: #eef2f7;
    border-top: 1px solid #d0dde8;
    color: #6b8299;
    font-size: 11px;
}
QStatusBar::item { border: none; }
"""


class SegmentedButton(QWidget):
    """
    Replaces CTkSegmentedButton.
    Horizontal row of mutually-exclusive toggle buttons.
    """
    changed = Signal(str)

    def __init__(self, values: list, default: str = "", parent=None):
        super().__init__(parent)
        self._btns: dict[str, QPushButton] = {}
        self._current = default if default in values else (values[0] if values else "")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for i, v in enumerate(values):
            btn = QPushButton(str(v))
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            # Rounded corners only on first/last
            radius = "4px"
            if len(values) == 1:
                style = f"border-radius:{radius};"
            elif i == 0:
                style = f"border-radius:{radius} 0 0 {radius}; border-right:none;"
            elif i == len(values) - 1:
                style = f"border-radius:0 {radius} {radius} 0;"
            else:
                style = "border-radius:0; border-right:none;"
            btn.setStyleSheet(
                f"QPushButton {{ {style} border:1px solid #c0cdd8; background:#e8eef5; color:#3a5068; padding:2px 8px; }}"
                f"QPushButton:checked {{ background:{DHIS2_BLUE}; color:white; border-color:{DHIS2_BLUE}; }}"
                f"QPushButton:hover:!checked {{ background:#d0dde8; }}"
            )
            btn.clicked.connect(lambda _, val=v: self._on_click(val))
            self._btns[v] = btn
            layout.addWidget(btn)

        # Set initial checked state
        if self._current in self._btns:
            self._btns[self._current].setChecked(True)

    def _on_click(self, value: str):
        if value == self._current:
            # Re-check it (prevent deselection)
            self._btns[value].setChecked(True)
            return
        self._current = value
        for v, btn in self._btns.items():
            btn.setChecked(v == value)
        self.changed.emit(value)

    def get(self) -> str:
        return self._current

    def set(self, value: str):
        if value not in self._btns or value == self._current:
            return
        self._current = value
        for v, btn in self._btns.items():
            btn.setChecked(v == value)

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        for btn in self._btns.values():
            btn.setEnabled(enabled)


def make_scroll_area(parent=None, h_scroll=False) -> tuple:
    """
    Create a QScrollArea with an inner QWidget that has a VBoxLayout.
    Returns (scroll_area, inner_widget, inner_layout).
    Use inner_layout.addWidget(...) to add content.
    """
    sa = QScrollArea(parent)
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    if not h_scroll:
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    inner = QWidget()
    inner.setObjectName("scroll_inner")
    layout = QVBoxLayout(inner)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addStretch()   # will be removed when content added
    sa.setWidget(inner)
    return sa, inner, layout


def section_label(text: str, parent=None) -> QLabel:
    """Bold section header label (replaces _sec_lbl)."""
    lbl = QLabel(text.upper(), parent)
    lbl.setStyleSheet("color: #8aa3b8; font-size: 9px; font-weight: bold; padding: 6px 12px 2px 12px;")
    return lbl


def divider(parent=None, vertical=False) -> QFrame:
    """Thin 1px separator line."""
    line = QFrame(parent)
    line.setFrameShape(QFrame.VLine if vertical else QFrame.HLine)
    line.setStyleSheet("color: #d0dde8;")
    return line


def primary_btn(text: str, parent=None, h=30) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setProperty("class", "primary")
    btn.setFixedHeight(h)
    return btn


def success_btn(text: str, parent=None, h=30) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setProperty("class", "success")
    btn.setFixedHeight(h)
    return btn


def outline_btn(text: str, parent=None, h=30) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setProperty("class", "outline-primary")
    btn.setFixedHeight(h)
    return btn


def ghost_btn(text: str, parent=None, h=30) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setProperty("class", "ghost")
    btn.setFixedHeight(h)
    return btn
