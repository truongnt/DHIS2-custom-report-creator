"""
DashboardFilterDialog — set the dashboard-level filter defaults (PART K).

DHIS2 adaptation of Superset native filters: a shared Period (time) filter and a
shared Org-Unit (value) filter scoped to every chart. The user picks the DEFAULT
selections here; the generated dashboard's filter bar starts on these and re-queries
all charts when the viewer changes them.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
    QVBoxLayout, QWidget,
)

DHIS2_BLUE = "#1a6fa8"
PANEL_BG   = "#f7f9fc"
BORDER_CLR = "#d0dde8"

# (label, value) — mirror the relative options the generated filter bar offers.
PERIOD_OPTIONS = [
    ("Last month", "LAST_MONTH"), ("Last 3 months", "LAST_3_MONTHS"),
    ("Last 6 months", "LAST_6_MONTHS"), ("Last 12 months", "LAST_12_MONTHS"),
    ("This quarter", "THIS_QUARTER"), ("Last quarter", "LAST_QUARTER"),
    ("This year", "THIS_YEAR"), ("Last year", "LAST_YEAR"),
    ("Custom range…", "__RANGE__"),                       # Time Range filter (REQ-DASH-FILTER-07)
]
# Org-Unit value filter: user-relative modes + hierarchical "by level" (REQ-DASH-FILTER-06).
OU_OPTIONS = [
    ("User organisation unit", "USER_ORGUNIT"),
    ("User sub-units", "USER_ORGUNIT_CHILDREN"),
    ("User sub-x2-units", "USER_ORGUNIT_GRANDCHILDREN"),
    ("All — Level 1 (national)", "LEVEL-1"),
    ("All — Level 2 (province)", "LEVEL-2"),
    ("All — Level 3 (district)", "LEVEL-3"),
    ("All — Level 4 (facility)", "LEVEL-4"),
]


def _recent_months(n: int = 36):
    """Return [(label, 'YYYYMM'), …] for the last n months (newest first)."""
    from datetime import date
    out, d = [], date.today()
    y, m = d.year, d.month
    for _ in range(n):
        out.append((f"Month {m}/{y}", f"{y}{m:02d}"))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return out


class DashboardFilterDialog(QDialog):
    """Edit {"period", "ou"} defaults for the dashboard's shared filter bar."""

    def __init__(self, parent, filters: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Dashboard Filters")
        self.resize(420, 240)
        self._filters = dict(filters or {})
        self.result_filters: dict | None = None
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QFrame(); hdr.setFixedHeight(40); hdr.setStyleSheet(f"background:{DHIS2_BLUE};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 14, 0)
        t = QLabel("Dashboard Filters"); t.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        t.setStyleSheet("color:white;background:transparent;")
        hl.addWidget(t); root.addWidget(hdr)

        body = QWidget(); body.setStyleSheet(f"background:{PANEL_BG};")
        bl = QVBoxLayout(body); bl.setContentsMargins(16, 14, 16, 10); bl.setSpacing(10)

        info = QLabel("These filters apply to ALL charts in the dashboard. Viewers can "
                      "change them; the values below are the defaults.")
        info.setWordWrap(True); info.setFont(QFont("Segoe UI", 9))
        info.setStyleSheet("color:#5a7a9a;")
        bl.addWidget(info)

        has_range = bool(self._filters.get("period_from") and self._filters.get("period_to"))

        self._pe = QComboBox()
        for label, val in PERIOD_OPTIONS:
            self._pe.addItem(label, val)
        self._select(self._pe, "__RANGE__" if has_range
                     else self._filters.get("period", "LAST_12_MONTHS"))
        self._pe.currentIndexChanged.connect(self._toggle_range)
        bl.addWidget(self._row("Default period:", self._pe))

        # Custom-range month pickers (shown only when period = Custom range)
        self._from = QComboBox(); self._to = QComboBox()
        for label, val in _recent_months():
            self._from.addItem(label, val); self._to.addItem(label, val)
        if has_range:
            self._select(self._from, self._filters["period_from"])
            self._select(self._to, self._filters["period_to"])
        self._range_row = self._row("From / To:", self._range_widget())
        bl.addWidget(self._range_row)

        self._ou = QComboBox()
        for label, val in OU_OPTIONS:
            self._ou.addItem(label, val)
        self._select(self._ou, self._filters.get("ou", "USER_ORGUNIT"))
        bl.addWidget(self._row("Default org unit:", self._ou))

        bl.addStretch(1)
        self._toggle_range()
        root.addWidget(body, 1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        from ui.qt_utils import style_dialog_buttons
        footer = style_dialog_buttons(btns)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        root.addWidget(footer)

    @staticmethod
    def _row(label: str, widget: QWidget) -> QWidget:
        w = QWidget(); w.setStyleSheet("background:transparent;")
        h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
        lbl = QLabel(label); lbl.setFixedWidth(120); lbl.setFont(QFont("Segoe UI", 9))
        lbl.setStyleSheet("color:#3a5068;")
        h.addWidget(lbl); h.addWidget(widget, 1)
        return w

    def _range_widget(self) -> QWidget:
        w = QWidget(); w.setStyleSheet("background:transparent;")
        h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(6)
        h.addWidget(self._from, 1); h.addWidget(self._to, 1)
        return w

    def _toggle_range(self) -> None:
        self._range_row.setVisible(self._pe.currentData() == "__RANGE__")

    @staticmethod
    def _select(combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _on_ok(self) -> None:
        ou = self._ou.currentData()
        if self._pe.currentData() == "__RANGE__":
            self.result_filters = {
                "ou": ou,
                "period_from": self._from.currentData(),
                "period_to": self._to.currentData(),
            }
        else:
            self.result_filters = {"period": self._pe.currentData(), "ou": ou}
        self.accept()
