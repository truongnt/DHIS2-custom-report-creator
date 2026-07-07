"""
DashboardBuilderPanel — Superset-inspired dashboard assembler (PySide6).

Layout:
  ┌──────────────────────┬────────────────────────────────────────┐
  │  CHART LIBRARY       │  DASHBOARD CANVAS                      │
  │  (240px)             │  (expands)                             │
  │                      │                                        │
  │  Saved charts:       │  Cards added to this dashboard         │
  │  ┌──────────────┐    │  ┌────────┐ ┌────────┐               │
  │  │ Chart name   │    │  │ card 1 │ │ card 2 │               │
  │  │ 📊 Bar trend │[+] │  │        │ │        │               │
  │  └──────────────┘    │  └────────┘ └────────┘               │
  │  ┌──────────────┐    │                                        │
  │  │ ...          │[+] │  [report name entry]                   │
  │  └──────────────┘    │  [Export HTML]  [🚀 Deploy to DHIS2]  │
  │                      │                                        │
  │  [↺ Refresh]         │                                        │
  └──────────────────────┴────────────────────────────────────────┘

Callbacks:
  on_export(cards)
  on_deploy(name, cards)
  on_switch_to_editor()   — request to switch back to Chart Editor tab
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal, QMimeData
from PySide6.QtGui import QFont, QColor, QDrag
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QStackedWidget,
    QComboBox,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QMessageBox,
    QSpacerItem,
    QInputDialog,
)


class _ChatPlannerWorker(QThread):
    """Runs the dashboard planner off the UI thread (REQ-DASH-AI-05)."""
    finished = Signal(list)   # list[dict] recommendations
    failed   = Signal(str)

    def __init__(self, intent: str, context: dict, ai_client, mock_key: str | None,
                 model: str):
        super().__init__()
        self._intent   = intent
        self._context  = context
        self._client   = ai_client
        self._mock_key = mock_key
        self._model    = model

    def run(self) -> None:
        try:
            from llm.ai_dashboard_planner import recommend_charts
            recs = recommend_charts(self._intent, self._context,
                                    ai_client=self._client, mock_key=self._mock_key,
                                    model=self._model)
            self.finished.emit(recs)
        except Exception as exc:
            self.failed.emit(str(exc))


class _RefineWorker(QThread):
    """Refine ONE chart recommendation with a natural-language instruction, off the UI thread."""
    finished = Signal(dict)   # updated rec
    failed   = Signal(str)

    def __init__(self, rec: dict, instruction: str, context: dict, ai_client, model: str):
        super().__init__()
        self._rec = rec
        self._instruction = instruction
        self._context = context
        self._client = ai_client
        self._model = model

    def run(self) -> None:
        try:
            from llm.ai_dashboard_planner import refine_chart
            self.finished.emit(refine_chart(
                self._rec, self._instruction, self._context,
                ai_client=self._client, model=self._model))
        except Exception as exc:
            self.failed.emit(str(exc))


# Model choices for the AI dashboard workspace (label → id)
_AI_MODELS = [
    ("Haiku 4.5", "claude-haiku-4-5-20251001"),
    ("Sonnet 4.6", "claude-sonnet-4-6"),
    ("Opus 4.8", "claude-opus-4-8"),
]

DHIS2_BLUE = "#1a6fa8"
PANEL_BG   = "#f7f9fc"
BORDER_CLR = "#d0dde8"
HEADER_BG  = "#e8eef5"
AI_GREEN   = "#1e7e48"


def _h_line() -> QFrame:
    """Thin horizontal separator."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    line.setStyleSheet(f"color: {BORDER_CLR};")
    return line


class _LibDragFrame(QFrame):
    """Library card wrapper that starts a drag carrying its chart id (REQ-DASH-LIB-04)."""

    def __init__(self, chart_id: str):
        super().__init__()
        self._chart_id = chart_id

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton and self._chart_id:
            from ui.dashboard_grid import MIME_LIB_CHART
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(MIME_LIB_CHART, str(self._chart_id).encode())
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.CopyAction)
        super().mouseMoveEvent(ev)


class DashboardBuilderPanel(QWidget):
    """PySide6 dashboard assembler panel."""

    # (label, intent text) — quick-start presets for AI chat (REQ-DASH-AI-02)
    _CHAT_PRESETS = [
        ("Custom…", ""),
        ("Malaria overview", "Show key malaria indicators: monthly trend, geographic "
                             "distribution, case breakdown, and facility ranking"),
        ("Supply chain", "Supply chain stock levels: facility comparison, trend over "
                         "time, geographic coverage, and a national KPI"),
        ("Performance review", "Performance dashboard: key indicator trend, multi-indicator "
                               "comparison, district map, and facility ranking"),
    ]

    def __init__(self, master: QWidget, callbacks: dict, **kw):
        super().__init__(master, **kw)
        self._callbacks: dict = callbacks
        self._cards: list[dict] = []
        self._card_widgets: list[QFrame] = []   # parallel list to self._cards
        self._mode: str | None = None           # None until a mode is chosen
        self._chat_input: QLineEdit | None = None
        self._ai_client = None                   # set via set_context; None → mock mode
        self._ai_model  = "claude-haiku-4-5-20251001"
        self._chat_worker: _ChatPlannerWorker | None = None
        self._suggestion_cards: list[QWidget] = []
        self._ai_card_chips: list[tuple] = []    # [(chip_widget, cfg), ...]
        self._dash_filters: dict = {"period": "LAST_12_MONTHS", "ou": "USER_ORGUNIT"}
        self._dash_custom_css: str = ""                   # dashboard-level CSS (REQ-DASH-CSS)
        self._current_dashboard_name: str | None = None   # None = new, unsaved dashboard
        self._current_dashboard_description: str = ""
        self._build()
        self.refresh_library()

    def set_context(self, *, metadata: dict | None = None,
                    descriptions: dict | None = None, base_url: str = "",
                    ai_client=None, model: str | None = None) -> None:
        """Supply loaded metadata + descriptions (+ optional AI client) for AI chat."""
        self._metadata     = metadata or {}
        self._descriptions = descriptions or {}
        self._base_url     = base_url
        if ai_client is not None:
            self._ai_client = ai_client
        if model:
            self._ai_model = model
            combo = getattr(self, "_ai_model_combo", None)
            if combo is not None:
                idx = next((i for i, (_, mid) in enumerate(_AI_MODELS) if mid == model), -1)
                if idx >= 0:
                    combo.blockSignals(True); combo.setCurrentIndex(idx); combo.blockSignals(False)

    # ─── Build ───────────────────────────────────────────────────────────────

    def _build(self):
        """Root = QStackedWidget with 3 pages: 0 mode-chooser, 1 manual, 2 AI chat."""
        self.setStyleSheet(f"background-color: {PANEL_BG};")
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._stack = QStackedWidget(self)
        root_layout.addWidget(self._stack)

        self._chooser_page = QWidget()
        self._build_mode_chooser(self._chooser_page)
        self._stack.addWidget(self._chooser_page)           # index 0

        self._manual_page = QWidget()
        self._build_manual_workspace(self._manual_page)
        self._stack.addWidget(self._manual_page)            # index 1

        self._ai_page = QWidget()
        self._build_ai_workspace(self._ai_page)
        self._stack.addWidget(self._ai_page)                # index 2

        self._stack.setCurrentWidget(self._chooser_page)

    # ── Page 0: Mode chooser ───────────────────────────────────────────────

    def _build_mode_chooser(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(6)

        # Compact "create new" header + two slim mode cards side by side.
        title = QLabel("Create a dashboard")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c4257;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)
        cards_row.addStretch(1)
        self._manual_btn = self._make_mode_card(
            "🖱  Manual", "Drag && drop saved charts into a grid", DHIS2_BLUE)
        self._manual_btn.clicked.connect(lambda: self._choose_mode("manual"))
        cards_row.addWidget(self._manual_btn)
        self._ai_btn = self._make_mode_card(
            "🤖  AI Chat", "Describe it and let AI build it", AI_GREEN)
        self._ai_btn.clicked.connect(lambda: self._choose_mode("ai"))
        cards_row.addWidget(self._ai_btn)
        cards_row.addStretch(1)
        layout.addLayout(cards_row)

        layout.addSpacing(12)
        sep = QLabel("Or open a saved dashboard")
        sep.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        sep.setStyleSheet("color: #3a5068;")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sep)

        # ── Embedded "open existing" — the SAME LoadDashboardDialog shown inline so the
        #    saved dashboards are openable right here (no extra Open click). It takes the
        #    remaining height (stretch) so the dashboard rows are always visible. ───────
        open_row = QHBoxLayout()
        open_row.addStretch(1)
        self._open_container = QFrame()
        self._open_container.setMinimumWidth(680)
        self._open_container.setMaximumWidth(820)
        self._open_container.setStyleSheet("background: transparent;")
        self._open_layout = QVBoxLayout(self._open_container)
        self._open_layout.setContentsMargins(0, 0, 0, 0)
        open_row.addWidget(self._open_container, 1)
        open_row.addStretch(1)
        layout.addLayout(open_row, 1)            # dominant — fills remaining space

        self._embedded_load = None
        self._mount_embedded_load()

    def _mount_embedded_load(self):
        """(Re)build the embedded saved-dashboards picker — reuses LoadDashboardDialog inline."""
        while self._open_layout.count():
            it = self._open_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._embedded_load = None

        from config.dashboard_library import load_dashboards
        dashes = load_dashboards()
        if not dashes:
            hint = QLabel("No saved dashboards yet — create one above.")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setFont(QFont("Segoe UI", 10))
            hint.setStyleSheet("color: #8aa3b8; padding: 16px;")
            self._open_layout.addWidget(hint)
            return

        from ui.load_dashboard_dialog import LoadDashboardDialog
        dlg = LoadDashboardDialog(self, dashes)
        dlg.setWindowFlags(Qt.WindowType.Widget)        # render inline, not as a popup
        dlg.accepted.connect(self._on_embedded_open)     # double-click / Open → load
        dlg.rejected.connect(self._mount_embedded_load)  # Cancel → just refresh the list
        self._embedded_load = dlg
        self._open_layout.addWidget(dlg)

    def _on_embedded_open(self):
        if self._embedded_load is not None:
            entry = self._embedded_load.get_selected()
            if entry:
                self.load_dashboard_entry(entry)

    def _make_mode_card(self, title: str, desc: str, color: str) -> QPushButton:
        """A compact clickable card-style button for choosing a build mode."""
        btn = QPushButton()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(250, 76)
        btn.setText(f"{title}\n{desc}")
        btn.setStyleSheet(
            "QPushButton {"
            "  background-color: white;"
            f" border: 2px solid {BORDER_CLR};"
            "  border-radius: 10px;"
            "  color: #3a5068;"
            "  font-size: 12px;"
            "  padding: 8px 12px;"
            "  text-align: center;"
            "}"
            f"QPushButton:hover {{ border-color: {color}; background-color: #fbfdff; }}"
        )
        return btn

    # ── Page 1: Manual workspace (library + grid canvas) ───────────────────

    def _build_manual_workspace(self, parent: QWidget):
        layout = QHBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, parent)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background-color: {BORDER_CLR}; }}"
        )
        layout.addWidget(splitter)

        left_widget = QWidget()
        left_widget.setFixedWidth(240)
        left_widget.setStyleSheet(f"background-color: {PANEL_BG};")
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_widget.setStyleSheet(f"background-color: {PANEL_BG};")
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self._build_library(left_widget)
        self._build_canvas(right_widget)

    # ── Left: Chart Library ───────────────────────────────────────────────

    def _build_library(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(f"background-color: {HEADER_BG}; border: none;")
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(14, 0, 14, 0)
        lbl = QLabel("Chart Library")
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #3a5068;")
        hdr_layout.addWidget(lbl)
        layout.addWidget(hdr)

        # Search box (REQ-DASH-LIB-03)
        self._lib_search = QLineEdit()
        self._lib_search.setPlaceholderText("Search charts…")
        self._lib_search.setFixedHeight(26)
        self._lib_search.setFont(QFont("Segoe UI", 9))
        self._lib_search.setStyleSheet(
            "QLineEdit { border: 1px solid #c0cdd8; border-radius: 4px; margin: 6px;"
            "  padding: 0 6px; background-color: white; color: #1e2d3d; }"
            "QLineEdit:focus { border-color: #1a6fa8; }")
        self._lib_search.textChanged.connect(lambda _=None: self.refresh_library())
        layout.addWidget(self._lib_search)

        # Scrollable chart list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {PANEL_BG}; border: none; }}"
        )

        self._lib_container = QWidget()
        self._lib_container.setStyleSheet(f"background-color: {PANEL_BG};")
        self._lib_layout = QVBoxLayout(self._lib_container)
        self._lib_layout.setContentsMargins(0, 4, 0, 4)
        self._lib_layout.setSpacing(0)
        self._lib_layout.addStretch(1)   # sentinel stretch at bottom

        scroll.setWidget(self._lib_container)
        layout.addWidget(scroll, 1)

        # Footer
        footer = QFrame()
        footer.setFixedHeight(40)
        footer.setStyleSheet(f"background-color: {HEADER_BG}; border: none;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(8, 0, 8, 0)
        footer_layout.setSpacing(6)

        refresh_btn = QPushButton("↺ Refresh")
        refresh_btn.setFixedHeight(26)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent;"
            f" border: 1px solid #c0cdd8;"
            "  border-radius: 4px;"
            "  color: #5a7a9a;"
            "  font-size: 11px;"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #d8e4f0; }"
        )
        refresh_btn.clicked.connect(self.refresh_library)

        editor_btn = QPushButton("← Chart Editor")
        editor_btn.setFixedHeight(26)
        editor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        editor_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent;"
            f" border: 1px solid {DHIS2_BLUE};"
            "  border-radius: 4px;"
            f" color: {DHIS2_BLUE};"
            "  font-size: 11px;"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #e8f0f8; }"
        )
        editor_btn.clicked.connect(
            lambda: self._callbacks.get("on_switch_to_editor", lambda: None)()
        )

        footer_layout.addWidget(refresh_btn)
        footer_layout.addStretch(1)
        footer_layout.addWidget(editor_btn)
        layout.addWidget(footer)

    # ── Right: Dashboard Canvas ───────────────────────────────────────────

    def _build_canvas(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(f"background-color: {HEADER_BG}; border: none;")
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(14, 0, 14, 0)

        canvas_lbl = QLabel("Dashboard Canvas")
        canvas_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        canvas_lbl.setStyleSheet("color: #3a5068;")
        hdr_layout.addWidget(canvas_lbl)

        hdr_layout.addStretch(1)

        # Change-mode button (hard fork: manual workspace stays manual)
        change_btn = QPushButton("⇄ Change mode")
        change_btn.setFixedHeight(26)
        change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_btn.setFont(QFont("Segoe UI", 9))
        change_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent;"
            f" border: 1px solid #7a9ab0;"
            "  border-radius: 4px;"
            "  color: #4a6a80; padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #e0ecf4; }"
        )
        change_btn.clicked.connect(self._on_change_mode)
        hdr_layout.addWidget(change_btn)

        self._card_count_lbl = QLabel("0 charts")
        self._card_count_lbl.setFont(QFont("Segoe UI", 9))
        self._card_count_lbl.setStyleSheet("color: #8aa3b8;")
        hdr_layout.addWidget(self._card_count_lbl)
        layout.addWidget(hdr)

        # 12-column drag-drop grid (REQ-DASH-GRID-*)
        from ui.dashboard_grid import GridCanvas
        self._grid = GridCanvas()
        self._grid.changed.connect(self._on_grid_changed)
        self._grid.external_drop.connect(self._on_library_drop)
        self._grid.open_chart.connect(self._on_open_chart_from_card)
        layout.addWidget(self._grid, 1)

        # Bottom panel
        bottom = QFrame()
        bottom.setStyleSheet(f"background-color: {HEADER_BG}; border: none;")
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 6, 12, 8)
        bottom_layout.setSpacing(6)

        # Current-dashboard title row (name + description are entered via the Save dialog,
        # mirroring the Chart Editor — no inline name field).
        rn_row = QWidget()
        rn_row.setStyleSheet("background-color: transparent;")
        rn_layout = QHBoxLayout(rn_row)
        rn_layout.setContentsMargins(0, 0, 0, 0)
        rn_layout.setSpacing(6)
        self._manual_dash_lbl = QLabel("• new dashboard")
        self._manual_dash_lbl.setFont(QFont("Segoe UI", 10))
        self._manual_dash_lbl.setStyleSheet(
            "color: #3a5068; background-color: transparent; font-style: italic;")
        rn_layout.addWidget(self._manual_dash_lbl)
        rn_layout.addStretch(1)
        bottom_layout.addWidget(rn_row)

        # Save / Load dashboard row
        sl_row = QWidget()
        sl_row.setStyleSheet("background-color: transparent;")
        sl_layout = QHBoxLayout(sl_row)
        sl_layout.setContentsMargins(0, 0, 0, 0)
        sl_layout.setSpacing(6)

        save_dash_btn = QPushButton("💾 Save")
        save_dash_btn.setFixedHeight(26)
        save_dash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_dash_btn.setFont(QFont("Segoe UI", 9))
        save_dash_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent;"
            f" border: 1px solid {DHIS2_BLUE};"
            "  border-radius: 4px;"
            f" color: {DHIS2_BLUE};"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #e8f0f8; }"
        )
        save_dash_btn.clicked.connect(self._on_save_dashboard)

        save_as_dash_btn = QPushButton("Save As…")
        save_as_dash_btn.setFixedHeight(26)
        save_as_dash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_as_dash_btn.setFont(QFont("Segoe UI", 9))
        save_as_dash_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent;"
            "  border: 1px solid #8e44ad;"
            "  border-radius: 4px;"
            "  color: #8e44ad;"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #ead6f5; color: #5b2c6f; }"
            "QPushButton:disabled { color: #c2b0cf; border-color: #ddd0e6; }"
        )
        save_as_dash_btn.clicked.connect(self._on_save_dashboard_as)

        new_dash_btn = QPushButton("🆕 New")
        new_dash_btn.setFixedHeight(26)
        new_dash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_dash_btn.setFont(QFont("Segoe UI", 9))
        new_dash_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent;"
            "  border: 1px solid #7a9ab0;"
            "  border-radius: 4px;"
            "  color: #4a6a80;"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #cdd8e4; color: #2c4257; }"
            "QPushButton:disabled { color: #aab4be; border-color: #dde3e9; }"
        )
        new_dash_btn.clicked.connect(self._on_new_dashboard)

        load_dash_btn = QPushButton("📂 Open")
        load_dash_btn.setFixedHeight(26)
        load_dash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_dash_btn.setFont(QFont("Segoe UI", 9))
        load_dash_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent;"
            f" border: 1px solid #7a9ab0;"
            "  border-radius: 4px;"
            "  color: #4a6a80;"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #e0ecf4; }"
        )
        load_dash_btn.clicked.connect(self._on_load_dashboard)

        filters_btn = QPushButton("🎚 Filters")
        filters_btn.setFixedHeight(26)
        filters_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        filters_btn.setFont(QFont("Segoe UI", 9))
        filters_btn.setStyleSheet(
            "QPushButton { background-color: transparent;"
            f" border: 1px solid #7a9ab0; border-radius: 4px; color: #4a6a80; padding: 0 10px; }}"
            "QPushButton:hover { background-color: #e0ecf4; }")
        filters_btn.clicked.connect(self._on_edit_filters)

        css_btn = QPushButton("🎨 CSS")
        css_btn.setFixedHeight(26)
        css_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        css_btn.setFont(QFont("Segoe UI", 9))
        css_btn.setStyleSheet(
            "QPushButton { background-color: transparent;"
            f" border: 1px solid #7a9ab0; border-radius: 4px; color: #4a6a80; padding: 0 10px; }}"
            "QPushButton:hover { background-color: #e0ecf4; }")
        css_btn.clicked.connect(self._on_edit_css)

        # Canonical entity-action order (consistent across screens): New · Open · Save · Save As.
        sl_layout.addWidget(new_dash_btn)
        sl_layout.addWidget(load_dash_btn)
        sl_layout.addWidget(save_dash_btn)
        sl_layout.addWidget(save_as_dash_btn)
        sl_layout.addWidget(filters_btn)
        sl_layout.addWidget(css_btn)
        sl_layout.addStretch(1)

        bottom_layout.addWidget(sl_row)

        # Export / Deploy row
        action_row = QWidget()
        action_row.setStyleSheet("background-color: transparent;")
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)

        self._preview_btn = QPushButton("👁 Preview")
        self._preview_btn.setFixedHeight(34)
        self._preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._preview_btn.setStyleSheet(
            "QPushButton {"
            f" background-color: {DHIS2_BLUE};"
            "  border: none; border-radius: 5px; color: white; padding: 0 14px;"
            "}"
            "QPushButton:hover { background-color: #155a8a; }"
            "QPushButton:disabled { background-color: #a8c8e8; color: #e0eaf4; }"
        )
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self._on_preview)
        action_layout.addWidget(self._preview_btn, 1)

        self._export_btn = QPushButton("⬇ Export HTML")
        self._export_btn.setFixedHeight(34)
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._export_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #2980b9;"
            "  border: none;"
            "  border-radius: 5px;"
            "  color: white;"
            "  padding: 0 14px;"
            "}"
            "QPushButton:hover { background-color: #1e6b99; }"
            "QPushButton:disabled { background-color: #a8c8e8; color: #e0eaf4; }"
        )
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)
        action_layout.addWidget(self._export_btn, 1)

        self._deploy_btn = QPushButton("🚀 Deploy to DHIS2")
        self._deploy_btn.setFixedHeight(34)
        self._deploy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._deploy_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._deploy_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #27ae60;"
            "  border: none;"
            "  border-radius: 5px;"
            "  color: white;"
            "  padding: 0 14px;"
            "}"
            "QPushButton:hover { background-color: #1e8449; }"
            "QPushButton:disabled { background-color: #a8d8bc; color: #e0f4ea; }"
        )
        self._deploy_btn.setEnabled(False)
        self._deploy_btn.clicked.connect(self._on_deploy)
        action_layout.addWidget(self._deploy_btn, 1)

        bottom_layout.addWidget(action_row)

        # Clear all row (right-aligned)
        clear_row = QWidget()
        clear_row.setStyleSheet("background-color: transparent;")
        clear_layout = QHBoxLayout(clear_row)
        clear_layout.setContentsMargins(0, 0, 0, 0)
        clear_layout.addStretch(1)

        clear_btn = QPushButton("🗑 Clear all")
        clear_btn.setFixedHeight(24)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setFont(QFont("Segoe UI", 9))
        clear_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent;"
            "  border: 1px solid #e74c3c;"
            "  border-radius: 4px;"
            "  color: #e74c3c;"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #fdecea; }"
        )
        clear_btn.clicked.connect(self._on_clear_all)
        clear_layout.addWidget(clear_btn)

        bottom_layout.addWidget(clear_row)
        layout.addWidget(bottom)

    # ─── Library ─────────────────────────────────────────────────────────────

    def refresh_library(self):
        """Clear and rebuild the library scroll from chart_library.load_charts()."""
        from config.chart_library import load_charts

        # Remove all widgets except the trailing stretch
        while self._lib_layout.count() > 1:
            item = self._lib_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        charts = load_charts()
        query = self._lib_search.text().strip().lower() if hasattr(self, "_lib_search") else ""
        if query:
            charts = [c for c in charts
                      if query in (c.get("name") or c.get("title", "")).lower()]

        if not charts:
            msg = ("No charts match your search." if query
                   else "No saved charts yet.\nBuild a chart and click\n'Save to Library'.")
            empty_lbl = QLabel(msg)
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setFont(QFont("Segoe UI", 9))
            empty_lbl.setStyleSheet(
                f"color: #8aa3b8; background-color: {PANEL_BG}; padding: 24px 8px;"
            )
            self._lib_layout.insertWidget(0, empty_lbl)
            return

        for i, chart in enumerate(charts):
            card = self._make_library_card(chart)
            self._lib_layout.insertWidget(i, card)

    def _make_library_card(self, chart: dict) -> QFrame:
        """Return a QFrame representing one chart in the library list."""
        rf = QFrame()
        rf.setStyleSheet(
            "QFrame {"
            "  background-color: white;"
            f" border: 1px solid {BORDER_CLR};"
            "  border-radius: 6px;"
            "}"
        )
        rf.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        row_layout = QHBoxLayout(rf)
        row_layout.setContentsMargins(8, 5, 6, 5)
        row_layout.setSpacing(4)

        # Text block
        text_widget = QWidget()
        text_widget.setStyleSheet("border: none; background-color: transparent;")
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        name_lbl = QLabel(chart.get("name") or chart.get("title", "?"))
        name_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #1e2d3d; border: none;")
        text_layout.addWidget(name_lbl)

        tmpl_label = chart.get("template_label", chart.get("template_id", "?"))
        tmpl_lbl = QLabel(tmpl_label)
        tmpl_lbl.setFont(QFont("Segoe UI", 8))
        tmpl_lbl.setStyleSheet("color: #8aa3b8; border: none;")
        text_layout.addWidget(tmpl_lbl)

        row_layout.addWidget(text_widget, 1)

        # Button column
        btn_col = QWidget()
        btn_col.setStyleSheet("border: none; background-color: transparent;")
        btn_layout = QVBoxLayout(btn_col)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(2)

        add_btn = QPushButton("+ Add")
        add_btn.setFixedSize(52, 26)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFont(QFont("Segoe UI", 9))
        add_btn.setStyleSheet(
            "QPushButton {"
            f" background-color: {DHIS2_BLUE};"
            "  border: none;"
            "  border-radius: 4px;"
            "  color: white;"
            "}"
            "QPushButton:hover { background-color: #155a8a; }"
        )
        add_btn.clicked.connect(lambda checked=False, c=chart: self.add_card(c))
        btn_layout.addWidget(add_btn)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(52, 22)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setFont(QFont("Segoe UI", 9))
        del_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent;"
            "  border: 1px solid #e0b0b0;"
            "  border-radius: 4px;"
            "  color: #c0392b;"
            "}"
            "QPushButton:hover { background-color: #f5c6cb; }"
        )
        del_btn.clicked.connect(
            lambda checked=False, c=chart: self._delete_library_chart(c)
        )
        btn_layout.addWidget(del_btn)

        row_layout.addWidget(btn_col)

        # Outer wrapper is a drag source carrying the chart id (REQ-DASH-LIB-04)
        wrapper = _LibDragFrame(chart.get("id", ""))
        wrapper.setStyleSheet("background-color: transparent; border: none;")
        wrapper.setCursor(Qt.CursorShape.OpenHandCursor)
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(6, 3, 6, 3)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(rf)
        return wrapper

    def _delete_library_chart(self, chart: dict):
        name = chart.get("name") or chart.get("title", "")
        reply = QMessageBox.question(
            self,
            "Delete Chart",
            f"Delete '{name}' from library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from config.chart_library import delete_chart
            delete_chart(chart["id"])
            self.refresh_library()

    # ─── Dashboard Canvas ─────────────────────────────────────────────────────

    def add_card(self, cfg: dict):
        """Add cfg to the manual 12-column grid (REQ-DASH-GRID-02)."""
        self._grid.add_card(cfg)        # grid.changed → _on_grid_changed updates count/buttons

    def _on_library_drop(self, chart_id: str) -> None:
        """A library chart was dropped on the grid — resolve its id and add it (REQ-DASH-GRID-02)."""
        from config.chart_library import load_charts
        chart = next((c for c in load_charts() if c.get("id") == chart_id), None)
        if chart:
            self._grid.add_card(dict(chart))

    def _on_open_chart_from_card(self, cfg: dict) -> None:
        """Card 'Edit' button → open that chart in the Chart Editor (quick edit from dashboard)."""
        cb = self._callbacks.get("on_open_chart")
        if cb:
            cb(cfg)

    def _on_grid_changed(self):
        """Keep the manual header count + Preview/Export/Deploy enabling in sync with the grid."""
        n = self._grid.count()
        self._card_count_lbl.setText(f"{n} chart{'s' if n != 1 else ''}")
        self._preview_btn.setEnabled(n > 0)
        self._export_btn.setEnabled(n > 0)
        self._deploy_btn.setEnabled(n > 0)

    def _on_preview(self):
        """Assemble the current dashboard and open it in the browser (like Chart Editor).

        Manual cards carry their grid layout (col width + row height) so the preview
        matches the configured sizes; preview=True injects sample-data fixtures so the
        charts render offline instead of spinning forever.
        """
        if not self._collect_cards():
            return
        cards = self._cards if self._mode == "ai" else self._grid.cards_with_layout()
        cards = self._synced_cards(cards)
        fixed = [c for c in cards if not (c.get("mode") == "ai" and c.get("html_path"))]
        name = self._dashboard_name() or "Dashboard"
        from charts.fixed_templates import assemble_dashboard
        from ui.preview_window import update_preview
        html = assemble_dashboard(fixed, title=name, filters=self._dash_filters,
                                  preview=True, custom_css=self._dash_custom_css)
        update_preview(html, title=name)

    def _on_clear_all(self):
        if not self._collect_cards():
            return
        reply = QMessageBox.question(
            self,
            "Clear Dashboard",
            "Remove all charts from this dashboard?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._on_clear_all_silent()

    def _collect_cards(self) -> list[dict]:
        """Active workspace's cards: AI chips in ai mode, else the manual grid.

        Manual cards carry their CURRENT grid layout (col width + row height) so
        export/deploy match what Preview and Save use — otherwise a height changed in
        the grid (live in it['h']) wouldn't reach the deployed HTML (it reads layout.h).
        """
        if self._mode == "ai":
            return list(self._cards)
        return self._grid.cards_with_layout()

    def _synced_cards(self, cards: list[dict]) -> list[dict]:
        """Refresh card content from the chart library by id (latest options) while
        keeping each card's canvas layout — so preview/export/deploy always reflect the
        current chart. See config.dashboard_library.sync_cards_with_charts."""
        from config.chart_library import load_charts
        from config.dashboard_library import sync_cards_with_charts
        return sync_cards_with_charts(cards, load_charts())

    # ─── Export / Deploy ──────────────────────────────────────────────────────

    def _on_edit_filters(self):
        """Open the dynamic filters manager (Superset-style list — REQ-DASH-FILTER)."""
        from ui.dashboard_filters_manager import FiltersManagerDialog
        from charts.fixed_templates import _normalize_filters
        titles = [c.get("title") or c.get("name") or f"Chart {i+1}"
                  for i, c in enumerate(self._collect_cards())]
        dlg = FiltersManagerDialog(self, _normalize_filters(self._dash_filters), titles,
                                   metadata=getattr(self, "_metadata", {}))
        if dlg.exec() == FiltersManagerDialog.DialogCode.Accepted and dlg.result_filters is not None:
            self._dash_filters = dlg.result_filters

    def _on_edit_css(self):
        """Open the dashboard-level CSS editor (Superset 'Edit CSS' — REQ-DASH-CSS-02)."""
        from ui.dashboard_css_dialog import CustomCssDialog
        css = CustomCssDialog.prompt(self, self._dash_custom_css)
        if css is not None:
            self._dash_custom_css = css
            # Apply → auto-refresh an already-open preview so the CSS shows at once
            # (the preview server auto-reloads the open tab). REQ-DASH-CSS-09.
            from ui.preview_server import is_preview_open
            if is_preview_open() and self._collect_cards():
                self._on_preview()

    def _filters_copy(self):
        """A copy of the dashboard filters — handles both V3 list and legacy flat dict."""
        f = self._dash_filters
        return [dict(x) for x in f] if isinstance(f, list) else dict(f)

    def _on_export(self):
        cb = self._callbacks.get("on_export")
        if cb:
            cb(self._synced_cards(self._collect_cards()), self._filters_copy(),
               custom_css=self._dash_custom_css)

    def _on_deploy(self):
        name = self._dashboard_name()
        if not name:
            QMessageBox.warning(self, "Deploy", "Save the dashboard first (it needs a name).")
            return
        cb = self._callbacks.get("on_deploy")
        if cb:
            cb(name, self._synced_cards(self._collect_cards()), self._filters_copy(),
               custom_css=self._dash_custom_css)

    # ─── Page 2: AI chat workspace ─────────────────────────────────────────────

    def _build_ai_workspace(self, parent: QWidget):
        """Conversational chat workspace: history, presets, suggestions, added-cards strip."""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(f"background-color: {HEADER_BG}; border: none;")
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(14, 0, 10, 0)
        title = QLabel("🤖 AI Dashboard Chat")
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #3a5068;")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch(1)

        change_btn = QPushButton("⇄ Change mode")
        change_btn.setFixedHeight(26)
        change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_btn.setFont(QFont("Segoe UI", 9))
        change_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent;"
            f" border: 1px solid #7a9ab0;"
            "  border-radius: 4px; color: #4a6a80; padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #e0ecf4; }"
        )
        change_btn.clicked.connect(self._on_change_mode)
        hdr_layout.addWidget(change_btn)
        layout.addWidget(hdr)

        # Conversation area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {PANEL_BG}; border: none; }}")
        self._chat_container = QWidget()
        self._chat_container.setStyleSheet(f"background-color: {PANEL_BG};")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(14, 12, 14, 12)
        self._chat_layout.setSpacing(8)
        self._chat_layout.addStretch(1)
        scroll.setWidget(self._chat_container)
        layout.addWidget(scroll, 1)

        self._add_chat_message(
            "assistant",
            "Hi! Describe the dashboard you want — e.g. \"monthly malaria cases, a district "
            "map, and a facility ranking\" — and I'll suggest charts to add.")

        # Added-charts strip (REQ-DASH-AI-06)
        self._ai_cards_bar = QFrame()
        self._ai_cards_bar.setStyleSheet(
            f"background-color: #eef4fa; border-top: 1px solid {BORDER_CLR};")
        cards_bar_layout = QHBoxLayout(self._ai_cards_bar)
        cards_bar_layout.setContentsMargins(12, 6, 12, 6)
        cards_bar_layout.setSpacing(6)
        added_lbl = QLabel("Added:")
        added_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        added_lbl.setStyleSheet("color: #5a7a9a; background: transparent;")
        cards_bar_layout.addWidget(added_lbl)
        self._ai_chips_layout = QHBoxLayout()
        self._ai_chips_layout.setContentsMargins(0, 0, 0, 0)
        self._ai_chips_layout.setSpacing(4)
        cards_bar_layout.addLayout(self._ai_chips_layout)
        cards_bar_layout.addStretch(1)
        self._ai_count_lbl = QLabel("0 charts")
        self._ai_count_lbl.setFont(QFont("Segoe UI", 8))
        self._ai_count_lbl.setStyleSheet("color: #8aa3b8; background: transparent;")
        cards_bar_layout.addWidget(self._ai_count_lbl)
        self._ai_cards_bar.setVisible(False)
        layout.addWidget(self._ai_cards_bar)

        # Quick-start presets (REQ-DASH-AI-02)
        preset_row = QFrame()
        preset_row.setStyleSheet(f"background-color: {HEADER_BG}; border: none;")
        pr_layout = QHBoxLayout(preset_row)
        pr_layout.setContentsMargins(12, 6, 12, 0)
        pr_layout.setSpacing(6)
        qs_lbl = QLabel("Quick start:")
        qs_lbl.setFont(QFont("Segoe UI", 9))
        qs_lbl.setStyleSheet("color: #5a7a9a; background: transparent;")
        pr_layout.addWidget(qs_lbl)
        self._preset_combo = QComboBox()
        self._preset_combo.setFont(QFont("Segoe UI", 9))
        for label, _ in self._CHAT_PRESETS:
            self._preset_combo.addItem(label)
        self._preset_combo.currentIndexChanged.connect(self._on_chat_preset)
        pr_layout.addWidget(self._preset_combo, 1)

        model_lbl = QLabel("Model:")
        model_lbl.setFont(QFont("Segoe UI", 9))
        model_lbl.setStyleSheet("color: #5a7a9a; background: transparent;")
        pr_layout.addWidget(model_lbl)
        self._ai_model_combo = QComboBox()
        self._ai_model_combo.setFont(QFont("Segoe UI", 9))
        for label, mid in _AI_MODELS:
            self._ai_model_combo.addItem(label, mid)
        # default to the model supplied by the app
        _idx = next((i for i, (_, mid) in enumerate(_AI_MODELS) if mid == self._ai_model), 0)
        self._ai_model_combo.setCurrentIndex(_idx)
        self._ai_model_combo.currentIndexChanged.connect(self._on_ai_model_changed)
        pr_layout.addWidget(self._ai_model_combo)
        layout.addWidget(preset_row)

        # Status + input row
        self._chat_status = QLabel("")
        self._chat_status.setFont(QFont("Segoe UI", 8))
        self._chat_status.setStyleSheet(
            f"color: #6a8aaa; background-color: {HEADER_BG}; padding: 2px 14px;")
        layout.addWidget(self._chat_status)

        input_row = QFrame()
        input_row.setStyleSheet(f"background-color: {HEADER_BG}; border: none;")
        ir_layout = QHBoxLayout(input_row)
        ir_layout.setContentsMargins(12, 4, 12, 8)
        ir_layout.setSpacing(6)

        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("Describe your dashboard…")
        self._chat_input.setFixedHeight(30)
        self._chat_input.setFont(QFont("Segoe UI", 10))
        self._chat_input.setStyleSheet(
            "QLineEdit {"
            "  border: 1px solid #c0cdd8; border-radius: 4px;"
            "  padding: 0 8px; background-color: white; color: #1e2d3d;"
            "}"
            "QLineEdit:focus { border-color: #1a6fa8; }"
        )
        self._chat_input.returnPressed.connect(self._on_chat_send)
        ir_layout.addWidget(self._chat_input, 1)

        self._chat_send_btn = QPushButton("➤")
        self._chat_send_btn.setFixedSize(36, 30)
        self._chat_send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chat_send_btn.setStyleSheet(
            "QPushButton {"
            f" background-color: {AI_GREEN}; border: none; border-radius: 4px;"
            "  color: white; font-size: 14px;"
            "}"
            "QPushButton:hover { background-color: #155a34; }"
            "QPushButton:disabled { background-color: #a8d8bc; }"
        )
        self._chat_send_btn.clicked.connect(self._on_chat_send)
        ir_layout.addWidget(self._chat_send_btn)
        layout.addWidget(input_row)

        # Action footer (Save / Export / Deploy) — shared self._cards
        footer = QFrame()
        footer.setStyleSheet(f"background-color: {HEADER_BG}; border-top: 1px solid {BORDER_CLR};")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(12, 6, 12, 8)
        f_layout.setSpacing(6)
        # Name + description are entered via the Save dialog (mirrors Chart Editor).
        self._ai_dash_lbl = QLabel("• new dashboard")
        self._ai_dash_lbl.setFont(QFont("Segoe UI", 10))
        self._ai_dash_lbl.setStyleSheet(
            "color: #3a5068; background-color: transparent; font-style: italic;")
        f_layout.addWidget(self._ai_dash_lbl, 1)
        # Canonical entity-action order (consistent across screens): New · Open · Save · Save As.
        for text, slot, attr in (
            ("🆕 New", self._on_new_dashboard, None),
            ("📂 Open", self._on_load_dashboard, None),
            ("💾 Save", self._on_save_dashboard, None),
            ("Save As…", self._on_save_dashboard_as, None),
            ("🎚 Filters", self._on_edit_filters, None),
            ("🎨 CSS", self._on_edit_css, None),
            ("👁 Preview", self._on_preview, "_ai_preview_btn"),
            ("⬇ Export", self._on_export, "_ai_export_btn"),
            ("🚀 Deploy", self._on_deploy, "_ai_deploy_btn"),
        ):
            b = QPushButton(text)
            b.setFixedHeight(28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton { background-color: white; border: 1px solid #7a9ab0;"
                "  border-radius: 4px; color: #2c4257; padding: 0 10px; }"
                "QPushButton:hover { background-color: #e0ecf4; }"
                "QPushButton:disabled { color: #aac0d0; border-color: #d0dde8; }")
            b.clicked.connect(slot)
            if attr:
                setattr(self, attr, b)
                b.setEnabled(False)
            f_layout.addWidget(b)
        layout.addWidget(footer)

    def _add_chat_message(self, role: str, text: str) -> None:
        """Append a chat bubble (role = 'user' | 'assistant')."""
        is_user = role == "user"
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setFont(QFont("Segoe UI", 10))
        bubble.setMaximumWidth(520)
        bubble.setStyleSheet(
            "QLabel {"
            f" background-color: {'#d8e8f6' if is_user else 'white'};"
            f" border: 1px solid {BORDER_CLR}; border-radius: 8px;"
            "  padding: 8px 10px; color: #1e2d3d;"
            "}"
        )
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if is_user:
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch(1)
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        holder.setLayout(row)
        # Insert before the trailing stretch
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, holder)

    def _on_chat_preset(self, idx: int) -> None:
        if 0 <= idx < len(self._CHAT_PRESETS):
            text = self._CHAT_PRESETS[idx][1]
            if text:
                self._chat_input.setText(text)

    def _on_ai_model_changed(self, idx: int) -> None:
        if 0 <= idx < len(_AI_MODELS):
            self._ai_model = _AI_MODELS[idx][1]

    def _mock_key_for(self, intent: str) -> str:
        """Pick a mock scenario from intent keywords (REQ-DASH-AI-07)."""
        low = intent.lower()
        if "supply" in low or "stock" in low:
            return "supply_chain"
        if "performance" in low or "compare" in low:
            return "performance_review"
        return "malaria_overview"

    def _on_chat_send(self) -> None:
        """Run the planner off-thread and render chart suggestions (REQ-DASH-AI-03/04/05)."""
        if self._chat_input is None:
            return
        text = self._chat_input.text().strip()
        if not text:
            return
        self._add_chat_message("user", text)
        self._chat_input.clear()
        self._clear_suggestions()

        from llm.ai_dashboard_planner import build_context
        context = build_context(self._metadata if hasattr(self, "_metadata") else {},
                                self._descriptions if hasattr(self, "_descriptions") else {})
        # Refine across turns: include current dashboard state as context (REQ-DASH-AI-04)
        existing = ", ".join(c.get("title", "") for c in self._cards)
        intent = text if not existing else f"{text}\n\nCurrent dashboard already has: {existing}"
        mock_key = None if self._ai_client is not None else self._mock_key_for(text)

        self._chat_status.setText("Generating recommendations…")
        self._chat_send_btn.setEnabled(False)
        self._chat_ctx = context     # stash for suggestion → config conversion

        self._chat_worker = _ChatPlannerWorker(
            intent, context, self._ai_client, mock_key, self._ai_model)
        self._chat_worker.finished.connect(self._on_recs_ready)
        self._chat_worker.failed.connect(self._on_recs_failed)
        self._chat_worker.start()

    def _on_recs_ready(self, recs: list) -> None:
        self._chat_send_btn.setEnabled(True)
        if not recs:
            self._chat_status.setText("")
            self._add_chat_message(
                "assistant", "I couldn't find matching charts. Try describing it differently.")
            return
        self._chat_status.setText(f"{len(recs)} suggestions")
        self._add_chat_message("assistant", f"Here are {len(recs)} charts I suggest:")
        self._render_suggestions(recs)

    def _on_recs_failed(self, msg: str) -> None:
        self._chat_send_btn.setEnabled(True)
        self._chat_status.setText("")
        self._add_chat_message("assistant", f"Error: {msg}")

    def _render_suggestions(self, recs: list) -> None:
        """Show each recommendation as a card with '+ Add' and a per-chart Refine box
        (REQ-DASH-AI-03; REQ-DASH-AI-REFINE-01)."""
        from llm.ai_dashboard_planner import recs_to_chart_configs
        ctx = getattr(self, "_chat_ctx", {"de_list": []})
        de_list = ctx.get("de_list", [])
        pairs = []                                   # [[rec, cfg], …] kept aligned for refine
        for rec in recs:
            cs = recs_to_chart_configs([rec], de_list)
            if cs:
                pairs.append([rec, cs[0]])
        self._last_suggestion_configs = [p[1] for p in pairs]   # exposed for tests
        if not pairs:
            return

        holder = QWidget(); holder.setStyleSheet("background: transparent;")
        v = QVBoxLayout(holder); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(4)
        states = []
        for rec, cfg in pairs:
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background-color: #f3f9f4; border: 1px solid #bfe0cb; border-radius: 6px; }")
            cv = QVBoxLayout(card); cv.setContentsMargins(10, 6, 8, 6); cv.setSpacing(4)
            top = QHBoxLayout(); top.setContentsMargins(0, 0, 0, 0)
            tw = QWidget(); tw.setStyleSheet("border: none; background: transparent;")
            tl = QVBoxLayout(tw); tl.setContentsMargins(0, 0, 0, 0); tl.setSpacing(1)
            t = QLabel(cfg.get("title", "")); t.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            t.setStyleSheet("color: #1e2d3d; border: none;"); tl.addWidget(t)
            m = QLabel(f"{cfg.get('template_id','')}  ·  {cfg.get('_ai_rationale','')}")
            m.setFont(QFont("Segoe UI", 8)); m.setStyleSheet("color: #6a8aaa; border: none;")
            m.setWordWrap(True); tl.addWidget(m)
            top.addWidget(tw, 1)
            add_b = QPushButton("+ Add"); add_b.setFixedSize(54, 26)
            add_b.setCursor(Qt.CursorShape.PointingHandCursor)
            add_b.setStyleSheet(
                "QPushButton { background-color: #1e7e48; border: none; border-radius: 4px;"
                "  color: white; font-size: 9px; }"
                "QPushButton:hover { background-color: #155a34; }"
                "QPushButton:disabled { background-color: #a8d8bc; }")
            top.addWidget(add_b, 0, Qt.AlignmentFlag.AlignVCenter)
            cv.addLayout(top)
            # Per-chart refine box
            rr = QHBoxLayout(); rr.setContentsMargins(0, 0, 0, 0); rr.setSpacing(4)
            rin = QLineEdit(); rin.setFixedHeight(24); rin.setFont(QFont("Segoe UI", 8))
            rin.setPlaceholderText("Sửa chart này… (vd: đổi sang pie, đổi metric)")
            rin.setStyleSheet("QLineEdit{border:1px solid #c0cdd8;border-radius:4px;padding:0 6px;"
                              "background:white;color:#1e2d3d;} QLineEdit:focus{border-color:#1a6fa8;}")
            rb = QPushButton("✎ Refine"); rb.setFixedHeight(24)
            rb.setCursor(Qt.CursorShape.PointingHandCursor)
            rb.setStyleSheet("QPushButton{background:#eef4fa;border:1px solid #7a9ab0;border-radius:4px;"
                             "color:#1a6fa8;font-size:8px;padding:0 8px;} QPushButton:hover{background:#d8e8f6;}"
                             "QPushButton:disabled{color:#aac0d0;border-color:#d0dde8;}")
            rr.addWidget(rin, 1); rr.addWidget(rb)
            cv.addLayout(rr)

            st = {"rec": rec, "cfg": cfg, "title": t, "meta": m, "input": rin, "add": add_b}
            states.append(st)
            add_b.clicked.connect(lambda _=False, s=st, b=add_b: self._on_add_suggestion(s["cfg"], b))
            rb.clicked.connect(lambda _=False, s=st, b=rb: self._on_refine_suggestion(s, b))
            rin.returnPressed.connect(lambda s=st, b=rb: self._on_refine_suggestion(s, b))
            v.addWidget(card)

        if len(states) > 1:
            all_b = QPushButton(f"Add all {len(states)}")
            all_b.setFixedHeight(24); all_b.setCursor(Qt.CursorShape.PointingHandCursor)
            all_b.setStyleSheet(
                "QPushButton { background: transparent; border: none; color: #1a6fa8; font-size: 9px; }"
                "QPushButton:hover { text-decoration: underline; }")
            all_b.clicked.connect(lambda _=False, ss=states: self._on_add_all([s["cfg"] for s in ss]))
            v.addWidget(all_b, 0, Qt.AlignmentFlag.AlignLeft)

        self._chat_layout.insertWidget(self._chat_layout.count() - 1, holder)
        self._suggestion_cards.append(holder)

    def _on_refine_suggestion(self, st: dict, btn) -> None:
        instr = st["input"].text().strip()
        if not instr:
            return
        ctx = getattr(self, "_chat_ctx", None)
        if not ctx:
            from llm.ai_dashboard_planner import build_context
            ctx = build_context(getattr(self, "_metadata", {}), getattr(self, "_descriptions", {}))
            self._chat_ctx = ctx
        btn.setEnabled(False); st["input"].setEnabled(False)
        self._chat_status.setText("Refining chart…")
        w = _RefineWorker(st["rec"], instr, ctx, self._ai_client, self._ai_model)
        w.finished.connect(lambda newrec, s=st, b=btn: self._on_refine_done(s, newrec, b))
        w.failed.connect(lambda msg, s=st, b=btn: self._on_refine_fail(s, b, msg))
        st["_worker"] = w                       # keep a reference so it isn't GC'd
        w.start()

    def _on_refine_done(self, st: dict, newrec: dict, btn) -> None:
        btn.setEnabled(True); st["input"].setEnabled(True); self._chat_status.setText("")
        from llm.ai_dashboard_planner import recs_to_chart_configs
        de_list = getattr(self, "_chat_ctx", {}).get("de_list", [])
        cs = recs_to_chart_configs([newrec], de_list)
        if not cs:
            self._chat_status.setText("Refine: no valid change")
            return
        st["rec"] = newrec; st["cfg"] = cs[0]; st["input"].clear()
        st["title"].setText(cs[0].get("title", ""))
        st["meta"].setText(f"{cs[0].get('template_id','')}  ·  {cs[0].get('_ai_rationale','')}")

    def _on_refine_fail(self, st: dict, btn, msg: str) -> None:
        btn.setEnabled(True); st["input"].setEnabled(True)
        self._chat_status.setText(f"Refine error: {msg}")

    def _on_add_suggestion(self, cfg: dict, btn: QPushButton) -> None:
        self._ai_add_card(dict(cfg))
        btn.setText("✓ Added")
        btn.setEnabled(False)

    def _on_add_all(self, configs: list) -> None:
        for cfg in configs:
            self._ai_add_card(dict(cfg))
        for holder in self._suggestion_cards:
            for b in holder.findChildren(QPushButton):
                b.setEnabled(False)

    def _clear_suggestions(self) -> None:
        for holder in self._suggestion_cards:
            holder.hide()
            holder.deleteLater()
        self._suggestion_cards.clear()

    # ─── AI added-cards strip ──────────────────────────────────────────────────

    def _ai_add_card(self, cfg: dict) -> None:
        """Add an AI-suggested card to the dashboard (data + chip). REQ-DASH-AI-06/13."""
        cfg["mode"] = "ai"                       # tag for export/deploy (REQ-DASH-AI-13)
        self._cards.append(cfg)
        chip = self._make_ai_chip(cfg)
        self._ai_chips_layout.addWidget(chip)
        self._ai_card_chips.append((chip, cfg))
        self._ai_cards_bar.setVisible(True)
        self._ai_update_count()
        if hasattr(self, "_ai_export_btn"):
            self._ai_preview_btn.setEnabled(True)
            self._ai_export_btn.setEnabled(True)
            self._ai_deploy_btn.setEnabled(True)

    def _make_ai_chip(self, cfg: dict) -> QFrame:
        chip = QFrame()
        chip.setStyleSheet(
            "QFrame { background-color: white; border: 1px solid #bfe0cb; border-radius: 10px; }")
        h = QHBoxLayout(chip); h.setContentsMargins(8, 2, 4, 2); h.setSpacing(4)
        lbl = QLabel(cfg.get("title", "?")); lbl.setFont(QFont("Segoe UI", 8))
        lbl.setStyleSheet("color: #2c4257; border: none;")
        h.addWidget(lbl)
        x = QPushButton("✕"); x.setFixedSize(16, 16); x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #c0392b; font-size: 9px; }"
            "QPushButton:hover { color: #e74c3c; }")
        x.clicked.connect(lambda _=False, c=cfg: self._ai_remove_card(c))
        h.addWidget(x)
        return chip

    def _ai_remove_card(self, cfg: dict) -> None:
        for i, (chip, c) in enumerate(self._ai_card_chips):
            if c is cfg:
                chip.hide(); chip.deleteLater()
                self._ai_card_chips.pop(i)
                break
        try:
            self._cards.remove(cfg)
        except ValueError:
            pass
        self._ai_update_count()
        if not self._cards and hasattr(self, "_ai_export_btn"):
            self._ai_preview_btn.setEnabled(False)
            self._ai_export_btn.setEnabled(False)
            self._ai_deploy_btn.setEnabled(False)
            self._ai_cards_bar.setVisible(False)

    def _ai_update_count(self) -> None:
        n = len(self._cards)
        self._ai_count_lbl.setText(f"{n} chart{'s' if n != 1 else ''}")

    # ─── Mode selection ────────────────────────────────────────────────────────

    def current_mode(self) -> str | None:
        """Return the active build mode: 'manual', 'ai', or None (chooser shown)."""
        return self._mode

    def _choose_mode(self, mode: str) -> None:
        """Switch to the workspace for `mode` (hard fork — no mixing)."""
        self._mode = mode
        if mode == "ai":
            self._stack.setCurrentWidget(self._ai_page)
        else:
            self._stack.setCurrentWidget(self._manual_page)

    def _on_change_mode(self) -> None:
        """Return to the mode chooser. Confirm first if the canvas has unsaved cards."""
        if self._collect_cards():
            reply = QMessageBox.question(
                self, "Change mode",
                "Switching mode will clear the current dashboard. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._on_clear_all_silent()
        self._set_current_dashboard(None)
        self._mode = None
        self._mount_embedded_load()          # refresh the inline saved-dashboards picker
        self._stack.setCurrentWidget(self._chooser_page)

    # ─── Save / Load Dashboard ────────────────────────────────────────────────

    def _dashboard_name(self) -> str:
        """The name of the dashboard currently being edited ('' if unsaved)."""
        return self._current_dashboard_name or ""

    def _update_dash_title(self) -> None:
        """Reflect the current dashboard name/description in both workspace labels."""
        if self._current_dashboard_name:
            txt = f"• {self._current_dashboard_name}"
            if self._current_dashboard_description:
                txt += f" — {self._current_dashboard_description}"
        else:
            txt = "• new dashboard"
        for lbl in (getattr(self, "_manual_dash_lbl", None), getattr(self, "_ai_dash_lbl", None)):
            if lbl is not None:
                lbl.setText(txt)

    def _set_current_dashboard(self, name: str | None, description: str = "") -> None:
        self._current_dashboard_name = name
        self._current_dashboard_description = description or ""
        self._update_dash_title()

    def _save_dashboard_named(self, name: str, description: str) -> bool:
        """Persist the current canvas under `name` (upsert by name). Returns success."""
        if not self._collect_cards():
            QMessageBox.information(self, "Save Dashboard", "Add at least one chart before saving.")
            return False
        # Manual cards carry their grid layout; AI cards are a flat list.
        cards = self._cards if self._mode == "ai" else self._grid.cards_with_layout()
        from config.dashboard_library import save_dashboard
        save_dashboard(name, list(cards), mode=self._mode or "manual",
                       filters=self._filters_copy(), description=description,
                       custom_css=self._dash_custom_css)
        self._set_current_dashboard(name, description)
        return True

    def _on_save_dashboard(self) -> None:
        """Save: update the dashboard being edited; if none yet, prompt name + description
        (mirrors the Chart Editor Save flow)."""
        if not self._collect_cards():
            QMessageBox.information(self, "Save Dashboard", "Add at least one chart before saving.")
            return
        if self._current_dashboard_name:
            if self._save_dashboard_named(self._current_dashboard_name,
                                          self._current_dashboard_description):
                QMessageBox.information(self, "Save Dashboard",
                                        f"Dashboard '{self._current_dashboard_name}' saved.")
            return
        # New dashboard → ask for a name + description.
        self._save_dashboard_as_dialog(initial_name="Dashboard", initial_desc="")

    def _on_save_dashboard_as(self) -> None:
        """Save As: always prompt for a new name + description and save a copy."""
        self._save_dashboard_as_dialog(
            initial_name=self._current_dashboard_name or "Dashboard",
            initial_desc=self._current_dashboard_description)

    def _save_dashboard_as_dialog(self, *, initial_name: str, initial_desc: str) -> None:
        from config.dashboard_library import get_dashboard
        from ui.save_entity_dialog import SaveEntityDialog
        res = SaveEntityDialog.prompt(self, title="Save Dashboard",
                                      name=initial_name, description=initial_desc)
        if not res:
            return
        name, description = res
        if name != self._current_dashboard_name and get_dashboard(name) is not None:
            if QMessageBox.question(
                self, "Overwrite?",
                f"A dashboard named '{name}' already exists. Overwrite it?",
            ) != QMessageBox.StandardButton.Yes:
                return
        if self._save_dashboard_named(name, description):
            QMessageBox.information(self, "Save Dashboard", f"Dashboard '{name}' saved.")

    def _on_new_dashboard(self) -> None:
        """New: clear the canvas and detach from any saved dashboard."""
        if self._collect_cards():
            if QMessageBox.question(
                self, "New Dashboard",
                "Clear the current dashboard and start a new one?",
            ) != QMessageBox.StandardButton.Yes:
                return
        self._on_clear_all_silent()
        self._dash_filters = {"period": "LAST_12_MONTHS", "ou": "USER_ORGUNIT"}
        self._dash_custom_css = ""
        self._set_current_dashboard(None, "")

    def _on_load_dashboard(self) -> None:
        from config.dashboard_library import load_dashboards
        from ui.load_dashboard_dialog import LoadDashboardDialog
        dashboards = load_dashboards()
        if not dashboards:
            QMessageBox.information(self, "Load Dashboard",
                                    "No saved dashboards found.\nSave a dashboard first.")
            return
        dlg = LoadDashboardDialog(self, dashboards)
        if dlg.exec() == LoadDashboardDialog.DialogCode.Accepted:
            selected = dlg.get_selected()
            if selected:
                self.load_dashboard_entry(selected)

    def load_dashboard_entry(self, entry: dict) -> None:
        """Open a saved dashboard: switch to its recorded mode and restore its cards."""
        mode = entry.get("mode", "manual")
        self._dash_filters = entry.get("filters") or {"period": "LAST_12_MONTHS", "ou": "USER_ORGUNIT"}
        self._dash_custom_css = entry.get("custom_css", "")
        self._choose_mode(mode)
        self._on_clear_all_silent()
        for card in entry.get("cards", []):
            if mode == "ai":
                self._ai_add_card(card)
            else:
                self.add_card(card)
        self._set_current_dashboard(entry.get("name", ""), entry.get("description", ""))

    def _on_clear_all_silent(self) -> None:
        """Clear both workspaces' card views + data, without prompting."""
        self._grid.clear()                       # manual grid (emits changed → updates UI)
        # AI chips + pending suggestions
        for chip, _ in list(self._ai_card_chips):
            chip.hide(); chip.deleteLater()
        self._ai_card_chips.clear()
        self._clear_suggestions()
        self._cards.clear()
        if hasattr(self, "_ai_export_btn"):
            self._ai_preview_btn.setEnabled(False)
            self._ai_export_btn.setEnabled(False)
            self._ai_deploy_btn.setEnabled(False)
            self._ai_cards_bar.setVisible(False)
            self._ai_update_count()

    # ─── Public API ──────────────────────────────────────────────────────────

    def get_cards(self) -> list[dict]:
        """Return a copy of the active workspace's card list."""
        return list(self._collect_cards())
