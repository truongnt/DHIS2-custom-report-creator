"""AiDashboardDialog — AI-powered chart recommendation dialog.

User types an intent, sees AI recommendations, selects which to add, and clicks OK.
In test mode (no AI client configured) uses mock scenarios.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

DHIS2_BLUE = "#1a6fa8"
PANEL_BG   = "#f7f9fc"
BORDER_CLR = "#d0dde8"
AI_GREEN   = "#1e7e48"


# ── Background worker ─────────────────────────────────────────────────────────

class _PlannerWorker(QThread):
    finished = Signal(list)   # list[dict] recommendations
    failed   = Signal(str)    # error message

    def __init__(self, user_intent: str, context: dict,
                 ai_client, mock_key: str | None, model: str):
        super().__init__()
        self._intent    = user_intent
        self._context   = context
        self._client    = ai_client
        self._mock_key  = mock_key
        self._model     = model

    def run(self) -> None:
        try:
            from llm.ai_dashboard_planner import recommend_charts
            recs = recommend_charts(
                self._intent, self._context,
                ai_client=self._client,
                mock_key=self._mock_key,
                model=self._model,
            )
            self.finished.emit(recs)
        except Exception as exc:
            self.failed.emit(str(exc))


# ── Dialog ────────────────────────────────────────────────────────────────────

class AiDashboardDialog(QDialog):
    """
    Dialog that lets the user describe a dashboard and get AI chart recommendations.

    Parameters
    ----------
    parent       : QWidget
    metadata     : dict from dhis2.metadata.fetch_all()
    descriptions : {uid: description} local descriptions
    base_url     : DHIS2 instance URL (for context only)
    ai_client    : anthropic.Anthropic instance (None → mock mode)
    """

    # Preset quick-start intents
    _PRESETS = [
        ("Custom intent…",          ""),
        ("Malaria disease overview", "Show key malaria indicators: monthly trend, geographic distribution, case breakdown, and facility ranking"),
        ("Supply chain review",      "Supply chain stock levels: facility comparison, trend over time, geographic coverage, and national KPI"),
        ("Performance review",       "Performance dashboard: key indicator trend, multi-indicator comparison, district map, and facility ranking"),
    ]

    def __init__(
        self,
        parent: QWidget,
        *,
        metadata: dict,
        descriptions: dict[str, str],
        base_url: str = "",
        ai_client=None,
        model: str = "claude-haiku-4-5-20251001",
    ):
        super().__init__(parent)
        self.setWindowTitle("AI Dashboard Generator")
        self.resize(700, 560)
        self.setMinimumSize(560, 420)

        self._metadata     = metadata
        self._descriptions = descriptions
        self._base_url     = base_url
        self._ai_client    = ai_client
        self._model        = model
        self._recs: list[dict]       = []
        self._checkboxes: list[QCheckBox] = []
        self._worker: _PlannerWorker | None = None
        self._configs: list[dict]    = []

        self._build()

    # ─── UI ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background-color: {DHIS2_BLUE};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        t = QLabel("AI Dashboard Generator")
        t.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        t.setStyleSheet("color: white; background: transparent;")
        hl.addWidget(t)
        hl.addStretch(1)
        mode_lbl = QLabel("Mock mode" if self._ai_client is None else f"Model: {self._model}")
        mode_lbl.setFont(QFont("Segoe UI", 9))
        mode_lbl.setStyleSheet("color: rgba(255,255,255,0.7); background: transparent;")
        hl.addWidget(mode_lbl)
        root.addWidget(hdr)

        body = QWidget()
        body.setStyleSheet(f"background-color: {PANEL_BG};")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 12, 16, 8)
        body_layout.setSpacing(8)

        # Preset combo
        preset_row = QWidget()
        pr_layout = QHBoxLayout(preset_row)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        pr_layout.setSpacing(8)
        pr_layout.addWidget(QLabel("Quick start:"))
        self._preset_combo = QComboBox()
        self._preset_combo.setFont(QFont("Segoe UI", 10))
        for label, _ in self._PRESETS:
            self._preset_combo.addItem(label)
        self._preset_combo.currentIndexChanged.connect(self._on_preset)
        pr_layout.addWidget(self._preset_combo, 1)
        body_layout.addWidget(preset_row)

        # Intent text
        intent_lbl = QLabel("Describe what you want in your dashboard:")
        intent_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        intent_lbl.setStyleSheet("color: #3a5068;")
        body_layout.addWidget(intent_lbl)

        self._intent_edit = QPlainTextEdit()
        self._intent_edit.setPlaceholderText(
            "E.g.: 'Show monthly malaria cases, geographic distribution by district, "
            "test positivity rate as a KPI, and ranking of top facilities.'"
        )
        self._intent_edit.setFont(QFont("Segoe UI", 10))
        self._intent_edit.setFixedHeight(80)
        self._intent_edit.setStyleSheet(
            "QPlainTextEdit {"
            "  border: 1px solid #c0cdd8; border-radius: 4px;"
            "  padding: 6px; background-color: white;"
            "}"
            "QPlainTextEdit:focus { border-color: #1a6fa8; }"
        )
        body_layout.addWidget(self._intent_edit)

        # Generate button + status
        gen_row = QWidget()
        gen_row.setStyleSheet("background: transparent;")
        gen_layout = QHBoxLayout(gen_row)
        gen_layout.setContentsMargins(0, 0, 0, 0)
        gen_layout.setSpacing(8)

        self._gen_btn = QPushButton("Generate recommendations")
        self._gen_btn.setFixedHeight(34)
        self._gen_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gen_btn.setStyleSheet(
            "QPushButton {"
            f" background-color: {AI_GREEN};"
            "  border: none; border-radius: 5px;"
            "  color: white; padding: 0 16px;"
            "}"
            "QPushButton:hover { background-color: #155a34; }"
            "QPushButton:disabled { background-color: #a8d8bc; }"
        )
        self._gen_btn.clicked.connect(self._on_generate)
        gen_layout.addWidget(self._gen_btn)

        self._status_lbl = QLabel("")
        self._status_lbl.setFont(QFont("Segoe UI", 9))
        self._status_lbl.setStyleSheet("color: #6a8aaa;")
        gen_layout.addWidget(self._status_lbl, 1)
        body_layout.addWidget(gen_row)

        # Results area
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER_CLR};")
        body_layout.addWidget(sep)

        results_hdr = QWidget()
        rh_layout = QHBoxLayout(results_hdr)
        rh_layout.setContentsMargins(0, 0, 0, 0)
        recs_lbl = QLabel("Recommended charts:")
        recs_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        recs_lbl.setStyleSheet("color: #3a5068;")
        rh_layout.addWidget(recs_lbl)
        rh_layout.addStretch(1)
        self._select_all_btn = QPushButton("Select all")
        self._select_all_btn.setFixedHeight(22)
        self._select_all_btn.setFont(QFont("Segoe UI", 8))
        self._select_all_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #1a6fa8; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        self._select_all_btn.clicked.connect(self._select_all)
        self._select_all_btn.setVisible(False)
        rh_layout.addWidget(self._select_all_btn)
        body_layout.addWidget(results_hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {PANEL_BG}; border: none; }}")
        self._recs_container = QWidget()
        self._recs_container.setStyleSheet(f"background-color: {PANEL_BG};")
        self._recs_layout = QVBoxLayout(self._recs_container)
        self._recs_layout.setContentsMargins(0, 0, 0, 0)
        self._recs_layout.setSpacing(4)
        self._recs_layout.addStretch(1)
        scroll.setWidget(self._recs_container)
        body_layout.addWidget(scroll, 1)

        root.addWidget(body, 1)

        # Dialog buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        from ui.qt_utils import style_dialog_buttons
        footer = style_dialog_buttons(btn_box)
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self.reject)
        root.addWidget(footer)

    # ─── Slots ───────────────────────────────────────────────────────────────

    def _on_preset(self, idx: int) -> None:
        _, text = self._PRESETS[idx]
        if text:
            self._intent_edit.setPlainText(text)

    def _on_generate(self) -> None:
        intent = self._intent_edit.toPlainText().strip()
        if not intent:
            QMessageBox.warning(self, "AI Generate", "Enter a description first.")
            return

        self._gen_btn.setEnabled(False)
        self._status_lbl.setText("Generating recommendations…")
        self._clear_recs()

        from llm.ai_dashboard_planner import build_context
        context = build_context(self._metadata, self._descriptions)

        # Determine mock key based on preset if no AI client
        mock_key: str | None = None
        if self._ai_client is None:
            idx = self._preset_combo.currentIndex()
            mock_map = {1: "malaria_overview", 2: "supply_chain", 3: "performance_review"}
            mock_key = mock_map.get(idx, "malaria_overview")

        self._worker = _PlannerWorker(
            intent, context, self._ai_client, mock_key, self._model
        )
        self._worker.finished.connect(self._on_recs_ready)
        self._worker.failed.connect(self._on_recs_failed)
        self._worker.start()

    def _on_recs_ready(self, recs: list[dict]) -> None:
        self._gen_btn.setEnabled(True)
        if not recs:
            self._status_lbl.setText("No recommendations returned. Try a different description.")
            return
        self._status_lbl.setText(f"{len(recs)} chart recommendations")
        self._recs = recs
        self._show_recs(recs)

    def _on_recs_failed(self, msg: str) -> None:
        self._gen_btn.setEnabled(True)
        self._status_lbl.setText(f"Error: {msg}")

    def _show_recs(self, recs: list[dict]) -> None:
        self._clear_recs()
        self._checkboxes.clear()
        self._select_all_btn.setVisible(bool(recs))

        # Build context de_list for display names
        from llm.ai_dashboard_planner import build_context
        ctx = build_context(self._metadata, self._descriptions)
        uid_to_name = {d["uid"]: d["name"] for d in ctx["de_list"]}
        chart_type_labels = {c["id"]: c["label"] for c in ctx["chart_types"]}

        for rec in recs:
            cb = QCheckBox()
            cb.setChecked(True)

            card = QFrame()
            card.setStyleSheet(
                "QFrame {"
                "  background-color: white;"
                f" border: 1px solid {BORDER_CLR}; border-radius: 6px;"
                "}"
            )
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

            hl = QHBoxLayout(card)
            hl.setContentsMargins(10, 8, 10, 8)
            hl.addWidget(cb)

            text_w = QWidget()
            text_w.setStyleSheet("border: none; background: transparent;")
            tl = QVBoxLayout(text_w)
            tl.setContentsMargins(0, 0, 0, 0)
            tl.setSpacing(2)

            title_lbl = QLabel(rec.get("title", ""))
            title_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            title_lbl.setStyleSheet("color: #1e2d3d; border: none;")
            tl.addWidget(title_lbl)

            chart_label = chart_type_labels.get(rec.get("chart_type", ""), rec.get("chart_type", ""))
            de_name = uid_to_name.get(rec.get("de_uid", ""), rec.get("de_uid", ""))
            meta_lbl = QLabel(f"{chart_label}  ·  {de_name}")
            meta_lbl.setFont(QFont("Segoe UI", 8))
            meta_lbl.setStyleSheet("color: #6a8aaa; border: none;")
            tl.addWidget(meta_lbl)

            rationale_lbl = QLabel(rec.get("rationale", ""))
            rationale_lbl.setFont(QFont("Segoe UI", 8))
            rationale_lbl.setStyleSheet("color: #8aa3b8; border: none;")
            rationale_lbl.setWordWrap(True)
            tl.addWidget(rationale_lbl)

            hl.addWidget(text_w, 1)
            self._checkboxes.append(cb)

            # Insert before stretch
            idx = self._recs_layout.count() - 1
            self._recs_layout.insertWidget(idx, card)

    def _clear_recs(self) -> None:
        while self._recs_layout.count() > 1:
            item = self._recs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._checkboxes.clear()
        self._select_all_btn.setVisible(False)

    def _select_all(self) -> None:
        for cb in self._checkboxes:
            cb.setChecked(True)

    def _on_ok(self) -> None:
        selected_recs = [
            rec for rec, cb in zip(self._recs, self._checkboxes) if cb.isChecked()
        ]
        if not selected_recs:
            QMessageBox.information(self, "AI Generate",
                                    "Select at least one chart to add to the dashboard.")
            return

        from llm.ai_dashboard_planner import build_context, recs_to_chart_configs
        ctx = build_context(self._metadata, self._descriptions)
        self._configs = recs_to_chart_configs(selected_recs, ctx["de_list"])
        self.accept()

    # ─── Result ──────────────────────────────────────────────────────────────

    def get_chart_configs(self) -> list[dict]:
        """Return chart config dicts for the selected recommendations."""
        return list(self._configs)
