"""
FilterConfigDialog — cấu hình bộ lọc metadata (PySide6).

Layout:
  ┌─────────────────────────────────────────────────────────┐
  │  TẦNG 1 — SCOPE  (Programs bên trái | Datasets bên phải)│
  │  Chọn programs/datasets xác định phạm vi dữ liệu sẽ dùng│
  ├─────────────────────────────────────────────────────────┤
  │  TẦNG 2 — THU HẸP THÊM  (tabs: Indicators | DE)        │
  │  Tùy chọn — bỏ qua = lấy tất cả từ scope trên          │
  ├─────────────────────────────────────────────────────────┤
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
        self.setMinimumSize(860, 620)
        self.resize(1000, 700)
        self.setModal(True)

        self._opts  = filter_options
        self._cfg   = dict(current_cfg)
        self.result: dict | None = None

        # Checkbox tracking: uid → QCheckBox
        self._prg_cbs: dict[str, QCheckBox] = {}
        self._ds_cbs:  dict[str, QCheckBox] = {}
        self._de_cbs:  dict[str, QCheckBox] = {}

        self._de_name_entry   = QLineEdit()
        self._prog_name_entry = QLineEdit()

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
        scope_splitter.setMinimumHeight(200)

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

        # ── Tầng 2: Thu hẹp ────────────────────────────────────────────────
        root.addWidget(_section_header(
            "② THU HẸP THÊM  (tùy chọn)",
            "Bỏ qua = lấy tất cả từ scope trên",
        ))

        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border:none; background:white; }"
            f"QTabBar::tab {{ background:#e8f0f8; padding:6px 14px; font-size:11px; }}"
            f"QTabBar::tab:selected {{ background:{DHIS2_BLUE}; color:white; }}"
        )
        tabs.setMinimumHeight(160)

        tab_de = QWidget()
        tab_de.setStyleSheet("background:white;")
        tab_kw = QWidget()
        tab_kw.setStyleSheet("background:white;")
        tabs.addTab(tab_de, "🔢 Data Element Groups")
        tabs.addTab(tab_kw, "🔍 Keyword Filters")

        self._build_refine_groups(tab_de, self._opts.get("de_groups", []), self._de_cbs)
        self._build_keywords(tab_kw)

        root.addWidget(tabs, stretch=1)

        # ── Summary label ───────────────────────────────────────────────────
        self._summary_lbl = QLabel("")
        self._summary_lbl.setStyleSheet(
            "color:#e67e22; font-size:11px; padding:4px 16px; background:white;"
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
            "border-radius:4px; color:#4a6278; font-size:11px; padding:0 16px; }}"
            "QPushButton:hover { background:#e8f0f8; }"
        )
        cancel_btn.clicked.connect(self._on_cancel)
        bot_lay.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply && Load Metadata ▶")
        apply_btn.setFixedHeight(34)
        apply_btn.setStyleSheet(
            f"QPushButton {{ background:{DHIS2_BLUE}; border:none; border-radius:4px; "
            "color:white; font-size:11px; font-weight:bold; padding:0 20px; }}"
            "QPushButton:hover { background:#155a8a; }"
        )
        apply_btn.clicked.connect(self._on_apply)
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
            lbl.setStyleSheet("color:#8aa3b8; font-size:11px; padding:12px;")
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
                col3_lbl.setStyleSheet("font-size:10px; color:#8aa3b8; background:transparent;")
                col3_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_lay.addWidget(col3_lbl)

                inner_lay.addWidget(row_w)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, stretch=1)
        return panel

    # ── Refine groups tab ─────────────────────────────────────────────────────

    def _build_refine_groups(self, parent: QWidget, items: list[dict],
                              cb_dict: dict[str, QCheckBox]):
        lay = QVBoxLayout(parent)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        # Quick select
        qs_row = QWidget()
        qs_row.setStyleSheet("background:transparent;")
        qs_lay = QHBoxLayout(qs_row)
        qs_lay.setContentsMargins(0, 0, 0, 0)
        qs_lay.setSpacing(6)

        all_btn = QPushButton("Select All")
        all_btn.setFixedHeight(22)
        all_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; border:1px solid {DHIS2_BLUE}; "
            f"border-radius:4px; color:{DHIS2_BLUE}; font-size:10px; padding:0 10px; }}"
            f"QPushButton:hover {{ background:#e8f0f8; }}"
        )
        all_btn.clicked.connect(lambda: self._select_all(cb_dict, True))
        qs_lay.addWidget(all_btn)

        none_btn = QPushButton("Clear")
        none_btn.setFixedHeight(22)
        none_btn.setStyleSheet(
            "QPushButton { background:transparent; border:1px solid #8aa3b8; "
            "border-radius:4px; color:#4a6278; font-size:10px; padding:0 10px; }"
            "QPushButton:hover { background:#e8f0f8; }"
        )
        none_btn.clicked.connect(lambda: self._select_all(cb_dict, False))
        qs_lay.addWidget(none_btn)
        qs_lay.addStretch()
        lay.addWidget(qs_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background:white; border:1px solid #d0dde8; border-radius:4px; }"
            "QScrollBar:vertical { width:8px; }"
            "QScrollBar::handle:vertical { background:#c0cdd8; border-radius:4px; }"
        )
        inner = QWidget()
        inner.setStyleSheet("background:white;")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 0, 0)
        inner_lay.setSpacing(0)

        if not items:
            lbl = QLabel("Không có groups trên DHIS2 này.")
            lbl.setStyleSheet("color:#8aa3b8; font-size:11px; padding:12px;")
            inner_lay.addWidget(lbl)
        else:
            for i, item in enumerate(items):
                uid  = item["id"]
                name = item.get("displayName", uid)
                cnt  = str(item.get("count", ""))

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

                cnt_lbl = QLabel(cnt)
                cnt_lbl.setFixedWidth(56)
                cnt_lbl.setStyleSheet("font-size:10px; color:#8aa3b8; background:transparent;")
                cnt_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_lay.addWidget(cnt_lbl)

                inner_lay.addWidget(row_w)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, stretch=1)

    # ── Keyword filters tab ───────────────────────────────────────────────────

    def _build_keywords(self, parent: QWidget):
        lay = QGridLayout(parent)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)
        lay.setColumnStretch(1, 1)

        rows = [
            ("Program name:", self._prog_name_entry,
             "Lọc tên program khi fetch (stage DEs + TEAs)"),
            ("Data Element name:", self._de_name_entry,
             "Lọc tên data element khi fetch"),
        ]
        for i, (lbl_text, entry, placeholder) in enumerate(rows):
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet("font-size:12px; color:#4a6278; background:transparent;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lay.addWidget(lbl, i, 0)
            entry.setPlaceholderText(placeholder)
            entry.setFixedHeight(32)
            entry.setStyleSheet(
                "QLineEdit { border:1px solid #c0cdd8; border-radius:4px; "
                "padding:0 8px; font-size:12px; background:white; }"
                "QLineEdit:focus { border-color:#1a6fa8; }"
            )
            lay.addWidget(entry, i, 1)

        note = QLabel("Để trống = lấy tất cả (không lọc theo tên)")
        note.setStyleSheet("font-size:10px; color:#8aa3b8; background:transparent;")
        lay.addWidget(note, len(rows), 0, 1, 2)

    # ─── Summary ─────────────────────────────────────────────────────────────

    def _update_summary(self, *_):
        prg = sum(1 for cb in self._prg_cbs.values() if cb.isChecked())
        ds  = sum(1 for cb in self._ds_cbs.values()  if cb.isChecked())
        de  = sum(1 for cb in self._de_cbs.values()  if cb.isChecked())

        scope_parts = []
        if prg: scope_parts.append(f"{prg} program{'s' if prg > 1 else ''}")
        if ds:  scope_parts.append(f"{ds} dataset{'s' if ds > 1 else ''}")
        refine_parts = []
        if de:  refine_parts.append(f"{de} DE group{'s' if de > 1 else ''}")

        if not scope_parts and not refine_parts:
            self._summary_lbl.setStyleSheet(
                "color:#e67e22; font-size:11px; padding:4px 16px; background:white;"
            )
            self._summary_lbl.setText(
                "⚠  Chưa chọn gì — sẽ tải TOÀN BỘ metadata (chậm hơn)"
            )
        else:
            txt = ""
            if scope_parts:
                txt += "Scope: " + ", ".join(scope_parts)
            if refine_parts:
                txt += ("  |  Thu hẹp: " if scope_parts else "Thu hẹp: ") + ", ".join(refine_parts)
            self._summary_lbl.setStyleSheet(
                f"color:{DHIS2_BLUE}; font-size:11px; padding:4px 16px; background:white;"
            )
            self._summary_lbl.setText(txt)

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
        for uid in self._cfg.get("de_group_ids", []):
            if uid in self._de_cbs:
                self._de_cbs[uid].setChecked(True)
        self._de_name_entry.setText(self._cfg.get("de_name", ""))
        self._prog_name_entry.setText(self._cfg.get("program_name", ""))
        self._update_summary()

    def _clear_all(self):
        self._select_all(self._prg_cbs, False)
        self._select_all(self._ds_cbs,  False)
        self._select_all(self._de_cbs,  False)
        self._de_name_entry.clear()
        self._prog_name_entry.clear()

    # ─── Apply / Cancel ──────────────────────────────────────────────────────

    def _on_apply(self):
        self.result = {
            "program_ids":  [uid for uid, cb in self._prg_cbs.items() if cb.isChecked()],
            "program_name":  self._prog_name_entry.text().strip(),
            "dataset_ids":  [uid for uid, cb in self._ds_cbs.items()  if cb.isChecked()],
            "de_group_ids": [uid for uid, cb in self._de_cbs.items()  if cb.isChecked()],
            "de_name":       self._de_name_entry.text().strip(),
            "domain_type":  "AGGREGATE",
        }
        self.accept()

    def _on_cancel(self):
        self.result = None
        self.reject()
