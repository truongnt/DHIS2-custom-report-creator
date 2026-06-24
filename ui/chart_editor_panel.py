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
    QLineEdit, QTextEdit, QComboBox, QScrollArea, QSplitter,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy,
    QInputDialog, QMessageBox, QButtonGroup,
)

from charts.fixed_templates import FIXED_TEMPLATES
from ui.qt_utils import SegmentedButton, section_label, divider, DHIS2_BLUE, PANEL_BG, BORDER_CLR

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

class ChartEditorPanel(QWidget):

    _FILTER_OPS = ["EQ", "≠ (NE)", "IN", ">", "≥", "<", "≤", "LIKE"]
    _OP_MAP = {
        "EQ": "EQ", "≠ (NE)": "NE", "IN": "IN",
        ">": "GT", "≥": "GE", "<": "LT", "≤": "LE", "LIKE": "LIKE",
    }

    def __init__(self, parent=None, callbacks: dict[str, Callable] | None = None, **kw):
        super().__init__(parent)
        self._callbacks = callbacks or {}

        # ── State ─────────────────────────────────────────────────────────────
        self._custom_options: dict = {}
        self._chat_history: list[tuple[str, str]] = []
        self._metadata: dict = {}
        self._programs: list[dict] = []
        self._agg_des: list[dict] = []
        self._current_de_items: list[dict] = []
        self._de_checkboxes: list[tuple[dict, QCheckBox]] = []
        self._metric_rows: list[tuple] = []          # (de, cb, agg_combo | None)
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

        # Dimension state
        self._select_vars: dict[str, SegmentedButton] = {}
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
        self.setStyleSheet(f"background:{PANEL_BG};")

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

        tmpl_icon = next((t["icon"] for t in FIXED_TEMPLATES
                          if t["id"] == chart.get("template_id")), "📊")
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
        tmpl = next((t for t in FIXED_TEMPLATES
                     if t["id"] == chart.get("template_id")), None)
        if tmpl:
            self._on_chart_type_click(tmpl)

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

        sources = chart.get("de_sources", [])
        if sources:
            first_de = sources[0]
            de_type = first_de.get("type", "")
            prog_name = first_de.get("prog_name", "")
            if de_type in ("tracker_option", "tracker_numeric") and prog_name:
                self._src_prog_cb.setChecked(True)
                self._src_agg_cb.setChecked(False)
                prog = next((p for p in self._programs
                             if p["displayName"] == prog_name), None)
                if prog:
                    idx = self._prog_menu.findText(prog_name)
                    if idx >= 0:
                        self._prog_menu.setCurrentIndex(idx)
                    self._on_prog_selected()
            elif de_type == "aggregate":
                self._src_prog_cb.setChecked(False)
                self._src_agg_cb.setChecked(True)
                self._on_src_check()

            saved_uids = {d.get("uid") for d in sources}
            QTimer.singleShot(100, lambda: self._try_select_saved_des(saved_uids))

    def _try_select_saved_des(self, uids: set):
        for de, cb, *_ in self._de_checkboxes:
            if de["uid"] in uids:
                cb.setChecked(True)
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
        outer_lay.setContentsMargins(10, 8, 10, 8)
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
        cb_lay.addStretch()
        outer_lay.addWidget(cb_row)

        # Program dropdown
        self._prog_menu = QComboBox()
        self._prog_menu.addItem("—")
        self._prog_menu.setFixedHeight(30)
        self._prog_menu.currentTextChanged.connect(self._on_prog_selected)
        outer_lay.addWidget(self._prog_menu)

        # Stage dropdown
        self._stage_menu = QComboBox()
        self._stage_menu.addItem("—")
        self._stage_menu.setFixedHeight(30)
        self._stage_menu.currentTextChanged.connect(self._on_stage_selected)
        outer_lay.addWidget(self._stage_menu)

        # Agg search entry (hidden by default)
        self._agg_search_entry = QLineEdit()
        self._agg_search_entry.setPlaceholderText("🔍 Search aggregate DEs...")
        self._agg_search_entry.setFixedHeight(30)
        self._agg_search_entry.textChanged.connect(self._refresh_metrics_display)
        self._agg_search_entry.setVisible(False)
        outer_lay.addWidget(self._agg_search_entry)

        parent_lay.addWidget(outer)

    # =========================================================================
    # Section 3: Metrics
    # =========================================================================

    def _build_metrics_section(self, parent_lay: QVBoxLayout):
        self._metrics_section_lbl = QLabel("3. METRICS  (TICK 1)")
        self._metrics_section_lbl.setStyleSheet(
            "color:#8aa3b8; font-size:9px; font-weight:bold; padding:6px 12px 2px 12px;"
            "background:transparent;"
        )
        parent_lay.addWidget(self._metrics_section_lbl)
        # Alias for backward compat
        self._de_section_lbl = self._metrics_section_lbl

        outer = _make_card()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(4, 6, 4, 4)
        outer_lay.setSpacing(4)

        # Search bar row
        search_row = QWidget()
        search_row.setStyleSheet("background:transparent;")
        sr_lay = QHBoxLayout(search_row)
        sr_lay.setContentsMargins(0, 0, 0, 0)
        sr_lay.setSpacing(2)

        self._de_search_entry = QLineEdit()
        self._de_search_entry.setPlaceholderText("🔍 Filter DEs...")
        self._de_search_entry.setFixedHeight(26)
        self._de_search_entry.textChanged.connect(self._on_de_search_changed)
        sr_lay.addWidget(self._de_search_entry, stretch=1)

        clr_btn = QPushButton("✕")
        clr_btn.setFixedSize(26, 26)
        clr_btn.setStyleSheet(
            "QPushButton { background:#e8eef5; border:1px solid #c0cdd8; "
            "border-radius:4px; color:#5a7a9a; font-size:10px; }"
            "QPushButton:hover { background:#d0dde8; }"
        )
        clr_btn.clicked.connect(lambda: self._de_search_entry.clear())
        sr_lay.addWidget(clr_btn)
        outer_lay.addWidget(search_row)

        # Scrollable DE list
        self._metrics_scroll = QScrollArea()
        self._metrics_scroll.setWidgetResizable(True)
        self._metrics_scroll.setFrameShape(QFrame.NoFrame)
        self._metrics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._metrics_scroll.setFixedHeight(140)
        self._metrics_scroll.setStyleSheet("background:white;")

        self._metrics_inner = QWidget()
        self._metrics_inner.setStyleSheet("background:white;")
        self._metrics_inner_lay = QVBoxLayout(self._metrics_inner)
        self._metrics_inner_lay.setContentsMargins(2, 2, 2, 2)
        self._metrics_inner_lay.setSpacing(1)

        placeholder = QLabel("Select chart type first")
        placeholder.setStyleSheet("color:#8aa3b8; font-size:10px;")
        placeholder.setAlignment(Qt.AlignCenter)
        self._metrics_inner_lay.addWidget(placeholder)
        self._metrics_inner_lay.addStretch()

        self._metrics_scroll.setWidget(self._metrics_inner)
        outer_lay.addWidget(self._metrics_scroll)

        # Alias
        self._de_scroll = self._metrics_scroll

        parent_lay.addWidget(outer)

        # Selected DEs label
        self._sel_lbl = QLabel("")
        self._sel_lbl.setStyleSheet(
            "color:#1565c0; font-size:10px; background:transparent; padding:2px 10px;"
        )
        self._sel_lbl.setWordWrap(True)
        parent_lay.addWidget(self._sel_lbl)

    def _on_de_search_changed(self, text: str):
        q = text.strip().lower()
        filtered = [i for i in self._current_de_items if q in i["name"].lower()] \
            if q else self._current_de_items
        checked = {de["uid"] for de, cb, *_ in self._de_checkboxes if cb.isChecked()}
        self._populate_de_list(filtered, preserve_checked=checked)

    # =========================================================================
    # Section: Dimensions
    # =========================================================================

    def _build_dimensions_section(self, parent_lay: QVBoxLayout):
        parent_lay.addWidget(self._sec_lbl("Dimensions"))

        outer = _make_card()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(8, 6, 8, 8)
        outer_lay.setSpacing(4)

        # ── SelectControls (plugin.options) ───────────────────────────────────
        self._select_controls_frame = QWidget()
        self._select_controls_frame.setStyleSheet("background:white;")
        self._select_controls_lay = QVBoxLayout(self._select_controls_frame)
        self._select_controls_lay.setContentsMargins(0, 0, 0, 0)
        self._select_controls_lay.setSpacing(2)
        self._select_controls_frame.setVisible(False)
        outer_lay.addWidget(self._select_controls_frame)

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

        # ── Dimension row ─────────────────────────────────────────────────────
        self._dimension_row = QWidget()
        self._dimension_row.setStyleSheet("background:transparent;")
        dim_vlay = QVBoxLayout(self._dimension_row)
        dim_vlay.setContentsMargins(0, 0, 0, 0)
        dim_vlay.setSpacing(2)

        dim_hrow = QWidget()
        dim_hrow.setStyleSheet("background:transparent;")
        dim_hlay = QHBoxLayout(dim_hrow)
        dim_hlay.setContentsMargins(0, 0, 0, 0)
        dim_hlay.setSpacing(8)
        dim_lbl = QLabel("Dimension:")
        dim_lbl.setStyleSheet("font-size:9px; color:#5a7a9a; background:transparent;")
        dim_hlay.addWidget(dim_lbl)
        self._dimension_menu = QComboBox()
        self._dimension_menu.addItem("—")
        self._dimension_menu.setFixedHeight(26)
        self._dimension_menu.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        dim_hlay.addWidget(self._dimension_menu, stretch=1)
        dim_vlay.addWidget(dim_hrow)

        self._dim_hint_lbl = QLabel("")
        self._dim_hint_lbl.setStyleSheet("font-size:8px; color:#8aa3b8; background:transparent;")
        dim_vlay.addWidget(self._dim_hint_lbl)

        self._dimension_row.setVisible(False)
        outer_lay.addWidget(self._dimension_row)

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
        self._row_limit_combo.setFixedHeight(22)
        self._row_limit_combo.setFixedWidth(64)
        opts_lay.addWidget(self._row_limit_combo)

        opts_lay.addWidget(QLabel("Sort:"))

        self._sort_by_combo = QComboBox()
        self._sort_by_combo.addItems(["None", "Value", "Label"])
        self._sort_by_combo.setFixedHeight(22)
        self._sort_by_combo.setFixedWidth(72)
        opts_lay.addWidget(self._sort_by_combo)

        self._sort_dir_combo = QComboBox()
        self._sort_dir_combo.addItems(["Desc", "Asc"])
        self._sort_dir_combo.setFixedHeight(22)
        self._sort_dir_combo.setFixedWidth(60)
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

        # ── Color ─────────────────────────────────────────────────────────────
        color_lbl = QLabel("Color")
        color_lbl.setStyleSheet(
            f"font-size:9px; color:#5a7a9a; padding:4px 12px 0 12px; background:transparent;"
        )
        parent_lay.addWidget(color_lbl)

        color_row = QWidget()
        color_row.setStyleSheet("background:transparent;")
        cr_lay = QHBoxLayout(color_row)
        cr_lay.setContentsMargins(12, 0, 12, 4)
        cr_lay.setSpacing(3)

        for hex_c, _ in COLOR_PRESETS:
            swatch = _ColorSwatch(hex_c)
            swatch.clicked.connect(self._on_color_select)
            cr_lay.addWidget(swatch)
            self._color_swatches.append(swatch)
        cr_lay.addStretch()
        parent_lay.addWidget(color_row)
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

    def _build_actions(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(46)
        bar.setStyleSheet("background:#e8eef5; border:none;")

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        save_btn = QPushButton("💾 Save")
        save_btn.setFixedHeight(30)
        save_btn.setStyleSheet(
            "QPushButton { background:#8e44ad; color:white; border:none; "
            "border-radius:4px; font-size:12px; padding:2px 12px; }"
            "QPushButton:hover { background:#6c3483; }"
        )
        save_btn.clicked.connect(self._on_save)
        lay.addWidget(save_btn)

        dash_btn = QPushButton("+ Add to Dashboard")
        dash_btn.setFixedHeight(30)
        dash_btn.setStyleSheet(
            "QPushButton { background:#27ae60; color:white; border:none; "
            "border-radius:4px; font-size:12px; padding:2px 12px; }"
            "QPushButton:hover { background:#1e8449; }"
        )
        dash_btn.clicked.connect(self._on_add_to_dashboard)
        lay.addWidget(dash_btn)

        preview_btn = QPushButton("🌐 Preview in Browser")
        preview_btn.setFixedHeight(30)
        preview_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; border:1px solid {DHIS2_BLUE}; "
            f"color:{DHIS2_BLUE}; border-radius:4px; font-size:12px; padding:2px 12px; }}"
            f"QPushButton:hover {{ background:#e8f0f8; }}"
        )
        preview_btn.clicked.connect(self._on_preview_browser)
        lay.addWidget(preview_btn)
        lay.addStretch()

        return bar

    # =========================================================================
    # Metadata
    # =========================================================================

    def load_metadata(self, meta: dict):
        self._metadata = meta
        prog_map: dict[str, dict] = {}
        for de in meta.get("program_stage_data_elements", []):
            pid   = de.get("program", {}).get("id", "")
            pname = de.get("program", {}).get("displayName", pid)
            sid   = de.get("stage", {}).get("id", "")
            sname = de.get("stage", {}).get("displayName", sid)
            if pid not in prog_map:
                prog_map[pid] = {"id": pid, "displayName": pname, "stages": {}}
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
            })

        self._programs = sorted(
            [{"id": p["id"], "displayName": p["displayName"],
              "stages": list(p["stages"].values())}
             for p in prog_map.values()],
            key=lambda x: x["displayName"].lower())

        self._agg_des = sorted(
            [{"uid": d["id"], "name": d.get("displayName", d["id"]),
              "type": "aggregate", "prog_uid": "", "stage_uid": ""}
             for d in meta.get("data_elements", [])],
            key=lambda x: x["name"].lower())

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

    def _on_src_check(self):
        prog = self._src_prog_cb.isChecked()
        agg  = self._src_agg_cb.isChecked()
        self._prog_menu.setVisible(prog)
        self._stage_menu.setVisible(prog)
        self._agg_search_entry.setVisible(agg)
        if not agg:
            self._agg_search_entry.clear()
        if not prog and not agg:
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
                    {"tracker_option", "tracker_numeric", "aggregate"}
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
                items.extend(de for de in prog_des if de["type"] in for_types)
        if self._src_agg_cb.isChecked():
            q = self._agg_search_entry.text().strip().lower()
            items.extend(de for de in self._agg_des
                         if "aggregate" in for_types and (not q or q in de["name"].lower()))
        self._current_de_items = items

    # =========================================================================
    # Chart type selection
    # =========================================================================

    def _on_chart_type_click(self, tmpl: dict):
        self._selected_template = tmpl
        self._min_des = tmpl.get("min_sources", 1)
        self._max_des = tmpl.get("max_sources", 1 if not tmpl.get("multi") else 3)

        plugin = tmpl.get("plugin")
        self._selected_plugin = plugin

        if self._min_des == self._max_des:
            lbl = str(self._max_des)
        else:
            lbl = f"{self._min_des}–{self._max_des}"
        self._metrics_section_lbl.setText(f"3. METRICS  (tick {lbl})")
        self._chart_info_lbl.setText(tmpl.get("description", ""))
        self._chart_info_lbl.setStyleSheet("font-size:9px; color:#5a7a9a; background:transparent;")

        prog_ok = bool({"tracker_option", "tracker_numeric"} & tmpl["for_types"])
        agg_ok  = "aggregate" in tmpl["for_types"]
        self._src_prog_cb.setEnabled(prog_ok)
        self._src_agg_cb.setEnabled(agg_ok)
        if not prog_ok:
            self._src_prog_cb.setChecked(False)
        if not agg_ok:
            self._src_agg_cb.setChecked(False)
        if not self._src_prog_cb.isChecked() and not self._src_agg_cb.isChecked():
            if prog_ok:
                self._src_prog_cb.setChecked(True)
            elif agg_ok:
                self._src_agg_cb.setChecked(True)

        # Enforce DE max
        sel = self._get_selected_des()
        if len(sel) > self._max_des:
            count = 0
            for de, cb, *_ in self._de_checkboxes:
                if cb.isChecked():
                    count += 1
                    if count > self._max_des:
                        cb.setChecked(False)

        # Highlight tiles
        for tid, tile in self._chart_tiles.items():
            tile.set_selected(tid == tmpl["id"])

        self._on_src_check()
        self._collapse_chart_grid()
        self._rebuild_chart_options()
        self._refresh_metrics_display()
        self._refresh_dimensions_display()
        self._auto_preview()

    # =========================================================================
    # Metrics display
    # =========================================================================

    def _refresh_metrics_display(self, *_):
        """Rebuild metrics scroll content based on current plugin + available DEs."""
        self._refresh_de_list()

        # Clear inner widget
        while self._metrics_inner_lay.count():
            item = self._metrics_inner_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._metric_rows = []

        if not self._current_de_items:
            lbl = QLabel("Select source first")
            lbl.setStyleSheet("color:#8aa3b8; font-size:10px;")
            lbl.setAlignment(Qt.AlignCenter)
            self._metrics_inner_lay.addWidget(lbl)
            self._metrics_inner_lay.addStretch()
            return

        existing_checked = {de["uid"] for de, cb, *_ in self._de_checkboxes if cb.isChecked()}
        self._de_checkboxes = []

        for de in self._current_de_items:
            checked = de["uid"] in existing_checked

            row_w = QWidget()
            row_w.setStyleSheet("background:white;")
            row_lay = QHBoxLayout(row_w)
            row_lay.setContentsMargins(4, 1, 4, 1)
            row_lay.setSpacing(4)

            cb = QCheckBox(de["name"])
            cb.setChecked(checked)
            cb.setStyleSheet("font-size:10px;")
            cb.stateChanged.connect(self._on_de_check)
            row_lay.addWidget(cb, stretch=1)

            de_type = de.get("type", "")
            needs_agg = de_type in ("tracker_numeric", "aggregate", "indicator")
            agg_combo: QComboBox | None = None

            if needs_agg:
                agg_combo = QComboBox()
                agg_combo.addItems(["SUM", "COUNT", "AVG", "MIN", "MAX"])
                agg_combo.setFixedWidth(80)
                agg_combo.setFixedHeight(22)
                agg_combo.currentTextChanged.connect(lambda _: self._on_de_check())
                row_lay.addWidget(agg_combo)

            self._metrics_inner_lay.addWidget(row_w)
            self._de_checkboxes.append((de, cb, agg_combo))
            self._metric_rows.append((de, cb, agg_combo))

        self._metrics_inner_lay.addStretch()

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

        if plugin_cls and getattr(plugin_cls, "options", []):
            self._select_controls_frame.setVisible(True)
            old_vals = {k: v.get() for k, v in self._select_vars.items()}
            self._select_vars = {}
            for sc in plugin_cls.options:
                prev = old_vals.get(sc.id, sc.default)
                val  = prev if prev in sc.choices else sc.default

                row_w = QWidget()
                row_w.setStyleSheet("background:transparent;")
                row_lay = QHBoxLayout(row_w)
                row_lay.setContentsMargins(0, 1, 0, 1)
                row_lay.setSpacing(6)

                lbl = QLabel(sc.label + ":")
                lbl.setStyleSheet("font-size:9px; color:#5a7a9a; background:transparent;")
                row_lay.addWidget(lbl)

                seg = SegmentedButton(list(sc.choices), default=val)
                seg.changed.connect(self._on_select_control_change)
                row_lay.addWidget(seg)
                row_lay.addStretch()

                self._select_vars[sc.id] = seg
                self._select_controls_lay.addWidget(row_w)
        else:
            self._select_controls_frame.setVisible(False)
            self._select_vars = {}

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
            dim_hint = plugin_cls.dimensions[0].hint
        elif self._selected_template:
            tid = self._selected_template.get("id", "")
            if "stacked" in tid:
                dim_hint = "Each option value becomes one stack layer"
            elif "pie" in tid:
                dim_hint = "Each option value becomes one pie slice"
            elif "line" in tid:
                dim_hint = "Split into multiple lines by option value"

        current_dim = self._dimension_menu.currentText()
        dim_names = ["—"] + [d["name"] for d in self._current_de_items]
        self._dimension_menu.blockSignals(True)
        self._dimension_menu.clear()
        self._dimension_menu.addItems(dim_names)
        if current_dim in dim_names:
            self._dimension_menu.setCurrentText(current_dim)
        else:
            self._dimension_menu.setCurrentText("—")
        self._dimension_menu.blockSignals(False)

        self._dim_hint_lbl.setText(dim_hint)
        self._dimension_row.setVisible(bool(self._selected_template))

        # ── Refresh filter DE dropdowns ─────────────────────────────────────────
        de_names = ["—"] + [d["name"] for d in self._current_de_items]
        de_map   = {d["name"]: d for d in self._current_de_items}
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
        de_names = ["—"] + [d["name"] for d in self._current_de_items]
        de_map   = {d["name"]: d for d in self._current_de_items}

        row_w = QWidget()
        row_w.setStyleSheet("background:transparent;")
        row_lay = QHBoxLayout(row_w)
        row_lay.setContentsMargins(0, 1, 0, 1)
        row_lay.setSpacing(3)

        de_menu = QComboBox()
        de_menu.addItems(de_names)
        de_menu.setFixedHeight(22)
        de_menu.setFixedWidth(110)
        row_lay.addWidget(de_menu)

        op_menu = QComboBox()
        op_menu.addItems(self._FILTER_OPS)
        op_menu.setFixedHeight(22)
        op_menu.setFixedWidth(70)
        row_lay.addWidget(op_menu)

        val_entry = QLineEdit()
        val_entry.setFixedHeight(22)
        val_entry.setPlaceholderText("value")
        row_lay.addWidget(val_entry, stretch=1)

        row_data = dict(
            frame=row_w,
            de_menu=de_menu,
            op_menu=op_menu,
            val_entry=val_entry,
            de_map=de_map,
        )

        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(22, 22)
        rm_btn.setStyleSheet(
            "QPushButton { background:#f0f4f8; border:1px solid #c0cdd8; "
            "border-radius:3px; color:#8aa3b8; font-size:10px; }"
            "QPushButton:hover { background:#e8eef5; }"
        )
        rm_btn.clicked.connect(lambda _, rd=row_data: self._remove_filter_row(rd))
        row_lay.addWidget(rm_btn)

        self._filter_rows.append(row_data)
        self._filter_rows_lay.addWidget(row_w)

    def _remove_filter_row(self, row_data: dict):
        row_data["frame"].setParent(None)
        row_data["frame"].deleteLater()
        self._filter_rows = [r for r in self._filter_rows if r is not row_data]

    def _on_select_control_change(self, *_):
        self._schedule_preview_refresh()

    # =========================================================================
    # DE list helpers
    # =========================================================================

    def _clear_de_list(self, msg: str = "Select chart type first"):
        while self._metrics_inner_lay.count():
            item = self._metrics_inner_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._de_checkboxes = []
        self._metric_rows = []
        self._current_de_items = []
        lbl = QLabel(msg)
        lbl.setStyleSheet("color:#8aa3b8; font-size:10px;")
        lbl.setAlignment(Qt.AlignCenter)
        self._metrics_inner_lay.addWidget(lbl)
        self._metrics_inner_lay.addStretch()
        self._sel_lbl.setText("")

    def _populate_de_list(self, items: list[dict],
                          preserve_checked: set[str] | None = None):
        self._current_de_items = items
        checked = preserve_checked or {de["uid"] for de, cb, *_ in self._de_checkboxes
                                       if cb.isChecked()}
        while self._metrics_inner_lay.count():
            item = self._metrics_inner_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._de_checkboxes = []
        self._metric_rows = []

        if not items:
            lbl = QLabel("No results")
            lbl.setStyleSheet("color:#8aa3b8; font-size:10px;")
            lbl.setAlignment(Qt.AlignCenter)
            self._metrics_inner_lay.addWidget(lbl)
            self._metrics_inner_lay.addStretch()
            return

        for de in items:
            row_w = QWidget()
            row_w.setStyleSheet("background:white;")
            row_lay = QHBoxLayout(row_w)
            row_lay.setContentsMargins(4, 1, 4, 1)
            row_lay.setSpacing(4)

            cb = QCheckBox(de["name"])
            cb.setChecked(de["uid"] in checked)
            cb.setStyleSheet("font-size:10px;")
            cb.stateChanged.connect(self._on_de_check)
            row_lay.addWidget(cb, stretch=1)

            de_type = de.get("type", "")
            needs_agg = de_type in ("tracker_numeric", "aggregate", "indicator")
            agg_combo: QComboBox | None = None
            if needs_agg:
                agg_combo = QComboBox()
                agg_combo.addItems(["SUM", "COUNT", "AVG", "MIN", "MAX"])
                agg_combo.setFixedWidth(80)
                agg_combo.setFixedHeight(22)
                agg_combo.currentTextChanged.connect(lambda _: self._on_de_check())
                row_lay.addWidget(agg_combo)

            self._metrics_inner_lay.addWidget(row_w)
            self._de_checkboxes.append((de, cb, agg_combo))
            self._metric_rows.append((de, cb, agg_combo))

        self._metrics_inner_lay.addStretch()

    def _on_de_check(self):
        if len(self._get_selected_des()) > self._max_des:
            count = 0
            for de, cb, *_ in self._de_checkboxes:
                if cb.isChecked():
                    count += 1
                    if count > self._max_des:
                        cb.blockSignals(True)
                        cb.setChecked(False)
                        cb.blockSignals(False)

        # Collect selected metrics with agg type
        self._selected_metrics = []
        for de, cb, agg_combo in self._metric_rows:
            if cb.isChecked():
                agg = agg_combo.currentText() if agg_combo is not None else "COUNT"
                self._selected_metrics.append({
                    "uid":  de["uid"],
                    "name": de["name"],
                    "type": de["type"],
                    "agg":  agg,
                })

        sel = self._get_selected_des()
        if not sel:
            self._sel_lbl.setText("")
            self._sel_lbl.setStyleSheet(
                "color:#1565c0; font-size:10px; background:transparent; padding:2px 10px;"
            )
        else:
            text = "  ✓ " + " + ".join(d["name"][:22] for d in sel) + "  "
            self._sel_lbl.setText(text)
            self._sel_lbl.setStyleSheet(
                "color:#1565c0; font-size:10px; background:#e3f2fd; "
                "padding:2px 10px; border-radius:3px;"
            )

        if self._mode_fixed_rb.isChecked() and len(sel) >= self._min_des:
            self._auto_preview()

    def _get_selected_des(self) -> list[dict]:
        return [de for de, cb, *_ in self._de_checkboxes if cb.isChecked()]

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
                seg = SegmentedButton(opt["values"], default=default_val)
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
        for swatch in self._color_swatches:
            swatch._set_selected(swatch._color == color)
        self._schedule_preview_refresh()

    def _on_mode_change(self):
        is_ai = self._mode_ai_rb.isChecked()
        self._ai_desc_wrap.setVisible(is_ai)

    # =========================================================================
    # Preview
    # =========================================================================

    def _auto_preview(self):
        self._schedule_preview_refresh()

    def _schedule_preview_refresh(self):
        self._preview_timer.stop()
        self._preview_timer.start(400)

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
            QTimer.singleShot(0, lambda: self._on_ai_customize_done(summary))
        except Exception as exc:
            QTimer.singleShot(0, lambda: self._on_ai_customize_done(f"Error: {exc}"))

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
        dim_text = self._dimension_menu.currentText()
        _has_dim = bool(dim_text and dim_text not in ("—", ""))
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

        # Resolve dimension field
        dimension_de = None
        if dim_text and dim_text != "—":
            dimension_de = next(
                (d for d in self._current_de_items if d["name"] == dim_text), None
            )
        group_by = [dimension_de] if dimension_de else []

        # Collect filters
        op_map = self.__class__._OP_MAP
        filters = []
        for r in self._filter_rows:
            de_name = r["de_menu"].currentText()
            if de_name == "—":
                continue
            de_obj = r["de_map"].get(de_name, {})
            val = r["val_entry"].text().strip()
            if not val:
                continue
            op_display = r["op_menu"].currentText()
            op_dhis2 = op_map.get(op_display, op_display)
            filters.append({
                "de_uid":  de_obj.get("uid", ""),
                "de_name": de_name,
                "de_type": de_obj.get("type", ""),
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

    def _on_save(self):
        cfg = self._build_config()
        if not cfg:
            QMessageBox.warning(self, "Save Chart",
                                "Select a chart type and data element(s) first.")
            return
        if self._mode_ai_rb.isChecked():
            cfg["ai_desc"] = self._ai_desc.toPlainText().strip()
        name, ok = QInputDialog.getText(
            self, "Save Chart", "Chart name:", text=cfg["title"]
        )
        if not ok or not name:
            return
        cfg["name"] = name
        from config.chart_library import save_chart
        saved = save_chart(cfg)
        cb = self._callbacks.get("on_chart_saved")
        if cb:
            cb(saved)

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
