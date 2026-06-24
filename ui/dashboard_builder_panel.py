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

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QMessageBox,
    QSpacerItem,
)

DHIS2_BLUE = "#1a6fa8"
PANEL_BG   = "#f7f9fc"
BORDER_CLR = "#d0dde8"
HEADER_BG  = "#e8eef5"


def _h_line() -> QFrame:
    """Thin horizontal separator."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    line.setStyleSheet(f"color: {BORDER_CLR};")
    return line


class DashboardBuilderPanel(QWidget):
    """PySide6 dashboard assembler panel."""

    def __init__(self, master: QWidget, callbacks: dict, **kw):
        super().__init__(master, **kw)
        self._callbacks: dict = callbacks
        self._cards: list[dict] = []
        self._card_widgets: list[QFrame] = []   # parallel list to self._cards
        self._build()
        self.refresh_library()

    # ─── Build ───────────────────────────────────────────────────────────────

    def _build(self):
        self.setStyleSheet(f"background-color: {PANEL_BG};")
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background-color: {BORDER_CLR}; }}"
        )
        root_layout.addWidget(splitter)

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

        self._card_count_lbl = QLabel("0 charts")
        self._card_count_lbl.setFont(QFont("Segoe UI", 9))
        self._card_count_lbl.setStyleSheet("color: #8aa3b8;")
        hdr_layout.addWidget(self._card_count_lbl)
        layout.addWidget(hdr)

        # Scrollable card list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {PANEL_BG}; border: none; }}"
        )

        self._canvas_container = QWidget()
        self._canvas_container.setStyleSheet(f"background-color: {PANEL_BG};")
        self._canvas_layout = QVBoxLayout(self._canvas_container)
        self._canvas_layout.setContentsMargins(6, 4, 6, 4)
        self._canvas_layout.setSpacing(0)

        self._no_cards_lbl = QLabel(
            "No charts yet.\nAdd charts from the library\nor use Chart Editor."
        )
        self._no_cards_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_cards_lbl.setFont(QFont("Segoe UI", 10))
        self._no_cards_lbl.setStyleSheet(
            f"color: #8aa3b8; background-color: {PANEL_BG}; padding: 32px;"
        )
        self._canvas_layout.addWidget(self._no_cards_lbl)
        self._canvas_layout.addStretch(1)

        scroll.setWidget(self._canvas_container)
        layout.addWidget(scroll, 1)

        # Bottom panel
        bottom = QFrame()
        bottom.setStyleSheet(f"background-color: {HEADER_BG}; border: none;")
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 6, 12, 8)
        bottom_layout.setSpacing(6)

        # Report name row
        rn_row = QWidget()
        rn_row.setStyleSheet("background-color: transparent;")
        rn_layout = QHBoxLayout(rn_row)
        rn_layout.setContentsMargins(0, 0, 0, 0)
        rn_layout.setSpacing(6)

        rn_lbl = QLabel("Report name:")
        rn_lbl.setFont(QFont("Segoe UI", 9))
        rn_lbl.setStyleSheet("color: #5a7a9a; background-color: transparent;")
        rn_lbl.setFixedWidth(85)
        rn_layout.addWidget(rn_lbl)

        self._report_name_entry = QLineEdit()
        self._report_name_entry.setPlaceholderText("My Dashboard")
        self._report_name_entry.setFixedHeight(26)
        self._report_name_entry.setFont(QFont("Segoe UI", 10))
        self._report_name_entry.setStyleSheet(
            "QLineEdit {"
            "  border: 1px solid #c0cdd8;"
            "  border-radius: 4px;"
            "  padding: 0 6px;"
            "  background-color: white;"
            "  color: #1e2d3d;"
            "}"
            "QLineEdit:focus { border-color: #1a6fa8; }"
        )
        rn_layout.addWidget(self._report_name_entry, 1)
        bottom_layout.addWidget(rn_row)

        # Export / Deploy row
        action_row = QWidget()
        action_row.setStyleSheet("background-color: transparent;")
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)

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
        if not charts:
            empty_lbl = QLabel(
                "No saved charts yet.\nBuild a chart and click\n'Save to Library'."
            )
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

        # Outer wrapper with margins
        wrapper = QFrame()
        wrapper.setStyleSheet("background-color: transparent; border: none;")
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
        """Add cfg to the dashboard canvas."""
        # Hide empty-state label on first card
        if self._no_cards_lbl is not None and self._no_cards_lbl.isVisible():
            self._no_cards_lbl.hide()

        self._cards.append(cfg)
        card_widget = self._make_canvas_card(cfg, len(self._cards) - 1)
        # Insert before the trailing stretch
        stretch_idx = self._canvas_layout.count() - 1
        self._canvas_layout.insertWidget(stretch_idx, card_widget)
        self._card_widgets.append(card_widget)

        self._export_btn.setEnabled(True)
        self._deploy_btn.setEnabled(True)
        self._update_count()

    def _make_canvas_card(self, cfg: dict, idx: int) -> QFrame:
        """Return a QFrame representing one card on the dashboard canvas."""
        chart_color = cfg.get("chart_color", "#3498db")
        name = cfg.get("name") or cfg.get("title", "?")
        mode_lbl = "AI" if cfg.get("mode") == "ai" else "Fixed"
        src_n = len(cfg.get("de_sources", [])) or 1
        col_w = cfg.get("col_width", 6)
        tmpl  = cfg.get("template_label", "")

        outer = QFrame()
        outer.setStyleSheet("background-color: transparent; border: none;")
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 3, 0, 3)
        outer_layout.setSpacing(0)

        rf = QFrame()
        rf.setStyleSheet(
            "QFrame {"
            "  background-color: white;"
            f" border: 1px solid {BORDER_CLR};"
            "  border-radius: 6px;"
            "}"
        )
        rf.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row_layout = QHBoxLayout(rf)
        row_layout.setContentsMargins(8, 5, 6, 5)
        row_layout.setSpacing(4)

        # Text block
        text_widget = QWidget()
        text_widget.setStyleSheet("border: none; background-color: transparent;")
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        name_lbl = QLabel(f"●  {name}")
        name_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {chart_color}; border: none;")
        text_layout.addWidget(name_lbl)

        meta_lbl = QLabel(f"{tmpl}  •  col-{col_w}  •  {src_n} src  •  {mode_lbl}")
        meta_lbl.setFont(QFont("Segoe UI", 8))
        meta_lbl.setStyleSheet("color: #8aa3b8; border: none;")
        text_layout.addWidget(meta_lbl)

        row_layout.addWidget(text_widget, 1)

        # Remove button — captures outer frame reference for deletion
        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(24, 24)
        rm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rm_btn.setFont(QFont("Segoe UI", 10))
        rm_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #f0f4f8;"
            "  border: none;"
            "  border-radius: 4px;"
            "  color: #c0392b;"
            "}"
            "QPushButton:hover { background-color: #f5c6cb; }"
        )
        rm_btn.clicked.connect(
            lambda checked=False, w=outer: self._remove_card(w)
        )
        row_layout.addWidget(rm_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        outer_layout.addWidget(rf)
        return outer

    def _remove_card(self, widget: QFrame):
        """Remove widget from canvas and corresponding entry from self._cards."""
        if widget in self._card_widgets:
            idx = self._card_widgets.index(widget)
            self._card_widgets.pop(idx)
            if 0 <= idx < len(self._cards):
                self._cards.pop(idx)

        widget.hide()
        self._canvas_layout.removeWidget(widget)
        widget.deleteLater()

        self._update_count()
        if not self._cards:
            self._no_cards_lbl.show()
            self._export_btn.setEnabled(False)
            self._deploy_btn.setEnabled(False)

    def _on_clear_all(self):
        if not self._cards:
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

        for w in list(self._card_widgets):
            w.hide()
            self._canvas_layout.removeWidget(w)
            w.deleteLater()

        self._cards.clear()
        self._card_widgets.clear()
        self._update_count()
        self._no_cards_lbl.show()
        self._export_btn.setEnabled(False)
        self._deploy_btn.setEnabled(False)

    def _update_count(self):
        count = len(self._cards)
        self._card_count_lbl.setText(
            f"{count} chart{'s' if count != 1 else ''}"
        )

    # ─── Export / Deploy ──────────────────────────────────────────────────────

    def _on_export(self):
        cb = self._callbacks.get("on_export")
        if cb:
            cb(list(self._cards))

    def _on_deploy(self):
        name = self._report_name_entry.text().strip()
        if not name:
            QMessageBox.warning(self, "Deploy", "Enter a report name first.")
            self._report_name_entry.setFocus()
            return
        cb = self._callbacks.get("on_deploy")
        if cb:
            cb(name, list(self._cards))

    # ─── Public API ──────────────────────────────────────────────────────────

    def get_cards(self) -> list[dict]:
        """Return a copy of the current dashboard card list."""
        return list(self._cards)
