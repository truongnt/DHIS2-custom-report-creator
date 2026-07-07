"""Shared Qt utilities for DHIS2 Auto Report."""
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QScrollArea, QSizePolicy, QApplication, QComboBox, QLineEdit,
    QDialogButtonBox, QInputDialog, QColorDialog,
)
from PySide6.QtCore import Qt, Signal, QTimer, QMimeData
from PySide6.QtGui import QFont, QColor, QDrag

# Agg-type dropdown inside a metric chip. Includes the popup-view styling so the list
# isn't a black top-level popup (a bare font-size stylesheet resets the global rule).
_AGG_COMBO_QSS = (
    "QComboBox { border:1px solid #c0cdd8; border-radius:4px; padding:1px 6px;"
    "  background:white; color:#1e2d3d; font-size:9px; }"
    "QComboBox:focus { border-color:#1a6fa8; }"
    "QComboBox::drop-down { border:none; width:16px; }"
    "QComboBox QAbstractItemView { background:#ffffff; color:#1e2d3d;"
    "  border:1px solid #c0cdd8; selection-background-color:#dbeafe; selection-color:#1e2d3d; }"
)

# ── DE type icons ──────────────────────────────────────────────
_DE_ICONS: dict[str, str] = {
    "tracker_option":  "◈",
    "tracker_numeric": "⊞",
    "aggregate":       "▤",
    "indicator":       "⊙",
    "tea":             "👤",
}

# ── Brand colours ─────────────────────────────────────────────
DHIS2_BLUE  = "#1a6fa8"
SIDEBAR_BG  = "#1e2d3d"
SIDEBAR_FG  = "#ffffff"
PANEL_BG    = "#f7f9fc"
BORDER_CLR  = "#d0dde8"


def style_dialog_buttons(box: QDialogButtonBox, *, bg: str = PANEL_BG,
                         border: str = BORDER_CLR) -> QWidget:
    """Standard dialog footer (REQ-UI-COMP-09). Styles `box` and returns a padded
    container to add to the dialog (so buttons never sit flush in a corner):

        root.addWidget(style_dialog_buttons(btn_box))

    - Accept/OK is the primary (blue) button, others neutral;
    - every button has visible :hover / :pressed / :disabled + a sane min size;
    - the returned footer carries real margins (QDialogButtonBox ignores QSS padding and
      resets its own layout margins on polish, so we wrap it instead).
    """
    box.setStyleSheet("QDialogButtonBox { background: transparent; border: none; }")
    box.setCenterButtons(False)        # standard right-alignment
    for b in box.buttons():
        b.setMinimumHeight(30)
        b.setMinimumWidth(88)
        b.setCursor(Qt.PointingHandCursor)
        if box.buttonRole(b) == QDialogButtonBox.ButtonRole.AcceptRole:
            b.setStyleSheet(
                f"QPushButton {{ background:{DHIS2_BLUE}; color:white; border:1px solid {DHIS2_BLUE};"
                "  border-radius:4px; padding:4px 16px; }"
                "QPushButton:hover { background:#155a8a; }"
                "QPushButton:pressed { background:#0f4870; }"
                "QPushButton:disabled { background:#cdd8e4; color:#eef3f8; border-color:#cdd8e4; }"
            )
        else:
            b.setStyleSheet(
                "QPushButton { background:white; color:#3a5068; border:1px solid #c0cdd8;"
                "  border-radius:4px; padding:4px 16px; }"
                "QPushButton:hover { background:#e3eaf2; }"
                "QPushButton:pressed { background:#d0dde8; }"
            )

    footer = QFrame()
    footer.setStyleSheet(f"QFrame {{ background-color: {bg}; border-top: 1px solid {border}; }}")
    fl = QHBoxLayout(footer)
    fl.setContentsMargins(12, 8, 12, 10)   # real padding from the dialog edge
    fl.addWidget(box)
    return footer


# ── Global QSS ────────────────────────────────────────────────
APP_QSS = """
/* ── Base ── */
QWidget {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
}

/* ── Labels on light panels: always dark so dark-mode OS can't flip them ── */
QLabel {
    color: #1e2d3d;
    background: transparent;
}

/* Dialogs and pop-ups */
QDialog, QMessageBox {
    background-color: #ffffff;
    color: #1e2d3d;
}
QDialog QLabel, QMessageBox QLabel {
    color: #1e2d3d;
    background: transparent;
}
QDialog QPushButton, QMessageBox QPushButton {
    color: #1e2d3d;
    background: #f0f4f8;
    border: 1px solid #c0cdd8;
    border-radius: 4px;
    padding: 4px 14px;
    min-width: 60px;
}
QDialog QPushButton:hover, QMessageBox QPushButton:hover {
    background: #d6eaf8;
}

/* Menus */
QMenu {
    background: #ffffff;
    color: #1e2d3d;
    border: 1px solid #c0cdd8;
}
QMenu::item:selected {
    background: #dbeafe;
    color: #1e2d3d;
}

/* Tooltips */
QToolTip {
    background: #1e2d3d;
    color: #ffffff;
    border: 1px solid #3a5068;
    padding: 3px 6px;
    border-radius: 3px;
}

/* Input dialogs */
QInputDialog QLabel { color: #1e2d3d; background: transparent; }
QInputDialog QLineEdit { color: #1e2d3d; background: #ffffff; }

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
    color: #1e2d3d;
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
    image: url(__CHECK_IMG__);
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
    image: url(__DOT_IMG__);
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


def _install_indicator_assets() -> None:
    """Write the checkbox tick / radio dot SVGs to disk and point APP_QSS at them.

    Qt style sheets resolve ``image: url(...)`` as a file/resource path — NOT a ``data:``
    URI — so an inline data-URI tick silently fails and the box just fills with colour
    ('bôi màu cả ô'). Referencing a real .svg file (rendered by the bundled qsvg plugin)
    shows the tick correctly. Falls back to leaving the flat fill if writing fails.
    """
    global APP_QSS
    from pathlib import Path
    check_svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">'
                 '<path d="M2.5 6.3 L5 8.8 L9.5 3.5" stroke="white" stroke-width="1.8" '
                 'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    dot_svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">'
               '<circle cx="6" cy="6" r="2.6" fill="white"/></svg>')
    try:
        assets = Path(__file__).parent.parent / "cache" / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        chk = assets / "checkbox_tick.svg"
        dot = assets / "radio_dot.svg"
        chk.write_text(check_svg, encoding="utf-8")
        dot.write_text(dot_svg, encoding="utf-8")
        APP_QSS = (APP_QSS
                   .replace("__CHECK_IMG__", chk.as_posix())
                   .replace("__DOT_IMG__", dot.as_posix()))
    except Exception:
        # Leave the flat fill (still functional) rather than crash on a read-only dir.
        APP_QSS = APP_QSS.replace("    image: url(__CHECK_IMG__);\n", "") \
                         .replace("    image: url(__DOT_IMG__);\n", "")


_install_indicator_assets()


class SegmentedButton(QWidget):
    """
    Replaces CTkSegmentedButton.
    Horizontal row of mutually-exclusive toggle buttons.

    custom : None | "text" | "number" | "color"
        Only use when a custom value is genuinely useful (size, colour…).
        - "number"/"text" → an INLINE input box is appended (type directly, no popup).
        - "color"         → a 🎨 button opens the colour picker.
        Selecting a preset clears the custom selection and vice-versa.
    """
    changed = Signal(str)

    def __init__(self, values: list, default: str = "", parent=None, custom=None):
        super().__init__(parent)
        self._values: list[str] = [str(v) for v in values]
        self._custom = custom
        self._btns: dict[str, QPushButton] = {}
        self._input: QLineEdit | None = None
        self._color_btn: QPushButton | None = None
        default = str(default) if default is not None else ""
        self._current = default if default in self._values else (
            default if (default and custom) else
            (self._values[0] if self._values else ""))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        n = len(self._values) + (1 if custom else 0)
        for i, v in enumerate(self._values):
            btn = QPushButton(str(v))
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btn.setStyleSheet(self._seg_style(i, n))
            btn.setChecked(v == self._current)
            btn.clicked.connect(lambda _, val=v: self._on_click(val))
            self._btns[v] = btn
            lay.addWidget(btn)

        if custom == "color":
            self._color_btn = QPushButton("🎨")
            self._color_btn.setFixedHeight(24)
            self._color_btn.setToolTip("Pick a custom colour")
            self._color_btn.setCursor(Qt.PointingHandCursor)
            self._color_btn.setStyleSheet(self._seg_style(n - 1, n))
            self._color_btn.clicked.connect(self._pick_color)
            lay.addWidget(self._color_btn)
            if self._current.startswith("#"):
                self._color_btn.setStyleSheet(
                    f"QPushButton {{ background:{self._current}; border:1px solid #c0cdd8;"
                    " border-radius:0 4px 4px 0; }}")
        elif custom in ("number", "text"):
            self._input = QLineEdit()
            self._input.setFixedHeight(24)
            self._input.setFixedWidth(60)
            self._input.setPlaceholderText("custom")
            self._input.setStyleSheet(
                "QLineEdit { border:1px solid #c0cdd8; border-left:none;"
                "  border-radius:0 4px 4px 0; padding:1px 6px; background:white; color:#1e2d3d; }"
                "QLineEdit:focus { border-color:#1a6fa8; }")
            if self._current and self._current not in self._btns:
                self._input.setText(self._current)
            self._input.editingFinished.connect(self._on_input)
            self._input.returnPressed.connect(self._on_input)
            lay.addWidget(self._input)

    # ── internal ──────────────────────────────────────────────────────────────
    def _seg_style(self, i: int, n: int) -> str:
        r = "4px"
        if n == 1:
            corners = f"border-radius:{r};"
        elif i == 0:
            corners = f"border-radius:{r} 0 0 {r}; border-right:none;"
        elif i == n - 1:
            corners = f"border-radius:0 {r} {r} 0;"
        else:
            corners = "border-radius:0; border-right:none;"
        return (
            f"QPushButton {{ {corners} border:1px solid #c0cdd8; background:#e8eef5;"
            f" color:#3a5068; padding:2px 8px; }}"
            f"QPushButton:checked {{ background:{DHIS2_BLUE}; color:white; border-color:{DHIS2_BLUE}; }}"
            f"QPushButton:hover:!checked {{ background:#d0dde8; }}"
        )

    def _on_input(self):
        v = self._input.text().strip()
        if not v or v == self._current:
            return
        self._current = v
        for b in self._btns.values():
            b.setChecked(False)
        self.changed.emit(v)

    def _pick_color(self):
        col = QColorDialog.getColor()
        if not col.isValid():
            return
        v = col.name()
        self._current = v
        for b in self._btns.values():
            b.setChecked(False)
        self._color_btn.setStyleSheet(
            f"QPushButton {{ background:{v}; border:1px solid #c0cdd8; border-radius:0 4px 4px 0; }}")
        self.changed.emit(v)

    def _on_click(self, value: str):
        if value == self._current:
            self._btns[value].setChecked(True)
            return
        self._current = value
        for v, btn in self._btns.items():
            btn.setChecked(v == value)
        if self._input:
            self._input.clear()        # a preset overrides any custom value
        self.changed.emit(value)

    def get(self) -> str:
        return self._current

    def set(self, value: str):
        value = str(value)
        if value == self._current:
            return
        self._current = value
        if value in self._btns:
            for v, btn in self._btns.items():
                btn.setChecked(v == value)
            if self._input:
                self._input.clear()
        elif self._custom:
            for btn in self._btns.values():
                btn.setChecked(False)
            if self._input:
                self._input.setText(value)
            elif self._color_btn and value.startswith("#"):
                self._color_btn.setStyleSheet(
                    f"QPushButton {{ background:{value}; border:1px solid #c0cdd8;"
                    " border-radius:0 4px 4px 0; }}")

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        for btn in self._btns.values():
            btn.setEnabled(enabled)
        if self._input:
            self._input.setEnabled(enabled)
        if self._color_btn:
            self._color_btn.setEnabled(enabled)


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


# ─────────────────────────────────────────────────────────────────────────────
# Drag-to-reorder support for the selected-metric chips
# ─────────────────────────────────────────────────────────────────────────────

class _DragGrip(QLabel):
    """A small grip handle that starts a drag carrying its chip's uid."""
    def __init__(self, uid: str):
        super().__init__("⠿")
        self._uid = uid
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Drag to reorder")
        self.setStyleSheet("color:#7d96ad; background:transparent; font-size:13px; padding:0 2px;")

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            md = QMimeData()
            md.setText(self._uid)
            drag = QDrag(self)
            drag.setMimeData(md)
            drag.exec(Qt.MoveAction)


class _ChipHost(QWidget):
    """Container for the metric chips; accepts drops to reorder them."""
    def __init__(self, on_reorder):
        super().__init__()
        self._on_reorder = on_reorder
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        if not e.mimeData().hasText():
            return
        pos = e.position().toPoint() if hasattr(e, "position") else e.pos()
        y = pos.y()
        lay = self.layout()
        target = lay.count()
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if w is None:
                continue
            if y < w.y() + w.height() / 2:
                target = i
                break
        self._on_reorder(e.mimeData().text(), target)
        e.acceptProposedAction()


# ─────────────────────────────────────────────────────────────────────────────
# DEPickerWidget — Superset-style compact DE selector
# ─────────────────────────────────────────────────────────────────────────────

class _ClickRow(QLabel):
    """A clickable, rich-text list row (so the ``(DE)`` prefix can be colour-coded).
    Replaces a flat QPushButton, which cannot render HTML."""
    clicked = Signal()

    def __init__(self, html: str, enabled: bool = True, parent=None):
        super().__init__(html, parent)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setFixedHeight(22)
        self._enabled = enabled
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled
                       else Qt.CursorShape.ArrowCursor)
        self.setStyleSheet(
            "QLabel { background:transparent; font-size:10px; padding:1px 6px; border-radius:3px; }"
            + ("QLabel:hover { background:#dbeafe; }" if enabled else "QLabel { color:#b0b8c4; }"))

    def mousePressEvent(self, e):
        if self._enabled and e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        else:
            super().mousePressEvent(e)


class DEPickerWidget(QWidget):
    """
    Compact data-element selector (metrics or dimension).

    Layout:
      ┌ selected chips (icon + name + [agg] + ×) ──────────────────┐
      │ ─────────────────── separator ─────────────────────────── │
      │ 🔍 Search...                                              │
      │ ┌ available list (scrollable buttons) ─────────────────┐ │
      │ │  ◈  PF Cases                                         │ │
      │ │  ⊞  Temperature                                      │ │
      │ └──────────────────────────────────────────────────────┘ │
      └───────────────────────────────────────────────────────────┘

    Parameters
    ----------
    max_count : int
        1 = single-select (adding replaces existing); >1 = multi.
    show_agg : bool
        Show SUM/COUNT/AVG/MIN/MAX dropdown inside each chip.
    avail_height : int
        Fixed height of the scrollable available-items area.
    """

    changed = Signal()

    _AGG_ITEMS  = ["SUM", "COUNT", "AVG", "MIN", "MAX"]
    _AGG_TYPES  = {"tracker_numeric", "aggregate", "indicator"}
    _MAX_RENDER = 200   # cap available-list buttons (thousands of items would freeze the UI)

    def __init__(self, max_count: int = 3, show_agg: bool = True,
                 avail_height: int = 90, show_alias: bool = True, parent=None):
        super().__init__(parent)
        self._max_count    = max_count
        self._show_agg     = show_agg
        self._show_alias   = show_alias
        self._avail_height = avail_height
        self._all_items:  list[dict] = []
        self._selected:   list[dict] = []   # dicts, may have extra key 'agg'
        self._build_ui()

    # ── construction ─────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        # Selected chips area (drag-to-reorder)
        self._chips_w = _ChipHost(self._reorder_to)
        self._chips_w.setStyleSheet("background:transparent;")
        self._chips_lay = QVBoxLayout(self._chips_w)
        # Right margin so the agg dropdown + × button don't run under the panel scrollbar.
        self._chips_lay.setContentsMargins(0, 0, 10, 0)
        self._chips_lay.setSpacing(2)
        outer.addWidget(self._chips_w)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#d0dde8; border:none;")
        outer.addWidget(sep)

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 Search…")
        self._search.setFixedHeight(24)
        self._search.textChanged.connect(self._refresh_available)
        outer.addWidget(self._search)
        self._search_default_ph = "🔍 Search…"

        # Available list
        self._avail_scroll = QScrollArea()
        self._avail_scroll.setWidgetResizable(True)
        self._avail_scroll.setFrameShape(QFrame.NoFrame)
        self._avail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._avail_scroll.setFixedHeight(self._avail_height)
        self._avail_scroll.setStyleSheet("background:white;")

        self._avail_w = QWidget()
        self._avail_w.setStyleSheet("background:white;")
        self._avail_lay = QVBoxLayout(self._avail_w)
        self._avail_lay.setContentsMargins(2, 2, 2, 2)
        self._avail_lay.setSpacing(0)
        self._avail_scroll.setWidget(self._avail_w)
        outer.addWidget(self._avail_scroll)

    # ── public API ────────────────────────────────────────────────────────────

    def set_items(self, items: list[dict]):
        """
        Replace the full available list.
        Preserves selected items that still exist in the new list.
        """
        avail_uids = {d["uid"] for d in items}
        self._all_items = list(items)
        # Drop selected items that are no longer available
        self._selected = [s for s in self._selected if s["uid"] in avail_uids]
        self._rebuild()

    def set_selected_uids(self, uids: list[str],
                          agg_map: dict[str, str] | None = None,
                          alias_map: dict[str, str] | None = None,
                          known: dict[str, dict] | None = None):
        """Restore a saved selection (e.g. on chart load), incl. per-metric alias.

        `known` maps uid → the saved metric dict; used as a fallback so a selection can be
        restored even when the item is not (yet) in the available list — e.g. indicators
        that load on demand after the chart is opened.
        """
        uid_map = {d["uid"]: d for d in self._all_items}
        for uid, d in (known or {}).items():
            uid_map.setdefault(uid, d)
        agg_map = agg_map or {}
        alias_map = alias_map or {}
        self._selected = []
        for uid in uids:
            if uid in uid_map:
                entry = dict(uid_map[uid])
                entry["agg"] = agg_map.get(uid, entry.get("agg", "SUM"))
                if alias_map.get(uid):
                    entry["alias"] = alias_map[uid]
                self._selected.append(entry)
        self._rebuild()

    def set_max_count(self, n: int):
        self._max_count = n
        if len(self._selected) > n:
            self._selected = self._selected[:n]
        self._rebuild()

    def set_show_agg(self, show: bool):
        """Show/hide the per-metric aggregation dropdown (e.g. hidden for raw tables)."""
        if self._show_agg != show:
            self._show_agg = show
            self._rebuild_chips()

    def set_show_alias(self, show: bool):
        """Show/hide the per-item alias input (e.g. enabled for dimension picker)."""
        if self._show_alias != show:
            self._show_alias = show
            self._rebuild_chips()

    def get_selected_des(self) -> list[dict]:
        """Return selected DE dicts (each has 'uid', 'name', 'type', 'agg', ...)."""
        return list(self._selected)

    def get_first_de(self) -> dict | None:
        return self._selected[0] if self._selected else None

    def clear_selection(self):
        self._selected = []
        self._rebuild()

    # ── internals ────────────────────────────────────────────────────────────

    def _rebuild(self):
        self._rebuild_chips()
        self._refresh_available()

    def _rebuild_chips(self):
        while self._chips_lay.count():
            item = self._chips_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        _RH = 28                                   # uniform chip + control height
        reorderable = len(self._selected) > 1
        for sel in self._selected:
            chip = QFrame()
            chip.setObjectName("deChip")
            chip.setFixedHeight(_RH)
            chip.setStyleSheet(
                "QFrame#deChip { background:#dbeafe; border:1px solid #93c5fd; "
                "border-radius:4px; }"
            )
            chip_lay = QHBoxLayout(chip)
            chip_lay.setContentsMargins(6, 0, 4, 0)
            chip_lay.setSpacing(4)

            # Drag handle (only meaningful when there's more than one metric).
            if reorderable:
                chip_lay.addWidget(_DragGrip(sel["uid"]))

            from ui.metadata_display import html_label
            lbl = QLabel(html_label(sel, name_color="#1e3a5f"))   # (DE) coloured prefix
            lbl.setStyleSheet("font-size:10px; background:transparent; color:#1e3a5f;")
            lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            lbl.setMinimumWidth(0)          # let a long name clip instead of pushing the
            lbl.setToolTip(sel["name"])     # agg dropdown / × button out of the row
            chip_lay.addWidget(lbl, stretch=1)

            if self._show_alias:
                alias_in = QLineEdit(sel.get("alias", ""))
                alias_in.setPlaceholderText("alias")
                alias_in.setFixedHeight(22)
                alias_in.setFixedWidth(92)
                alias_in.setToolTip("Display name (alias) — shown instead of the original")
                alias_in.setStyleSheet(
                    "QLineEdit { border:1px solid #c0cdd8; border-radius:4px; padding:1px 6px;"
                    "  background:white; color:#1e2d3d; font-size:9px; }"
                    "QLineEdit:focus { border-color:#1a6fa8; }"
                )
                alias_in.textChanged.connect(lambda t, d=sel: self._on_alias_change(d, t))
                chip_lay.addWidget(alias_in)

            if self._show_agg and sel.get("type") in self._AGG_TYPES:
                agg_cb = QComboBox()
                agg_cb.addItems(self._AGG_ITEMS)
                agg_cb.setCurrentText(sel.get("agg", "SUM"))
                agg_cb.setFixedWidth(60)
                agg_cb.setFixedHeight(22)
                agg_cb.setStyleSheet(_AGG_COMBO_QSS)
                agg_cb.view().setStyleSheet(          # popup is a top-level window
                    "background:#ffffff; color:#1e2d3d;")
                agg_cb.currentTextChanged.connect(
                    lambda v, d=sel: self._on_agg_change(d, v)
                )
                chip_lay.addWidget(agg_cb)

            rm = QPushButton("×")
            rm.setFixedSize(22, 22)
            rm.setStyleSheet(
                "QPushButton { background:transparent; border:none; color:#6b8299; "
                "font-size:14px; font-weight:bold; padding:0; }"
                "QPushButton:hover { color:#c0392b; }"
            )
            rm.clicked.connect(lambda _, d=sel: self._remove(d))
            chip_lay.addWidget(rm)

            self._chips_lay.addWidget(chip)

        if not self._selected:
            hint = QLabel("Nothing selected")
            hint.setStyleSheet("font-size:9px; color:#aaaaaa; padding:2px 0;")
            self._chips_lay.addWidget(hint)

    def set_placeholder(self, text: str | None = None):
        """Set the search-box placeholder (used for transient status like 'Loading…').
        Pass None to restore the default."""
        self._search.setPlaceholderText(text or self._search_default_ph)

    def _refresh_available(self):
        while self._avail_lay.count():
            item = self._avail_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        q        = self._search.text().strip().lower()
        sel_uids = {s["uid"] for s in self._selected}
        can_add  = len(self._selected) < self._max_count

        available = [
            d for d in self._all_items
            if d["uid"] not in sel_uids
            and (not q or q in d["name"].lower())
        ]

        # Cap rendered rows — instances can have thousands of indicators/DEs; building a
        # button per item froze the picker (looked like "nothing loaded"). Show the first
        # _MAX_RENDER and prompt the user to type to narrow.
        from ui.metadata_display import html_label
        shown = available[: self._MAX_RENDER]
        for de in shown:
            row = _ClickRow(html_label(de), enabled=can_add)   # (DE) coloured prefix
            row.clicked.connect(lambda d=de: self._add(d))
            self._avail_lay.addWidget(row)

        if not available:
            msg = "All selected" if not q and not can_add else \
                  "No match" if q else "No items"
            lbl = QLabel(msg)
            lbl.setStyleSheet("color:#aaaaaa; font-size:9px; padding:4px;")
            lbl.setAlignment(Qt.AlignCenter)
            self._avail_lay.addWidget(lbl)
        elif len(available) > self._MAX_RENDER:
            lbl = QLabel(f"Showing {self._MAX_RENDER} of {len(available)} — type to search…")
            lbl.setStyleSheet("color:#7a93a8; font-size:9px; padding:4px;")
            lbl.setAlignment(Qt.AlignCenter)
            self._avail_lay.addWidget(lbl)

        self._avail_lay.addStretch()

    def _add(self, de: dict):
        if self._max_count == 1:
            self._selected = [dict(**de, agg="SUM")]
        elif len(self._selected) < self._max_count:
            self._selected.append(dict(**de, agg="SUM"))
        self._rebuild()
        self.changed.emit()

    def _remove(self, de: dict):
        self._selected = [s for s in self._selected if s["uid"] != de["uid"]]
        self._rebuild()
        self.changed.emit()

    def _on_agg_change(self, de: dict, val: str):
        for s in self._selected:
            if s["uid"] == de["uid"]:
                s["agg"] = val
                break
        self.changed.emit()

    def _on_alias_change(self, de: dict, val: str):
        # Update in place (no rebuild → keep typing focus); display layers read 'alias'.
        for s in self._selected:
            if s["uid"] == de["uid"]:
                s["alias"] = val.strip()
                break
        self.changed.emit()

    def _reorder_to(self, uid: str, target_idx: int):
        """Move the selected metric `uid` to position `target_idx` (drag-and-drop)."""
        cur = next((i for i, s in enumerate(self._selected) if s["uid"] == uid), -1)
        if cur < 0:
            return
        item = self._selected.pop(cur)
        if cur < target_idx:           # account for the removed slot before the target
            target_idx -= 1
        target_idx = max(0, min(target_idx, len(self._selected)))
        if target_idx == cur:          # dropped onto itself — nothing to do
            self._selected.insert(cur, item)
            return
        self._selected.insert(target_idx, item)
        self._rebuild()
        self.changed.emit()
