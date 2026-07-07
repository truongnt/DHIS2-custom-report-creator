"""
FiltersManagerDialog — Superset-style dynamic dashboard filters (PART K v3).

Lets the user build a LIST of filters, each with:
  - alias        (display name shown on the dashboard's filter bar)
  - type         Org unit (value) / Period (time range) / Dimension (data source)
  - value        default selection (relative period, OU mode/level, or dimension value)
  - scope        which charts in the dashboard the filter applies to (all / a subset)

Returns `result_filters` as the V3 list consumed by charts/fixed_templates._normalize_filters.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QRadioButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from ui.dashboard_filter_dialog import OU_OPTIONS, PERIOD_OPTIONS, _recent_months

DHIS2_BLUE = "#1a6fa8"
PANEL_BG   = "#f7f9fc"
BORDER_CLR = "#d0dde8"

# Combo QSS incl. the popup-view rule — without it the dropdown list renders as a
# black top-level popup on some platforms (see ui/qt_utils._AGG_COMBO_QSS note).
COMBO_QSS = (
    "QComboBox { border:1px solid #c0cdd8; border-radius:4px; padding:2px 6px;"
    "  background:white; color:#1e2d3d; font-size:12px; }"
    "QComboBox:focus { border-color:#1a6fa8; }"
    "QComboBox::drop-down { border:none; width:18px; }"
    "QComboBox QAbstractItemView { background:#ffffff; color:#1e2d3d;"
    "  border:1px solid #c0cdd8; selection-background-color:#dbeafe; selection-color:#1e2d3d; }"
)

TYPE_OPTIONS = [("Org unit (value)", "ou"), ("Period (time)", "period"),
                ("Dimension (data source)", "dimension")]


def _default_filter(ftype: str = "dimension") -> dict:
    base = {"ou": ("Org unit", "USER_ORGUNIT"), "period": ("Period", "LAST_12_MONTHS"),
            "dimension": ("New filter", "")}[ftype]
    return {"id": f"f{id(object()) & 0xffff:x}", "alias": base[0], "type": ftype,
            "default": base[1], "from": "", "to": "", "scope": "all", "source": ""}


def _control_type(item: dict) -> str:
    """Map a DHIS2 valueType / optionSet to the filter control the viewer should get."""
    if ((item.get("optionSet") or {}).get("options")):
        return "option"
    vt = (item.get("valueType") or "").upper()
    if vt in ("INTEGER", "NUMBER", "INTEGER_POSITIVE", "INTEGER_NEGATIVE",
              "INTEGER_ZERO_OR_POSITIVE", "PERCENTAGE", "UNIT_INTERVAL"):
        return "number"
    if vt in ("DATE", "DATETIME", "TIME"):
        return "date"
    if vt in ("BOOLEAN", "TRUE_ONLY"):
        return "boolean"
    return "text"


def _build_dim_sources(metadata: dict) -> list[dict]:
    """Flatten loaded metadata into pickable dimension sources (tracker DE + program attr).

    Each: {label, kind, program, uid, source, value_type, options:[(label,value)]}
      source     = "<stageId>.<uid>" for a tracker DE, "<uid>" for a program attribute.
      value_type = option / number / date / boolean / text — decides the viewer's control.
    """
    out: list[dict] = []

    def _opts(item):
        return [(o.get("displayName") or o.get("code") or o.get("id"),
                 o.get("code") or o.get("id"))
                for o in ((item.get("optionSet") or {}).get("options") or [])]

    for de in (metadata or {}).get("program_stage_data_elements", []):
        stage = (de.get("stage") or {}).get("id", "")
        prog = de.get("program") or {}
        out.append({"label": de.get("displayName", ""), "kind": "DE",
                    "program": prog.get("displayName", ""), "program_id": prog.get("id", ""),
                    "uid": de.get("id", ""), "options": _opts(de),
                    "value_type": _control_type(de),
                    "source": f"{stage}.{de.get('id','')}" if stage else de.get("id", "")})
    for pa in (metadata or {}).get("tracked_entity_attributes", []):
        prog = pa.get("program") or {}
        out.append({"label": pa.get("displayName", ""), "kind": "PA",
                    "program": prog.get("displayName", ""), "program_id": prog.get("id", ""),
                    "uid": pa.get("id", ""), "options": _opts(pa),
                    "value_type": _control_type(pa), "source": pa.get("id", "")})
    return out


class FiltersManagerDialog(QDialog):
    def __init__(self, parent, filters=None, chart_titles=None, metadata=None):
        super().__init__(parent)
        self.setWindowTitle("Dashboard Filters")
        # Cap to the available screen so the popup never overflows (content scrolls).
        scr = QApplication.primaryScreen()
        avail = scr.availableGeometry() if scr else None
        h = min(560, (avail.height() - 80) if avail else 560)
        w = min(680, (avail.width() - 80) if avail else 680)
        self.resize(w, h)
        self.setMaximumHeight((avail.height() - 40) if avail else 700)
        self._titles = list(chart_titles or [])
        self._dim_sources = _build_dim_sources(metadata or {})
        self._has_dim_meta = bool(self._dim_sources)
        self._filters = [dict(f) for f in (filters or [])] or [
            _default_filter("ou"), _default_filter("period")]
        for f in self._filters:                       # ensure all keys present
            f.setdefault("from", ""); f.setdefault("to", "")
            f.setdefault("scope", "all"); f.setdefault("source", "")
        self.result_filters: list | None = None
        self._cur = -1
        self._build()
        if self._filters:
            self._list.setCurrentRow(0)

    # ── UI ──────────────────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        hdr = QFrame(); hdr.setFixedHeight(40); hdr.setStyleSheet(f"background:{DHIS2_BLUE};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 14, 0)
        t = QLabel("Dashboard Filters"); t.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        t.setStyleSheet("color:white;background:transparent;"); hl.addWidget(t)
        root.addWidget(hdr)

        body = QWidget(); body.setStyleSheet(f"background:{PANEL_BG};")
        bl = QHBoxLayout(body); bl.setContentsMargins(12, 12, 12, 12); bl.setSpacing(12)

        # Left — filter list + add/remove
        left = QVBoxLayout(); left.setSpacing(6)
        self._list = QListWidget(); self._list.setFixedWidth(190)
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list, 1)
        row = QHBoxLayout(); row.setSpacing(6)
        add = QPushButton("+ Add"); add.clicked.connect(self._on_add)
        rm = QPushButton("Remove"); rm.clicked.connect(self._on_remove)
        for b in (add, rm):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(add); row.addWidget(rm); left.addLayout(row)
        bl.addLayout(left)

        # Right — editor (scrollable so a tall editor never overflows the screen)
        self._editor = self._build_editor()
        for cb in self._editor.findChildren(QComboBox):
            cb.setStyleSheet(COMBO_QSS)          # ensure dropdown popup isn't black
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setWidget(self._editor)
        bl.addWidget(scroll, 1)
        root.addWidget(body, 1)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        try:
            from ui.qt_utils import style_dialog_buttons
            footer = style_dialog_buttons(btns)
        except Exception:
            footer = btns
        btns.accepted.connect(self._on_ok); btns.rejected.connect(self.reject)
        root.addWidget(footer)
        self._refresh_list()

    def _build_editor(self) -> QWidget:
        w = QWidget(); w.setStyleSheet("background:transparent;")
        v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(8)

        self._alias = QLineEdit(); self._alias.textEdited.connect(self._commit)
        v.addWidget(self._row("Alias:", self._alias))

        self._type = QComboBox()
        for label, val in TYPE_OPTIONS:
            self._type.addItem(label, val)
        self._type.currentIndexChanged.connect(self._on_type_change)
        v.addWidget(self._row("Type:", self._type))

        # Value editors (one per type) in a stack
        self._stack = QStackedWidget()
        # ou
        self._ou = QComboBox()
        for label, val in OU_OPTIONS:
            self._ou.addItem(label, val)
        self._ou.currentIndexChanged.connect(self._commit)
        self._stack.addWidget(self._wrap(self._ou))
        # period (+ range)
        pe_w = QWidget(); pe_w.setStyleSheet("background:transparent;")
        pv = QVBoxLayout(pe_w); pv.setContentsMargins(0, 0, 0, 0); pv.setSpacing(6)
        self._pe = QComboBox()
        for label, val in PERIOD_OPTIONS:
            self._pe.addItem(label, val)
        self._pe.currentIndexChanged.connect(self._on_period_change)
        pv.addWidget(self._pe)
        self._from = QComboBox(); self._to = QComboBox()
        for label, val in _recent_months():
            self._from.addItem(label, val); self._to.addItem(label, val)
        self._from.currentIndexChanged.connect(self._commit)
        self._to.currentIndexChanged.connect(self._commit)
        self._range_row = QWidget(); rr = QHBoxLayout(self._range_row)
        rr.setContentsMargins(0, 0, 0, 0); rr.setSpacing(6)
        rr.addWidget(QLabel("From")); rr.addWidget(self._from, 1)
        rr.addWidget(QLabel("To")); rr.addWidget(self._to, 1)
        pv.addWidget(self._range_row)
        self._stack.addWidget(pe_w)
        # dimension — metadata-driven Program → DE/PA → Value picker (fallback: free text)
        dim_w = QWidget(); dim_w.setStyleSheet("background:transparent;")
        dv = QVBoxLayout(dim_w); dv.setContentsMargins(0, 0, 0, 0); dv.setSpacing(6)
        if self._has_dim_meta:
            self._dim_prog = QComboBox(); self._dim_prog.addItem("All programs", "")
            for p in sorted({s["program"] for s in self._dim_sources if s["program"]}):
                self._dim_prog.addItem(p, p)
            self._dim_prog.currentIndexChanged.connect(self._on_dim_prog_change)
            dv.addWidget(self._labeled("Program", self._dim_prog))
            self._dim_src = QComboBox()
            self._dim_src.currentIndexChanged.connect(self._on_dim_src_change)
            dv.addWidget(self._labeled("DE / PA", self._dim_src))
            self._dim_val = QComboBox(); self._dim_val.setEditable(True)
            self._dim_val.currentIndexChanged.connect(self._commit)
            self._dim_val.editTextChanged.connect(self._commit)
            dv.addWidget(self._labeled("Default", self._dim_val))
            hint = QLabel("Viewers pick the value on the dashboard; the control type follows "
                          "the DE/PA data type. 'Default' is optional (blank = no filter).")
            hint.setWordWrap(True); hint.setStyleSheet("color:#8aa3b8;font-size:11px;")
            dv.addWidget(hint)
            self._populate_dim_src("")
        else:
            self._src = QLineEdit(); self._src.setPlaceholderText("Dimension UID (data source)")
            self._src.textEdited.connect(self._commit)
            self._dimval = QLineEdit(); self._dimval.setPlaceholderText("Default value")
            self._dimval.textEdited.connect(self._commit)
            dv.addWidget(self._src); dv.addWidget(self._dimval)
            note = QLabel("Connect + load metadata to pick a Program and DE/PA here.")
            note.setWordWrap(True); note.setStyleSheet("color:#8aa3b8;font-size:11px;")
            dv.addWidget(note)
        self._stack.addWidget(dim_w)
        v.addWidget(self._row("Value:", self._stack))

        # Scope
        self._scope_all = QRadioButton("All charts")
        self._scope_sel = QRadioButton("Selected charts:")
        grp = QButtonGroup(self); grp.addButton(self._scope_all); grp.addButton(self._scope_sel)
        self._scope_all.toggled.connect(self._on_scope_toggle)
        v.addWidget(self._scope_all); v.addWidget(self._scope_sel)
        self._charts = QListWidget()
        self._charts.setMaximumHeight(150)              # bounded → no screen overflow
        for i, title in enumerate(self._titles):
            it = QListWidgetItem(f"{i+1}. {title}")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked)
            self._charts.addItem(it)
        self._charts.itemChanged.connect(lambda *_: self._commit())
        v.addWidget(self._charts, 1)
        return w

    @staticmethod
    def _row(label, widget):
        w = QWidget(); w.setStyleSheet("background:transparent;")
        h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
        lbl = QLabel(label); lbl.setFixedWidth(60); lbl.setFont(QFont("Segoe UI", 9))
        lbl.setStyleSheet("color:#3a5068;")
        h.addWidget(lbl, 0, Qt.AlignmentFlag.AlignTop); h.addWidget(widget, 1)
        return w

    @staticmethod
    def _wrap(widget):
        w = QWidget(); w.setStyleSheet("background:transparent;")
        h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); h.addWidget(widget)
        return w

    @staticmethod
    def _labeled(text, widget):
        w = QWidget(); w.setStyleSheet("background:transparent;")
        h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(6)
        l = QLabel(text); l.setFixedWidth(70); l.setStyleSheet("color:#5a7a9a;font-size:11px;")
        h.addWidget(l); h.addWidget(widget, 1)
        return w

    # ── Dimension picker (metadata-driven Program → DE/PA → Value) ──────────────
    def _populate_dim_src(self, program: str):
        self._dim_src.blockSignals(True)
        self._dim_src.clear()
        for i, s in enumerate(self._dim_sources):
            if program and s["program"] != program:
                continue
            self._dim_src.addItem(f"[{s['kind']}] {s['label']}", i)
        self._dim_src.blockSignals(False)
        self._populate_dim_val()

    def _populate_dim_val(self):
        idx = self._dim_src.currentData()
        self._dim_val.blockSignals(True)
        self._dim_val.clear()
        if isinstance(idx, int) and 0 <= idx < len(self._dim_sources):
            for label, val in self._dim_sources[idx]["options"]:
                self._dim_val.addItem(label, val)
        self._dim_val.blockSignals(False)

    def _on_dim_prog_change(self):
        if getattr(self, "_loading", False):
            return
        self._populate_dim_src(self._dim_prog.currentData())
        self._commit()

    def _on_dim_src_change(self):
        self._populate_dim_val()
        if getattr(self, "_loading", False):
            return
        # Auto-fill alias with the picked DE/PA name when the user hasn't set one.
        idx = self._dim_src.currentData()
        if not self._alias.text().strip() and isinstance(idx, int) and 0 <= idx < len(self._dim_sources):
            self._alias.setText(self._dim_sources[idx]["label"])
        self._commit()

    # ── List management ───────────────────────────────────────────────────────
    def _refresh_list(self):
        self._list.blockSignals(True)
        self._list.clear()
        for f in self._filters:
            self._list.addItem(f"{f.get('alias') or f['type']}  ·  {f['type']}")
        self._list.blockSignals(False)

    def _on_add(self):
        self._filters.append(_default_filter("dimension"))
        self._refresh_list()
        self._list.setCurrentRow(len(self._filters) - 1)

    def _on_remove(self):
        if 0 <= self._cur < len(self._filters):
            self._filters.pop(self._cur)
            self._cur = -1
            self._refresh_list()
            if self._filters:
                self._list.setCurrentRow(min(self._cur if self._cur >= 0 else 0,
                                             len(self._filters) - 1))

    # ── Editor binding ───────────────────────────────────────────────────────
    def _on_select(self, row):
        self._cur = row
        if not (0 <= row < len(self._filters)):
            return
        f = self._filters[row]
        self._loading = True
        self._alias.setText(f.get("alias", ""))
        self._type.setCurrentIndex(max(0, self._type.findData(f.get("type", "dimension"))))
        self._sync_value_widgets(f)
        is_all = f.get("scope", "all") == "all"
        self._scope_all.setChecked(is_all); self._scope_sel.setChecked(not is_all)
        sel = set(f.get("scope") if isinstance(f.get("scope"), list) else [])
        for i in range(self._charts.count()):
            self._charts.item(i).setCheckState(
                Qt.CheckState.Checked if i in sel else Qt.CheckState.Unchecked)
        self._charts.setEnabled(not is_all)
        self._loading = False

    def _sync_value_widgets(self, f):
        self._stack.setCurrentIndex({"ou": 0, "period": 1, "dimension": 2}.get(f["type"], 2))
        if f["type"] == "ou":
            i = self._ou.findData(f.get("default", "USER_ORGUNIT")); self._ou.setCurrentIndex(max(0, i))
        elif f["type"] == "period":
            has_range = bool(f.get("from") and f.get("to"))
            i = self._pe.findData("__RANGE__" if has_range else f.get("default", "LAST_12_MONTHS"))
            self._pe.setCurrentIndex(max(0, i))
            if has_range:
                self._from.setCurrentIndex(max(0, self._from.findData(f["from"])))
                self._to.setCurrentIndex(max(0, self._to.findData(f["to"])))
            self._range_row.setVisible(self._pe.currentData() == "__RANGE__")
        elif self._has_dim_meta:
            match = next((i for i, s in enumerate(self._dim_sources)
                          if s["source"] == f.get("source")), None)
            prog = self._dim_sources[match]["program"] if match is not None else ""
            self._dim_prog.setCurrentIndex(max(0, self._dim_prog.findData(prog)))
            self._populate_dim_src(prog)
            if match is not None:
                self._dim_src.setCurrentIndex(max(0, self._dim_src.findData(match)))
            self._populate_dim_val()
            dv = f.get("default", "")
            vi = self._dim_val.findData(dv)
            if vi >= 0:
                self._dim_val.setCurrentIndex(vi)
            else:
                self._dim_val.setEditText(dv)
        else:
            self._src.setText(f.get("source", "")); self._dimval.setText(f.get("default", ""))

    def _on_type_change(self):
        if getattr(self, "_loading", False) or not (0 <= self._cur < len(self._filters)):
            return
        self._filters[self._cur]["type"] = self._type.currentData()
        self._sync_value_widgets(self._filters[self._cur])
        self._commit()

    def _on_period_change(self):
        self._range_row.setVisible(self._pe.currentData() == "__RANGE__")
        self._commit()

    def _on_scope_toggle(self, *_):
        self._charts.setEnabled(self._scope_sel.isChecked())
        self._commit()

    def _commit(self):
        if getattr(self, "_loading", False) or not (0 <= self._cur < len(self._filters)):
            return
        f = self._filters[self._cur]
        f["alias"] = self._alias.text().strip() or f["type"]
        f["type"] = self._type.currentData()
        if f["type"] == "ou":
            f["default"] = self._ou.currentData(); f["from"] = f["to"] = ""
        elif f["type"] == "period":
            if self._pe.currentData() == "__RANGE__":
                f["default"] = "__RANGE__"
                f["from"] = self._from.currentData(); f["to"] = self._to.currentData()
            else:
                f["default"] = self._pe.currentData(); f["from"] = f["to"] = ""
        elif self._has_dim_meta:
            idx = self._dim_src.currentData()
            if isinstance(idx, int) and 0 <= idx < len(self._dim_sources):
                s = self._dim_sources[idx]
                f["source"] = s["source"]
                f["options"] = s["options"]            # carried so the bar renders the right control
                f["value_type"] = s.get("value_type", "text")
                f["program"] = s.get("program_id", "")  # only filter charts of this program
            vd = self._dim_val.currentData()
            f["default"] = vd if vd not in (None, "") else self._dim_val.currentText().strip()
        else:
            f["source"] = self._src.text().strip(); f["default"] = self._dimval.text().strip()
            f["value_type"] = "text"; f["options"] = []
        if self._scope_all.isChecked():
            f["scope"] = "all"
        else:
            f["scope"] = [i for i in range(self._charts.count())
                          if self._charts.item(i).checkState() == Qt.CheckState.Checked]
        # live label
        if 0 <= self._cur < self._list.count():
            self._list.item(self._cur).setText(f"{f.get('alias') or f['type']}  ·  {f['type']}")

    def _on_ok(self):
        self._commit()
        self.result_filters = self._filters
        self.accept()
