"""
QuickFormPanel — report-request form shown when the chat is empty.

Flow:
  1. User selects Program / Dataset / Period / OU level.
  2. User configures N charts (title, type, data element, notes for AI).
  3. Click "Generate Dashboard" → on_generate(configs, scope, scope_text) callback.

PySide6 rewrite — same public API as the CTk version.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

DHIS2_BLUE = "#1a6fa8"

_SKIP = "— (skip) —"

_PERIOD_TYPES = ["Monthly", "Quarterly", "Yearly"]
_TIME_RANGES = [
    "Last 12 months",
    "Current year",
    "Last quarter",
    "Last 6 months",
    "Last 2 years",
    "Custom…",
]

_CHART_TYPES = [
    "Bar chart",
    "Stacked bar chart",
    "Line chart",
    "Area chart",
    "Pie chart",
    "Donut chart",
    "Scorecard / KPI card",
    "Data table",
    "Bar + Line combo",
    "Horizontal bar",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_label(parent: QWidget, text: str, bold: bool = False,
                color: str = "#4a6278", size: int = 10) -> QLabel:
    lbl = QLabel(text, parent)
    font = QFont()
    font.setPointSize(size)
    font.setBold(bold)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl


def _make_combo(parent: QWidget, items: list[str],
                min_width: int = 0, fixed_width: int = 0,
                editable: bool = False) -> QComboBox:
    cb = QComboBox(parent)
    cb.addItems(items)
    cb.setEditable(editable)
    cb.setStyleSheet(
        "QComboBox {"
        "  background: white; border: 1px solid #b8cfe8;"
        "  border-radius: 4px; padding: 2px 6px;"
        "  color: #1e2d3d; font-size: 11px;"
        "}"
        "QComboBox::drop-down { border: none; width: 20px; }"
        "QComboBox QAbstractItemView {"
        "  background: white; color: #1e2d3d;"
        "  selection-background-color: #dbeaf8;"
        "}"
    )
    cb.setFixedHeight(28)
    if fixed_width:
        cb.setFixedWidth(fixed_width)
    elif min_width:
        cb.setMinimumWidth(min_width)
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    else:
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return cb


# ---------------------------------------------------------------------------
# _ChartRow
# ---------------------------------------------------------------------------

class _ChartRow(QFrame):
    """Compact 2-row chart card: [#N | Title | Type | X] / [metric combo | Notes]."""

    def __init__(self, parent: QWidget, index: int, on_remove, **kwargs):
        super().__init__(parent, **kwargs)
        self._index = index
        self._on_remove = on_remove
        self._de_map: dict[str, str] = {}   # displayName -> UID

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame {"
            "  background: white;"
            "  border: 1px solid #dde8f4;"
            "  border-radius: 6px;"
            "}"
        )
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        # ── Row 0: #N | Title | Type | X ────────────────────────────────
        row0 = QHBoxLayout()
        row0.setSpacing(6)

        self._idx_lbl = QLabel(f"#{self._index}")
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self._idx_lbl.setFont(font)
        self._idx_lbl.setStyleSheet(f"color: {DHIS2_BLUE}; background: transparent; border: none;")
        self._idx_lbl.setFixedWidth(26)
        row0.addWidget(self._idx_lbl)

        self.title_entry = QLineEdit()
        self.title_entry.setPlaceholderText("Title")
        self.title_entry.setFixedHeight(26)
        self.title_entry.setStyleSheet(
            "QLineEdit {"
            "  background: white; border: 1px solid #b8cfe8;"
            "  border-radius: 4px; padding: 2px 6px;"
            "  color: #1e2d3d; font-size: 11px;"
            "}"
        )
        row0.addWidget(self.title_entry, 2)

        self.type_combo = QComboBox()
        self.type_combo.addItems(_CHART_TYPES)
        self.type_combo.setFixedHeight(26)
        self.type_combo.setFixedWidth(148)
        self.type_combo.setStyleSheet(
            "QComboBox {"
            "  background: white; border: 1px solid #b8cfe8;"
            "  border-radius: 4px; padding: 2px 6px;"
            "  color: #1e2d3d; font-size: 10px;"
            "}"
            "QComboBox::drop-down { border: none; width: 18px; }"
            "QComboBox QAbstractItemView {"
            "  background: white; color: #1e2d3d;"
            "  selection-background-color: #dbeaf8;"
            "}"
        )
        row0.addWidget(self.type_combo, 1)

        self._remove_btn = QPushButton("✕")
        self._remove_btn.setFixedSize(22, 22)
        self._remove_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent; color: #cccccc;"
            "  border: none; border-radius: 4px; font-size: 10px;"
            "}"
            "QPushButton:hover { background: #fde8e8; color: #e53e3e; }"
        )
        self._remove_btn.clicked.connect(self._on_remove)
        row0.addWidget(self._remove_btn)

        outer.addLayout(row0)

        # ── Row 1: metric combo | Notes entry ───────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        self.metric_combo = QComboBox()
        self.metric_combo.setEditable(True)
        self.metric_combo.setFixedHeight(26)
        self.metric_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.metric_combo.lineEdit().setPlaceholderText("Data element / metric")
        self.metric_combo.setStyleSheet(
            "QComboBox {"
            "  background: white; border: 1px solid #b8cfe8;"
            "  border-radius: 4px; padding: 2px 6px;"
            "  color: #1e2d3d; font-size: 11px;"
            "}"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox QAbstractItemView {"
            "  background: white; color: #1e2d3d;"
            "  selection-background-color: #dbeaf8;"
            "}"
        )
        row1.addWidget(self.metric_combo, 2)

        self.notes_entry = QLineEdit()
        self.notes_entry.setPlaceholderText("Notes for AI")
        self.notes_entry.setFixedHeight(26)
        self.notes_entry.setStyleSheet(
            "QLineEdit {"
            "  background: white; border: 1px solid #b8cfe8;"
            "  border-radius: 4px; padding: 2px 6px;"
            "  color: #1e2d3d; font-size: 11px;"
            "}"
        )
        row1.addWidget(self.notes_entry, 1)

        outer.addLayout(row1)

    # ── Public API ──────────────────────────────────────────────────────

    def update_index(self, index: int):
        self._index = index
        self._idx_lbl.setText(f"#{index}")

    def update_de_options(self, des: list[tuple[str, str]]):
        """Populate DE combobox. des = [(displayName, uid), ...]"""
        cur = self.metric_combo.currentText().strip()
        self._de_map = {name: uid for name, uid in des}
        self.metric_combo.blockSignals(True)
        self.metric_combo.clear()
        self.metric_combo.addItems([name for name, _ in des])
        # Keep current value if still valid, else restore as typed text
        if cur in self._de_map:
            idx = self.metric_combo.findText(cur)
            if idx >= 0:
                self.metric_combo.setCurrentIndex(idx)
            else:
                self.metric_combo.setCurrentText(cur)
        elif cur:
            self.metric_combo.setCurrentText(cur)
        else:
            self.metric_combo.setCurrentText("")
        self.metric_combo.blockSignals(False)

    def _metric_text(self) -> str:
        """Return 'Name (UID: xyz)' when UID known, else raw text."""
        name = self.metric_combo.currentText().strip()
        uid = self._de_map.get(name, "")
        if uid:
            return f"{name} (UID: {uid})"
        return name

    def get_config(self) -> dict:
        return {
            "index":       self._index,
            "title":       self.title_entry.text().strip(),
            "chart_type":  self.type_combo.currentText(),
            "metric":      self._metric_text(),
            "metric_uid":  self._de_map.get(self.metric_combo.currentText().strip(), ""),
            "description": "",
            "notes":       self.notes_entry.text().strip(),
        }

    def is_valid(self) -> bool:
        return bool(
            self.title_entry.text().strip()
            and self.metric_combo.currentText().strip()
        )

    def get_state(self) -> dict:
        return {
            "title":      self.title_entry.text(),
            "chart_type": self.type_combo.currentText(),
            "metric":     self.metric_combo.currentText(),
            "notes":      self.notes_entry.text(),
        }

    def restore_state(self, state: dict):
        if not state:
            return
        if state.get("title"):
            self.title_entry.setText(state["title"])
        if state.get("chart_type") in _CHART_TYPES:
            idx = self.type_combo.findText(state["chart_type"])
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
        if state.get("metric"):
            self.metric_combo.setCurrentText(state["metric"])
        if state.get("notes"):
            self.notes_entry.setText(state["notes"])


# ---------------------------------------------------------------------------
# QuickFormPanel
# ---------------------------------------------------------------------------

class QuickFormPanel(QFrame):
    """
    Compact form: scope selectors (top) + per-chart config (bottom).
    Callback: on_generate(configs: list[dict], scope: tuple[str, list[str]], scope_text: str)
    """

    MIN_CHARTS = 1
    MAX_CHARTS = 8
    DEFAULT_CHARTS = 3

    def __init__(self, parent: QWidget | None = None, on_generate=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._on_generate = on_generate
        self._metadata: dict = {}
        self._collapsed = False
        self._cards: list[_ChartRow] = []
        self._de_options: list[tuple[str, str]] = []

        self._prog_names: list[str] = []
        self._ds_names: list[str] = []
        self._ou_levels: list[dict] = []
        self._prog_map: dict[str, dict] = {}

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QuickFormPanel {"
            "  background: #f0f6fc;"
            "  border: 1px solid #c8ddf0;"
            "  border-radius: 8px;"
            "}"
        )

        self._build()

    # ── Public API ──────────────────────────────────────────────────────────────

    def set_metadata(self, metadata: dict):
        self._metadata = metadata or {}
        programs = self._metadata.get("programs", [])
        datasets = self._metadata.get("datasets", [])
        ou_levels = self._metadata.get("org_unit_levels", [])

        self._prog_names = [p.get("displayName", p.get("id", "?")) for p in programs]
        self._ds_names = [d.get("displayName", d.get("id", "?")) for d in datasets]
        self._ou_levels = ou_levels
        self._prog_map = {
            p.get("displayName", p.get("id", "?")): p for p in programs
        }

        prog_opts = [_SKIP] + (["(all)"] + self._prog_names if self._prog_names else [])
        ds_opts = [_SKIP] + (["(all)"] + self._ds_names if self._ds_names else [])
        ou_opts = ["(all)"] + [
            f"Level {l.get('level')}: {l.get('displayName', l.get('name', ''))}"
            for l in ou_levels
        ]

        self._prog_combo.blockSignals(True)
        self._prog_combo.clear()
        self._prog_combo.addItems(prog_opts)
        self._prog_combo.blockSignals(False)

        self._ds_combo.blockSignals(True)
        self._ds_combo.clear()
        self._ds_combo.addItems(ds_opts)
        self._ds_combo.blockSignals(False)

        self._ou_combo.blockSignals(True)
        self._ou_combo.clear()
        self._ou_combo.addItems(ou_opts)
        self._ou_combo.blockSignals(False)

        if self._prog_names:
            self._prog_row.show()
        else:
            self._prog_row.hide()
        if self._ds_names:
            self._ds_row.show()
        else:
            self._ds_row.hide()

        self._update_stage_row(prog_opts[0])

    def get_scope(self) -> tuple[str, list[str]]:
        """Return (program_name, [stage_names]) for metadata filtering."""
        _none = (_SKIP, "(none)", "(all)", "")
        prog = self._prog_combo.currentText()
        stages = [
            self._stage_lb.item(i).text()
            for i in range(self._stage_lb.count())
            if self._stage_lb.item(i).isSelected()
        ]
        return ("" if prog in _none else prog, stages)

    def get_analytics_params(self) -> dict:
        """Return period / org-unit params for DHIS2 analytics API calls."""
        return {
            "time_range":  self._range_combo.currentText(),
            "period_type": self._period_combo.currentText(),
            "ou_level":    self._ou_combo.currentText(),
        }

    def reset(self):
        self.set_metadata(self._metadata)
        self._period_combo.setCurrentText(_PERIOD_TYPES[0])
        self._range_combo.setCurrentText(_TIME_RANGES[0])
        for card in self._cards[:]:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        self._set_count(self.DEFAULT_CHARTS)
        self._count_lbl.setText(str(self.DEFAULT_CHARTS))

    def get_state(self) -> dict:
        stages = [
            self._stage_lb.item(i).text()
            for i in range(self._stage_lb.count())
            if self._stage_lb.item(i).isSelected()
        ]
        return {
            "program":     self._prog_combo.currentText(),
            "stages":      stages,
            "dataset":     self._ds_combo.currentText(),
            "period_type": self._period_combo.currentText(),
            "time_range":  self._range_combo.currentText(),
            "ou_level":    self._ou_combo.currentText(),
            "charts":      [c.get_state() for c in self._cards],
        }

    def restore_state(self, state: dict):
        if not state:
            return
        prog = state.get("program", "")
        if prog and prog in self._prog_names:
            self._prog_combo.setCurrentText(prog)
            self._update_stage_row(prog)
            saved_stages = set(state.get("stages", []))
            for i in range(self._stage_lb.count()):
                item = self._stage_lb.item(i)
                item.setSelected(item.text() in saved_stages)
        ds = state.get("dataset", "")
        if ds and ds in self._ds_names:
            self._ds_combo.setCurrentText(ds)
        if state.get("period_type") in _PERIOD_TYPES:
            self._period_combo.setCurrentText(state["period_type"])
        if state.get("time_range") in _TIME_RANGES:
            self._range_combo.setCurrentText(state["time_range"])
        ou = state.get("ou_level", "")
        if ou and self._ou_combo.findText(ou) >= 0:
            self._ou_combo.setCurrentText(ou)
        # Restore chart cards
        saved_charts = state.get("charts", [])
        if saved_charts:
            for card in self._cards[:]:
                card.setParent(None)
                card.deleteLater()
            self._cards.clear()
            for cs in saved_charts:
                self._add_card()
                self._cards[-1].restore_state(cs)
            self._count_lbl.setText(str(len(self._cards)))

    def set_generating(self, generating: bool):
        pass  # generate button is managed by app_window

    # ── Build ───────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setFixedHeight(28)
        hdr.setStyleSheet(
            "QFrame { background: #dbeaf8; border-radius: 0px; border: none; }"
        )
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(10, 0, 6, 0)
        hdr_layout.setSpacing(0)

        hdr_lbl = QLabel("📝  Report Settings")
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        hdr_lbl.setFont(font)
        hdr_lbl.setStyleSheet("color: #1e2d3d; background: transparent; border: none;")
        hdr_layout.addWidget(hdr_lbl)
        hdr_layout.addStretch()

        self._collapse_btn = QPushButton("▲")
        self._collapse_btn.setFixedSize(28, 20)
        self._collapse_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent; color: #4a6278;"
            "  border: none; border-radius: 4px; font-size: 10px;"
            "}"
            "QPushButton:hover { background: #c8ddf0; }"
        )
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        hdr_layout.addWidget(self._collapse_btn)

        root.addWidget(hdr)

        # ── Content ───────────────────────────────────────────────────────
        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(10, 6, 10, 8)
        content_layout.setSpacing(4)

        # ── Program row ──────────────────────────────────────────────────
        self._prog_row = QWidget()
        self._prog_row.setStyleSheet("background: transparent;")
        prog_hl = QHBoxLayout(self._prog_row)
        prog_hl.setContentsMargins(0, 0, 0, 0)
        prog_hl.setSpacing(6)
        prog_hl.addWidget(_make_label(self._prog_row, "Program:"))
        self._prog_combo = _make_combo(self._prog_row, ["(none)"])
        self._prog_combo.currentTextChanged.connect(self._on_program_change)
        prog_hl.addWidget(self._prog_combo)
        content_layout.addWidget(self._prog_row)

        # ── Stage row (hidden until program selected) ─────────────────────
        self._stage_row = QWidget()
        self._stage_row.setStyleSheet("background: transparent;")
        stage_hl = QHBoxLayout(self._stage_row)
        stage_hl.setContentsMargins(0, 0, 0, 0)
        stage_hl.setSpacing(6)
        stage_lbl = _make_label(self._stage_row, "Stage:")
        stage_lbl.setAlignment(Qt.AlignTop)
        stage_hl.addWidget(stage_lbl)

        self._stage_lb = QListWidget()
        self._stage_lb.setSelectionMode(QListWidget.MultiSelection)
        self._stage_lb.setFixedHeight(60)
        self._stage_lb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._stage_lb.setStyleSheet(
            "QListWidget {"
            "  background: white; border: 1px solid #b8cfe8;"
            "  border-radius: 4px; color: #1e2d3d; font-size: 10px;"
            "}"
            "QListWidget::item:selected {"
            "  background: #dbeafe; color: #1e2d3d;"
            "}"
        )
        self._stage_lb.itemSelectionChanged.connect(self._on_stage_select)
        stage_hl.addWidget(self._stage_lb)
        content_layout.addWidget(self._stage_row)
        self._stage_row.hide()

        # ── Dataset row ───────────────────────────────────────────────────
        self._ds_row = QWidget()
        self._ds_row.setStyleSheet("background: transparent;")
        ds_hl = QHBoxLayout(self._ds_row)
        ds_hl.setContentsMargins(0, 0, 0, 0)
        ds_hl.setSpacing(6)
        ds_hl.addWidget(_make_label(self._ds_row, "Dataset:"))
        self._ds_combo = _make_combo(self._ds_row, ["(none)"])
        ds_hl.addWidget(self._ds_combo)
        content_layout.addWidget(self._ds_row)

        # ── Period + Time range row ───────────────────────────────────────
        period_row = QWidget()
        period_row.setStyleSheet("background: transparent;")
        period_hl = QHBoxLayout(period_row)
        period_hl.setContentsMargins(0, 0, 0, 0)
        period_hl.setSpacing(6)
        period_hl.addWidget(_make_label(period_row, "Period type:"))
        self._period_combo = _make_combo(period_row, _PERIOD_TYPES, fixed_width=110)
        period_hl.addWidget(self._period_combo)
        period_hl.addSpacing(10)
        period_hl.addWidget(_make_label(period_row, "Time range:"))
        self._range_combo = _make_combo(period_row, _TIME_RANGES, fixed_width=180)
        period_hl.addWidget(self._range_combo)
        period_hl.addStretch()
        content_layout.addWidget(period_row)

        # ── OU level row ──────────────────────────────────────────────────
        ou_row = QWidget()
        ou_row.setStyleSheet("background: transparent;")
        ou_hl = QHBoxLayout(ou_row)
        ou_hl.setContentsMargins(0, 0, 0, 4)
        ou_hl.setSpacing(6)
        ou_hl.addWidget(_make_label(ou_row, "Org unit level:"))
        self._ou_combo = _make_combo(ou_row, ["(all)"], fixed_width=240)
        ou_hl.addWidget(self._ou_combo)
        ou_hl.addStretch()
        content_layout.addWidget(ou_row)

        # ── Horizontal divider ────────────────────────────────────────────
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #c8ddf0; border: none;")
        content_layout.addWidget(divider)
        content_layout.addSpacing(4)

        # ── Chart count row ───────────────────────────────────────────────
        cnt_row = QWidget()
        cnt_row.setStyleSheet("background: transparent;")
        cnt_hl = QHBoxLayout(cnt_row)
        cnt_hl.setContentsMargins(0, 0, 0, 0)
        cnt_hl.setSpacing(4)

        charts_lbl = QLabel("Charts:")
        font2 = QFont()
        font2.setPointSize(11)
        font2.setBold(True)
        charts_lbl.setFont(font2)
        charts_lbl.setStyleSheet("color: #1e2d3d; background: transparent;")
        cnt_hl.addWidget(charts_lbl)
        cnt_hl.addSpacing(4)

        btn_style = (
            "QPushButton {"
            f"  background: #dde8f4; color: {DHIS2_BLUE};"
            "  border: none; border-radius: 5px;"
            "  font-size: 14px; font-weight: bold;"
            "}"
            "QPushButton:hover { background: #c8d8e8; }"
        )

        self._dec_btn = QPushButton("−")
        self._dec_btn.setFixedSize(26, 26)
        self._dec_btn.setStyleSheet(btn_style)
        self._dec_btn.clicked.connect(self._dec_count)
        cnt_hl.addWidget(self._dec_btn)

        self._count_lbl = QLabel(str(self.DEFAULT_CHARTS))
        count_font = QFont()
        count_font.setPointSize(13)
        count_font.setBold(True)
        self._count_lbl.setFont(count_font)
        self._count_lbl.setFixedWidth(32)
        self._count_lbl.setAlignment(Qt.AlignCenter)
        self._count_lbl.setStyleSheet(f"color: {DHIS2_BLUE}; background: transparent;")
        cnt_hl.addWidget(self._count_lbl)

        self._inc_btn = QPushButton("+")
        self._inc_btn.setFixedSize(26, 26)
        self._inc_btn.setStyleSheet(btn_style)
        self._inc_btn.clicked.connect(self._inc_count)
        cnt_hl.addWidget(self._inc_btn)

        cnt_hl.addStretch()
        content_layout.addWidget(cnt_row)
        content_layout.addSpacing(4)

        # ── Scrollable chart cards ─────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setMinimumHeight(110)

        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 4, 0)
        self._cards_layout.setSpacing(6)
        self._cards_layout.addStretch()

        scroll.setWidget(self._cards_container)
        content_layout.addWidget(scroll)

        root.addWidget(self._content)

        # Initialise default cards
        self._set_count(self.DEFAULT_CHARTS)

    # ── Chart card management ────────────────────────────────────────────────────

    def _inc_count(self):
        self._set_count(len(self._cards) + 1)

    def _dec_count(self):
        self._set_count(max(self.MIN_CHARTS, len(self._cards) - 1))

    def _set_count(self, n: int):
        n = max(self.MIN_CHARTS, min(self.MAX_CHARTS, n))
        while len(self._cards) < n:
            self._add_card()
        while len(self._cards) > n:
            self._remove_card(self._cards[-1], _reindex=False)
        self._count_lbl.setText(str(len(self._cards)))

    def _add_card(self):
        idx = len(self._cards) + 1
        card = _ChartRow(self._cards_container, index=idx,
                         on_remove=lambda _card=None: None)
        # Wire remove after card exists so we can reference it
        card._remove_btn.clicked.disconnect()
        card._remove_btn.clicked.connect(lambda checked=False, c=card: self._remove_card(c))

        # Insert before the stretch item (always last)
        insert_pos = self._cards_layout.count() - 1
        self._cards_layout.insertWidget(insert_pos, card)
        card.update_de_options(self._de_options)
        self._cards.append(card)

    def _remove_card(self, card: _ChartRow, _reindex: bool = True):
        if len(self._cards) <= self.MIN_CHARTS:
            return
        self._cards_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()
        self._cards.remove(card)
        if _reindex:
            for i, c in enumerate(self._cards, 1):
                c.update_index(i)
        self._count_lbl.setText(str(len(self._cards)))

    # ── Internals ────────────────────────────────────────────────────────────────

    def _on_program_change(self, value: str):
        self._update_stage_row(value)
        self._on_stage_select()

    def _update_stage_row(self, prog_value: str):
        if prog_value in (_SKIP, "(none)", "(all)", ""):
            self._stage_lb.clear()
            self._stage_row.hide()
            self._de_options = []
            self._update_card_de_options()
            return
        prog = self._prog_map.get(prog_value)
        stages = (prog or {}).get("programStages", [])
        if not stages:
            self._stage_lb.clear()
            self._stage_row.hide()
            self._de_options = []
            self._update_card_de_options()
            return
        self._stage_lb.clear()
        for s in stages:
            self._stage_lb.addItem(s.get("displayName", s.get("id", "?")))
        self._stage_row.show()

    def _on_stage_select(self):
        """Rebuild DE list from selected stages using pre-fetched metadata."""
        prog_value = self._prog_combo.currentText()
        sel_stages = {
            self._stage_lb.item(i).text()
            for i in range(self._stage_lb.count())
            if self._stage_lb.item(i).isSelected()
        }

        all_stage_des = self._metadata.get("program_stage_data_elements", [])

        seen: set[str] = set()
        des: list[tuple[str, str]] = []
        for de in all_stage_des:
            # Filter by program
            if prog_value not in (_SKIP, "(none)", "(all)", ""):
                if de.get("program", {}).get("displayName") != prog_value:
                    continue
            # Filter by stage (if any selected; if none → all stages)
            if sel_stages:
                if de.get("stage", {}).get("displayName") not in sel_stages:
                    continue
            uid = de.get("id", "")
            name = de.get("displayName", "?")
            if uid and uid not in seen:
                seen.add(uid)
                des.append((name, uid))

        des.sort(key=lambda x: x[0])
        self._de_options = des
        self._update_card_de_options()

    def _update_card_de_options(self):
        for card in self._cards:
            card.update_de_options(self._de_options)

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._content.hide()
            self._collapse_btn.setText("▼")
        else:
            self._content.show()
            self._collapse_btn.setText("▲")

    def _build_scope_text(self) -> str:
        """Human-readable context description for the LLM prompt."""
        parts: list[str] = []
        prog = self._prog_combo.currentText()
        ds = self._ds_combo.currentText()
        if prog and prog not in (_SKIP, "(none)"):
            label = "all programs" if prog == "(all)" else f'program "{prog}"'
            sel_stages = [
                self._stage_lb.item(i).text()
                for i in range(self._stage_lb.count())
                if self._stage_lb.item(i).isSelected()
            ]
            if sel_stages and prog != "(all)":
                label += ", stages: " + ", ".join(f'"{s}"' for s in sel_stages)
            parts.append(label)
        if ds and ds not in (_SKIP, "(none)"):
            parts.append("all datasets" if ds == "(all)" else f'dataset "{ds}"')
        parts.append(
            f"period: {self._period_combo.currentText().lower()}, "
            f"{self._range_combo.currentText().lower()}"
        )
        ou = self._ou_combo.currentText()
        if ou and ou != "(all)":
            parts.append(f"org unit: {ou}")
        return "Context: " + "; ".join(parts) if parts else ""

    def _on_generate_click(self):
        from PySide6.QtWidgets import QMessageBox
        configs = [c.get_config() for c in self._cards]
        invalid = [c["index"] for c in configs if not c["title"] or not c["metric"]]
        if invalid:
            names = ", ".join(f"Chart {i}" for i in invalid)
            QMessageBox.warning(
                self,
                "Missing required fields",
                f"{names}: Title and Data element/metric are required.",
            )
            return
        if self._on_generate:
            scope = self.get_scope()
            scope_text = self._build_scope_text()
            self._on_generate(configs, scope, scope_text)
