"""
ChartEditorPanel — PySide6 replacement (formerly CTk/Tkinter).

Layout:
  ┌──────────────────────────────────────────────────────────────────┐
  │  Header bar: "Chart Editor"  +  "📚 My Charts" toggle           │
  │  My Charts panel (collapsible horizontal scroll)                 │
  │  ─────────────────────────────────────────────────────────────   │
  │  QSplitter (horizontal)                                          │
  │    Left scroll:                                                  │
  │      1. Chart Type (4-col grid)                                  │
  │      2. Source (program/dataset checkboxes + dropdowns)          │
  │      3. Metrics (searchable DE list with checkboxes + agg)       │
  │         Dimensions (SelectControls + time grain + dim + filters) │
  │    Right scroll:                                                  │
  │      4. Style & Options (color + title + width + mode + opts)    │
  │         AI Customize (collapsible)                               │
  │  ─────────────────────────────────────────────────────────────   │
  │  Actions bar: [💾 Save] [+ Add to Dashboard] [🌐 Preview]       │
  └──────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QCheckBox, QRadioButton,
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QScrollArea, QSplitter,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy,
    QInputDialog, QMessageBox, QButtonGroup, QCompleter, QDialog, QColorDialog,
    QFileDialog,
)

from charts.fixed_templates import FIXED_TEMPLATES
from charts.plugins.base import SelectControl, CheckboxGroupControl, TextAreaControl
from ui.qt_utils import (SegmentedButton, DEPickerWidget, section_label, divider,
                         DHIS2_BLUE, PANEL_BG, BORDER_CLR)

# A combobox popup is a TOP-LEVEL window, so a QSS rule on an ancestor (the panel)
# does NOT reach it. The popup's view is only styled reliably when the rule is set
# on the combobox itself. Apply this per-combobox (see _style_combo).
_COMBO_QSS = (
    "QComboBox { background:#ffffff; color:#1e2d3d; border:1px solid #c0cdd8;"
    "  border-radius:4px; padding:1px 8px; }"
    "QComboBox:focus { border-color:#1a6fa8; }"
    "QComboBox::drop-down { border:none; width:18px; }"
    "QComboBox QAbstractItemView { background:#ffffff; color:#1e2d3d;"
    "  border:1px solid #c0cdd8; padding:2px;"
    "  selection-background-color:#1a6fa8; selection-color:#ffffff; outline:0; }"
)


def _style_combo(combo) -> None:
    """Force a light, readable popup on a QComboBox (overrides OS dark popups)."""
    combo.setStyleSheet(_COMBO_QSS)
    try:                      # also style the view object directly (belt & braces)
        combo.view().setStyleSheet(
            "background:#ffffff; color:#1e2d3d; selection-background-color:#1a6fa8;"
            " selection-color:#ffffff;")
    except Exception:
        pass


class _MultiToggleWidget(QWidget):
    """Row of toggle buttons — multiple can be active simultaneously."""
    changed = Signal()

    def __init__(self, choices: list[str], parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        self._btns: dict[str, QPushButton] = {}
        for ch in choices:
            btn = QPushButton(ch)
            btn.setCheckable(True)
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                "QPushButton{font-size:9px;padding:2px 6px;border:1px solid #1a6fa8;"
                "border-radius:3px;background:#fff;color:#1a6fa8;}"
                "QPushButton:checked{background:#1a6fa8;color:#fff;}"
            )
            btn.clicked.connect(self.changed)
            self._btns[ch] = btn
            lay.addWidget(btn)
        lay.addStretch()

    def get(self) -> str:
        return ",".join(ch for ch, btn in self._btns.items() if btn.isChecked())

    def set(self, value: str) -> None:
        selected = {v.strip() for v in str(value).split(",") if v.strip()}
        for ch, btn in self._btns.items():
            btn.setChecked(ch in selected)

# ── Constants ─────────────────────────────────────────────────────────────────

COLOR_PRESETS = [
    ("#3498db", "Blue"),
    ("#e74c3c", "Red"),
    ("#27ae60", "Green"),
    ("#8e44ad", "Purple"),
    ("#e67e22", "Orange"),
    ("#1abc9c", "Teal"),
    ("#1a6fa8", "DHIS2"),
    ("#f39c12", "Yellow"),
]

COL_WIDTH_OPTIONS = {
    "Full  (12)": 12,
    "Half  (6)":   6,
    "Third (4)":   4,
}

CHART_STYLE_CONFIGS: dict[str, list[dict]] = {
    # ── Unified bar plugin ──────────────────────────────────────────────────────
    "bar": [
        {"id": "show_values",   "label": "Show value labels",    "type": "check",   "default": False},
        {"id": "show_legend",   "label": "Show legend",          "type": "check",   "default": True},
        {"id": "only_total",    "label": "Stack total only",     "type": "check",   "default": True},
        {"id": "rich_tooltip",  "label": "Rich tooltip",         "type": "check",   "default": True},
        {"id": "tooltip_total", "label": "Tooltip show total",   "type": "check",   "default": True},
        {"id": "log_scale",     "label": "Log scale Y",          "type": "check",   "default": False},
        {"id": "legend_pos",    "label": "Legend position",      "type": "segment", "values": ["Bottom","Top","Left","Right"], "default": "Bottom"},
        {"id": "x_rotation",    "label": "X label rotation",     "type": "segment", "values": ["0","45","90"], "default": "45"},
        {"id": "x_interval",    "label": "X label interval",     "type": "segment", "values": ["Auto","All"], "default": "Auto"},
        {"id": "y_format",      "label": "Y format",             "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
        {"id": "bar_width",     "label": "Bar width",            "type": "segment", "values": ["Auto","Thin","Normal","Wide"], "default": "Auto"},
        {"id": "x_title",       "label": "X axis title",         "type": "entry",   "default": ""},
        {"id": "y_title",       "label": "Y axis title",         "type": "entry",   "default": ""},
    ],
    # ── Legacy plugins ──────────────────────────────────────────────────────────
    "ft_bar_monthly": [
        {"id": "show_values",  "label": "Show values on bars",  "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "stack",        "label": "Stacked bars",         "type": "check",   "default": False},
        {"id": "bar_width",    "label": "Bar width",            "type": "segment", "values": ["Thin","Normal","Wide"], "default": "Normal"},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
        {"id": "y_label",      "label": "Y axis label",         "type": "entry",   "default": ""},
    ],
    "ft_line_trend": [
        {"id": "show_values",  "label": "Show values",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "smooth",       "label": "Smooth line",          "type": "check",   "default": True},
        {"id": "fill_area",    "label": "Fill area under line", "type": "check",   "default": False},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
        {"id": "y_label",      "label": "Y axis label",         "type": "entry",   "default": ""},
    ],
    "ft_stacked_cat": [
        {"id": "show_values",  "label": "Show values",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
    ],
    "ft_pie_cat": [
        {"id": "show_values",  "label": "Show values on slices","type": "check",   "default": False},
        {"id": "donut",        "label": "Donut style",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
    ],
    "ft_bar_ou": [
        {"id": "show_values",  "label": "Show values",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "bar_width",    "label": "Bar width",            "type": "segment", "values": ["Thin","Normal","Wide"], "default": "Normal"},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
    ],
    "ft_scorecard": [
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
    ],
    "ft_line_multi": [
        {"id": "show_values",  "label": "Show values",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "smooth",       "label": "Smooth lines",         "type": "check",   "default": True},
        {"id": "fill_area",    "label": "Fill area",            "type": "check",   "default": False},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
        {"id": "y_label",      "label": "Y axis label",         "type": "entry",   "default": ""},
    ],
    "ft_grouped_bar": [
        {"id": "show_values",  "label": "Show values",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "bar_width",    "label": "Bar width",            "type": "segment", "values": ["Thin","Normal","Wide"], "default": "Normal"},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
    ],
    "ft_combined_bar_line": [
        {"id": "show_values",  "label": "Show values",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
    ],
}


def _option_to_chartjs(opt_id: str, value) -> dict:
    from llm.chart_customizer import deep_merge
    if opt_id == "show_values" and value:
        return {"plugins": {"showValues": {"display": True, "color": "#333", "fontSize": 11}}}
    if opt_id == "hide_legend" and value:
        return {"plugins": {"legend": {"display": False}}}
    if opt_id == "stack" and value:
        return {"scales": {"x": {"stacked": True}, "y": {"stacked": True}}}
    if opt_id == "bar_width":
        w = {"Thin": 14, "Normal": 26, "Wide": 40}.get(value, 26)
        return {"datasets": [{"barThickness": w, "maxBarThickness": w + 8}]}
    if opt_id == "smooth":
        return {"datasets": [{"tension": 0.4 if value else 0}]}
    if opt_id == "fill_area":
        return {"datasets": [{"fill": bool(value)}]}
    if opt_id == "donut" and value:
        return {"cutout": "50%"}
    if opt_id == "y_label" and value:
        return {"scales": {"y": {"title": {"display": True, "text": value}}}}
    if opt_id == "num_format" and value != "Default":
        return {"numFormat": value}
    return {}


# ── Helper: create a scroll area with a VBox inner widget ──────────────────────

def _make_vscroll(parent=None) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    sa = QScrollArea(parent)
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    inner = QWidget()
    inner.setStyleSheet(f"background:{PANEL_BG};")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    sa.setWidget(inner)
    return sa, inner, lay


def _make_card(parent=None) -> QFrame:
    """White rounded card with border."""
    f = QFrame(parent)
    f.setStyleSheet(
        f"QFrame {{ background:white; border:1px solid {BORDER_CLR}; border-radius:8px; }}"
    )
    return f


# ── ColorSwatch widget ─────────────────────────────────────────────────────────

class _ColorSwatch(QFrame):
    clicked = Signal(str)

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(20, 20)
        self.setCursor(Qt.PointingHandCursor)
        self._set_selected(False)

    def _set_selected(self, selected: bool):
        self._selected = selected
        border = "white" if selected else self._color
        width = 3 if selected else 1
        self.setStyleSheet(
            f"QFrame {{ background:{self._color}; border:{width}px solid {border}; border-radius:2px; }}"
        )

    def mousePressEvent(self, event):
        self.clicked.emit(self._color)


# ── ChartTile widget ───────────────────────────────────────────────────────────

class _ChartTile(QFrame):
    clicked = Signal(dict)

    def __init__(self, tmpl: dict, parent=None):
        super().__init__(parent)
        self._tmpl = tmpl
        self.setFixedSize(90, 60)
        self.setCursor(Qt.PointingHandCursor)
        self._selected = False
        self._hovered = False
        self._update_style()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(1)

        # Mini preview area (colored background)
        preview = QFrame()
        preview.setFixedHeight(32)
        preview.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        preview.setStyleSheet("background:#e8f0f8; border-radius:3px; border:none;")
        lay.addWidget(preview)

        lbl = QLabel(f"{tmpl['icon']} {tmpl['label'][:13]}")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lbl.setStyleSheet("font-size:8px; color:#3a5068; background:transparent; border:none;")
        lay.addWidget(lbl)

    def _update_style(self):
        if self._selected:
            self.setStyleSheet(
                f"QFrame {{ background:#e8f0f8; border:2px solid {DHIS2_BLUE}; border-radius:4px; }}"
            )
        elif self._hovered:
            self.setStyleSheet(
                f"QFrame {{ background:#e8f0f8; border:1px solid {BORDER_CLR}; border-radius:4px; }}"
            )
        else:
            self.setStyleSheet(
                f"QFrame {{ background:white; border:1px solid {BORDER_CLR}; border-radius:4px; }}"
            )

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def enterEvent(self, event):
        self._hovered = True
        self._update_style()

    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()

    def mousePressEvent(self, event):
        self.clicked.emit(self._tmpl)


# ── Main panel ────────────────────────────────────────────────────────────────

def _short_model_name(model_id: str) -> str:
    """Friendly short name for the button label (e.g. 'claude-opus-4-8' → 'Opus')."""
    m = (model_id or "").lower()
    if "opus" in m:
        return "Opus"
    if "sonnet" in m:
        return "Sonnet"
    if "haiku" in m:
        return "Haiku"
    return "AI"


class ChartEditorPanel(QWidget):

    # Marshal a callable from a worker thread back onto the GUI thread. (QTimer.singleShot
    # does NOT cross threads — a plain threading.Thread has no Qt event loop — so worker
    # results must come home via a queued signal.)
    _call_main = Signal(object)

    _FILTER_OPS = ["EQ", "≠ (NE)", "IN", ">", "≥", "<", "≤", "LIKE"]
    _OP_MAP = {
        "EQ": "EQ", "≠ (NE)": "NE", "IN": "IN",
        ">": "GT", "≥": "GE", "<": "LT", "≤": "LE", "LIKE": "LIKE",
    }

    def __init__(self, parent=None, callbacks: dict[str, Callable] | None = None, **kw):
        super().__init__(parent)
        self._callbacks = callbacks or {}
        # Run worker-thread callbacks on the GUI thread (queued across threads).
        self._call_main.connect(lambda fn: fn())

        # ── State ─────────────────────────────────────────────────────────────
        self._custom_options: dict = {}
        self._chat_history: list[tuple[str, str]] = []
        self._metadata: dict = {}
        self._programs: list[dict] = []
        self._agg_des: list[dict] = []
        self._agg_indicators: list[dict] = []   # aggregate indicators (loaded on demand)
        self._indicators_loaded = False
        self._indicators_loading = False
        self._dhis2_client = None   # set by app_window after connect
        self._in_use: set[str] = set()   # curated in-use UIDs (Metadata Library); empty = none offered
        self._current_de_items: list[dict] = []
        self._selected_metrics: list[dict] = []
        self._selected_template: dict | None = None
        self._selected_plugin = None
        self._max_des = 1
        self._min_des = 1
        self._selected_color: str = COLOR_PRESETS[0][0]
        self._color_swatches: list[_ColorSwatch] = []
        self._chart_tiles: dict[str, _ChartTile] = {}
        self._quick_options: dict = {}
        self._chart_options: dict = {}
        self._option_vars: dict = {}         # opt_id -> QCheckBox | SegmentedButton | QLineEdit
        self._ai_chat_visible = False
        self._my_charts_visible = False
        self._current_prog = None
        self._chat_display_text = ""
        # Identity of the chart currently being edited (None = a new, unsaved chart).
        self._current_chart_id: str | None = None
        self._current_chart_name: str | None = None
        self._current_chart_description: str = ""

        # Dimension state
        self._select_vars: dict[str, SegmentedButton] = {}
        self._textarea_vars: dict = {}   # opt_id -> QPlainTextEdit (e.g. Custom HTML template)
        self._html_highlighter = None    # syntax highlighter for the Custom HTML editor
        self._filter_rows: list[dict] = []

        # Preview timer
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._do_refresh)

        self._build()

    # =========================================================================
    # Build
    # =========================================================================

    def _build(self):
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        # Panel-local combobox/list styling — the global APP_QSS popup rule does not
        # reliably reach comboboxes nested under widgets that set their own background,
        # so the dropdown popup rendered dark/unreadable. Force a light, readable popup.
        self.setStyleSheet(
            f"background:{PANEL_BG};"
            "QComboBox { background:#ffffff; color:#1e2d3d; border:1px solid #c0cdd8;"
            "  border-radius:4px; padding:2px 8px; }"
            "QComboBox:focus { border-color:#1a6fa8; }"
            "QComboBox::drop-down { border:none; width:18px; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#1e2d3d;"
            "  border:1px solid #c0cdd8; selection-background-color:#1a6fa8;"
            "  selection-color:#ffffff; outline:none; }"
            "QLineEdit { background:#ffffff; color:#1e2d3d; border:1px solid #c0cdd8;"
            "  border-radius:4px; padding:2px 6px; }"
            "QLineEdit:focus { border-color:#1a6fa8; }"
        )

        # 1. Header bar
        root_lay.addWidget(self._build_header())

        # 2. My Charts panel (initially hidden)
        self._my_charts_panel = self._build_my_charts_panel()
        self._my_charts_panel.setVisible(False)
        root_lay.addWidget(self._my_charts_panel)

        # 3. Main content splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #d0dde8; }")

        # Left pane: data
        left_scroll, left_inner, left_lay = _make_vscroll()
        left_inner.setStyleSheet(f"background:{PANEL_BG};")
        left_scroll.setMinimumWidth(280)

        self._build_chart_type_section(left_lay)
        left_lay.addWidget(self._make_hdiv())
        self._build_source_section(left_lay)
        self._build_metrics_section(left_lay)
        self._build_dimensions_section(left_lay)
        left_lay.addStretch()

        # Right pane: style
        right_scroll, right_inner, right_lay = _make_vscroll()
        right_inner.setStyleSheet(f"background:{PANEL_BG};")
        right_scroll.setMinimumWidth(260)

        self._build_style_section(right_lay)
        right_lay.addStretch()

        splitter.addWidget(left_scroll)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root_lay.addWidget(splitter, stretch=1)

        # 4. Actions bar
        root_lay.addWidget(self._build_actions())

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> QWidget:
        hdr = QFrame()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet("background:#e8eef5; border:none;")
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(12, 0, 8, 0)

        title = QLabel("Chart Editor")
        title.setStyleSheet("font-size:12px; font-weight:bold; color:#3a5068; background:transparent;")
        lay.addWidget(title)

        # Shows which saved chart is being edited (or "new chart").
        self._chart_name_lbl = QLabel("• new chart")
        self._chart_name_lbl.setStyleSheet(
            "font-size:11px; color:#5a7a9a; background:transparent; font-style:italic;")
        lay.addWidget(self._chart_name_lbl)
        lay.addStretch()

        self._my_charts_btn = QPushButton("📚 My Charts ▶")
        self._my_charts_btn.setFixedHeight(24)
        self._my_charts_btn.setStyleSheet(
            "QPushButton { background:transparent; border:none; color:#5a7a9a; "
            "font-size:10px; padding:2px 6px; border-radius:4px; }"
            "QPushButton:hover { background:#d0dde8; }"
        )
        self._my_charts_btn.clicked.connect(self._toggle_my_charts)
        lay.addWidget(self._my_charts_btn)
        return hdr

    # ── My Charts panel ───────────────────────────────────────────────────────

    def _build_my_charts_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background:#f0f4f8; border-bottom:1px solid {BORDER_CLR}; }}"
        )
        panel.setFixedHeight(90)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(4, 4, 4, 4)

        # Horizontal scroll area for cards
        self._mc_scroll = QScrollArea()
        self._mc_scroll.setWidgetResizable(True)
        self._mc_scroll.setFrameShape(QFrame.NoFrame)
        self._mc_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._mc_scroll.setFixedHeight(78)

        self._mc_inner = QWidget()
        self._mc_inner.setStyleSheet("background:transparent;")
        self._mc_hlay = QHBoxLayout(self._mc_inner)
        self._mc_hlay.setContentsMargins(0, 0, 0, 0)
        self._mc_hlay.setSpacing(4)

        self._mc_empty_lbl = QLabel("No saved charts yet.")
        self._mc_empty_lbl.setStyleSheet("color:#8aa3b8; font-size:10px;")
        self._mc_hlay.addWidget(self._mc_empty_lbl)
        self._mc_hlay.addStretch()

        self._mc_scroll.setWidget(self._mc_inner)
        lay.addWidget(self._mc_scroll)
        return panel

    def _toggle_my_charts(self):
        self._my_charts_visible = not self._my_charts_visible
        self._my_charts_panel.setVisible(self._my_charts_visible)
        if self._my_charts_visible:
            self._my_charts_btn.setText("📚 My Charts ▼")
            self._refresh_my_charts()
        else:
            self._my_charts_btn.setText("📚 My Charts ▶")

    def _refresh_my_charts(self):
        from config.chart_library import load_charts
        # Clear existing widgets
        while self._mc_hlay.count():
            item = self._mc_hlay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        charts = load_charts()
        if not charts:
            lbl = QLabel("No saved charts yet.")
            lbl.setStyleSheet("color:#8aa3b8; font-size:10px;")
            self._mc_hlay.addWidget(lbl)
            self._mc_hlay.addStretch()
            return

        for chart in charts:
            self._build_my_chart_card(chart)
        self._mc_hlay.addStretch()

    def _build_my_chart_card(self, chart: dict):
        card = QFrame()
        card.setFixedSize(130, 72)
        card.setStyleSheet(
            f"QFrame {{ background:white; border:1px solid {BORDER_CLR}; border-radius:6px; }}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(6, 5, 6, 5)
        lay.setSpacing(2)

        _tid = chart.get("template_id") or chart.get("plugin_id")   # template id == plugin id
        tmpl_icon = next((t["icon"] for t in FIXED_TEMPLATES if t["id"] == _tid), "📊")
        name = (chart.get("name") or chart.get("title", "?"))[:16]

        name_lbl = QLabel(f"{tmpl_icon} {name}")
        name_lbl.setStyleSheet(
            "font-size:10px; font-weight:bold; color:#1e2d3d; background:transparent; border:none;"
        )
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl)

        sub_lbl = QLabel(chart.get("template_label", "")[:20])
        sub_lbl.setStyleSheet("font-size:9px; color:#8aa3b8; background:transparent; border:none;")
        lay.addWidget(sub_lbl)

        load_btn = QPushButton("Load ↩")
        load_btn.setFixedHeight(22)
        load_btn.setStyleSheet(
            f"QPushButton {{ background:{DHIS2_BLUE}; color:white; border:none; "
            f"border-radius:3px; font-size:10px; padding:1px 6px; }}"
            f"QPushButton:hover {{ background:#155a8a; }}"
        )
        load_btn.clicked.connect(lambda _, c=chart: self._load_chart_config(c))
        lay.addWidget(load_btn)

        self._mc_hlay.addWidget(card)

    def _load_chart_config(self, chart: dict):
        # Track identity so a subsequent Save updates this entity (not a duplicate).
        self._current_chart_id = chart.get("id")
        self._current_chart_name = chart.get("name") or chart.get("title")
        self._current_chart_description = chart.get("description", "")
        self._update_chart_name_lbl()

        # 1) Chart type — rebuilds the dynamic option / dimension / filter widgets.
        #    template id == plugin id (as_template_dict), so fall back to plugin_id for charts
        #    saved without a template_id (e.g. built programmatically / imported).
        _tid = chart.get("template_id") or chart.get("plugin_id")
        tmpl = next((t for t in FIXED_TEMPLATES if t["id"] == _tid), None)
        if tmpl:
            self._on_chart_type_click(tmpl)

        # 2) Simple scalar fields.
        self._title_entry.setText(chart.get("title") or chart.get("name", ""))
        color = chart.get("chart_color")
        if color:
            self._on_color_select(color)
        col_seg = {12: "Full", 6: "Half", 4: "Third"}
        self._col_width_seg.set(col_seg.get(chart.get("col_width", 6), "Half"))

        self._custom_options = dict(chart.get("custom_options", {}))
        if self._custom_options:
            self._chat_display_text = "AI customizations loaded from saved chart.\n"
            self._chat_display.setReadOnly(False)
            self._chat_display.setPlainText(self._chat_display_text)
            self._chat_display.setReadOnly(True)

        dims = chart.get("dimensions") or {}

        # 3) Style / plugin options (widgets already rebuilt by step 1).
        for k, v in (chart.get("plugin_options") or {}).items():
            seg = self._select_vars.get(k)
            if seg is not None:
                try:
                    seg.set(v)
                except Exception:
                    pass
            ta = self._textarea_vars.get(k)
            if ta is not None:
                ta.setPlainText(str(v))
            w = self._option_vars.get(k)
            if isinstance(w, QCheckBox):
                w.setChecked(bool(v))
            elif isinstance(w, SegmentedButton):
                try:
                    w.set(v)
                except Exception:
                    pass
            elif isinstance(w, QLineEdit):
                w.setText(str(v))

        if dims.get("time_grain"):
            try:
                self._time_grain_seg.set(dims["time_grain"])
            except Exception:
                pass
        rl = dims.get("row_limit", 0)
        self._row_limit_combo.setCurrentText("All" if not rl else str(rl))
        if dims.get("sort_by"):
            self._sort_by_combo.setCurrentText(dims["sort_by"])
        if dims.get("sort_dir"):
            self._sort_dir_combo.setCurrentText(dims["sort_dir"])

        # 4) Source (program + stage, or aggregate). Selecting these populates the DE
        #    lists, which the metrics/dimension/filter restore (step 5) depends on.
        src = chart.get("source") or {}
        metrics = chart.get("metrics") or chart.get("de_sources") or []
        first = metrics[0] if metrics else {}
        de_type   = src.get("type")      or first.get("type", "")
        prog_uid  = src.get("prog_uid")  or first.get("prog_uid", "")
        prog_name = src.get("prog_name") or first.get("prog_name", "")
        stage_name = src.get("stage_name") or first.get("stage_name", "")
        # Three "dx-like" cases share type "indicator"; disambiguate by prog_uid:
        #   program-scoped (PI, has prog_uid) → program source;
        #   aggregate indicator (no prog_uid) → aggregate source.
        is_pi      = de_type == "indicator" and bool(prog_uid)
        is_agg_ind = de_type == "indicator" and not prog_uid
        if de_type in ("tracker_option", "tracker_numeric") or is_pi:
            self._src_prog_cb.setChecked(True)
            self._src_agg_cb.setChecked(False)
            self._src_ind_cb.setChecked(False)
            if is_pi and "PI" in self._kind_cbs:
                self._kind_cbs["PI"].setChecked(True)
            self._on_src_check()
            prog = next((p for p in self._programs if p.get("id") == prog_uid), None) \
                or next((p for p in self._programs if p["displayName"] == prog_name), None)
            if prog:
                idx = self._prog_menu.findText(prog["displayName"])
                if idx >= 0:
                    self._prog_menu.setCurrentIndex(idx)   # → _on_prog_selected
                else:
                    self._on_prog_selected()
                if stage_name:
                    sidx = self._stage_menu.findText(stage_name)
                    if sidx >= 0:
                        self._stage_menu.setCurrentIndex(sidx)  # → _on_stage_selected
        elif is_agg_ind:
            self._src_prog_cb.setChecked(False)
            self._src_agg_cb.setChecked(False)
            self._src_ind_cb.setChecked(True)          # → _on_src_check triggers lazy load
            self._on_src_check()
        elif de_type == "aggregate":
            self._src_prog_cb.setChecked(False)
            self._src_agg_cb.setChecked(True)
            self._src_ind_cb.setChecked(False)
            self._on_src_check()

        # 5) Metrics / dimension / filters depend on the DE lists, which refresh on the
        #    next event-loop tick (see _on_stage_selected) — restore after they settle.
        QTimer.singleShot(120, lambda: self._restore_selection(chart))

    def _restore_selection(self, chart: dict):
        """Restore metric DEs, the split-by dimension, and filter rows (deferred so the
        available-DE lists are populated first)."""
        dims = chart.get("dimensions") or {}
        metrics = chart.get("metrics") or chart.get("de_sources") or []
        uids = [m.get("uid") for m in metrics if m.get("uid")]
        agg_map = {m.get("uid", ""): m.get("agg", "SUM") for m in metrics}
        # Restore alias: prefer explicit 'alias', else derive from a saved name that
        # differs from the real DE name (older saves stored alias in 'name').
        alias_map = {}
        for m in metrics:
            uid = m.get("uid", "")
            alias = (m.get("alias") or "").strip()
            if not alias and m.get("orig_name") and m.get("name") not in (None, m.get("orig_name")):
                alias = m["name"]
            if alias:
                alias_map[uid] = alias
        # Pass the saved metric dicts as `known` so the selection restores even when the
        # item isn't in the available list yet (e.g. indicators loaded on demand). Use the
        # REAL name (orig_name) for the chip — the alias is carried separately via alias_map,
        # otherwise the chip would show the alias as its name (no real name visible).
        known = {}
        for m in metrics:
            if not m.get("uid"):
                continue
            d = dict(m)
            d["name"] = m.get("orig_name") or m.get("name") or m["uid"]
            known[m["uid"]] = d
        self._metrics_picker.set_selected_uids(uids, agg_map, alias_map, known=known)
        self._on_de_check()

        # Restore ALL dimensions (group_by) with their aliases; fall back to the single
        # legacy `dimension` for older saves.
        gb = dims.get("group_by") or ([dims["dimension"]] if dims.get("dimension") else [])
        gb = [d for d in gb if isinstance(d, dict) and d.get("uid")]
        if gb:
            dim_uids = [d["uid"] for d in gb]
            dim_alias = {}
            for d in gb:
                a = (d.get("alias") or "").strip()
                if not a and d.get("orig_name") and d.get("name") not in (None, d.get("orig_name")):
                    a = d["name"]
                if a:
                    dim_alias[d["uid"]] = a
            self._dim_picker.set_selected_uids(dim_uids, alias_map=dim_alias)

        for rd in list(self._filter_rows):
            self._remove_filter_row(rd)
        rev_op = {v: k for k, v in self._OP_MAP.items()}
        for f in dims.get("filters", []):
            self._add_filter_row()
            rd = self._filter_rows[-1]
            if f.get("de_name") or f.get("de_uid"):
                # Combo items are "(DE) Name"; match the saved filter by uid → its label.
                from ui.metadata_display import plain_label
                label = next((plain_label(d) for d in self._current_de_items
                              if d.get("uid") == f.get("de_uid")), f.get("de_name", ""))
                rd["de_menu"].setCurrentText(label)          # → _on_filter_de_changed
            rd["op_menu"].setCurrentText(rev_op.get(f.get("op", "EQ"), "EQ"))
            val = f.get("value", "")
            vc = rd.get("val_combo")
            if rd.get("use_combo") and vc is not None:
                i = next((k for k in range(vc.count()) if vc.itemData(k) == val), -1)
                if i >= 0:
                    vc.setCurrentIndex(i)
            else:
                rd["val_entry"].setText(str(val))

        self._update_action_buttons()
        self._auto_preview()

    def _try_select_saved_des(self, uids: set):
        agg_map = {d.get("uid", ""): d.get("agg", "SUM")
                   for d in self._selected_metrics}
        self._metrics_picker.set_selected_uids(list(uids), agg_map)
        self._on_de_check()

    # =========================================================================
    # Section 1: Chart Type
    # =========================================================================

    def _build_chart_type_section(self, parent_lay: QVBoxLayout):
        parent_lay.addWidget(self._sec_lbl("1. Chart Type"))

        outer = _make_card()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(8, 6, 8, 8)
        outer_lay.setSpacing(4)

        # Collapsed summary row (shown after selection)
        self._chart_sel_row = QWidget()
        sel_lay = QHBoxLayout(self._chart_sel_row)
        sel_lay.setContentsMargins(0, 0, 0, 0)
        self._chart_sel_lbl = QLabel("")
        self._chart_sel_lbl.setStyleSheet(
            f"font-size:11px; font-weight:bold; color:{DHIS2_BLUE}; background:transparent;"
        )
        sel_lay.addWidget(self._chart_sel_lbl, stretch=1)
        change_btn = QPushButton("Change ▼")
        change_btn.setFixedHeight(26)
        change_btn.setStyleSheet(
            f"QPushButton {{ background:#e8eef5; border:1px solid {BORDER_CLR}; "
            f"border-radius:4px; color:#5a7a9a; font-size:10px; padding:2px 8px; }}"
            f"QPushButton:hover {{ background:#d0dde8; }}"
        )
        change_btn.clicked.connect(self._expand_chart_grid)
        sel_lay.addWidget(change_btn)
        self._chart_sel_row.setVisible(False)
        outer_lay.addWidget(self._chart_sel_row)

        # Expanded grid
        self._chart_grid_outer = QWidget()
        grid_outer_lay = QVBoxLayout(self._chart_grid_outer)
        grid_outer_lay.setContentsMargins(0, 0, 0, 0)
        grid_outer_lay.setSpacing(4)

        self._chart_info_lbl = QLabel("← Select a chart type to begin")
        self._chart_info_lbl.setStyleSheet("font-size:9px; color:#8aa3b8; background:transparent;")
        grid_outer_lay.addWidget(self._chart_info_lbl)

        COLS = 4
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background:white;")
        grid_lay = QGridLayout(grid_widget)
        grid_lay.setContentsMargins(0, 0, 0, 0)
        grid_lay.setSpacing(4)

        visible = [t for t in FIXED_TEMPLATES
                   if not (t.get("plugin") and getattr(t["plugin"], "hidden", False))]
        for i, tmpl in enumerate(visible):
            r, c = divmod(i, COLS)
            tile = _ChartTile(tmpl)
            tile.clicked.connect(self._on_chart_type_click)
            grid_lay.addWidget(tile, r, c)
            self._chart_tiles[tmpl["id"]] = tile

        grid_outer_lay.addWidget(grid_widget)
        outer_lay.addWidget(self._chart_grid_outer)

        parent_lay.addWidget(outer)

    def _collapse_chart_grid(self):
        tmpl = self._selected_template
        if not tmpl:
            return
        self._chart_grid_outer.setVisible(False)
        self._chart_sel_lbl.setText(f"{tmpl['icon']}  {tmpl['label']}")
        self._chart_sel_row.setVisible(True)

    def _expand_chart_grid(self):
        self._chart_sel_row.setVisible(False)
        self._chart_grid_outer.setVisible(True)

    # =========================================================================
    # Section 2: Source
    # =========================================================================

    def _build_source_section(self, parent_lay: QVBoxLayout):
        parent_lay.addWidget(self._sec_lbl("2. Source"))

        outer = _make_card()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(10, 8, 10, 24)   # extra bottom space so last row isn't flush
        outer_lay.setSpacing(6)

        # Checkboxes row
        cb_row = QWidget()
        cb_row.setStyleSheet("background:transparent;")
        cb_lay = QHBoxLayout(cb_row)
        cb_lay.setContentsMargins(0, 0, 0, 0)
        cb_lay.setSpacing(20)

        self._src_prog_cb = QCheckBox("Program (Tracker)")
        self._src_prog_cb.setChecked(True)
        self._src_prog_cb.stateChanged.connect(self._on_src_check)
        cb_lay.addWidget(self._src_prog_cb)

        self._src_agg_cb = QCheckBox("Aggregate Dataset")
        self._src_agg_cb.setChecked(False)
        self._src_agg_cb.stateChanged.connect(self._on_src_check)
        cb_lay.addWidget(self._src_agg_cb)

        # Indicators are a standalone dx domain (like PI) — NOT tied to datasets/DEs.
        # Their own source toggle; loaded on demand to avoid pulling them needlessly.
        self._src_ind_cb = QCheckBox("Indicators")
        self._src_ind_cb.setChecked(False)
        self._src_ind_cb.stateChanged.connect(self._on_src_check)
        cb_lay.addWidget(self._src_ind_cb)
        cb_lay.addStretch()
        outer_lay.addWidget(cb_row)

        # Program dropdown
        self._prog_menu = QComboBox()
        self._prog_menu.addItem("—")
        self._prog_menu.setFixedHeight(30)
        _style_combo(self._prog_menu)
        self._prog_menu.currentTextChanged.connect(self._on_prog_selected)
        outer_lay.addWidget(self._prog_menu)

        # Stage dropdown
        self._stage_menu = QComboBox()
        self._stage_menu.addItem("—")
        self._stage_menu.setFixedHeight(30)
        _style_combo(self._stage_menu)
        self._stage_menu.currentTextChanged.connect(self._on_stage_selected)
        outer_lay.addWidget(self._stage_menu)

        # Kind filter (Program source): show Data Elements / Program Attributes /
        # Program Indicators independently. All on by default.
        self._kind_row = QWidget()
        self._kind_row.setStyleSheet("background:transparent;")
        _kind_lay = QHBoxLayout(self._kind_row)
        _kind_lay.setContentsMargins(0, 0, 0, 0)
        _kind_lay.setSpacing(16)
        _kind_lay.addWidget(QLabel("Show:"))
        self._kind_cbs: dict[str, QCheckBox] = {}
        for _k, _lbl in (("DE", "Data elements"), ("PA", "Attributes"), ("PI", "Program indicators")):
            cb = QCheckBox(_lbl)
            cb.setChecked(True)
            cb.setStyleSheet("font-size:11px; background:transparent;")
            cb.stateChanged.connect(self._on_kind_filter_change)
            self._kind_cbs[_k] = cb
            _kind_lay.addWidget(cb)
        _kind_lay.addStretch()
        outer_lay.addWidget(self._kind_row)

        # (No source-level search box — each picker has its own search; a second one here
        #  was redundant. Load status is shown on the metrics picker's search placeholder.)

        parent_lay.addWidget(outer)

    # =========================================================================
    # Section 3: Metrics
    # =========================================================================

    def _build_metrics_section(self, parent_lay: QVBoxLayout):
        self._metrics_section_lbl = QLabel("3. METRICS  (SELECT 1)")
        self._metrics_section_lbl.setStyleSheet(
            "color:#8aa3b8; font-size:9px; font-weight:bold; padding:6px 12px 2px 12px;"
            "background:transparent;"
        )
        parent_lay.addWidget(self._metrics_section_lbl)
        self._de_section_lbl = self._metrics_section_lbl  # backward compat

        outer = _make_card()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(6, 6, 6, 6)
        outer_lay.setSpacing(4)

        self._metrics_picker = DEPickerWidget(max_count=1, show_agg=True, avail_height=100)
        self._metrics_picker.changed.connect(self._on_de_check)
        outer_lay.addWidget(self._metrics_picker)

        parent_lay.addWidget(outer)

    # =========================================================================
    # Section: Dimensions
    # =========================================================================

    def _build_dimensions_section(self, parent_lay: QVBoxLayout):
        parent_lay.addWidget(self._sec_lbl("Dimensions"))

        outer = _make_card()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(8, 6, 8, 8)
        outer_lay.setSpacing(4)

        # ── Time grain row ────────────────────────────────────────────────────
        self._time_grain_row = QWidget()
        self._time_grain_row.setStyleSheet("background:transparent;")
        tg_lay = QHBoxLayout(self._time_grain_row)
        tg_lay.setContentsMargins(0, 0, 0, 0)
        tg_lay.setSpacing(8)
        tg_lbl = QLabel("Time grain:")
        tg_lbl.setStyleSheet("font-size:9px; color:#5a7a9a; background:transparent;")
        tg_lay.addWidget(tg_lbl)
        self._time_grain_seg = SegmentedButton(["Monthly", "Quarterly", "Yearly"], default="Monthly")
        self._time_grain_seg.changed.connect(lambda _: self._schedule_preview_refresh())
        tg_lay.addWidget(self._time_grain_seg)
        tg_lay.addStretch()
        self._time_grain_row.setVisible(False)
        outer_lay.addWidget(self._time_grain_row)

        # ── Dimension picker ──────────────────────────────────────────────────
        self._dim_picker_row = QWidget()
        self._dim_picker_row.setStyleSheet("background:transparent;")
        dpick_lay = QVBoxLayout(self._dim_picker_row)
        dpick_lay.setContentsMargins(0, 2, 0, 0)
        dpick_lay.setSpacing(2)

        split_lbl = QLabel("Split by:")
        split_lbl.setStyleSheet("font-size:9px; color:#5a7a9a; background:transparent;")
        dpick_lay.addWidget(split_lbl)

        self._dim_picker = DEPickerWidget(max_count=1, show_agg=False, avail_height=80,
                                          show_alias=False)
        self._dim_picker.changed.connect(self._schedule_preview_refresh)
        dpick_lay.addWidget(self._dim_picker)

        self._dim_hint_lbl = QLabel("")
        self._dim_hint_lbl.setStyleSheet("font-size:8px; color:#8aa3b8; background:transparent;")
        dpick_lay.addWidget(self._dim_hint_lbl)

        self._dim_picker_row.setVisible(False)
        outer_lay.addWidget(self._dim_picker_row)

        # ── Filters ───────────────────────────────────────────────────────────
        outer_lay.addWidget(self._make_hdiv())

        filter_hdr = QWidget()
        filter_hdr.setStyleSheet("background:transparent;")
        fhdr_lay = QHBoxLayout(filter_hdr)
        fhdr_lay.setContentsMargins(0, 2, 0, 0)
        fhdr_lbl = QLabel("Filters")
        fhdr_lbl.setStyleSheet("font-size:8px; font-weight:bold; color:#8aa3b8; background:transparent;")
        fhdr_lay.addWidget(fhdr_lbl)
        fhdr_lay.addStretch()

        add_filter_btn = QPushButton("+ Add filter")
        add_filter_btn.setFixedHeight(20)
        add_filter_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; border:1px solid #c5d3e0; "
            f"border-radius:3px; color:#5a7a9a; font-size:9px; padding:1px 6px; }}"
            f"QPushButton:hover {{ background:#f0f4f8; }}"
        )
        add_filter_btn.clicked.connect(self._add_filter_row)
        fhdr_lay.addWidget(add_filter_btn)
        outer_lay.addWidget(filter_hdr)

        self._filter_rows_widget = QWidget()
        self._filter_rows_widget.setStyleSheet("background:transparent;")
        self._filter_rows_lay = QVBoxLayout(self._filter_rows_widget)
        self._filter_rows_lay.setContentsMargins(0, 0, 0, 0)
        self._filter_rows_lay.setSpacing(2)
        outer_lay.addWidget(self._filter_rows_widget)

        # ── Options (limit + sort) ─────────────────────────────────────────────
        outer_lay.addWidget(self._make_hdiv())
        opts_row = QWidget()
        opts_row.setStyleSheet("background:transparent;")
        opts_lay = QHBoxLayout(opts_row)
        opts_lay.setContentsMargins(0, 4, 0, 0)
        opts_lay.setSpacing(6)

        opts_lay.addWidget(QLabel("Limit:"))

        self._row_limit_combo = QComboBox()
        self._row_limit_combo.addItems(["10", "20", "50", "100", "200", "All"])
        self._row_limit_combo.setCurrentText("All")
        self._row_limit_combo.setFixedHeight(24)
        self._row_limit_combo.setFixedWidth(64)
        _style_combo(self._row_limit_combo)
        opts_lay.addWidget(self._row_limit_combo)

        opts_lay.addWidget(QLabel("Sort:"))

        self._sort_by_combo = QComboBox()
        self._sort_by_combo.addItems(["None", "Value", "Label"])
        self._sort_by_combo.setFixedHeight(24)
        self._sort_by_combo.setFixedWidth(72)
        _style_combo(self._sort_by_combo)
        opts_lay.addWidget(self._sort_by_combo)

        self._sort_dir_combo = QComboBox()
        self._sort_dir_combo.addItems(["Desc", "Asc"])
        self._sort_dir_combo.setFixedHeight(24)
        self._sort_dir_combo.setFixedWidth(60)
        _style_combo(self._sort_dir_combo)
        opts_lay.addWidget(self._sort_dir_combo)
        opts_lay.addStretch()

        for lbl_w in opts_row.findChildren(QLabel):
            lbl_w.setStyleSheet("font-size:9px; color:#5a7a9a; background:transparent;")

        outer_lay.addWidget(opts_row)

        parent_lay.addWidget(outer)

    # =========================================================================
    # Section 4: Style & Options
    # =========================================================================

    def _build_style_section(self, parent_lay: QVBoxLayout):
        parent_lay.addWidget(self._sec_lbl("4. Style & Options"))

        # ── Plugin SelectControls (moved from Dimensions) ─────────────────────
        self._select_controls_frame = QWidget()
        self._select_controls_frame.setStyleSheet("background:transparent;")
        self._select_controls_lay = QVBoxLayout(self._select_controls_frame)
        self._select_controls_lay.setContentsMargins(12, 4, 12, 4)
        self._select_controls_lay.setSpacing(3)
        self._select_controls_frame.setVisible(False)
        parent_lay.addWidget(self._select_controls_frame)

        # ── Color ─────────────────────────────────────────────────────────────
        self._color_section_lbl = QLabel("Color")
        self._color_section_lbl.setStyleSheet(
            f"font-size:9px; color:#5a7a9a; padding:4px 12px 0 12px; background:transparent;"
        )
        parent_lay.addWidget(self._color_section_lbl)

        self._color_swatch_row = QWidget()
        self._color_swatch_row.setStyleSheet("background:transparent;")
        cr_lay = QHBoxLayout(self._color_swatch_row)
        cr_lay.setContentsMargins(12, 0, 12, 4)
        cr_lay.setSpacing(3)

        for hex_c, _ in COLOR_PRESETS:
            swatch = _ColorSwatch(hex_c)
            swatch.clicked.connect(self._on_color_select)
            cr_lay.addWidget(swatch)
            self._color_swatches.append(swatch)

        # Custom colour: a swatch (hidden until a colour is picked) + a picker button.
        self._custom_color_swatch = _ColorSwatch("#000000")
        self._custom_color_swatch.setVisible(False)
        self._custom_color_swatch.clicked.connect(self._on_color_select)
        cr_lay.addWidget(self._custom_color_swatch)
        self._color_swatches.append(self._custom_color_swatch)

        pick_btn = QPushButton("🎨")
        pick_btn.setFixedSize(24, 20)
        pick_btn.setToolTip("Custom colour…")
        pick_btn.setCursor(Qt.PointingHandCursor)
        pick_btn.setStyleSheet(
            "QPushButton { border:1px solid #c0cdd8; border-radius:2px; background:white;"
            "  font-size:11px; padding:0; }"
            "QPushButton:hover { background:#eef3f8; }"
        )
        pick_btn.clicked.connect(self._on_pick_custom_color)
        cr_lay.addWidget(pick_btn)

        cr_lay.addStretch()
        parent_lay.addWidget(self._color_swatch_row)
        self._on_color_select(self._selected_color)

        # ── Title + Col Width ──────────────────────────────────────────────────
        title_lbl = QLabel("Title")
        title_lbl.setStyleSheet(
            "font-size:9px; color:#5a7a9a; padding:0 12px; background:transparent;"
        )
        parent_lay.addWidget(title_lbl)

        self._title_entry = QLineEdit()
        self._title_entry.setPlaceholderText("Auto from DE name")
        self._title_entry.setFixedHeight(26)
        self._title_entry.setContentsMargins(0, 0, 0, 0)
        title_wrap = QWidget()
        title_wrap.setStyleSheet("background:transparent;")
        tw_lay = QHBoxLayout(title_wrap)
        tw_lay.setContentsMargins(12, 0, 12, 4)
        tw_lay.addWidget(self._title_entry)
        parent_lay.addWidget(title_wrap)

        col_lbl = QLabel("Col width")
        col_lbl.setStyleSheet(
            "font-size:9px; color:#5a7a9a; padding:0 12px; background:transparent;"
        )
        parent_lay.addWidget(col_lbl)

        cw_wrap = QWidget()
        cw_wrap.setStyleSheet("background:transparent;")
        cw_lay = QHBoxLayout(cw_wrap)
        cw_lay.setContentsMargins(12, 0, 12, 4)
        self._col_width_seg = SegmentedButton(["Full", "Half", "Third"], default="Half")
        self._col_width_seg.changed.connect(lambda _: self._schedule_preview_refresh())
        cw_lay.addWidget(self._col_width_seg)
        cw_lay.addStretch()
        parent_lay.addWidget(cw_wrap)

        # ── Mode ──────────────────────────────────────────────────────────────
        mode_wrap = QWidget()
        mode_wrap.setStyleSheet("background:transparent;")
        mode_vlay = QVBoxLayout(mode_wrap)
        mode_vlay.setContentsMargins(12, 0, 12, 4)
        mode_vlay.setSpacing(4)

        mode_lbl = QLabel("Mode")
        mode_lbl.setStyleSheet("font-size:9px; color:#5a7a9a; background:transparent;")
        mode_vlay.addWidget(mode_lbl)

        mode_btn_row = QWidget()
        mode_btn_row.setStyleSheet("background:transparent;")
        mode_btn_lay = QHBoxLayout(mode_btn_row)
        mode_btn_lay.setContentsMargins(0, 0, 0, 0)
        mode_btn_lay.setSpacing(16)

        self._mode_fixed_rb = QRadioButton("Fixed")
        self._mode_fixed_rb.setChecked(True)
        self._mode_fixed_rb.toggled.connect(self._on_mode_change)
        mode_btn_lay.addWidget(self._mode_fixed_rb)

        self._mode_ai_rb = QRadioButton("AI")
        self._mode_ai_rb.toggled.connect(self._on_mode_change)
        mode_btn_lay.addWidget(self._mode_ai_rb)
        mode_btn_lay.addStretch()

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._mode_fixed_rb, 0)
        self._mode_group.addButton(self._mode_ai_rb, 1)

        mode_vlay.addWidget(mode_btn_row)
        parent_lay.addWidget(mode_wrap)

        # AI description textbox (hidden by default)
        self._ai_desc = QTextEdit()
        self._ai_desc.setFixedHeight(48)
        self._ai_desc.setPlaceholderText("Describe the chart you want AI to generate…")
        ai_desc_wrap = QWidget()
        ai_desc_wrap.setStyleSheet("background:transparent;")
        ad_lay = QHBoxLayout(ai_desc_wrap)
        ad_lay.setContentsMargins(10, 0, 10, 4)
        ad_lay.addWidget(self._ai_desc)
        self._ai_desc_wrap = ai_desc_wrap
        self._ai_desc_wrap.setVisible(False)
        parent_lay.addWidget(self._ai_desc_wrap)

        # ── Chart Options ─────────────────────────────────────────────────────
        parent_lay.addWidget(self._make_hdiv())

        chart_opts_hdr = QLabel("CHART OPTIONS")
        chart_opts_hdr.setStyleSheet(
            "color:#8aa3b8; font-size:9px; font-weight:bold; "
            "padding:5px 12px 0 12px; background:transparent;"
        )
        parent_lay.addWidget(chart_opts_hdr)

        self._dyn_opts_frame = QWidget()
        self._dyn_opts_frame.setStyleSheet("background:transparent;")
        self._dyn_opts_lay = QVBoxLayout(self._dyn_opts_frame)
        self._dyn_opts_lay.setContentsMargins(12, 2, 12, 4)
        self._dyn_opts_lay.setSpacing(4)

        _placeholder = QLabel("← Select a chart type")
        _placeholder.setStyleSheet("font-size:9px; color:#8aa3b8; background:transparent;")
        self._dyn_opts_lay.addWidget(_placeholder)

        parent_lay.addWidget(self._dyn_opts_frame)

        # ── AI Customize (collapsible) ────────────────────────────────────────
        self._ai_chat_toggle_btn = QPushButton("🤖  AI Customize  ▶")
        self._ai_chat_toggle_btn.setFixedHeight(28)
        self._ai_chat_toggle_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; border:none; color:{DHIS2_BLUE}; "
            f"font-size:10px; font-weight:bold; text-align:left; padding:2px 8px; }}"
            f"QPushButton:hover {{ background:#e8eef5; }}"
        )
        self._ai_chat_toggle_btn.clicked.connect(self._toggle_ai_chat)
        parent_lay.addWidget(self._ai_chat_toggle_btn)

        self._ai_chat_panel = QWidget()
        self._ai_chat_panel.setStyleSheet("background:transparent;")
        ai_panel_lay = QVBoxLayout(self._ai_chat_panel)
        ai_panel_lay.setContentsMargins(10, 2, 10, 10)
        ai_panel_lay.setSpacing(4)

        self._chat_display = QTextEdit()
        self._chat_display.setFixedHeight(80)
        self._chat_display.setReadOnly(True)
        self._chat_display.setStyleSheet(
            f"QTextEdit {{ background:#f8fafc; border:1px solid {BORDER_CLR}; "
            f"border-radius:4px; font-size:10px; color:#2c3e50; }}"
        )
        ai_panel_lay.addWidget(self._chat_display)

        inp_row = QWidget()
        inp_row.setStyleSheet("background:transparent;")
        inp_lay = QHBoxLayout(inp_row)
        inp_lay.setContentsMargins(0, 0, 0, 0)
        inp_lay.setSpacing(4)

        self._ai_input = QLineEdit()
        self._ai_input.setFixedHeight(26)
        self._ai_input.setPlaceholderText("show labels, thinner bars, no grid…")
        self._ai_input.returnPressed.connect(self._on_ai_customize)
        inp_lay.addWidget(self._ai_input, stretch=1)

        send_btn = QPushButton("Send")
        send_btn.setFixedSize(52, 26)
        send_btn.setStyleSheet(
            f"QPushButton {{ background:{DHIS2_BLUE}; color:white; border:none; "
            f"border-radius:4px; font-size:10px; }}"
            f"QPushButton:hover {{ background:#155a8a; }}"
        )
        send_btn.clicked.connect(self._on_ai_customize)
        inp_lay.addWidget(send_btn)
        ai_panel_lay.addWidget(inp_row)

        reset_btn = QPushButton("↺ Reset all")
        reset_btn.setFixedHeight(22)
        reset_btn.setStyleSheet(
            "QPushButton { background:transparent; border:1px solid #e74c3c; "
            "border-radius:4px; color:#e74c3c; font-size:9px; padding:1px 8px; }"
            "QPushButton:hover { background:#fdecea; }"
        )
        reset_btn.clicked.connect(self._on_reset_customization)
        ai_panel_lay.addWidget(reset_btn, alignment=Qt.AlignLeft)

        self._ai_chat_panel.setVisible(False)
        parent_lay.addWidget(self._ai_chat_panel)

    # ── Actions bar ───────────────────────────────────────────────────────────

    # Disabled look shared by every action button (UI rule: a clearly greyed,
    # non-interactive state when the action isn't usable in the current flow).
    _BTN_DISABLED_QSS = (
        "QPushButton:disabled { background:#eef1f4; color:#aab4be; border-color:#dde3e9; }"
    )

    @staticmethod
    def _action_btn(text: str, *, fg: str, bg: str, border: str,
                    hover_bg: str, hover_fg: str | None = None) -> QPushButton:
        """Action button with an explicit, distinct hover colour + a disabled state."""
        btn = QPushButton(text)
        btn.setFixedHeight(30)
        btn.setCursor(Qt.PointingHandCursor)
        hf = hover_fg or fg
        btn.setStyleSheet(
            f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {border}; "
            f"border-radius:4px; font-size:12px; padding:2px 12px; }}"
            f"QPushButton:hover {{ background:{hover_bg}; color:{hf}; }}"
            f"QPushButton:pressed {{ background:{hover_bg}; }}"
            + ChartEditorPanel._BTN_DISABLED_QSS
        )
        return btn

    def _build_actions(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(46)
        bar.setStyleSheet("background:#e8eef5; border:none;")

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        # Each button gets a DISTINCT hover colour so they're visually separable.
        self._new_btn = self._action_btn(
            "🆕 New", fg="#5a7a9a", bg="white", border="#b0c0d0", hover_bg="#cdd8e4")
        self._new_btn.clicked.connect(self._on_new)
        lay.addWidget(self._new_btn)

        self._open_btn = self._action_btn(
            "📂 Open", fg="#2c6e49", bg="white", border="#8cc0a4", hover_bg="#cdeedd")
        self._open_btn.clicked.connect(self._on_open_chart)
        lay.addWidget(self._open_btn)

        self._save_btn = self._action_btn(
            "💾 Save", fg="white", bg="#8e44ad", border="#8e44ad", hover_bg="#6c3483")
        self._save_btn.clicked.connect(self._on_save)
        lay.addWidget(self._save_btn)

        self._save_as_btn = self._action_btn(
            "Save As…", fg="#8e44ad", bg="white", border="#8e44ad",
            hover_bg="#e3c6f0", hover_fg="#5b2c6f")
        self._save_as_btn.clicked.connect(self._on_save_as)
        lay.addWidget(self._save_as_btn)

        self._dash_btn = self._action_btn(
            "+ Add to Dashboard", fg="white", bg="#27ae60", border="#27ae60", hover_bg="#1e8449")
        self._dash_btn.clicked.connect(self._on_add_to_dashboard)
        lay.addWidget(self._dash_btn)

        self._preview_btn = self._action_btn(
            "🌐 Preview in Browser", fg=DHIS2_BLUE, bg="white", border=DHIS2_BLUE,
            hover_bg="#aed6f1", hover_fg="#1a5276")
        self._preview_btn.clicked.connect(self._on_preview_browser)
        lay.addWidget(self._preview_btn)
        lay.addStretch()

        self._update_action_buttons()
        return bar

    def _update_action_buttons(self):
        """Enable/disable actions based on the current flow state (UI rule:
        show a disabled colour when an action isn't usable right now)."""
        if not hasattr(self, "_save_btn"):
            return
        has_chart = bool(self._selected_template) and bool(self._get_selected_des())
        for b in (self._save_btn, self._save_as_btn, self._dash_btn, self._preview_btn):
            b.setEnabled(has_chart)
        try:
            from config.chart_library import load_charts
            self._open_btn.setEnabled(bool(load_charts()))
        except Exception:
            self._open_btn.setEnabled(True)

    # =========================================================================
    # Metadata
    # =========================================================================

    def set_in_use(self, uids) -> None:
        """Restrict metrics & dimensions to this set of curated UIDs (empty = show all).

        Called by app_window after connect and whenever the Metadata Library's selection
        changes (REQ-META-EDIT-04)."""
        self._in_use = set(uids or [])
        # Refresh the pickers if metadata is already loaded.
        if self._programs or self._agg_des or self._agg_indicators:
            self._refresh_metrics_display()
            self._refresh_dimensions_display()

    def load_metadata(self, meta: dict):
        self._metadata = meta
        prog_map: dict[str, dict] = {}
        for de in meta.get("program_stage_data_elements", []):
            pid   = de.get("program", {}).get("id", "")
            pname = de.get("program", {}).get("displayName", pid)
            sid   = de.get("stage", {}).get("id", "")
            sname = de.get("stage", {}).get("displayName", sid)
            if pid not in prog_map:
                prog_map[pid] = {"id": pid, "displayName": pname, "stages": {}, "teas": []}
            sm = prog_map[pid]["stages"]
            if sid not in sm:
                sm[sid] = {"id": sid, "displayName": sname, "des": []}
            os_data = de.get("optionSet") or {}
            options = [
                {"code": o.get("code", ""), "name": o.get("displayName", o.get("code", ""))}
                for o in os_data.get("options", [])
            ]
            sm[sid]["des"].append({
                "uid":        de["id"],
                "name":       de.get("displayName", de["id"]),
                "type":       "tracker_option" if os_data else "tracker_numeric",
                "prog_uid":   pid,
                "prog_name":  pname,
                "stage_uid":  sid,
                "stage_name": sname,
                "options":    options,
                "kind":       "DE",
            })

        # Program (tracked-entity) attributes — gender, age, etc. Available as
        # metrics / dimensions / filters alongside stage data elements (program-level,
        # not tied to a stage). Numeric valueType → tracker_numeric, else categorical.
        _NUM_VT = {"INTEGER", "NUMBER", "INTEGER_POSITIVE", "INTEGER_NEGATIVE",
                   "INTEGER_ZERO_OR_POSITIVE", "PERCENTAGE", "UNIT_INTERVAL"}
        for tea in meta.get("tracked_entity_attributes", []):
            pid   = tea.get("program", {}).get("id", "")
            if not pid:
                continue
            pname = tea.get("program", {}).get("displayName", pid)
            prog_map.setdefault(pid, {"id": pid, "displayName": pname, "stages": {}, "teas": []})
            prog_map[pid].setdefault("teas", [])
            os_data = tea.get("optionSet") or {}
            options = [
                {"code": o.get("code", ""), "name": o.get("displayName", o.get("code", ""))}
                for o in os_data.get("options", [])
            ]
            typ = ("tracker_option" if os_data
                   else "tracker_numeric" if tea.get("valueType") in _NUM_VT
                   else "tracker_option")
            prog_map[pid]["teas"].append({
                "uid":        tea["id"],
                "name":       tea.get("displayName", tea["id"]),
                "type":       typ,
                "prog_uid":   pid,
                "prog_name":  pname,
                "stage_uid":  "",        # TEAs are program-level (no stage)
                "is_tea":     True,      # → analytics dimension uses the bare uid
                "options":    options,
                "kind":       "PA",
            })

        # Program indicators — program-level metrics. Queried as dx in analytics.json
        # (DHIS2 treats a PI uid as a dx item), so type "indicator" reuses the existing
        # aggregate render path in every plugin. Metric-only (no option set).
        for pi in meta.get("program_indicators", []):
            pid = pi.get("program", {}).get("id", "")
            if not pid:
                continue
            pname = pi.get("program", {}).get("displayName", pid)
            prog_map.setdefault(pid, {"id": pid, "displayName": pname,
                                      "stages": {}, "teas": [], "pis": []})
            prog_map[pid].setdefault("pis", [])
            prog_map[pid]["pis"].append({
                "uid":        pi["id"],
                "name":       pi.get("displayName", pi["id"]),
                "type":       "indicator",   # → analytics.json dx (works for PI)
                "prog_uid":   pid,
                "prog_name":  pname,
                "stage_uid":  "",
                "is_pi":      True,
                "kind":       "PI",
            })

        self._programs = sorted(
            [{"id": p["id"], "displayName": p["displayName"],
              "stages": list(p["stages"].values()), "teas": p.get("teas", []),
              "pis": p.get("pis", [])}
             for p in prog_map.values()],
            key=lambda x: x["displayName"].lower())

        self._agg_des = sorted(
            [{"uid": d["id"], "name": d.get("displayName", d["id"]),
              "type": "aggregate", "prog_uid": "", "stage_uid": ""}
             for d in meta.get("data_elements", [])],
            key=lambda x: x["name"].lower())

        # Aggregate indicators: if the connect-time metadata already includes them (aggregate
        # scope), use them for free. Otherwise leave empty and fetch on demand when the user
        # ticks "Indicators" (see _ensure_indicators_loaded) — avoids loading them needlessly.
        self._agg_indicators = sorted(
            [{"uid": i["id"], "name": i.get("displayName", i["id"]),
              "type": "indicator", "prog_uid": "", "stage_uid": "", "kind": "I"}
             for i in meta.get("indicators", [])],
            key=lambda x: x["name"].lower())
        self._indicators_loaded = bool(self._agg_indicators)
        self._indicators_loading = False

        self._prog_menu.blockSignals(True)
        self._prog_menu.clear()
        self._prog_menu.addItem("— Select program —")
        for p in self._programs:
            self._prog_menu.addItem(p["displayName"])
        self._prog_menu.blockSignals(False)
        self._prog_menu.setCurrentIndex(0)

        self._stage_menu.blockSignals(True)
        self._stage_menu.clear()
        self._stage_menu.addItem("—")
        self._stage_menu.blockSignals(False)

    # =========================================================================
    # Source logic
    # =========================================================================

    def _on_kind_filter_change(self, *_):
        """DE/PA/PI filter toggled — re-list and refresh pickers."""
        self._refresh_metrics_display()
        self._refresh_dimensions_display()

    def _ensure_indicators_loaded(self):
        """Fetch indicators on demand the first time the user ticks the 'Indicators' source.

        Skipped entirely when they were already in the connect-time metadata, when offline
        (fixture mode), or while a fetch is already in flight — so we never load needlessly.
        """
        from ui.debug_logger import log
        if not (hasattr(self, "_src_ind_cb") and self._src_ind_cb.isChecked()):
            return
        if self._indicators_loaded or self._indicators_loading:
            log("indicators", f"skip: loaded={self._indicators_loaded} "
                              f"loading={self._indicators_loading} have={len(self._agg_indicators)}")
            return
        client = getattr(self, "_dhis2_client", None)
        if client is None:
            # Fixture/offline — can't fetch. Tell the user why the list is empty.
            log("indicators", "no client (offline/fixture) — cannot fetch")
            self._metrics_picker.set_placeholder("⚠ Connect to DHIS2 to load indicators")
            return
        self._indicators_loading = True
        # Fetch the full set once (then filter locally + cap rendering) — fetching by the
        # current search term would cache only a subset and confuse later searches.
        log("indicators", "fetch start (full set)…")
        self._metrics_picker.set_placeholder("⏳ Loading indicators…")
        threading.Thread(target=self._load_indicators_worker,
                         args=(client, ""), daemon=True).start()

    def _load_indicators_worker(self, client, name: str):
        from ui.debug_logger import log
        try:
            from dhis2.metadata import fetch_indicators
            cfg = {"indicator_name": name} if name else {}
            rows = fetch_indicators(client, cfg)
            log("indicators", f"fetch ok: {len(rows)} rows")
            inds = [{"uid": r["id"], "name": r.get("displayName", r["id"]),
                     "type": "indicator", "prog_uid": "", "stage_uid": "", "kind": "I"}
                    for r in rows]
            self._call_main.emit(lambda: self._on_indicators_loaded(inds, None))
        except Exception as exc:
            log("indicators", f"fetch ERROR: {exc!r}")
            self._call_main.emit(lambda e=exc: self._on_indicators_loaded([], str(e)))

    def _on_indicators_loaded(self, inds: list, err):
        from ui.debug_logger import log
        self._indicators_loading = False
        self._metrics_picker.set_placeholder(None)
        if err:
            log("indicators", f"load failed: {err}")
            QMessageBox.warning(self, "Indicators", f"Could not load indicators:\n{err}")
            return
        self._indicators_loaded = True
        self._agg_indicators = sorted(inds, key=lambda x: x["name"].lower())
        log("indicators", f"loaded {len(self._agg_indicators)}; "
                          f"ind_src={self._src_ind_cb.isChecked()} refreshing")
        self._refresh_metrics_display()
        self._refresh_dimensions_display()

    def _on_src_check(self):
        prog = self._src_prog_cb.isChecked()
        agg  = self._src_agg_cb.isChecked()
        ind  = self._src_ind_cb.isChecked() if hasattr(self, "_src_ind_cb") else False
        self._prog_menu.setVisible(prog)
        self._stage_menu.setVisible(prog)
        if hasattr(self, "_kind_row"):
            self._kind_row.setVisible(prog)          # kind filter is Program-only (DE/PA/PI)
        if ind:
            self._ensure_indicators_loaded()         # fetch on demand the first time
        if not prog and not agg and not ind:
            self._clear_de_list()
        else:
            self._refresh_metrics_display()

    def _on_prog_selected(self, _=None):
        prog_name = self._prog_menu.currentText()
        prog = next((p for p in self._programs
                     if p["displayName"] == prog_name), None)
        if not prog:
            self._refresh_de_list()
            return
        self._current_prog = prog
        self._stage_menu.blockSignals(True)
        self._stage_menu.clear()
        self._stage_menu.addItem("— All stages —")
        for s in prog["stages"]:
            self._stage_menu.addItem(s["displayName"])
        self._stage_menu.blockSignals(False)
        self._stage_menu.setCurrentIndex(0)
        self._refresh_de_list()
        self._refresh_metrics_display()
        self._refresh_dimensions_display()

    def _on_stage_selected(self, _=None):
        self._refresh_de_list()
        QTimer.singleShot(0, self._refresh_metrics_display)
        QTimer.singleShot(0, self._refresh_dimensions_display)

    def _refresh_de_list(self):
        """Update _current_de_items from current source selection. No widget creation."""
        for_types = self._selected_template["for_types"] if self._selected_template else \
                    {"tracker_option", "tracker_numeric", "aggregate", "indicator"}
        # DE/PA/PI kind filter (default: all kinds shown if checkboxes absent).
        kinds = {k for k, cb in getattr(self, "_kind_cbs", {}).items() if cb.isChecked()} \
                or {"DE", "PA", "PI"}
        items: list[dict] = []
        if self._src_prog_cb.isChecked():
            prog = getattr(self, "_current_prog", None)
            if prog:
                sname = self._stage_menu.currentText()
                if sname in ("— All stages —", "—", ""):
                    prog_des = [de for s in prog["stages"] for de in s["des"]]
                else:
                    stage = next((s for s in prog["stages"]
                                  if s["displayName"] == sname), None)
                    prog_des = stage["des"] if stage else []
                if "DE" in kinds:
                    items.extend(de for de in prog_des if de["type"] in for_types)
                # Program attributes (PA / TEA) — gender, age… (program-level)
                if "PA" in kinds:
                    items.extend(t for t in prog.get("teas", []) if t["type"] in for_types)
                # Program indicators (program-level, queried as dx)
                if "PI" in kinds:
                    items.extend(p for p in prog.get("pis", []) if p["type"] in for_types)
        # Aggregate DEs + Indicators — each picker has its own search box, so we pass the
        # full pool here and let the picker filter (no second source-level search).
        if self._src_agg_cb.isChecked():
            items.extend(de for de in self._agg_des if "aggregate" in for_types)
        # Indicators — standalone dx source (independent of datasets), queried as dx.
        if hasattr(self, "_src_ind_cb") and self._src_ind_cb.isChecked():
            items.extend(ind for ind in self._agg_indicators if "indicator" in for_types)
        # Metrics/dimensions come ONLY from the Metadata Library's in-use list. An empty
        # selection means "not configured yet" → offer nothing (the pickers show a prompt
        # to open the Metadata Library — see _refresh_metrics_display).
        in_use = getattr(self, "_in_use", set())
        items = [it for it in items if it.get("uid") in in_use]
        self._current_de_items = items

    # =========================================================================
    # Chart type selection
    # =========================================================================

    def _on_chart_type_click(self, tmpl: dict):
        self._selected_template = tmpl
        plugin = tmpl.get("plugin")
        self._selected_plugin = plugin

        # Derive max/min from plugin MetricControls (authoritative source)
        if plugin and getattr(plugin, "metrics", []):
            self._max_des = max(mc.max_count for mc in plugin.metrics)
            self._min_des = sum(1 for mc in plugin.metrics if getattr(mc, "required", True))
        else:
            self._min_des = tmpl.get("min_sources", 1)
            self._max_des = tmpl.get("max_sources", 1 if not tmpl.get("multi") else 3)

        self._chart_info_lbl.setText(tmpl.get("description", ""))
        self._chart_info_lbl.setStyleSheet("font-size:9px; color:#5a7a9a; background:transparent;")

        prog_ok = bool({"tracker_option", "tracker_numeric"} & tmpl["for_types"])
        agg_ok  = "aggregate" in tmpl["for_types"]
        ind_ok  = "indicator" in tmpl["for_types"]
        self._src_prog_cb.setEnabled(prog_ok)
        self._src_agg_cb.setEnabled(agg_ok)
        self._src_ind_cb.setEnabled(ind_ok)
        if not prog_ok:
            self._src_prog_cb.setChecked(False)
        if not agg_ok:
            self._src_agg_cb.setChecked(False)
        if not ind_ok:
            self._src_ind_cb.setChecked(False)
        if not (self._src_prog_cb.isChecked() or self._src_agg_cb.isChecked()
                or self._src_ind_cb.isChecked()):
            if prog_ok:
                self._src_prog_cb.setChecked(True)
            elif agg_ok:
                self._src_agg_cb.setChecked(True)
            elif ind_ok:
                self._src_ind_cb.setChecked(True)

        # Update picker max — picker preserves compatible selections automatically
        self._metrics_picker.set_max_count(self._max_des)

        # Highlight tiles
        for tid, tile in self._chart_tiles.items():
            tile.set_selected(tid == tmpl["id"])

        self._on_src_check()
        self._collapse_chart_grid()
        self._rebuild_chart_options()
        self._refresh_metrics_display()
        self._refresh_dimensions_display()
        self._update_metrics_agg_visibility()
        self._update_action_buttons()
        self._auto_preview()

    # =========================================================================
    # Metrics display
    # =========================================================================

    _NO_METADATA_HINT = ("⚠ No metadata in use — open “Metadata Library” "
                         "(sidebar) and move data elements into the In-use list.")

    def _refresh_metrics_display(self, *_):
        """Update metrics picker with current available DEs."""
        self._refresh_de_list()
        self._metrics_picker.set_items(self._current_de_items)
        # Nothing curated yet → tell the user to configure the Metadata Library.
        self._metrics_picker.set_placeholder(
            self._NO_METADATA_HINT if not self._in_use else None)
        # Update the section label to reflect max
        if self._min_des == self._max_des:
            lbl = str(self._max_des)
        else:
            lbl = f"{self._min_des}–{self._max_des}"
        self._metrics_section_lbl.setText(f"3. METRICS  (SELECT {lbl})")

    # =========================================================================
    # Dimensions display
    # =========================================================================

    def _refresh_dimensions_display(self):
        """Update SelectControls, time grain visibility, dimension picker, filter lists."""
        plugin_cls = self._selected_template.get("plugin") if self._selected_template else None

        # ── SelectControls ──────────────────────────────────────────────────────
        while self._select_controls_lay.count():
            item = self._select_controls_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_color_scheme = False
        if plugin_cls and getattr(plugin_cls, "options", []):
            self._select_controls_frame.setVisible(True)
            old_vals = {k: v.get() for k, v in self._select_vars.items()}
            self._select_vars = {}
            old_text = {k: v.toPlainText() for k, v in self._textarea_vars.items()}
            self._textarea_vars = {}
            self._html_highlighter = None
            for sc in plugin_cls.options:
                # Large free-form editor (e.g. Custom HTML template): full-width, tall.
                if isinstance(sc, TextAreaControl):
                    box = QWidget()
                    box.setStyleSheet("background:transparent;")
                    box_lay = QVBoxLayout(box)
                    box_lay.setContentsMargins(0, 2, 0, 2)
                    box_lay.setSpacing(2)
                    box_lay.addWidget(QLabel(sc.label + ":"))
                    editor = QPlainTextEdit()
                    editor.setPlainText(old_text.get(sc.id, sc.default))
                    if sc.placeholder:
                        editor.setPlaceholderText(sc.placeholder)
                    editor.setMinimumHeight(sc.height)
                    if sc.monospace:
                        editor.setStyleSheet(
                            "QPlainTextEdit{font-family:Consolas,'Courier New',monospace;"
                            "font-size:11px;background:#ffffff;color:#1e2d3d;"
                            "border:1px solid #c0cdd8;border-radius:4px;}")
                    editor.textChanged.connect(self._schedule_preview_refresh)
                    box_lay.addWidget(editor)
                    self._textarea_vars[sc.id] = editor
                    # HTML syntax highlighting + {{metric/dimension}} variable highlighting,
                    # plus an "AI generate from image" button.
                    if sc.id == "html":
                        from ui.html_highlighter import HtmlTemplateHighlighter
                        self._html_highlighter = HtmlTemplateHighlighter(
                            editor.document(), self._html_known_vars())
                        self._html_ai_btn = QPushButton("🤖 Generate from image…")
                        self._html_ai_btn.setStyleSheet(
                            "QPushButton{font-size:11px;padding:4px 10px;border:1px solid #1a6fa8;"
                            "border-radius:4px;background:#eaf3fa;color:#1a6fa8;}"
                            "QPushButton:hover{background:#d6e9f7;}"
                            "QPushButton:disabled{color:#9bb3c4;border-color:#c5d6e2;background:#f2f6f9;}")
                        self._html_ai_btn.setToolTip(
                            "Upload an image (table/mock-up) → Claude generates matching HTML")
                        self._html_ai_btn.clicked.connect(self._on_html_from_image)
                        self._html_lib_btn = QPushButton("📁 Templates")
                        self._html_lib_btn.setStyleSheet(
                            "QPushButton{font-size:11px;padding:4px 10px;border:1px solid #5a7a9a;"
                            "border-radius:4px;background:#f2f6f9;color:#5a7a9a;}"
                            "QPushButton:hover{background:#e3ecf2;}")
                        self._html_lib_btn.setToolTip(
                            "Browse saved templates and load one without re-generating")
                        self._html_lib_btn.clicked.connect(self._on_open_html_gallery)
                        btn_row = QHBoxLayout()
                        btn_row.setContentsMargins(0, 0, 0, 0)
                        btn_row.addWidget(self._html_ai_btn)
                        btn_row.addWidget(self._html_lib_btn)
                        btn_row.addStretch(1)
                        box_lay.addLayout(btn_row)
                    self._select_controls_lay.addWidget(box)
                    continue

                row_w = QWidget()
                row_w.setStyleSheet("background:transparent;")
                row_lay = QHBoxLayout(row_w)
                row_lay.setContentsMargins(0, 1, 0, 1)
                row_lay.setSpacing(6)

                lbl = QLabel(sc.label + ":")
                lbl.setStyleSheet("font-size:9px; color:#5a7a9a; background:transparent; min-width:72px;")
                row_lay.addWidget(lbl)

                if isinstance(sc, CheckboxGroupControl):
                    # Multi-select: any subset of choices can be active
                    default_val = ",".join(sc.default)
                    prev = old_vals.get(sc.id, default_val)
                    widget = _MultiToggleWidget(list(sc.choices), parent=row_w)
                    widget.set(prev)
                    widget.changed.connect(self._on_select_control_change)
                    row_lay.addWidget(widget)
                else:
                    # Single-select (SelectControl) — with a custom-value affordance so
                    # the user can type/pick any value beyond the presets (REQ-UI-OPT-01).
                    prev = old_vals.get(sc.id, sc.default)
                    val  = prev if prev else sc.default
                    widget = SegmentedButton(list(sc.choices), default=val,
                                             custom=self._custom_kind(sc.id))
                    widget.changed.connect(self._on_select_control_change)
                    row_lay.addWidget(widget)
                    row_lay.addStretch()

                self._select_vars[sc.id] = widget
                self._select_controls_lay.addWidget(row_w)
                if sc.id == "color_scheme":
                    has_color_scheme = True
        else:
            self._select_controls_frame.setVisible(False)
            self._select_vars = {}
            self._textarea_vars = {}

        # Hide plain color swatches when plugin provides its own color_scheme control
        if hasattr(self, "_color_section_lbl"):
            self._color_section_lbl.setVisible(not has_color_scheme)
        if hasattr(self, "_color_swatch_row"):
            self._color_swatch_row.setVisible(not has_color_scheme)

        # ── Time grain ──────────────────────────────────────────────────────────
        has_time_grain = False
        if plugin_cls:
            has_time_grain = plugin_cls.time_grain is not None
        elif self._selected_template:
            tid = self._selected_template.get("id", "")
            has_time_grain = any(x in tid for x in (
                "monthly", "trend", "line", "multi", "stacked", "grouped", "combined"))
        self._time_grain_row.setVisible(has_time_grain)

        # ── Dimension ───────────────────────────────────────────────────────────
        dim_hint = ""
        if plugin_cls and plugin_cls.dimensions:
            _dc = plugin_cls.dimensions[0]
            dim_hint = _dc.hint
            # Tables allow multiple dimensions with aliases (like metrics); others stay single.
            self._dim_picker.set_max_count(getattr(_dc, "max_count", 1))
            self._dim_picker.set_show_alias(getattr(_dc, "show_alias", False))
        elif self._selected_template:
            tid = self._selected_template.get("id", "")
            if "stacked" in tid:
                dim_hint = "Each option value becomes one stack layer"
            elif "pie" in tid:
                dim_hint = "Each option value becomes one pie slice"
            elif "line" in tid:
                dim_hint = "Split into multiple lines by option value"

        self._dim_picker.set_items(self._current_de_items)
        self._dim_picker.set_placeholder(
            self._NO_METADATA_HINT if not self._in_use else None)
        self._dim_hint_lbl.setText(dim_hint)
        # Only show the split-by picker for chart types that actually support a dimension
        # (e.g. maps declare none, so it must stay hidden — it was being ignored before).
        plugin = self._selected_plugin
        has_dims = bool(plugin and getattr(plugin, "dimensions", []))
        self._dim_picker_row.setVisible(bool(self._selected_template) and has_dims)

        # ── Refresh filter DE dropdowns ─────────────────────────────────────────
        from ui.metadata_display import plain_label
        de_names = ["—"] + [plain_label(d) for d in self._current_de_items]
        de_map   = {plain_label(d): d for d in self._current_de_items}
        for r in self._filter_rows:
            cur = r["de_menu"].currentText()
            r["de_menu"].blockSignals(True)
            r["de_menu"].clear()
            r["de_menu"].addItems(de_names)
            if cur in de_names:
                r["de_menu"].setCurrentText(cur)
            r["de_menu"].blockSignals(False)
            r["de_map"] = de_map

    # =========================================================================
    # Filter rows
    # =========================================================================

    def _add_filter_row(self):
        from ui.metadata_display import plain_label
        de_names = ["—"] + [plain_label(d) for d in self._current_de_items]
        de_map   = {plain_label(d): d for d in self._current_de_items}

        row_w = QWidget()
        row_w.setStyleSheet("background:transparent;")
        row_lay = QHBoxLayout(row_w)
        row_lay.setContentsMargins(0, 1, 0, 1)
        row_lay.setSpacing(3)

        _RH = 26   # uniform row height so all controls on the filter row line up

        # Searchable field dropdown — type to filter long DE/PA lists.
        de_menu = QComboBox()
        de_menu.addItems(de_names)
        de_menu.setEditable(True)
        de_menu.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        de_menu.lineEdit().setPlaceholderText("Search field…")
        comp = de_menu.completer()
        comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        de_menu.setCurrentIndex(0)
        de_menu.setFixedHeight(_RH)
        de_menu.setFixedWidth(150)
        _style_combo(de_menu)
        from ui.metadata_display import TypePrefixDelegate
        de_menu.view().setItemDelegate(TypePrefixDelegate(de_menu))
        row_lay.addWidget(de_menu)

        op_menu = QComboBox()
        op_menu.addItems(self._FILTER_OPS)
        op_menu.setFixedHeight(_RH)
        op_menu.setFixedWidth(70)
        _style_combo(op_menu)
        row_lay.addWidget(op_menu)

        # Value: free text by default; an option dropdown when the field has an option set.
        val_entry = QLineEdit()
        val_entry.setFixedHeight(_RH)
        val_entry.setPlaceholderText("value")
        row_lay.addWidget(val_entry, stretch=1)

        val_combo = QComboBox()
        val_combo.setFixedHeight(_RH)
        _style_combo(val_combo)
        val_combo.setVisible(False)
        row_lay.addWidget(val_combo, stretch=1)

        row_data = dict(
            frame=row_w,
            de_menu=de_menu,
            op_menu=op_menu,
            val_entry=val_entry,
            val_combo=val_combo,
            de_map=de_map,
        )
        de_menu.currentTextChanged.connect(
            lambda _t, rd=row_data: self._on_filter_de_changed(rd))

        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(_RH, _RH)
        rm_btn.setStyleSheet(
            "QPushButton { background:#f0f4f8; border:1px solid #c0cdd8; "
            "border-radius:3px; color:#8aa3b8; font-size:10px; }"
            "QPushButton:hover { background:#e8eef5; }"
        )
        rm_btn.clicked.connect(lambda _, rd=row_data: self._remove_filter_row(rd))
        row_lay.addWidget(rm_btn)

        self._filter_rows.append(row_data)
        self._filter_rows_lay.addWidget(row_w)

    def _on_filter_de_changed(self, rd: dict):
        """When the filter field is an option-set DE/PA, offer its captured option
        values as a dropdown instead of free text (REQ: pick from value set)."""
        de = rd["de_map"].get(rd["de_menu"].currentText(), {})
        opts = de.get("options") or []
        vc = rd["val_combo"]
        rd["use_combo"] = bool(opts)
        if opts:
            vc.blockSignals(True)
            vc.clear()
            vc.addItem("—", "")
            for o in opts:
                vc.addItem(o.get("name", o.get("code", "")), o.get("code", ""))
            vc.blockSignals(False)
            vc.setVisible(True)
            rd["val_entry"].setVisible(False)
        else:
            vc.setVisible(False)
            rd["val_entry"].setVisible(True)

    def _filter_value(self, rd: dict) -> str:
        """Current filter value from whichever value widget is active (option set → code)."""
        if rd.get("use_combo") and rd.get("val_combo") is not None:
            return (rd["val_combo"].currentData() or "").strip()
        return rd["val_entry"].text().strip()

    def _remove_filter_row(self, row_data: dict):
        row_data["frame"].setParent(None)
        row_data["frame"].deleteLater()
        self._filter_rows = [r for r in self._filter_rows if r is not row_data]

    @staticmethod
    def _custom_kind(ident: str):
        """Custom input ONLY where a free value is genuinely useful (colour / size).
        Enum-style controls (mode, base map, x-axis…) return None → no custom affordance."""
        n = (ident or "").lower()
        if ("color" in n or "colour" in n) and "scheme" not in n:
            return "color"   # single-colour controls (point_color, value_color, …)
        if any(k in n for k in ("size", "scale", "width", "height", "radius",
                                "rotation", "row_limit", "thickness")):
            return "number"
        return None

    def _on_select_control_change(self, *_):
        self._update_metrics_agg_visibility()
        self._schedule_preview_refresh()

    def _update_metrics_agg_visibility(self):
        """Hide the per-metric aggregation dropdown for a raw Data Table (no aggregation)."""
        tid = self._selected_template.get("id", "") if self._selected_template else ""
        mode_seg = self._select_vars.get("mode")
        is_raw_table = (tid == "table_view" and mode_seg is not None
                        and mode_seg.get() == "Raw")
        self._metrics_picker.set_show_agg(not is_raw_table)

    # =========================================================================
    # DE list helpers
    # =========================================================================

    def _clear_de_list(self, msg: str = "Select chart type first"):
        self._current_de_items = []
        self._metrics_picker.set_items([])

    def _populate_de_list(self, items: list[dict],
                          preserve_checked: set[str] | None = None):
        self._current_de_items = items
        self._metrics_picker.set_items(items)

    def _on_de_check(self):
        sel = self._get_selected_des()
        # Sync _selected_metrics (used in _build_config); include options for optionSet DEs
        self._selected_metrics = [
            {"uid": d["uid"], "name": d.get("name", d["uid"]), "type": d.get("type", ""),
             "agg": d.get("agg", "SUM"),
             "alias": d.get("alias", ""),
             "prog_uid": d.get("prog_uid", ""), "stage_uid": d.get("stage_uid", ""),
             "options": d.get("options", [])}
            for d in sel
        ]
        self._update_action_buttons()
        self._update_html_known_vars()   # recolor {{metric}} vars in the Custom HTML editor
        if self._mode_fixed_rb.isChecked() and len(sel) >= self._min_des:
            self._auto_preview()

    def _get_selected_des(self) -> list[dict]:
        return self._metrics_picker.get_selected_des()

    # =========================================================================
    # Dynamic Chart Options
    # =========================================================================

    def _rebuild_chart_options(self):
        while self._dyn_opts_lay.count():
            item = self._dyn_opts_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._option_vars = {}
        self._chart_options = {}

        tmpl = self._selected_template
        if not tmpl:
            lbl = QLabel("← Select a chart type to see options")
            lbl.setStyleSheet("font-size:9px; color:#8aa3b8; background:transparent;")
            self._dyn_opts_lay.addWidget(lbl)
            return

        config = CHART_STYLE_CONFIGS.get(tmpl["id"], [])
        if not config:
            lbl = QLabel("No style options for this chart type.")
            lbl.setStyleSheet("font-size:9px; color:#8aa3b8; background:transparent;")
            self._dyn_opts_lay.addWidget(lbl)
            return

        check_opts  = [o for o in config if o["type"] == "check"]
        other_opts  = [o for o in config if o["type"] != "check"]

        # Checkboxes: 2 per row
        for row_i in range(0, len(check_opts), 2):
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            row_lay = QHBoxLayout(row_w)
            row_lay.setContentsMargins(0, 1, 0, 1)
            row_lay.setSpacing(14)
            for opt in check_opts[row_i:row_i + 2]:
                cb = QCheckBox(opt["label"])
                cb.setChecked(bool(opt.get("default", False)))
                cb.setStyleSheet("font-size:10px;")
                cb.stateChanged.connect(self._apply_chart_options)
                self._option_vars[opt["id"]] = cb
                row_lay.addWidget(cb)
            row_lay.addStretch()
            self._dyn_opts_lay.addWidget(row_w)

        # Segments and entries
        for opt in other_opts:
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            row_lay = QHBoxLayout(row_w)
            row_lay.setContentsMargins(0, 2, 0, 2)
            row_lay.setSpacing(6)

            lbl = QLabel(opt["label"] + ":")
            lbl.setStyleSheet("font-size:9px; color:#5a7a9a; background:transparent;")
            row_lay.addWidget(lbl)

            if opt["type"] == "segment":
                default_val = opt.get("default", opt["values"][0])
                seg = SegmentedButton(opt["values"], default=default_val,
                                      custom=self._custom_kind(opt.get("id", opt.get("label", ""))))
                seg.changed.connect(lambda _: self._apply_chart_options())
                self._option_vars[opt["id"]] = seg
                row_lay.addWidget(seg)

            elif opt["type"] == "entry":
                entry = QLineEdit()
                entry.setFixedWidth(180)
                entry.setFixedHeight(24)
                entry.setPlaceholderText(opt.get("hint", opt["label"]))
                entry.setText(opt.get("default", ""))
                entry.editingFinished.connect(self._apply_chart_options)
                self._option_vars[opt["id"]] = entry
                row_lay.addWidget(entry)

            row_lay.addStretch()
            self._dyn_opts_lay.addWidget(row_w)

    def _apply_chart_options(self, *_):
        from llm.chart_customizer import deep_merge
        opts: dict = {}
        for opt_id, var in self._option_vars.items():
            if isinstance(var, QCheckBox):
                value = var.isChecked()
            elif isinstance(var, SegmentedButton):
                value = var.get()
            elif isinstance(var, QLineEdit):
                value = var.text()
            else:
                continue
            patch = _option_to_chartjs(opt_id, value)
            if patch:
                opts = deep_merge(opts, patch)
        self._chart_options = opts
        self._schedule_preview_refresh()

    # =========================================================================
    # Style controls
    # =========================================================================

    def _on_color_select(self, color: str):
        self._selected_color = color
        # If the colour isn't a preset, show it on the custom swatch so it stays visible.
        if hasattr(self, "_custom_color_swatch") and \
           color not in [c for c, _ in COLOR_PRESETS]:
            self._custom_color_swatch._color = color
            self._custom_color_swatch.setVisible(True)
        for swatch in self._color_swatches:
            swatch._set_selected(swatch._color == color)
        self._schedule_preview_refresh()

    def _on_pick_custom_color(self):
        col = QColorDialog.getColor()
        if not col.isValid():
            return
        self._on_color_select(col.name())

    def _on_mode_change(self):
        is_ai = self._mode_ai_rb.isChecked()
        self._ai_desc_wrap.setVisible(is_ai)

    # =========================================================================
    # Preview
    # =========================================================================

    def _auto_preview(self):
        self._schedule_preview_refresh()

    def _schedule_preview_refresh(self):
        self._update_html_known_vars()
        self._preview_timer.stop()
        self._preview_timer.start(400)

    def _html_known_vars(self) -> set[str]:
        """Column names that will exist in window.__chartData = metric + dimension display
        names (alias or original) + the Raw-mode standard columns."""
        names: set[str] = {"Event date", "Org unit"}
        try:
            picks = self._metrics_picker.get_selected_des() + self._dim_picker.get_selected_des()
        except Exception:
            picks = []
        for d in picks:
            label = (d.get("alias") or "").strip() or d.get("name", "")
            if label:
                names.add(label)
        return names

    def _update_html_known_vars(self):
        """Refresh the HTML editor's {{variable}} highlighting against the current columns."""
        hl = getattr(self, "_html_highlighter", None)
        if hl is not None:
            hl.set_known_vars(self._html_known_vars())

    def _do_refresh(self):
        from ui.preview_server import _browser_opened
        if _browser_opened:
            self._on_preview_browser()

    def _on_preview_browser(self):
        cfg = self._build_config()
        if not cfg:
            QMessageBox.warning(self, "Preview",
                                "Select chart type and data element(s) first.")
            return
        from charts.fixed_templates import generate_preview_page
        from ui.preview_window import update_preview
        from ui.debug_logger import log_action
        metrics_summary = "; ".join(
            f"{m.get('name','?')} [{m.get('type','?')}]"
            for m in (cfg.get("metrics") or [])
        )
        log_action("PREVIEW", f"plugin={cfg.get('plugin_id','?')} metrics=[{metrics_summary}] "
                   f"ou_level={((cfg.get('plugin_options') or {}).get('ou_level',''))} "
                   f"pe={((cfg.get('time_grain') or {}).get('period',''))}")
        html = generate_preview_page(cfg, title=cfg["title"])
        update_preview(html, title=cfg.get("title", "Chart Preview"))

    # =========================================================================
    # AI Customize
    # =========================================================================

    def _toggle_ai_chat(self):
        self._ai_chat_visible = not self._ai_chat_visible
        self._ai_chat_panel.setVisible(self._ai_chat_visible)
        self._ai_chat_toggle_btn.setText(
            "🤖  AI Customize  ▼" if self._ai_chat_visible else "🤖  AI Customize  ▶"
        )

    def _append_chat(self, role: str, text: str):
        prefix = "You: " if role == "user" else "AI: "
        self._chat_display_text += f"{prefix}{text}\n"
        self._chat_display.setReadOnly(False)
        self._chat_display.setPlainText(self._chat_display_text)
        self._chat_display.setReadOnly(True)
        sb = self._chat_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_ai_customize(self):
        request = self._ai_input.text().strip()
        if not request:
            return
        tmpl = self._selected_template
        if not tmpl:
            self._append_chat("ai", "⚠ Select a chart type first.")
            return
        api_key = self._callbacks.get("get_api_key", lambda: "")()
        if not api_key:
            self._append_chat("ai", "⚠ No Anthropic API key — enter it in the sidebar.")
            return
        self._append_chat("user", request)
        self._ai_input.clear()
        self._append_chat("ai", "⏳ Thinking…")
        threading.Thread(
            target=self._ai_customize_worker,
            args=(request, tmpl, api_key),
            daemon=True,
        ).start()

    def _ai_customize_worker(self, request: str, tmpl: dict, api_key: str):
        try:
            from llm.chart_customizer import customize_chart, deep_merge
            model = self._callbacks.get("get_model", lambda: "claude-haiku-4-5-20251001")()
            patch = customize_chart(
                template_label=tmpl["label"],
                current_custom_options=self._custom_options,
                user_request=request,
                api_key=api_key,
                model=model,
            )
            self._custom_options = deep_merge(self._custom_options, patch)
            import json
            summary = json.dumps(patch, ensure_ascii=False)
            self._call_main.emit(lambda: self._on_ai_customize_done(summary))
        except Exception as exc:
            self._call_main.emit(lambda e=exc: self._on_ai_customize_done(f"Error: {e}"))

    def _on_ai_customize_done(self, summary: str):
        lines = self._chat_display_text.rstrip("\n").split("\n")
        if lines and "⏳" in lines[-1]:
            lines = lines[:-1]
        self._chat_display_text = "\n".join(lines) + "\n"
        self._append_chat(
            "ai",
            f"✓ Applied: {summary[:120]}{'…' if len(summary) > 120 else ''}",
        )
        self._schedule_preview_refresh()

    # ── AI: generate HTML from an uploaded image (Custom HTML widget) ──────────

    def _load_image_for_ai(self, path: str):
        """Read + downscale an image (≤1568px long edge) → (png_bytes, 'image/png')."""
        from PySide6.QtGui import QImage
        from PySide6.QtCore import QBuffer, QByteArray, Qt
        img = QImage(path)
        if img.isNull():
            return None, None
        if max(img.width(), img.height()) > 1568:
            img = img.scaled(1568, 1568, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        return bytes(ba), "image/png"

    def _on_html_from_image(self):
        ed = self._textarea_vars.get("html")
        if ed is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose an image to reproduce as HTML", "",
            "Images (*.png *.jpg *.jpeg *.webp *.gif)")
        if not path:
            return
        data, media = self._load_image_for_ai(path)
        if not data:
            QMessageBox.warning(self, "AI", "Could not read that image.")
            return
        # Dedup: same image already generated? Offer to reuse the saved HTML (no API call).
        import config.html_template_library as htl
        existing = htl.find_by_hash(htl.image_hash(data))
        if existing:
            box = QMessageBox(self)
            box.setWindowTitle("Image already generated")
            box.setIcon(QMessageBox.Icon.Question)
            box.setText(f"This image was generated before — \"{existing.get('name', '')}\".\n"
                        "Reuse the saved HTML, or regenerate via the API?")
            reuse_btn  = box.addButton("Reuse saved", QMessageBox.ButtonRole.AcceptRole)
            regen_btn  = box.addButton("Regenerate",  QMessageBox.ButtonRole.DestructiveRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(reuse_btn)
            box.exec()
            clicked = box.clickedButton()
            if clicked is reuse_btn:
                ed.setPlainText(existing.get("html", ""))
                self._schedule_preview_refresh()
                return
            if clicked is not regen_btn:
                return
            # else: fall through and regenerate
        api_key = self._callbacks.get("get_api_key", lambda: "")()
        if not api_key:
            QMessageBox.warning(self, "AI", "No Anthropic API key — enter it in the sidebar.")
            return
        if QMessageBox.question(
                self, "Send image to AI",
                "The image will be sent to the Anthropic API to generate HTML. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes) != QMessageBox.StandardButton.Yes:
            return
        model = self._callbacks.get("get_model", lambda: "claude-haiku-4-5-20251001")()
        self._html_ai_model = _short_model_name(model)   # shown on the button
        if hasattr(self, "_html_ai_btn"):
            self._html_ai_btn.setEnabled(False)
            self._html_ai_btn.setText(f"⏳ Generating by {self._html_ai_model}… 0s")
        # Live elapsed-time ticker so a 15–60s vision call doesn't look frozen.
        self._html_ai_secs = 0
        if not getattr(self, "_html_ai_timer", None):
            self._html_ai_timer = QTimer(self)
            self._html_ai_timer.setInterval(1000)
            self._html_ai_timer.timeout.connect(self._html_ai_tick)
        self._html_ai_timer.start()
        cols = sorted(self._html_known_vars())
        threading.Thread(target=self._html_from_image_worker,
                         args=(data, media, api_key, cols, model), daemon=True).start()

    def _on_open_html_gallery(self):
        ed = self._textarea_vars.get("html")
        if ed is None:
            return
        from ui.html_template_gallery import HtmlTemplateGallery
        dlg = HtmlTemplateGallery(self)
        dlg.exec()
        if dlg.result_html is not None:
            ed.setPlainText(dlg.result_html)
            self._schedule_preview_refresh()

    def _html_ai_tick(self):
        self._html_ai_secs = getattr(self, "_html_ai_secs", 0) + 1
        if hasattr(self, "_html_ai_btn"):
            m = getattr(self, "_html_ai_model", "AI")
            self._html_ai_btn.setText(f"⏳ Generating by {m}… {self._html_ai_secs}s")

    def _html_from_image_worker(self, data: bytes, media: str, api_key: str, cols: list, model: str):
        try:
            from llm.html_from_image import generate_html_from_image
            html = generate_html_from_image(data, media, api_key, model, columns=cols)
            # Persist image + result so it can be reused without re-generating.
            try:
                import config.html_template_library as htl
                htl.save_template(data, html, model=model)
            except Exception:
                pass
            self._call_main.emit(lambda: self._on_html_from_image_done(html, None))
        except Exception as exc:
            self._call_main.emit(lambda e=exc: self._on_html_from_image_done(None, str(e)))

    def _on_html_from_image_done(self, html, err):
        if getattr(self, "_html_ai_timer", None):
            self._html_ai_timer.stop()
        if hasattr(self, "_html_ai_btn"):
            self._html_ai_btn.setEnabled(True)
            self._html_ai_btn.setText("🤖 Generate from image…")
        if err:
            QMessageBox.warning(self, "AI generate failed", err)
            return
        ed = self._textarea_vars.get("html")
        if ed is not None and html:
            ed.setPlainText(html)
            self._schedule_preview_refresh()

    def _on_reset_customization(self):
        self._custom_options = {}
        self._quick_options  = {}
        self._chart_options  = {}
        self._chat_history   = []
        self._chat_display_text = ""
        self._chat_display.setReadOnly(False)
        self._chat_display.clear()
        self._chat_display.setReadOnly(True)
        self._rebuild_chart_options()

    # =========================================================================
    # Build config — EXACT same logic as CTk version
    # =========================================================================

    def _build_config(self) -> dict | None:
        tmpl = self._selected_template
        if not tmpl:
            return None
        sel = self._get_selected_des()
        if len(sel) < self._min_des:
            return None
        de    = sel[0]
        title = self._title_entry.text().strip()
        if not title:
            title = de["name"] if len(sel) == 1 else \
                    " vs ".join(d["name"][:20] for d in sel[:2])

        seg_to_key = {"Full": "Full  (12)", "Half": "Half  (6)", "Third": "Third (4)"}
        col_w = COL_WIDTH_OPTIONS.get(
            seg_to_key.get(self._col_width_seg.get(), "Half  (6)"), 6
        )

        from llm.chart_customizer import deep_merge
        user_opts = deep_merge(self._custom_options,
                               deep_merge(self._quick_options, self._chart_options))

        # Only apply single color override when no dimension is configured.
        dimension_de = self._dim_picker.get_first_de()
        _has_dim = dimension_de is not None
        if de.get("type") not in ("tracker_option",) and not _has_dim:
            color_base = {"datasets": [{"backgroundColor": self._selected_color,
                                         "borderColor":     self._selected_color}]}
            merged_opts = deep_merge(color_base, user_opts)
        else:
            merged_opts = user_opts

        # Collect metrics (with agg) — fall back to plain sel if metric_rows empty
        metrics = self._selected_metrics if self._selected_metrics else [
            {"uid": d["uid"], "name": d["name"], "type": d["type"], "agg": "SUM"}
            for d in sel
        ]
        # Apply per-metric alias: render layers use `name`, so the alias becomes the
        # displayed label / column header. `orig_name` keeps the real DE name.
        metrics = [
            {**m, "orig_name": m.get("orig_name", m["name"]),
             "name": (m.get("alias") or "").strip() or m.get("orig_name", m["name"])}
            for m in metrics
        ]

        # Dimensions: support MULTIPLE (data table) with per-item alias (like metrics).
        # `dimension` keeps the first for back-compat (bar/pie/line read it); `group_by`
        # carries all selected dims (and feeds _extra_params' &dimension= params).
        dim_des = [
            {**d, "orig_name": d.get("orig_name", d["name"]),
             "name": (d.get("alias") or "").strip() or d.get("orig_name", d["name"])}
            for d in self._dim_picker.get_selected_des()
        ]
        dimension_de = dim_des[0] if dim_des else None
        group_by = dim_des

        # Collect filters
        op_map = self.__class__._OP_MAP
        filters = []
        for r in self._filter_rows:
            de_name = r["de_menu"].currentText()
            if de_name == "—":
                continue
            de_obj = r["de_map"].get(de_name, {})
            val = self._filter_value(r)
            if not val:
                continue
            op_display = r["op_menu"].currentText()
            op_dhis2 = op_map.get(op_display, op_display)
            filters.append({
                "de_uid":  de_obj.get("uid", ""),
                "de_name": de_obj.get("name", de_name),   # store the plain name, not "(DE) …"
                "de_type": de_obj.get("type", ""),
                "is_tea":  de_obj.get("is_tea", False),   # PA → bare-uid dimension
                "op":      op_dhis2,
                "value":   val,
            })

        # Row limit / sort
        limit_raw = self._row_limit_combo.currentText()
        row_limit = 0 if limit_raw == "All" else int(limit_raw)

        plugin_id = tmpl["id"].replace("ft_", "") if tmpl else None

        # plugin_options: SelectControls + style options
        plugin_options: dict = {}
        for k, seg in self._select_vars.items():
            plugin_options[k] = seg.get()
        for k, ta in self._textarea_vars.items():
            plugin_options[k] = ta.toPlainText()
        for opt_id, var in self._option_vars.items():
            if isinstance(var, QCheckBox):
                plugin_options[opt_id] = var.isChecked()
            elif isinstance(var, SegmentedButton):
                plugin_options[opt_id] = var.get()
            elif isinstance(var, QLineEdit):
                plugin_options[opt_id] = var.text()

        return {
            # ── New plugin-aware fields ──────────────────────────────────────
            "plugin_id":      plugin_id,
            "plugin_options": plugin_options,
            "source": {
                "type":       de.get("type", ""),
                "prog_uid":   de.get("prog_uid", ""),
                "prog_name":  de.get("prog_name", ""),
                "stage_uid":  de.get("stage_uid", ""),
                "stage_name": de.get("stage_name", ""),
            },
            "metrics": metrics,
            "dimensions": {
                "time_grain": self._time_grain_seg.get(),
                "dimension":  dimension_de,
                "group_by":   group_by,
                "filters":    filters,
                "row_limit":  row_limit,
                "sort_by":    self._sort_by_combo.currentText(),
                "sort_dir":   self._sort_dir_combo.currentText(),
                "breakdown":  None,
            },
            # ── Backward-compat fields ────────────────────────────────────────
            "template_id":    tmpl["id"],
            "template_label": tmpl["label"],
            "title":          title,
            "mode":           "ai" if self._mode_ai_rb.isChecked() else "fixed",
            "col_width":      col_w,
            "chart_color":    self._selected_color,
            "custom_options": merged_opts,
            "de_sources":     self._selected_metrics if self._selected_metrics else sel,
            "de_uid":         metrics[0]["uid"]  if metrics else "",
            "de_name":        metrics[0]["name"] if metrics else "",
            "de_type":        metrics[0]["type"] if metrics else "",
            "prog_uid":       de.get("prog_uid", ""),
            "prog_name":      de.get("prog_name", ""),
            "stage_uid":      de.get("stage_uid", ""),
            "stage_name":     de.get("stage_name", ""),
        }

    # =========================================================================
    # Actions
    # =========================================================================

    def _build_save_config(self) -> dict | None:
        """Build the config for saving (with ai_desc), or None + warning if invalid."""
        cfg = self._build_config()
        if not cfg:
            QMessageBox.warning(self, "Save Chart",
                                "Select a chart type and data element(s) first.")
            return None
        if self._mode_ai_rb.isChecked():
            cfg["ai_desc"] = self._ai_desc.toPlainText().strip()
        return cfg

    def _set_current_chart(self, saved: dict) -> None:
        """Remember which saved chart is being edited and reflect it in the header."""
        self._current_chart_id = saved.get("id")
        self._current_chart_name = saved.get("name") or saved.get("title")
        self._current_chart_description = saved.get("description", "")
        self._update_chart_name_lbl()
        self._update_action_buttons()

    def _update_chart_name_lbl(self) -> None:
        # Show the name whenever a chart is loaded — even a dashboard card (which has no
        # library id yet). Only a truly blank editor shows "new chart".
        if self._current_chart_name:
            tag = "editing" if self._current_chart_id else "opened"
            self._chart_name_lbl.setText(f"• {tag}: {self._current_chart_name}")
        else:
            self._chart_name_lbl.setText("• new chart")

    def _on_save(self):
        """Save: update the chart currently being edited, or save-as-new if none."""
        cfg = self._build_save_config()
        if cfg is None:
            return
        if not self._current_chart_id:
            # Nothing loaded → first save behaves like Save As (prompt for a name).
            self._save_as_new(cfg)
            return
        cfg["id"] = self._current_chart_id
        cfg["name"] = self._current_chart_name or cfg.get("title", "Chart")
        cfg["description"] = self._current_chart_description   # keep existing description
        from config.chart_library import save_chart
        saved = save_chart(cfg)
        self._set_current_chart(saved)
        if self._my_charts_visible:
            self._refresh_my_charts()
        cb = self._callbacks.get("on_chart_saved")
        if cb:
            cb(saved)
        QMessageBox.information(self, "Save Chart", f"Updated '{saved['name']}'.")

    def _on_save_as(self):
        """Save As: always create a NEW saved chart under a chosen name."""
        cfg = self._build_save_config()
        if cfg is None:
            return
        self._save_as_new(cfg)

    def _save_as_new(self, cfg: dict):
        from ui.save_entity_dialog import SaveEntityDialog
        res = SaveEntityDialog.prompt(
            self, title="Save Chart",
            name=self._current_chart_name or cfg.get("title", "Chart"),
            description=self._current_chart_description,
        )
        if not res:
            return
        name, description = res
        cfg.pop("id", None)            # force a brand-new entity
        cfg.pop("created_at", None)
        cfg["name"] = name
        cfg["description"] = description
        from config.chart_library import save_chart
        saved = save_chart(cfg)
        self._set_current_chart(saved)
        if self._my_charts_visible:
            self._refresh_my_charts()
        cb = self._callbacks.get("on_chart_saved")
        if cb:
            cb(saved)

    def _on_open_chart(self):
        """Open a saved chart back into the editor (parallels dashboard Load)."""
        from config.chart_library import load_charts
        from ui.load_chart_dialog import LoadChartDialog
        charts = load_charts()
        if not charts:
            QMessageBox.information(self, "Open Chart",
                                    "No saved charts yet.\nSave a chart first.")
            return
        dlg = LoadChartDialog(self, charts)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = dlg.get_selected()
            if selected:
                self._load_chart_config(selected)

    def _on_new(self):
        """Start a fresh chart: detach from any saved entity and clear the editor."""
        if self._selected_metrics or self._title_entry.text().strip():
            if QMessageBox.question(
                self, "New Chart",
                "Discard the current chart and start a new one?",
            ) != QMessageBox.StandardButton.Yes:
                return
        self._current_chart_id = None
        self._current_chart_name = None
        self._current_chart_description = ""
        self._reset_editor_fields()
        self._update_chart_name_lbl()
        self._update_action_buttons()

    def _reset_editor_fields(self):
        """Clear the user-entered content (title, metrics, filters, AI customizations)."""
        self._title_entry.clear()
        for rd in list(self._filter_rows):
            self._remove_filter_row(rd)
        try:
            self._metrics_picker.set_selected_uids([], {})
        except Exception:
            pass
        self._selected_metrics = []
        self._custom_options = {}
        self._chat_display_text = ""
        self._chat_display.setReadOnly(False)
        self._chat_display.setPlainText("")
        self._chat_display.setReadOnly(True)
        self._on_de_check()

    def _on_add_to_dashboard(self):
        cfg = self._build_config()
        if not cfg:
            QMessageBox.warning(self, "Add to Dashboard",
                                "Select a chart type and data element(s) first.")
            return
        if self._mode_ai_rb.isChecked():
            cfg["ai_desc"] = self._ai_desc.toPlainText().strip()
            ai_cb = self._callbacks.get("on_generate_ai")
            if ai_cb:
                ai_cb(cfg)
            return
        cfg.setdefault("name", cfg["title"])
        cb = self._callbacks.get("on_add_to_dashboard")
        if cb:
            cb(cfg)
        sw = self._callbacks.get("on_switch_to_dashboard")
        if sw:
            sw()

    # =========================================================================
    # Helpers
    # =========================================================================

    def _sec_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            "color:#8aa3b8; font-size:9px; font-weight:bold; "
            "padding:8px 12px 2px 12px; background:transparent;"
        )
        return lbl

    @staticmethod
    def _make_hdiv() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{BORDER_CLR}; border:none;")
        return line
