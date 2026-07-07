"""
FilterConfigDialog — cấu hình bộ lọc metadata (PySide6).

Layout (scope-only — REQ-FILTER-08 removed the refine tier):
  ┌─────────────────────────────────────────────────────────┐
  │  SCOPE  (Programs bên trái | Datasets bên phải)         │
  │  Chọn programs/datasets xác định phạm vi dữ liệu sẽ dùng│
  ├─────────────────────────────────────────────────────────┤
  │  Summary                                                 │
  │  [Clear All]  [Cancel]  [Apply & Load Metadata]         │
  └─────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QLabel, QPushButton, QCheckBox, QLineEdit,
    QScrollArea, QWidget, QSplitter, QTabWidget,
    QSizePolicy,
)

DHIS2_BLUE = "#1a6fa8"
BORDER     = "#d0dde8"
PANEL_BG   = "#f7f9fc"


def _section_header(text: str, sub: str = "") -> QFrame:
    hdr = QFrame()
    hdr.setFixedHeight(38)
    hdr.setStyleSheet("QFrame { background:#1a3a52; border:none; }")
    lay = QHBoxLayout(hdr)
    lay.setContentsMargins(14, 0, 14, 0)
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color:white; font-size:12px; font-weight:bold; background:transparent;"
    )
    lay.addWidget(lbl)
    if sub:
        slbl = QLabel(sub)
        slbl.setStyleSheet("color:#8aa3b8; font-size:10px; background:transparent;")
        lay.addWidget(slbl)
    lay.addStretch()
    return hdr


class FilterConfigDialog(QDialog):

    def __init__(self, parent, filter_options: dict, current_cfg: dict):
        super().__init__(parent)
        self.setWindowTitle("Configure Metadata Filters")
        self.setModal(True)
        # Fit within the available screen so the bottom action bar is never clipped.
        from PySide6.QtGui import QGuiApplication
        scr = QGuiApplication.primaryScreen()
        avail = scr.availableGeometry() if scr else None
        w = min(1000, avail.width() - 80) if avail else 1000
        h = min(700, avail.height() - 80) if avail else 700
        self.setMinimumSize(min(820, w), min(520, h))
        self.resize(w, h)

        self._opts  = filter_options
        self._cfg   = dict(current_cfg)
        self.result: dict | None = None

        # Checkbox tracking: uid → QCheckBox
        self._prg_cbs: dict[str, QCheckBox] = {}
        self._ds_cbs:  dict[str, QCheckBox] = {}

        self._build()
        self._restore_selection()

    # ─── Layout ──────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Tầng 1: Scope ──────────────────────────────────────────────────
        root.addWidget(_section_header(
            "① SCOPE — Programs & Datasets",
            "Xác định phạm vi dữ liệu sẽ tải",
        ))

        scope_splitter = QSplitter(Qt.Orientation.Horizontal)
        scope_splitter.setHandleWidth(1)
        scope_splitter.setStyleSheet(f"QSplitter::handle {{ background:{BORDER}; }}")
        scope_splitter.setMinimumHeight(140)   # panels scroll internally; keep dialog short

        scope_splitter.addWidget(self._build_scope_panel(
            icon="🗂", title="Programs",
            hint="PI + Data Elements của program sẽ tự động được tải",
            items=self._opts.get("programs", []),
            cb_dict=self._prg_cbs,
            col3_key="type", col3_label="Loại",
        ))
        scope_splitter.addWidget(self._build_scope_panel(
            icon="📋", title="Datasets",
            hint="Data Elements của dataset sẽ tự động được tải",
            items=self._opts.get("datasets", []),
            cb_dict=self._ds_cbs,
            col3_key="periodType", col3_label="Period",
        ))
        scope_splitter.setStretchFactor(0, 1)
        scope_splitter.setStretchFactor(1, 1)
        root.addWidget(scope_splitter, stretch=2)

        # (Removed: "② THU HẸP THÊM" — DE-group + keyword refinement. REQ-FILTER-08:
        #  scope alone defines the load; backend fetch_all tolerates the missing keys.)

        # ── Summary label ───────────────────────────────────────────────────
        self._summary_lbl = QLabel("")
        self._summary_lbl.setStyleSheet(
            "color:#a85600; font-size:11px; padding:4px 16px; background:white;"
        )
        self._summary_lbl.setWordWrap(True)
        root.addWidget(self._summary_lbl)

        # ── Bottom bar ──────────────────────────────────────────────────────
        bottom = QFrame()
        bottom.setFixedHeight(52)
        bottom.setStyleSheet(f"QFrame {{ background:#f0f4f8; border:none; }}")
        bot_lay = QHBoxLayout(bottom)
        bot_lay.setContentsMargins(16, 8, 16, 8)
        bot_lay.setSpacing(8)

        clear_btn = QPushButton("Clear All")
        clear_btn.setFixedHeight(34)
        clear_btn.setStyleSheet(
            "QPushButton { background:transparent; border:1px solid #e74c3c; "
            "border-radius:4px; color:#e74c3c; font-size:11px; padding:0 16px; }"
            "QPushButton:hover { background:#fdecea; }"
        )
        clear_btn.clicked.connect(self._clear_all)
        bot_lay.addWidget(clear_btn)
        bot_lay.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; border:1px solid {BORDER}; "
            "border-radius:4px; color:#4a6278; font-size:11px; padding:0 16px; }"
            "QPushButton:hover { background:#e8f0f8; }"
        )
        cancel_btn.clicked.connect(self._on_cancel)
        bot_lay.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply && Load Metadata ▶")
        apply_btn.setFixedHeight(34)
        apply_btn.setStyleSheet(
            f"QPushButton {{ background:{DHIS2_BLUE}; border:none; border-radius:4px; "
            "color:white; font-size:11px; font-weight:bold; padding:0 20px; }"
            "QPushButton:hover { background:#155a8a; }"
        )
        apply_btn.clicked.connect(self._on_apply)
        self.apply_btn = apply_btn          # exposed for layout/visibility tests
        bot_lay.addWidget(apply_btn)

        root.addWidget(bottom)
        self._update_summary()

    # ── Scope panel ──────────────────────────────────────────────────────────

    def _build_scope_panel(
        self, icon: str, title: str, hint: str,
        items: list[dict], cb_dict: dict[str, QCheckBox],
        col3_key: str, col3_label: str,
    ) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Panel header
        hdr = QFrame()
        hdr.setStyleSheet("QFrame { background:#e8f0f8; border:none; }")
        hdr_lay = QVBoxLayout(hdr)
        hdr_lay.setContentsMargins(14, 8, 14, 8)
        hdr_lay.setSpacing(2)
        title_lbl = QLabel(f"{icon}  {title}")
        title_lbl.setStyleSheet(
            "font-size:13px; font-weight:bold; color:#1e2d3d; background:transparent;"
        )
        hdr_lay.addWidget(title_lbl)
        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet("font-size:10px; color:#6b8299; background:transparent;")
        hdr_lay.addWidget(hint_lbl)
        lay.addWidget(hdr)

        # Quick-select row
        qs_row = QWidget()
        qs_row.setStyleSheet("background:#dde8f0;")
        qs_lay = QHBoxLayout(qs_row)
        qs_lay.setContentsMargins(8, 3, 8, 3)
        qs_lay.setSpacing(6)

        all_btn = QPushButton("All")
        all_btn.setFixedHeight(20)
        all_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; border:1px solid {DHIS2_BLUE}; "
            f"border-radius:3px; color:{DHIS2_BLUE}; font-size:9px; padding:0 8px; }}"
            f"QPushButton:hover {{ background:#e8f0f8; }}"
        )
        all_btn.clicked.connect(lambda: self._select_all(cb_dict, True))
        qs_lay.addWidget(all_btn)

        none_btn = QPushButton("None")
        none_btn.setFixedHeight(20)
        none_btn.setStyleSheet(
            "QPushButton { background:transparent; border:1px solid #8aa3b8; "
            "border-radius:3px; color:#4a6278; font-size:9px; padding:0 8px; }"
            "QPushButton:hover { background:#e8f0f8; }"
        )
        none_btn.clicked.connect(lambda: self._select_all(cb_dict, False))
        qs_lay.addWidget(none_btn)
        qs_lay.addStretch()

        col3_hdr = QLabel(col3_label)
        col3_hdr.setStyleSheet("font-size:9px; color:#4a6278; background:transparent;")
        col3_hdr.setFixedWidth(70)
        col3_hdr.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        qs_lay.addWidget(col3_hdr)
        lay.addWidget(qs_row)

        # Scrollable list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background:white; border:none; }"
            "QScrollBar:vertical { width:8px; }"
            "QScrollBar::handle:vertical { background:#c0cdd8; border-radius:4px; }"
        )
        inner = QWidget()
        inner.setStyleSheet("background:white;")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 0, 0)
        inner_lay.setSpacing(0)

        if not items:
            lbl = QLabel("Không có dữ liệu.")
            lbl.setStyleSheet("color:#5a7286; font-size:11px; padding:12px;")
            inner_lay.addWidget(lbl)
        else:
            for i, item in enumerate(items):
                uid  = item["id"]
                name = item.get("displayName", uid)
                val  = str(item.get(col3_key, ""))

                bg = "#f8fbff" if i % 2 == 0 else "white"
                row_w = QWidget()
                row_w.setFixedHeight(26)
                row_w.setStyleSheet(f"background:{bg};")
                row_lay = QHBoxLayout(row_w)
                row_lay.setContentsMargins(4, 1, 8, 1)
                row_lay.setSpacing(4)

                cb = QCheckBox(name)
                cb.setStyleSheet("font-size:11px;")
                cb.stateChanged.connect(self._update_summary)
                cb_dict[uid] = cb
                row_lay.addWidget(cb, stretch=1)

                col3_lbl = QLabel(val)
                col3_lbl.setFixedWidth(70)
                col3_lbl.setStyleSheet("font-size:10px; color:#5a7286; background:transparent;")
                col3_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_lay.addWidget(col3_lbl)

                inner_lay.addWidget(row_w)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, stretch=1)
        return panel

    # ─── Summary ─────────────────────────────────────────────────────────────

    def _update_summary(self, *_):
        prg = sum(1 for cb in self._prg_cbs.values() if cb.isChecked())
        ds  = sum(1 for cb in self._ds_cbs.values()  if cb.isChecked())

        scope_parts = []
        if prg: scope_parts.append(f"{prg} program{'s' if prg > 1 else ''}")
        if ds:  scope_parts.append(f"{ds} dataset{'s' if ds > 1 else ''}")

        if not scope_parts:
            self._summary_lbl.setStyleSheet(
                "color:#a85600; font-size:11px; padding:4px 16px; background:white;"
            )
            self._summary_lbl.setText(
                "⚠  Chưa chọn gì — sẽ tải TOÀN BỘ metadata (chậm hơn)"
            )
        else:
            self._summary_lbl.setStyleSheet(
                f"color:{DHIS2_BLUE}; font-size:11px; padding:4px 16px; background:white;"
            )
            self._summary_lbl.setText("Scope: " + ", ".join(scope_parts))

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _select_all(self, cb_dict: dict[str, QCheckBox], value: bool):
        for cb in cb_dict.values():
            cb.setChecked(value)

    def _restore_selection(self):
        for uid in self._cfg.get("program_ids", []):
            if uid in self._prg_cbs:
                self._prg_cbs[uid].setChecked(True)
        for uid in self._cfg.get("dataset_ids", []):
            if uid in self._ds_cbs:
                self._ds_cbs[uid].setChecked(True)
        self._update_summary()

    def _clear_all(self):
        self._select_all(self._prg_cbs, False)
        self._select_all(self._ds_cbs,  False)

    # ─── Apply / Cancel ──────────────────────────────────────────────────────

    def _on_apply(self):
        self.result = {
            "program_ids":  [uid for uid, cb in self._prg_cbs.items() if cb.isChecked()],
            "dataset_ids":  [uid for uid, cb in self._ds_cbs.items()  if cb.isChecked()],
            "domain_type":  "AGGREGATE",
        }
        self.accept()

    def _on_cancel(self):
        self.result = None
        self.reject()
