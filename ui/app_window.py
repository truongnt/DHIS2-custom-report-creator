import copy
import threading
import os
import re
from urllib.parse import urlparse
from dotenv import load_dotenv

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QFrame, QLabel, QPushButton, QStackedWidget,
    QScrollArea, QLineEdit, QComboBox, QProgressBar,
    QMessageBox, QSizePolicy, QStatusBar, QSpacerItem,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

from ui.chart_editor_panel import ChartEditorPanel
from ui.dashboard_builder_panel import DashboardBuilderPanel

load_dotenv()


def _merge_pinned(layout: list[dict] | None,
                  global_pinned: dict) -> dict:
    """Union all pinned UIDs from dashboard cards + global pin list."""
    merged: dict[str, list] = {
        "data_elements":               list(global_pinned.get("data_elements", [])),
        "program_stage_data_elements": list(global_pinned.get("program_stage_data_elements", [])),
        "tracked_entity_attributes":   list(global_pinned.get("tracked_entity_attributes", [])),
    }
    if not layout:
        return merged
    for card in layout:
        for key in ("data_elements", "program_stage_data_elements", "tracked_entity_attributes"):
            for uid in card.get("pinned", {}).get(key, []):
                if uid not in merged[key]:
                    merged[key].append(uid)
    return merged


def _detect_changed_cards(old_layout: list[dict], new_layout: list[dict]) -> set[str]:
    """Return IDs of cards whose template_id, title, or pinned UIDs changed."""
    old_map = {c.get("id"): c for c in old_layout}
    changed: set[str] = set()
    for card in new_layout:
        cid = card.get("id")
        old = old_map.get(cid)
        if old is None:
            continue
        if card.get("template_id") != old.get("template_id"):
            changed.add(cid)
            continue
        if card.get("title") != old.get("title"):
            changed.add(cid)
            continue
        def _flat_uids(c):
            p = c.get("pinned", {})
            return set(p.get("indicators", []) + p.get("program_indicators", []) + p.get("data_elements", []))
        if _flat_uids(card) != _flat_uids(old):
            changed.add(cid)
    return changed


DHIS2_BLUE = "#1a6fa8"
SIDEBAR_BG = "#1e2d3d"
SIDEBAR_FG = "#ffffff"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_sidebar_button(text: str, parent: QWidget) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setFixedHeight(42)
    btn.setCheckable(False)
    btn.setStyleSheet(
        "QPushButton {"
        "  background: transparent;"
        "  border: none;"
        "  color: #8aa3b8;"
        "  font-size: 12px;"
        "  text-align: left;"
        "  padding-left: 12px;"
        "  border-radius: 6px;"
        "}"
        "QPushButton:hover { background: #253d52; }"
        "QPushButton:disabled { color: #8499ac; }"
    )
    return btn


def _active_sidebar_button_style() -> str:
    return (
        "QPushButton {"
        f"  background: {DHIS2_BLUE};"
        "  border: none;"
        "  color: white;"
        "  font-size: 12px;"
        "  text-align: left;"
        "  padding-left: 12px;"
        "  border-radius: 6px;"
        "}"
        f"QPushButton:hover {{ background: #155a8a; }}"
    )


def _inactive_sidebar_button_style() -> str:
    return (
        "QPushButton {"
        "  background: transparent;"
        "  border: none;"
        "  color: #8aa3b8;"
        "  font-size: 12px;"
        "  text-align: left;"
        "  padding-left: 12px;"
        "  border-radius: 6px;"
        "}"
        "QPushButton:hover { background: #253d52; }"
        "QPushButton:disabled { color: #8499ac; }"
    )


class AppWindow(QMainWindow):
    # Signals for thread-safe callbacks from worker threads
    _sig_connect_done = Signal(str, int, object, bool)   # display, count, cached_at, from_cache
    _sig_connect_fail = Signal(str)                       # error message
    _sig_status       = Signal(str)                       # status message (non-error)
    _sig_call_main    = Signal(object)                    # generic: emit(callable) → calls it on main thread

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DHIS2 Dashboard Builder")
        self.setMinimumSize(1024, 640)
        self._sig_connect_done.connect(self._on_connect_done)
        self._sig_connect_fail.connect(self._on_connect_fail)
        self._sig_status.connect(lambda msg: self._set_status(msg))
        self._sig_call_main.connect(lambda fn: fn())

        self._client           = None   # DHIS2Client once connected
        self._metadata         = None   # loaded metadata dict
        self._filter_options   = None   # {indicator_groups, de_groups, programs}
        self._filter_cfg: dict = {}     # current FilterConfig applied to last load
        self._pinned: dict[str, list[str]] = {
            "data_elements": [],
            "program_stage_data_elements": [],
            "tracked_entity_attributes": [],
        }
        self._dashboard_layout: list[dict] | None = None  # cards from DashboardBuilder
        self._last_generated_layout: list[dict] | None = None  # layout used for current HTML
        self._scoped_context: str | None = None  # filtered metadata for generate/refine (conversation-scoped)
        self._full_ctx: str | None = None         # full context cache (rebuilt when metadata/pinned changes)
        self._summary_ctx: str | None = None      # compact planning context (~2-3k tokens)
        self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._profiles: list[dict] = []   # loaded from credentials store

        # Stub attributes to prevent AttributeError from legacy callback chain
        self.generate_btn    = None   # no dedicated generate button in new layout
        self.report_view     = _ReportViewStub()
        self.chat_panel      = _ChatPanelStub()
        self.quick_form      = _QuickFormStub()
        self.tabs            = _TabsStub()

        self._build_layout()
        self._lock_ui()          # locked until DHIS2 connect succeeds
        self._load_saved_credentials()

        # Maximize after event loop starts
        QTimer.singleShot(0, self.showMaximized)

    # ─── Lock / Unlock ────────────────────────────────────────────────────────

    def _lock_ui(self):
        """No-op — nav buttons handle access control."""
        pass

    def _unlock_ui(self):
        """Enable Chart Editor and Dashboard nav buttons after connect."""
        for key in ("chart_editor", "dashboard", "metadata_editor"):
            if key in self._nav_btns:
                self._nav_btns[key].setEnabled(True)

    def _invalidate_ctx_caches(self):
        """Clear cached contexts — call when metadata or pinned items change."""
        self._full_ctx    = None
        self._summary_ctx = None
        self._scoped_context = None

    # ─── Layout ──────────────────────────────────────────────────────────────

    def _build_layout(self):
        self._active_panel: str = "config"

        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Left sidebar
        self._sidebar = self._build_sidebar(central)
        self._sidebar.setFixedWidth(160)
        root_layout.addWidget(self._sidebar)

        # Right content area (stacked panels)
        self._content = QStackedWidget(central)
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root_layout.addWidget(self._content)

        self._build_panels()
        self._build_statusbar()

        # Show default panel
        self._show_panel("config")

    # ─── Left navigation sidebar ──────────────────────────────────────────────

    def _build_sidebar(self, parent: QWidget) -> QFrame:
        sidebar = QFrame(parent)
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet(f"QFrame#sidebar {{ background-color: {SIDEBAR_BG}; border: none; }}")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 16, 8, 12)
        layout.setSpacing(0)

        # App title
        title_lbl = QLabel("DHIS2\nDashboard Builder", sidebar)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet(
            "color: white; font-size: 13px; font-weight: bold;"
            "padding: 0 4px 10px 4px; background: transparent;"
        )
        layout.addWidget(title_lbl)

        # Divider
        div = QFrame(sidebar)
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: #2a4a6a; background-color: #2a4a6a; border: none; max-height: 1px;")
        div.setFixedHeight(1)
        layout.addWidget(div)
        layout.addSpacing(6)

        # Nav buttons
        NAV_ITEMS = [
            ("config",       "  ⚙  Login & Config"),
            ("chart_editor", "  \U0001f4ca  Viz Builder"),
            ("dashboard",    "  \U0001f5c2  Dashboard"),
        ]
        self._nav_btns: dict[str, QPushButton] = {}
        for key, label in NAV_ITEMS:
            btn = _make_sidebar_button(label, sidebar)
            btn.clicked.connect(lambda _checked=False, k=key: self._show_panel(k))
            layout.addWidget(btn)
            layout.addSpacing(2)
            self._nav_btns[key] = btn

        # Metadata editor button (enabled after connect)
        meta_btn = _make_sidebar_button("  \U0001f4da  Metadata Library", sidebar)
        meta_btn.setEnabled(False)
        meta_btn.clicked.connect(self._open_metadata_editor)
        layout.addWidget(meta_btn)
        layout.addSpacing(2)
        self._nav_btns["metadata_editor"] = meta_btn

        # Disable builder panels until connected
        self._nav_btns["chart_editor"].setEnabled(False)
        self._nav_btns["dashboard"].setEnabled(False)

        # Spacer
        layout.addStretch()

        # Version label
        ver_lbl = QLabel("v0.1.0 — CHAI Laos", sidebar)
        ver_lbl.setStyleSheet("color: #93a8bc; font-size: 9px; background: transparent; padding: 0 6px;")
        layout.addWidget(ver_lbl)

        return sidebar

    def _show_panel(self, name: str):
        PANEL_INDEX = {"config": 0, "chart_editor": 1, "dashboard": 2, "metadata_editor": 3}
        # Persist description edits when navigating away from the metadata editor.
        if getattr(self, "_active_panel", None) == "metadata_editor" and name != "metadata_editor":
            try:
                self._metadata_editor.flush_pending()
                self._update_dashboard_context()
                # Push the curated in-use selection to the Chart Editor's pickers.
                self._chart_editor.set_in_use(self._metadata_editor.get_selection())
            except Exception:
                pass

        idx = PANEL_INDEX.get(name, 0)
        self._content.setCurrentIndex(idx)

        if name == "dashboard":
            self._dashboard_builder.refresh_library()

        self._active_panel = name
        for key, btn in self._nav_btns.items():
            if key == name:
                btn.setStyleSheet(_active_sidebar_button_style())
            else:
                btn.setStyleSheet(_inactive_sidebar_button_style())
                # Re-apply disabled state if button was disabled
                if not btn.isEnabled():
                    btn.setStyleSheet(
                        _inactive_sidebar_button_style()
                        + "QPushButton { color: #8499ac; }"
                    )

    # ─── Content panels ───────────────────────────────────────────────────────

    def _build_panels(self):
        # Panel 0: Config
        config_panel = QWidget()
        config_panel.setStyleSheet(f"background-color: {SIDEBAR_BG};")
        config_scroll = QScrollArea(config_panel)
        config_scroll.setWidgetResizable(True)
        config_scroll.setFrameShape(QFrame.Shape.NoFrame)
        config_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        config_scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {SIDEBAR_BG}; border: none; }}"
            "QScrollBar:vertical { width: 8px; background: #162534; }"
            "QScrollBar::handle:vertical { background: #2a4a6a; border-radius: 4px; min-height: 20px; }"
            "QScrollBar::handle:vertical:hover { background: #3a5a7a; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        )

        config_inner = QWidget()
        config_inner.setStyleSheet(f"background-color: {SIDEBAR_BG};")
        config_scroll.setWidget(config_inner)

        panel_layout = QVBoxLayout(config_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.addWidget(config_scroll)

        self._build_config_content(config_inner)
        self._content.addWidget(config_panel)          # index 0

        # Panel 1: Chart Editor
        self._chart_editor = ChartEditorPanel(
            self._content,
            callbacks={
                "on_chart_saved":         self._on_chart_saved,
                "on_add_to_dashboard":    self._on_add_to_dashboard,
                "on_generate_ai":         self._on_ai_generate,
                "on_switch_to_dashboard": lambda: self._show_panel("dashboard"),
                "get_api_key": self.current_api_key,
                "get_model":   self._get_model,
            })
        self._content.addWidget(self._chart_editor)    # index 1
        self._viz_panel = self._chart_editor            # alias for load_metadata

        # Panel 2: Dashboard Builder
        self._dashboard_builder = DashboardBuilderPanel(
            self._content,
            callbacks={
                "on_export":           self._on_export,
                "on_deploy":           self._on_deploy_dashboard,
                "on_switch_to_editor": lambda: self._show_panel("chart_editor"),
                "on_open_chart":       self._open_chart_in_editor,
            })
        self._content.addWidget(self._dashboard_builder)   # index 2
        self._dashboard_panel = self._dashboard_builder    # alias

        # Panel 3: Metadata Library (curation + descriptions) — embedded, not a popup
        from ui.metadata_editor_panel import MetadataEditorPanel
        self._metadata_editor = MetadataEditorPanel(self._content)
        self._content.addWidget(self._metadata_editor)     # index 3

    # ─── Config panel content ─────────────────────────────────────────────────

    def _build_config_content(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── DHIS2 Connection section ──────────────────────────────────────────
        layout.addWidget(self._sb_section("DHIS2 Connection"))

        # Saved profiles row
        prof_row = QWidget()
        prof_row.setStyleSheet("background: transparent;")
        prof_hl = QHBoxLayout(prof_row)
        prof_hl.setContentsMargins(16, 2, 16, 4)
        prof_hl.setSpacing(4)

        self.profile_menu = QComboBox()
        self.profile_menu.addItem("— Saved profiles —")
        self.profile_menu.setStyleSheet(
            "QComboBox { background: #253d52; color: white; border: 1px solid #2a4a6a;"
            " border-radius: 4px; padding: 3px 8px; font-size: 11px; min-height: 26px; }"
            "QComboBox::drop-down { border: none; width: 18px; }"
            "QComboBox QAbstractItemView { background: #253d52; color: white;"
            " selection-background-color: #1a6fa8; }"
        )
        self.profile_menu.currentTextChanged.connect(self._on_profile_selected)
        prof_hl.addWidget(self.profile_menu, 1)

        self.del_profile_btn = QPushButton("✕")
        self.del_profile_btn.setFixedSize(28, 28)
        self.del_profile_btn.setToolTip("Delete selected profile")
        self.del_profile_btn.setStyleSheet(
            "QPushButton { background: #3a2020; color: white; border: none; border-radius: 4px; font-size: 11px; }"
            "QPushButton:hover { background: #5a2020; }"
        )
        self.del_profile_btn.clicked.connect(self._on_delete_profile)
        prof_hl.addWidget(self.del_profile_btn)
        layout.addWidget(prof_row)

        # ── Login fields ──────────────────────────────────────────────────────
        self._login_frame = QWidget()
        self._login_frame.setStyleSheet("background: transparent;")
        lf_layout = QVBoxLayout(self._login_frame)
        lf_layout.setContentsMargins(16, 0, 16, 0)
        lf_layout.setSpacing(2)

        lf_layout.addWidget(self._field_label("Server URL"))
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("https://hmis.example.org")
        self.url_entry.setFixedHeight(32)
        self.url_entry.setStyleSheet(self._entry_style())
        lf_layout.addWidget(self.url_entry)
        lf_layout.addSpacing(4)

        lf_layout.addWidget(self._field_label("Username"))
        self.user_entry = QLineEdit()
        self.user_entry.setPlaceholderText("admin")
        self.user_entry.setFixedHeight(32)
        self.user_entry.setStyleSheet(self._entry_style())
        lf_layout.addWidget(self.user_entry)
        lf_layout.addSpacing(4)

        lf_layout.addWidget(self._field_label("Password"))
        self.pass_entry = QLineEdit()
        self.pass_entry.setPlaceholderText("••••••••")
        self.pass_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_entry.setFixedHeight(32)
        self.pass_entry.setStyleSheet(self._entry_style())
        pw_row = QWidget()
        pw_row.setStyleSheet("background: transparent;")
        pw_hl = QHBoxLayout(pw_row)
        pw_hl.setContentsMargins(0, 0, 0, 0)
        pw_hl.setSpacing(4)
        pw_hl.addWidget(self.pass_entry, 1)
        self.pass_reveal_btn = self._make_reveal_btn(self.pass_entry)
        pw_hl.addWidget(self.pass_reveal_btn)
        lf_layout.addWidget(pw_row)
        lf_layout.addSpacing(4)

        # Buttons row
        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        btn_hl = QHBoxLayout(btn_row)
        btn_hl.setContentsMargins(0, 0, 0, 6)
        btn_hl.setSpacing(4)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setFixedHeight(34)
        self.connect_btn.setMinimumWidth(120)
        self.connect_btn.setStyleSheet(
            f"QPushButton {{ background: {DHIS2_BLUE}; color: white; border: none;"
            "  border-radius: 4px; font-size: 12px; padding: 0 12px; }"
            "QPushButton:hover { background: #155a8a; }"
            "QPushButton:disabled { background: #27ae60; color: white; }"
        )
        self.connect_btn.clicked.connect(self._on_connect)
        btn_hl.addWidget(self.connect_btn)

        self.save_profile_btn = QPushButton("\U0001f4be")
        self.save_profile_btn.setFixedSize(34, 34)
        self.save_profile_btn.setToolTip("Save credentials to Windows Credential Manager")
        self.save_profile_btn.setStyleSheet(
            "QPushButton { background: #1a5a2a; color: white; border: none; border-radius: 4px; font-size: 14px; }"
            "QPushButton:hover { background: #145020; }"
        )
        self.save_profile_btn.clicked.connect(self._on_save_profile)
        btn_hl.addWidget(self.save_profile_btn)

        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedSize(34, 34)
        self.refresh_btn.setToolTip("Force re-fetch metadata from server")
        self.refresh_btn.setStyleSheet(
            "QPushButton { background: #2a4a6a; color: white; border: none; border-radius: 4px; font-size: 16px; }"
            "QPushButton:hover { background: #1a3a5a; }"
            "QPushButton:disabled { background: #223344; color: #667788; }"
        )
        self.refresh_btn.clicked.connect(self._on_refresh_metadata)
        btn_hl.addWidget(self.refresh_btn)
        btn_hl.addStretch()

        lf_layout.addWidget(btn_row)
        layout.addWidget(self._login_frame)

        # ── Post-connect widgets ──────────────────────────────────────────────
        self.change_conn_btn = QPushButton("↺ Change connection")
        self.change_conn_btn.setFixedHeight(28)
        self.change_conn_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #8aa3b8; border: 1px solid #4a6278;"
            "  border-radius: 4px; font-size: 11px; margin: 0 16px; }"
            "QPushButton:hover { background: #253d52; }"
        )
        self.change_conn_btn.clicked.connect(self._on_change_connection)
        self.change_conn_btn.hide()
        layout.addWidget(self.change_conn_btn)
        layout.addSpacing(4)

        self.conn_status = QLabel("● Not connected")
        self.conn_status.setStyleSheet("color: #8aa3b8; font-size: 11px; padding: 0 16px; background: transparent;")
        layout.addWidget(self.conn_status)
        layout.addSpacing(2)

        self.cache_lbl = QLabel("")
        self.cache_lbl.setStyleSheet("color: #93a8bc; font-size: 10px; padding: 0 16px; background: transparent;")
        layout.addWidget(self.cache_lbl)
        layout.addSpacing(4)

        # Metadata scope filter moved to the Metadata Library panel (⚙ Filters && Load).
        layout.addSpacing(8)

        # ── Anthropic API Key ─────────────────────────────────────────────────
        layout.addWidget(self._sb_section("Anthropic API Key"))

        apikey_row = QWidget()
        apikey_row.setStyleSheet("background: transparent;")
        ak_hl = QHBoxLayout(apikey_row)
        ak_hl.setContentsMargins(16, 4, 16, 0)
        ak_hl.setSpacing(4)

        self.apikey_entry = QLineEdit()
        self.apikey_entry.setPlaceholderText("sk-ant-…")
        self.apikey_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.apikey_entry.setFixedHeight(32)
        self.apikey_entry.setStyleSheet(self._entry_style())
        ak_hl.addWidget(self.apikey_entry, 1)
        if self._api_key:
            self.apikey_entry.setText(self._api_key)

        self.apikey_reveal_btn = self._make_reveal_btn(self.apikey_entry)
        ak_hl.addWidget(self.apikey_reveal_btn)

        self.save_apikey_btn = QPushButton("\U0001f4be")
        self.save_apikey_btn.setFixedSize(34, 32)
        self.save_apikey_btn.setToolTip("Save API key to Windows Credential Manager")
        self.save_apikey_btn.setStyleSheet(
            "QPushButton { background: #1a5a2a; color: white; border: none; border-radius: 4px; font-size: 14px; }"
            "QPushButton:hover { background: #145020; }"
        )
        self.save_apikey_btn.clicked.connect(self._on_save_api_key)
        ak_hl.addWidget(self.save_apikey_btn)
        layout.addWidget(apikey_row)

        # ── AI Model ─────────────────────────────────────────────────────────
        layout.addWidget(self._sb_section("AI Model"))

        self._MODEL_OPTIONS = {
            "Haiku 4.5  (fast, cheap)":  "claude-haiku-4-5-20251001",
            "Sonnet 4.6  (balanced)":    "claude-sonnet-4-6",
            "Opus 4.8  (best quality)":  "claude-opus-4-8",
        }
        self.model_combo = QComboBox()
        for label in self._MODEL_OPTIONS:
            self.model_combo.addItem(label)
        self.model_combo.setStyleSheet(
            "QComboBox { background: white; color: #1e2d3d; border: 1px solid #c0cdd8;"
            "  border-radius: 4px; padding: 3px 8px; font-size: 11px; min-height: 28px; margin: 2px 16px 0 16px; }"
            "QComboBox::drop-down { border: none; width: 18px; }"
            "QComboBox QAbstractItemView { background: white; color: #1e2d3d;"
            "  selection-background-color: #dbeafe; }"
        )
        # Persist the AI model choice across restarts (config/app_settings.json — a plain
        # file in the app folder, not the Windows registry).
        from config import app_settings
        _saved = app_settings.get("ai_model_label", "")
        if _saved in self._MODEL_OPTIONS:
            self.model_combo.setCurrentText(_saved)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        layout.addWidget(self.model_combo)

        # Footer
        footer = QLabel("v0.1.0 — CHAI Laos")
        footer.setStyleSheet("color: #93a8bc; font-size: 10px; padding: 16px 16px 12px 16px; background: transparent;")
        layout.addWidget(footer)
        layout.addStretch()

    # ── Config panel helpers ───────────────────────────────────────────────

    def _sb_section(self, label: str) -> QLabel:
        lbl = QLabel(label)
        lbl.setStyleSheet(
            "color: #8aa3b8; font-size: 11px; font-weight: bold;"
            "padding: 8px 20px 2px 20px; background: transparent;"
        )
        return lbl

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: white; font-size: 12px; background: transparent;")
        return lbl

    def _entry_style(self) -> str:
        return (
            "QLineEdit { background: #253d52; color: white; border: 1px solid #2a4a6a;"
            "  border-radius: 4px; padding: 4px 8px; font-size: 12px; }"
            "QLineEdit:focus { border-color: #1a6fa8; }"
        )

    def _get_model(self) -> str:
        label = self.model_combo.currentText()
        return self._MODEL_OPTIONS.get(label, "claude-haiku-4-5-20251001")

    def _on_model_changed(self, label: str) -> None:
        """Remember the selected AI model across app restarts (config/app_settings.json)."""
        from config import app_settings
        app_settings.set("ai_model_label", label)

    def current_api_key(self) -> str:
        """REQ-LOGIN-APIKEY-03: field value takes precedence, falling back to the saved key."""
        return self.apikey_entry.text().strip() or self._api_key

    def _make_reveal_btn(self, entry: QLineEdit) -> QPushButton:
        """REQ-LOGIN-UX-01: 👁 toggle to show/hide a password-style field."""
        btn = QPushButton("\U0001f441")          # 👁
        btn.setFixedSize(34, 32)
        btn.setCheckable(True)
        btn.setToolTip("Show / hide")
        btn.setStyleSheet(
            "QPushButton { background: #253d52; color: white; border: 1px solid #2a4a6a;"
            "  border-radius: 4px; font-size: 13px; }"
            "QPushButton:checked { background: #1a6fa8; }"
        )
        btn.toggled.connect(
            lambda on: entry.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        return btn

    @staticmethod
    def _normalize_url(url: str) -> str:
        """REQ-LOGIN-VAL-01: trim, add https:// if no scheme, drop trailing slash."""
        url = (url or "").strip()
        if url and not re.match(r"^https?://", url, re.IGNORECASE):
            url = "https://" + url
        return url.rstrip("/")

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """REQ-LOGIN-VAL-01: must be http(s):// with a host."""
        try:
            p = urlparse(url)
        except Exception:
            return False
        return p.scheme in ("http", "https") and bool(p.netloc)

    # ─── Status bar ───────────────────────────────────────────────────────────

    def _build_statusbar(self):
        sb = self.statusBar()
        sb.setStyleSheet(
            "QStatusBar { background: #eef2f7; border-top: 1px solid #d0dde8;"
            "  color: #4a6278; font-size: 11px; }"
            "QStatusBar::item { border: none; }"
        )
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #4a6278; padding: 0 8px;")
        sb.addWidget(self.status_label, 1)

        self.progress = QProgressBar()
        self.progress.setFixedSize(160, 10)
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar { border: 1px solid #c0cdd8; border-radius: 4px; background: #e8eef5; }"
            "QProgressBar::chunk { background: #1a6fa8; border-radius: 3px; }"
        )
        sb.addPermanentWidget(self.progress)

    def _set_status(self, msg: str, error: bool = False):
        color = "#e74c3c" if error else "#4a6278"
        self.status_label.setStyleSheet(f"color: {color}; padding: 0 8px;")
        self.status_label.setText(msg)

    def _start_progress(self):
        self.progress.setRange(0, 0)  # indeterminate

    def _stop_progress(self):
        self.progress.setRange(0, 100)
        self.progress.setValue(100)

    # ─── Saved credentials ───────────────────────────────────────────────────

    def _load_saved_credentials(self):
        """On startup: populate profile dropdown, restore API key, auto-connect first profile."""
        from config.credentials import load_profiles, load_api_key, load_password, profile_label
        self._profiles = load_profiles()
        self._refresh_profile_menu()

        # Restore API key if not already set via .env
        if not self._api_key:
            saved_key = load_api_key()
            if saved_key:
                self._api_key = saved_key
                self.apikey_entry.setText(saved_key)

        # Auto-connect using first saved profile
        if self._profiles:
            p = self._profiles[0]
            # Block signals while filling to avoid triggering _on_profile_selected
            self.profile_menu.blockSignals(True)
            self.profile_menu.setCurrentText(profile_label(p))
            self.profile_menu.blockSignals(False)
            self.url_entry.setText(p["url"])
            self.user_entry.setText(p["username"])
            pwd = load_password(p["url"], p["username"])
            if pwd:
                self.pass_entry.setText(pwd)
                QTimer.singleShot(200, self._on_connect)

    def _refresh_profile_menu(self):
        from config.credentials import profile_label
        self.profile_menu.blockSignals(True)
        self.profile_menu.clear()
        self.profile_menu.addItem("— Saved profiles —")
        for p in self._profiles:
            self.profile_menu.addItem(profile_label(p))
        self.profile_menu.setCurrentIndex(0)
        self.profile_menu.blockSignals(False)

    def _on_profile_selected(self, label: str):
        if label == "— Saved profiles —":
            return
        from config.credentials import load_profiles, load_password, profile_label
        self._profiles = load_profiles()
        for p in self._profiles:
            if profile_label(p) == label:
                self.url_entry.setReadOnly(False)
                self.user_entry.setReadOnly(False)
                self.pass_entry.setReadOnly(False)
                self.url_entry.setText(p["url"])
                self.user_entry.setText(p["username"])
                pwd = load_password(p["url"], p["username"])
                self.pass_entry.clear()
                if pwd:
                    self.pass_entry.setText(pwd)
                # Reset connect button in case it shows "✓ Connected"
                self.connect_btn.setEnabled(True)
                self.connect_btn.setText("Connect")
                self.connect_btn.setStyleSheet(
                    f"QPushButton {{ background: {DHIS2_BLUE}; color: white; border: none;"
                    "  border-radius: 4px; font-size: 12px; padding: 0 12px; }"
                    "QPushButton:hover { background: #155a8a; }"
                    "QPushButton:disabled { background: #27ae60; color: white; }"
                )
                self.change_conn_btn.hide()
                # Auto-connect after filling credentials
                QTimer.singleShot(100, self._on_connect)
                break

    def _on_save_profile(self):
        url  = self.url_entry.text().strip()
        user = self.user_entry.text().strip()
        pwd  = self.pass_entry.text()
        if not (url and user):
            self._set_status("Enter URL and username before saving.", error=True)
            return
        from config.credentials import save_profile, load_profiles
        save_profile(url, user, pwd)
        self._profiles = load_profiles()
        self._refresh_profile_menu()
        self._set_status(f"Profile saved: {user} @ {url}")

    def _on_delete_profile(self):
        label = self.profile_menu.currentText()
        if label == "— Saved profiles —":
            return
        from config.credentials import delete_profile, load_profiles, profile_label
        self._profiles = load_profiles()
        for p in self._profiles:
            if profile_label(p) == label:
                reply = QMessageBox.question(
                    self, "Delete profile",
                    f"Delete saved profile:\n{label}\n\n"
                    "Password will be removed from Windows Credential Manager.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    delete_profile(p["url"], p["username"])
                    self._profiles = load_profiles()
                    self._refresh_profile_menu()
                    self._set_status("Profile deleted.")
                return

    def _on_save_api_key(self):
        key = self.apikey_entry.text().strip()
        if not key:
            self._set_status("Enter API key first.", error=True)
            return
        from config.credentials import save_api_key
        save_api_key(key)
        self._set_status("Anthropic API key saved to Windows Credential Manager.")

    # ─── Connect (cache-first) ────────────────────────────────────────────────

    def _on_connect(self):
        url  = self._normalize_url(self.url_entry.text())
        if url != self.url_entry.text():
            self.url_entry.setText(url)        # reflect normalisation in the field
        user = self.user_entry.text().strip()
        pwd  = self.pass_entry.text()
        if not (url and user and pwd):
            self._set_status("Fill in URL, username, and password.", error=True)
            return
        if not self._is_valid_url(url):
            self._set_status("Invalid server URL — must be http(s)://host", error=True)
            return

        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting…")
        self._set_status("Testing connection…")
        self._start_progress()
        threading.Thread(target=self._connect_worker,
                         args=(url, user, pwd, False), daemon=True).start()

    def _on_refresh_metadata(self):
        url  = self.url_entry.text().strip()
        user = self.user_entry.text().strip()
        pwd  = self.pass_entry.text()
        if not (url and user and pwd):
            self._set_status("Fill in connection details first.", error=True)
            return
        self.refresh_btn.setEnabled(False)
        self._set_status("Re-fetching metadata from server…")
        self._start_progress()
        threading.Thread(target=self._connect_worker,
                         args=(url, user, pwd, True), daemon=True).start()

    def _connect_worker(self, url: str, user: str, pwd: str, force_refresh: bool):
        try:
            from dhis2.client import DHIS2Client
            from dhis2.cache import load as cache_load, save as cache_save
            from dhis2.metadata import fetch_all
            from dhis2.filter_options import fetch_all_filter_options

            client = DHIS2Client(url, user, pwd)
            me = client.test_connection()
            display = me.get("name") or me.get("username") or user

            # Always load filter options (lightweight — just group names)
            self._sig_status.emit(f"Connected as {display}. Loading filter options…")
            filter_options = fetch_all_filter_options(client)
            self._client         = client
            self._filter_options = filter_options

            # Try cache for full metadata unless forced refresh
            from dhis2.cache import load_filter_cfg
            cached_meta, cached_at = cache_load(url)
            if cached_meta and not force_refresh:
                self._metadata    = cached_meta
                self._filter_cfg  = load_filter_cfg(url) or cached_meta.get("_filter_config", {})
                self._invalidate_ctx_caches()
                count = (len(cached_meta.get("indicators", [])) +
                         len(cached_meta.get("program_indicators", [])))
                self._sig_connect_done.emit(display, count, cached_at, True)
                return

            # No cache — fetch with current filter config
            self._sig_status.emit("Fetching metadata…")
            metadata = fetch_all(client, self._filter_cfg)
            cache_save(url, metadata)
            self._metadata   = metadata
            self._filter_cfg = metadata.get("_filter_config", {})
            self._invalidate_ctx_caches()

            count = (len(metadata.get("indicators", [])) +
                     len(metadata.get("program_indicators", [])))
            self._sig_connect_done.emit(display, count, None, False)

        except Exception as exc:
            self._sig_connect_fail.emit(str(exc))

    def _on_connect_done(self, display: str, count: int,
                          cached_at: str | None, from_cache: bool = False):
        self._stop_progress()
        # Show connected state — disable login fields until "Change" is clicked
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("✓ Connected")
        self.connect_btn.setStyleSheet(
            "QPushButton { background: #27ae60; color: white; border: none;"
            "  border-radius: 4px; font-size: 12px; padding: 0 12px; }"
            "QPushButton:disabled { background: #27ae60; color: white; }"
        )
        self._login_frame.hide()
        self.change_conn_btn.show()
        self.refresh_btn.setEnabled(True)
        # Enable the Metadata Library's scope-filter action now that we're connected.
        self._metadata_editor.set_filter_callback(self._on_open_filter_config)
        self._update_filter_summary()
        n_de   = len((self._metadata or {}).get("data_elements", []))
        n_prog = len((self._metadata or {}).get("programs", []))
        status_text = f"● {display}  ({n_de} DEs"
        if n_prog:
            status_text += f" | {n_prog} programs"
        status_text += ")"
        self.conn_status.setText(status_text)
        self.conn_status.setStyleSheet("color: #2ecc71; font-size: 11px; padding: 0 16px; background: transparent;")
        if from_cache and cached_at:
            self.cache_lbl.setText(f"Cached — {cached_at}")
            self.cache_lbl.setStyleSheet("color: #f39c12; font-size: 10px; padding: 0 16px; background: transparent;")
            self._set_status(f"Using cached metadata from {cached_at}. Press ↻ or reconfigure filters.")
        else:
            self.cache_lbl.setText("Metadata freshly loaded.")
            self.cache_lbl.setStyleSheet("color: #27ae60; font-size: 10px; padding: 0 16px; background: transparent;")
            self._set_status(f"Ready — {n_de} data elements, {n_prog} programs loaded.")
        self._update_filter_summary()
        self._unlock_ui()
        self._chart_editor._dhis2_client = self._client
        # Configure preview server proxy so /api/* calls reach DHIS2
        try:
            from ui.preview_server import configure_proxy
            auth = self._client._auth
            configure_proxy(self._client.base_url, auth.username, auth.password)
        except Exception:
            pass
        if self._metadata:
            self._viz_panel.load_metadata(self._metadata)
            self._download_sample_background(self._metadata)
            self._update_dashboard_context()
            # Apply the saved in-use selection so pickers offer only curated metadata.
            try:
                from config.selection import load_selection
                base_url = self._client.base_url if self._client else ""
                self._chart_editor.set_in_use(load_selection(base_url) if base_url else set())
            except Exception:
                pass
        self._show_panel("chart_editor")

    def _update_dashboard_context(self) -> None:
        """Pass current metadata + descriptions to the dashboard builder for AI generate."""
        if not self._metadata:
            return
        base_url = ""
        try:
            base_url = self._client.base_url if self._client else ""
        except Exception:
            pass
        try:
            from config.descriptions import load_descriptions
            descriptions = load_descriptions(base_url) if base_url else {}
        except Exception:
            descriptions = {}
        self._dashboard_builder.set_context(
            metadata=self._metadata,
            descriptions=descriptions,
            base_url=base_url,
        )

    def _open_metadata_editor(self) -> None:
        """Show the Metadata Library panel (curation + descriptions) — embedded, not a popup."""
        if not self._metadata:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Metadata Library",
                                    "Connect to a DHIS2 instance first.")
            return
        base_url = ""
        try:
            base_url = self._client.base_url if self._client else ""
        except Exception:
            pass
        try:
            from config.descriptions import load_descriptions
            descriptions = load_descriptions(base_url) if base_url else {}
        except Exception:
            descriptions = {}
        self._metadata_editor.set_context(base_url, self._metadata, descriptions)
        self._update_filter_summary()
        self._show_panel("metadata_editor")
        # Aggregate indicators are skipped on tracker-only connects — fetch them lazily so
        # they can be curated here (they'd otherwise never appear in the Library).
        if self._client and not self._metadata.get("indicators"):
            self._set_status("Loading indicators…")
            threading.Thread(target=self._load_indicators_for_library, daemon=True).start()

    def _load_indicators_for_library(self) -> None:
        try:
            from dhis2.metadata import fetch_indicators
            cfg = (self._metadata or {}).get("_filter_config") or {}
            rows = fetch_indicators(self._client, cfg)
        except Exception as exc:
            self._sig_call_main.emit(lambda e=exc: self._set_status(
                f"Could not load indicators: {e}", error=True))
            return

        def _apply():
            if not rows:
                self._set_status("No indicators found for this instance.")
                return
            self._metadata["indicators"] = rows
            self._metadata_editor.add_metadata({"indicators": rows})
            # Hand them to the Chart Editor too so curated indicators render without a re-fetch.
            self._chart_editor._agg_indicators = sorted(
                [{"uid": i["id"], "name": i.get("displayName", i["id"]),
                  "type": "indicator", "prog_uid": "", "stage_uid": "", "kind": "I"}
                 for i in rows], key=lambda x: x["name"].lower())
            self._chart_editor._indicators_loaded = True
            self._set_status(f"Loaded {len(rows)} indicators — now available in the Library.")
        self._sig_call_main.emit(_apply)

    def _download_sample_background(self, metadata: dict):
        """Silently download RAW sample events + metadata export after connect.

        Uses the DHIS2 export APIs (tracker events + metadata dependency export) and
        saves native JSON under data/<instance_slug>/ — see dhis2/sample_fetcher.py.
        """
        try:
            from dhis2 import data_store
            from dhis2.sample_fetcher import download_sample_data_async
        except Exception:
            return
        if not self._client:
            return

        base_url     = self._client.base_url
        program_ids  = [p["id"] for p in metadata.get("programs", []) if p.get("id")]
        dataset_ids  = [d["id"] for d in metadata.get("datasets", []) if d.get("id")]

        # Set the active instance now so the preview generator reads the right folder
        # even before the background download finishes (it falls back to any prior data).
        data_store.set_active_instance(base_url)
        download_sample_data_async(self._client, base_url, program_ids, dataset_ids)

    def _on_connect_fail(self, msg: str):
        self._stop_progress()
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")
        self.connect_btn.setStyleSheet(
            f"QPushButton {{ background: {DHIS2_BLUE}; color: white; border: none;"
            "  border-radius: 4px; font-size: 12px; padding: 0 12px; }"
            "QPushButton:hover { background: #155a8a; }"
            "QPushButton:disabled { background: #27ae60; color: white; }"
        )
        self.refresh_btn.setEnabled(True)
        self.conn_status.setText("● Connection failed")
        self.conn_status.setStyleSheet("color: #e74c3c; font-size: 11px; padding: 0 16px; background: transparent;")
        self._set_status(f"Connection failed: {msg}", error=True)

    def _on_change_connection(self):
        """Switch to config panel so user can change connection."""
        self._show_panel("config")
        self._login_frame.show()
        self.url_entry.setReadOnly(False)
        self.user_entry.setReadOnly(False)
        self.pass_entry.setReadOnly(False)
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")
        self.connect_btn.setStyleSheet(
            f"QPushButton {{ background: {DHIS2_BLUE}; color: white; border: none;"
            "  border-radius: 4px; font-size: 12px; padding: 0 12px; }"
            "QPushButton:hover { background: #155a8a; }"
            "QPushButton:disabled { background: #27ae60; color: white; }"
        )
        self.change_conn_btn.hide()

    # ─── Filter Config & Load Metadata ───────────────────────────────────────

    def _on_open_filter_config(self):
        if not self._client:
            self._set_status("Connect first.", error=True)
            return

        from ui.filter_config_dialog import FilterConfigDialog
        dlg = FilterConfigDialog(self,
                                  self._filter_options or {},
                                  self._filter_cfg)
        dlg.exec()

        if dlg.result is None:
            return  # cancelled

        self._filter_cfg = dlg.result
        self._update_filter_summary()
        self._set_status("Filter configured. Loading metadata…")
        self._start_progress()
        self._metadata_editor.set_filter_summary("⏳ Loading metadata…")

        threading.Thread(target=self._load_metadata_worker, daemon=True).start()

    def _load_metadata_worker(self):
        try:
            from dhis2.metadata import fetch_all
            from dhis2.cache import save as cache_save, save_filter_cfg

            url      = self.url_entry.text().strip()
            metadata = fetch_all(self._client, self._filter_cfg)
            cache_save(url, metadata)
            save_filter_cfg(url, self._filter_cfg)   # persist filter separately
            self._metadata   = metadata
            self._filter_cfg = metadata.get("_filter_config", {})
            self._invalidate_ctx_caches()

            count = (len(metadata.get("indicators", [])) +
                     len(metadata.get("program_indicators", [])))
            self._sig_call_main.emit(lambda c=count: self._on_metadata_loaded(c))
        except Exception as exc:
            import traceback; traceback.print_exc()
            exc_msg = str(exc)
            self._sig_call_main.emit(lambda m=exc_msg: self._on_metadata_load_fail(m))

    def _on_metadata_loaded(self, count: int):
        self._stop_progress()
        self.cache_lbl.setText("Metadata freshly loaded.")
        self.cache_lbl.setStyleSheet("color: #27ae60; font-size: 10px; padding: 0 16px; background: transparent;")
        self._update_filter_summary()
        n_de = len((self._metadata or {}).get("data_elements", []))
        self._set_status(f"Metadata loaded — {n_de} data elements.")
        if self._metadata:
            self._viz_panel.load_metadata(self._metadata)
            # Refresh the Metadata Library in place with the newly-scoped metadata.
            base_url = self._client.base_url if self._client else ""
            try:
                from config.descriptions import load_descriptions
                descriptions = load_descriptions(base_url) if base_url else {}
            except Exception:
                descriptions = {}
            self._metadata_editor.set_context(base_url, self._metadata, descriptions)
            self._update_filter_summary()
            try:
                from config.selection import load_selection
                self._chart_editor.set_in_use(load_selection(base_url) if base_url else set())
            except Exception:
                pass

    def _on_metadata_load_fail(self, msg: str):
        self._stop_progress()
        self._update_filter_summary()
        self._set_status(f"Metadata load failed: {msg}", error=True)

    def _update_filter_summary(self):
        """Push a short scope-summary to the Metadata Library's filter label."""
        cfg = self._filter_cfg or {}
        parts = []
        if cfg.get("indicator_group_ids"):
            parts.append(f"{len(cfg['indicator_group_ids'])} ind.groups")
        if cfg.get("de_group_ids"):
            parts.append(f"{len(cfg['de_group_ids'])} DE groups")
        if cfg.get("program_ids"):
            parts.append(f"{len(cfg['program_ids'])} programs")
        if cfg.get("dataset_ids"):
            parts.append(f"{len(cfg['dataset_ids'])} datasets")
        kws = [v for k, v in cfg.items() if k.endswith("_name") and v]
        if kws:
            parts.append(f"keywords: {', '.join(kws)}")
        text = ("Scope: " + " | ".join(parts)) if parts else "Scope: all metadata"
        try:
            self._metadata_editor.set_filter_summary(text)
        except Exception:
            pass

    # ─── Metadata Selector ───────────────────────────────────────────────────

    def _on_open_selector(self):
        if not self._metadata:
            self._set_status("Connect to DHIS2 first to load metadata.", error=True)
            return

        from dhis2.usage_tracker import get_counts
        url    = self.url_entry.text().strip()
        counts = get_counts(url)

        from ui.metadata_selector import MetadataSelector
        sel = MetadataSelector(self, self._metadata, counts, self._pinned)
        sel.exec()

        if sel.result is not None:
            self._pinned = sel.result
            self._invalidate_ctx_caches()
            self._refresh_pin_count()

    def _refresh_pin_count(self):
        if not hasattr(self, "pin_count_lbl"):
            return
        total = sum(len(v) for v in self._pinned.values())
        if total == 0:
            self.pin_count_lbl.setText("No items pinned")
            self.pin_count_lbl.setStyleSheet("color: #8aa3b8;")
        else:
            parts = []
            labels = {"data_elements": "DE", "program_stage_data_elements": "stage DE", "tracked_entity_attributes": "TEA"}
            for k, short in labels.items():
                n = len(self._pinned.get(k, []))
                if n:
                    parts.append(f"{n} {short}")
            self.pin_count_lbl.setText("★ Pinned: " + ", ".join(parts))
            self.pin_count_lbl.setStyleSheet(f"color: {DHIS2_BLUE};")

    # ─── Dashboard Builder ───────────────────────────────────────────────────

    def _on_open_dashboard_builder(self):
        if not self._metadata:
            self._set_status("Connect to DHIS2 and load metadata first.", error=True)
            return
        from ui.dashboard_builder import DashboardBuilder
        existing = self._dashboard_layout  # pass existing layout to edit
        dlg = DashboardBuilder(self, self._metadata, self._pinned, existing)
        dlg.exec()
        if dlg.result is not None:
            self._dashboard_layout = dlg.result
            self._invalidate_ctx_caches()
            n = len(dlg.result)
            self._set_status(f"Dashboard layout saved — {n} chart(s). Click Generate to build.")

    # ─── Edit Dashboard ──────────────────────────────────────────────────────

    def _on_edit_dashboard(self):
        """Open DashboardBuilder pre-loaded with last generated layout, then offer selective regen."""
        if not self._last_generated_layout:
            return
        from ui.dashboard_builder import DashboardBuilder
        dlg = DashboardBuilder(self, self._metadata, self._pinned,
                               copy.deepcopy(self._last_generated_layout))
        dlg.exec()
        if dlg.result is None:
            return  # cancelled

        old_layout = self._last_generated_layout
        new_layout = dlg.result
        self._dashboard_layout = new_layout

        # Detect whether structure changed (card IDs or count differ)
        old_ids = [c.get("id") for c in old_layout]
        new_ids = [c.get("id") for c in new_layout]

        if old_ids == new_ids:
            changed_ids = _detect_changed_cards(old_layout, new_layout)
            if not changed_ids:
                self._set_status("No cards changed — layout updated.")
                return
            n_changed = len(changed_ids)
            reply = QMessageBox.question(
                self, "Regenerate",
                f"{n_changed} card(s) changed.\n\n"
                f"Yes  → Regenerate only changed card(s) — faster\n"
                f"No   → Regenerate entire dashboard",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._regenerate_changed_cards(new_layout, changed_ids)
                return

        # Full regeneration
        self._on_generate()

    def _regenerate_changed_cards(self, new_layout: list[dict], changed_ids: set[str]):
        """Regenerate only the changed cards and splice them into the existing HTML."""
        api_key = self.apikey_entry.text().strip()
        if not api_key:
            self._set_status("Enter Anthropic API key.", error=True)
            return
        current_html = self.report_view.get_html()
        if not current_html:
            return

        n = len(changed_ids)
        if self.generate_btn:
            self.generate_btn.setEnabled(False)
            self.generate_btn.setText("Regenerating…")
        self._set_status(f"Regenerating {n} card(s)…")
        self._start_progress()

        threading.Thread(
            target=self._regen_cards_worker,
            args=(new_layout, changed_ids, current_html, api_key, self._get_model()),
            daemon=True,
        ).start()

    def _regen_cards_worker(self, new_layout, changed_ids, current_html, api_key,
                            model: str = "claude-haiku-4-5-20251001"):
        try:
            from llm.context_builder import build_context
            from llm.dashboard_generator import (
                regenerate_single_card, splice_card_in_html,
                _group_into_rows, _bs_cols,
            )
            from dhis2.usage_tracker import get_counts

            url    = self.url_entry.text().strip()
            counts = get_counts(url)
            merged = _merge_pinned(new_layout, self._pinned)
            context = build_context(self._metadata or {}, url,
                                    pinned=merged, usage_counts=counts)

            # Compute chart_index and bs_cols per card from the layout order
            rows = _group_into_rows(new_layout)
            card_info: dict[str, tuple[int, int]] = {}
            idx = 1
            for row in rows:
                row_w = sum(c["w"] for c in row)
                for card in row:
                    card_info[card.get("id", "")] = (idx, _bs_cols(card["w"], row_w))
                    idx += 1

            html = current_html
            for card in new_layout:
                cid = card.get("id", "")
                if cid not in changed_ids:
                    continue
                chart_idx, bs = card_info.get(cid, (1, 6))
                self._sig_call_main.emit(lambda i=chart_idx: self._set_status(f"Regenerating card {i}…"))
                fragment = regenerate_single_card(card, chart_idx, context, bs,
                                                  api_key=api_key, model=model)
                try:
                    html = splice_card_in_html(html, cid, fragment)
                except ValueError:
                    # Markers not found — fall back to full regen silently
                    self._sig_call_main.emit(lambda: self._set_status(
                        "Edit markers missing — regenerating full dashboard…"))
                    self._sig_call_main.emit(self._on_generate)
                    return

            self._sig_call_main.emit(lambda h=html: self._on_regen_cards_done(h, new_layout))

        except Exception as exc:
            exc_msg = str(exc)
            self._sig_call_main.emit(lambda: self._on_generate_fail(exc_msg))

    def _on_regen_cards_done(self, html: str, new_layout: list[dict]):
        self._stop_progress()
        if self.generate_btn:
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("Generate from chat ▶")
        self.report_view.show(html)
        self._last_generated_layout = copy.deepcopy(new_layout)
        self.report_view.set_edit_callback(self._on_edit_dashboard)
        self._set_status("Card(s) regenerated. Preview or Deploy to DHIS2.")

    # ─── Chart Library (single chart fallback) ──────────────────────────────

    def _open_chart_in_editor(self, cfg: dict):
        """Open a dashboard card's chart in the Chart Editor for quick editing. Resolve the
        library id (by name) if the card lacks one, so Save updates the saved chart (Save As
        makes a copy) instead of always behaving like Save As."""
        cfg = dict(cfg)
        if not cfg.get("id"):
            try:
                from config.chart_library import load_charts
                nm = cfg.get("name") or cfg.get("title")
                match = next((c for c in load_charts()
                              if (c.get("name") or c.get("title")) == nm), None)
                if match:
                    cfg["id"] = match.get("id")
                    cfg.setdefault("name", match.get("name") or match.get("title"))
            except Exception:
                pass
        self._show_panel("chart_editor")
        try:
            self._chart_editor._load_chart_config(cfg)
        except Exception as e:
            print("open chart in editor failed:", e)

    def _on_open_chart_library(self):
        from ui.chart_library import ChartLibrary
        current = None
        if self._dashboard_layout and len(self._dashboard_layout) == 1:
            current = self._dashboard_layout[0].get("template_id")
        lib = ChartLibrary(self, current)
        lib.exec()
        if lib.result is not None:
            # Wrap single template as a minimal one-card layout
            from charts.templates import get_by_id
            tmpl = get_by_id(lib.result)
            name = tmpl["name"] if tmpl else lib.result
            self._dashboard_layout = [{
                "id": "single",
                "template_id": lib.result,
                "title": name,
                "x": 20, "y": 20, "w": 900, "h": 400,
                "pinned": {k: list(v) for k, v in self._pinned.items()},
            }]
            self._set_status(f"Single chart: {name} — click Generate from chat to build.")

    # ─── Generate ────────────────────────────────────────────────────────────

    def _on_generate(self):
        api_key = self.apikey_entry.text().strip()
        if not api_key:
            self._set_status("Enter your Anthropic API key.", error=True)
            return

        messages = self.chat_panel.get_messages()
        if not messages:
            self._set_status("Enter a request in chat before generating.", error=True)
            return

        if self.generate_btn:
            self.generate_btn.setEnabled(False)
            self.generate_btn.setText("Generating…")
        self._set_status("Building context…")
        self._start_progress()
        self.report_view.clear()
        self.chat_panel.set_generating(True)

        model = self._get_model()
        scope = self.quick_form.get_scope()
        threading.Thread(target=self._generate_worker, args=(api_key, model, scope), daemon=True).start()

    def _generate_worker(self, api_key: str, model: str = "claude-haiku-4-5-20251001",
                         scope: tuple[str, str] = ("", "")):
        try:
            from llm.context_builder import build_context, filter_metadata_by_scope
            from dhis2.usage_tracker import get_counts
            url    = self.url_entry.text().strip()
            counts = get_counts(url)
            merged_pinned = _merge_pinned(self._dashboard_layout, self._pinned)

            # Full context — cached for the lifetime of the session
            if self._full_ctx is None:
                self._full_ctx = build_context(
                    self._metadata or {}, url, pinned=merged_pinned, usage_counts=counts)

            messages = self.chat_panel.get_messages()

            # Apply scope pre-filter (program/stage selection) — free, no LLM call.
            # Each generate is fresh — reset scoped_context so it matches current scope.
            self._scoped_context = None
            prog_name, stage_names = scope
            if prog_name:
                scoped_meta = filter_metadata_by_scope(
                    self._metadata or {}, prog_name, stage_names)
                # Lazy-load option sets only for DEs in scope
                if self._client:
                    from dhis2.metadata import enrich_with_option_sets
                    self._sig_call_main.emit(lambda: self._set_status("Loading option sets…"))
                    enrich_with_option_sets(self._client, scoped_meta)
                base_ctx = build_context(
                    scoped_meta, url, pinned=merged_pinned, usage_counts=counts)
            else:
                base_ctx = self._full_ctx

            # LLM filter — further compress to only what the conversation needs
            from llm.chat_generator import filter_metadata_context
            self._sig_call_main.emit(lambda: self._set_status("Filtering metadata to report scope…"))
            self._scoped_context = filter_metadata_context(messages, base_ctx, api_key)

            context = self._scoped_context

            # Extract prompt string for layout-based modes (join all user messages)
            prompt = " ".join(m["content"] for m in messages if m["role"] == "user")

            layout = self._dashboard_layout
            if layout and len(layout) > 1:
                from llm.dashboard_generator import generate_dashboard_html
                n = len(layout)
                self._sig_call_main.emit(lambda: self._set_status(f"Calling Claude to build {n}-chart dashboard…"))
                html = generate_dashboard_html(prompt, layout, context, api_key=api_key, model=model)

            elif layout and len(layout) == 1:
                from llm.report_generator import generate_report_html
                from charts.templates import get_by_id
                card = layout[0]
                tmpl = get_by_id(card.get("template_id", ""))
                if tmpl:
                    tmpl_name = tmpl["name"]
                    self._sig_call_main.emit(lambda: self._set_status(f"Filling template '{tmpl_name}' with Claude…"))
                    html = generate_report_html(
                        prompt, context, api_key=api_key,
                        template_html=tmpl["html"], template_name=tmpl["name"],
                        model=model,
                    )
                else:
                    self._sig_call_main.emit(lambda: self._set_status("Calling Claude to generate HTML…"))
                    html = generate_report_html(prompt, context, api_key=api_key, model=model)

            else:
                from llm.chat_generator import generate_from_chat
                self._sig_call_main.emit(lambda: self._set_status("Calling Claude to generate HTML from chat…"))
                html = generate_from_chat(messages, context, api_key, model=model)

            self._sig_call_main.emit(lambda h=html: self._on_generate_done(h))

        except Exception as exc:
            exc_msg = str(exc)
            self._sig_call_main.emit(lambda: self._on_generate_fail(exc_msg))

    def _on_generate_done(self, html: str):
        self._stop_progress()
        if self.generate_btn:
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("Generate from chat ▶")
        self.chat_panel.set_generating(False)
        self.report_view.show(html)
        # Auto-save for debugging
        try:
            from pathlib import Path
            from datetime import datetime
            debug_dir = Path(__file__).resolve().parent.parent / "debug"
            debug_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            (debug_dir / f"{ts}.html").write_text(html, encoding="utf-8")
        except Exception:
            pass
        self.chat_panel.add_system_note(
            "HTML generated — send a message to refine  |  Clear chat to change scope"
        )
        self.chat_panel.set_hint("Refine mode — send edit requests")

        # Track for edit-dashboard flow
        if self._dashboard_layout and len(self._dashboard_layout) > 1:
            self._last_generated_layout = copy.deepcopy(self._dashboard_layout)
            self.report_view.set_edit_callback(self._on_edit_dashboard)
        else:
            self._last_generated_layout = None
            self.report_view.set_edit_callback(None)

        self._set_status("HTML report generated. Preview or Deploy to DHIS2.")

    def _on_generate_fail(self, msg: str):
        self._stop_progress()
        if self.generate_btn:
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("Generate from chat ▶")
        self.chat_panel.set_generating(False)
        self._set_status(f"Generation failed: {msg}", error=True)

    # ─── Deploy ──────────────────────────────────────────────────────────────

    def _on_deploy(self):
        html = self.report_view.get_html()
        if not html:
            return
        if not self._client:
            self._set_status("Connect to DHIS2 first.", error=True)
            return
        name = self.report_view.get_report_name()
        if not name:
            self._set_status("Enter a report name before deploying.", error=True)
            self.report_view.focus_report_name()
            return

        # Fix broken CDN links (browser "Save As" rewrites) before any check
        from llm.html_utils import fix_cdn_links
        html = fix_cdn_links(html)

        # Warn only if _files/ is still present after the CDN fix (unrecognised pattern)
        if "_files/" in html:
            reply = QMessageBox.question(
                self, "Warning: broken CDN links detected",
                "The HTML still contains '_files/' references that could not be\n"
                "auto-fixed. Bootstrap or Chart.js may not load in DHIS2.\n\n"
                "Continue deploying anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._set_status("Deploying to DHIS2…")
        self._start_progress()
        threading.Thread(target=self._deploy_worker, args=(name, html), daemon=True).start()

    def _deploy_worker(self, name: str, html: str):
        try:
            from dhis2.report_api import deploy_report, report_url
            from dhis2.usage_tracker import record_usage
            from llm.html_utils import fix_cdn_links

            html = fix_cdn_links(html)  # ensure CDN links are correct before deploying
            # Upsert by name → re-deploying overwrites the same report (no duplicates).
            result = deploy_report(self._client, name, html)
            uid    = result.get("uid", "")
            base   = self.url_entry.text().strip()
            url    = report_url(base, uid) if uid else base

            # Record usage for pinned indicators
            record_usage(base, self._pinned)

            self._sig_call_main.emit(lambda: self._on_deploy_done(name, uid, url))
        except Exception as exc:
            exc_msg = str(exc)
            self._sig_call_main.emit(lambda: self._on_deploy_fail(exc_msg))

    def _on_deploy_done(self, name: str, uid: str, url: str):
        self._stop_progress()
        self._set_status(f"Deployed: '{name}'  (UID: {uid})")
        # Refresh pin count label (usage counts updated)
        self._refresh_pin_count()
        import webbrowser
        reply = QMessageBox.question(
            self, "Deploy successful",
            f"Report '{name}' created in DHIS2.\nUID: {uid}\n\nOpen in DHIS2 now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            webbrowser.open(url)

    def _on_deploy_fail(self, msg: str):
        self._stop_progress()
        self._set_status(f"Deploy failed: {msg}", error=True)

    # ─── Clear ───────────────────────────────────────────────────────────────

    def _on_clear(self):
        self.chat_panel.clear()
        self.report_view.clear()
        self.report_view.set_edit_callback(None)
        self._last_generated_layout = None
        self._scoped_context = None  # only the conversation scope resets; full/summary caches stay
        self.chat_panel.set_hint("Describe the report → click Generate")
        self._set_status("Ready")
        self.quick_form.reset()
        self._show_welcome_template()

    def _show_welcome_template(self):
        """Show quick form panel after metadata loads (only when chat is empty)."""
        if not self._metadata:
            return
        if self.chat_panel.get_messages():
            return  # don't overwrite an active conversation
        self.quick_form.set_metadata(self._metadata)
        # Restore last-used form values for this server
        url = self.url_entry.text().strip()
        if url:
            try:
                from dhis2.de_preferences import load_form_state
                self.quick_form.restore_state(load_form_state(url))
            except Exception:
                pass
        self.quick_form.show()
        if self.generate_btn:
            self.generate_btn.setText("Generate Dashboard ▶")
        self.chat_panel.add_welcome_message(
            "Hello! Fill in the form below and click \"Build Request\" — "
            "or type directly in the chat.")

    def _on_form_generate(self, configs: list[dict],
                          scope: tuple, scope_text: str):
        """Called when user clicks 'Generate Dashboard' in the form panel."""
        api_key = self.apikey_entry.text().strip()
        if not api_key:
            self._set_status("Enter your Anthropic API key.", error=True)
            return
        if not self._metadata:
            self._set_status("Connect to DHIS2 and load metadata first.", error=True)
            return

        # Save form state
        url = self.url_entry.text().strip()
        if url:
            try:
                from dhis2.de_preferences import save_form_state
                save_form_state(url, self.quick_form.get_state())
            except Exception:
                pass

        analytics_params = self.quick_form.get_analytics_params()
        if self.generate_btn:
            self.generate_btn.setEnabled(False)
            self.generate_btn.setText("Generating…")
        self.report_view.clear()
        self._set_status(f"Generating {len(configs)}-chart dashboard…")
        self._start_progress()
        model = self._get_model()
        threading.Thread(
            target=self._form_generate_worker,
            args=(configs, scope, scope_text, analytics_params, api_key, model),
            daemon=True,
        ).start()

    def _form_generate_worker(self, configs: list[dict],
                              scope: tuple, scope_text: str,
                              analytics_params: dict,
                              api_key: str, model: str):
        try:
            from llm.context_builder import build_context, filter_metadata_by_scope
            from llm.dashboard_generator import generate_from_chart_configs
            from dhis2.usage_tracker import get_counts

            url    = self.url_entry.text().strip()
            counts = get_counts(url)
            merged = _merge_pinned(self._dashboard_layout, self._pinned)

            # Filter metadata to selected program/stage scope
            prog_name, stage_names = scope
            base_meta = self._metadata or {}
            scoped_meta = (
                filter_metadata_by_scope(base_meta, prog_name, stage_names)
                if prog_name else base_meta
            )

            # ── Lazy-fetch program stage DEs if missing ──────────────────────
            if prog_name and self._client and not scoped_meta.get("program_stage_data_elements"):
                prog_uid = next(
                    (p.get("id") for p in base_meta.get("programs", [])
                     if p.get("displayName") == prog_name), None)
                if prog_uid:
                    self._sig_call_main.emit(lambda: self._set_status(f"Loading data elements for {prog_name}…"))
                    from dhis2.metadata import fetch_program_stage_data_elements
                    fresh_des = fetch_program_stage_data_elements(self._client, [prog_uid])
                    if fresh_des:
                        # Merge into base metadata so future generate calls are fast
                        existing = base_meta.get("program_stage_data_elements", [])
                        existing_ids = {d.get("id") for d in existing}
                        for de in fresh_des:
                            if de.get("id") not in existing_ids:
                                existing.append(de)
                        base_meta["program_stage_data_elements"] = existing
                        # Re-scope with fresh DEs
                        scoped_meta = filter_metadata_by_scope(
                            base_meta, prog_name, stage_names)
                        # Update form dropdowns on main thread
                        self._sig_call_main.emit(lambda: self.quick_form.set_metadata(base_meta))

            # ── Backfill missing metric_uid from name match ──────────────────
            psde_by_name = {
                d.get("displayName", "").lower(): d
                for d in scoped_meta.get("program_stage_data_elements", [])
            }
            agg_by_name = {
                d.get("displayName", "").lower(): d
                for d in scoped_meta.get("data_elements", [])
            }
            for c in configs:
                if not c.get("metric_uid"):
                    metric_lower = c.get("metric", "").lower().strip()
                    match = psde_by_name.get(metric_lower) or agg_by_name.get(metric_lower)
                    if not match:
                        # substring search
                        for name, de in {**psde_by_name, **agg_by_name}.items():
                            if name and (name in metric_lower or metric_lower in name):
                                match = de
                                break
                    if match:
                        c["metric_uid"] = match.get("id", "")

            context = build_context(scoped_meta, url, pinned=merged, usage_counts=counts)

            # ── Enrich configs with program/stage UIDs for JS generation ────
            psde_list = scoped_meta.get("program_stage_data_elements", [])
            for c in configs:
                de_uid = c.get("metric_uid", "")
                if de_uid:
                    psde_match = next(
                        (d for d in psde_list if d.get("id") == de_uid), None)
                    if psde_match:
                        c["program_uid"]  = psde_match.get("program", {}).get("id", "")
                        c["stage_uid"]    = psde_match.get("stage",   {}).get("id", "")
                        c["program_name"] = psde_match.get("program", {}).get("displayName", "")
                        c["stage_name"]   = psde_match.get("stage",   {}).get("displayName", "")

            self._sig_call_main.emit(lambda: self._set_status("Calling Claude to build dashboard…"))
            html = generate_from_chart_configs(
                configs, context,
                context_hint=scope_text,
                analytics_params=analytics_params,
                api_key=api_key, model=model)
            self._sig_call_main.emit(lambda h=html: self._on_form_generate_done(h))

        except Exception as exc:
            exc_msg = str(exc)
            self._sig_call_main.emit(lambda: self._on_form_generate_fail(exc_msg))

    def _on_form_generate_fail(self, msg: str):
        self._stop_progress()
        if self.generate_btn:
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("Generate Dashboard ▶")
        self._set_status(f"Generation failed: {msg}", error=True)

    def _on_form_generate_done(self, html: str):
        self._stop_progress()
        if self.generate_btn:
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("Generate from chat ▶")
        self.quick_form.hide()
        self.report_view.show(html)
        try:
            from pathlib import Path
            from datetime import datetime
            debug_dir = Path(__file__).resolve().parent.parent / "debug"
            debug_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            (debug_dir / f"{ts}.html").write_text(html, encoding="utf-8")
        except Exception:
            pass
        self.chat_panel.add_system_note(
            "Dashboard generated — send a message to refine  |  Clear to start over")
        self.chat_panel.set_hint("Refine mode — send edit requests")
        self._set_status("Dashboard generated. Preview or Deploy to DHIS2.")

    # ─── Chat send handler ────────────────────────────────────────────────────

    def _on_chat_send(self, text: str):
        """Called when user sends a chat message."""
        api_key = self.apikey_entry.text().strip()
        current_html = self.report_view.get_html()

        if current_html:
            # Phase 2 — refine existing HTML
            if not api_key:
                self._set_status("Enter Anthropic API key to refine.", error=True)
                return
            self.chat_panel.set_generating(True)
            self._start_progress()
            self._set_status("Refining report…")
            threading.Thread(
                target=self._refine_worker,
                args=(text, api_key, current_html, self._get_model()),
                daemon=True,
            ).start()

        elif self._metadata and api_key:
            # Phase 1 — planning, ask LLM for clarification
            self.chat_panel.set_generating(True)
            self._set_status("Thinking…")
            threading.Thread(
                target=self._chat_plan_worker,
                args=(api_key, self._get_model()),
                daemon=True,
            ).start()

        else:
            # No connection or no API key — message stored, no LLM response
            hint = "Connect to DHIS2 and enter your API key for AI assistance."
            self._set_status(hint)

    def _chat_plan_worker(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        try:
            from llm.chat_generator import chat_plan

            if self._summary_ctx is None:
                from llm.context_builder import build_summary_context
                from dhis2.usage_tracker import get_counts
                url    = self.url_entry.text().strip()
                counts = get_counts(url)
                merged = _merge_pinned(self._dashboard_layout, self._pinned)
                self._summary_ctx = build_summary_context(
                    self._metadata or {}, url, pinned=merged, usage_counts=counts)

            messages = self.chat_panel.get_messages()
            response = chat_plan(messages, self._summary_ctx, api_key, model=model)
            self._sig_call_main.emit(lambda r=response: self._on_chat_plan_done(r))
        except Exception as exc:
            exc_msg = str(exc)
            self._sig_call_main.emit(lambda: self._on_chat_fail(exc_msg))

    def _on_chat_plan_done(self, response: str):
        self.chat_panel.set_generating(False)
        self.chat_panel.add_assistant_message(response)
        self._set_status("Ready — click Generate when requirements are clear.")

    def _refine_worker(self, request: str, api_key: str, current_html: str,
                       model: str = "claude-haiku-4-5-20251001"):
        try:
            from llm.chat_generator import refine_from_chat

            # Reuse the scoped context from the generate phase if available;
            # only fall back to rebuilding when the session has no cached scope.
            if self._scoped_context:
                context = self._scoped_context
            else:
                from llm.context_builder import build_context
                from dhis2.usage_tracker import get_counts
                url    = self.url_entry.text().strip()
                counts = get_counts(url)
                merged = _merge_pinned(self._dashboard_layout, self._pinned)
                context = build_context(self._metadata or {}, url, pinned=merged, usage_counts=counts)

            html = refine_from_chat(request, current_html, context, api_key, model=model)
            self._sig_call_main.emit(lambda h=html: self._on_refine_done(h))
        except Exception as exc:
            exc_msg = str(exc)
            self._sig_call_main.emit(lambda: self._on_chat_fail(exc_msg))

    def _on_refine_done(self, html: str):
        self._stop_progress()
        self.chat_panel.set_generating(False)
        self.report_view.show(html)
        self.chat_panel.add_system_note("HTML updated")
        self._set_status("Report refined. Preview or Deploy to DHIS2.")
        # Re-apply edit dashboard tracking if applicable
        if self._dashboard_layout and len(self._dashboard_layout) > 1:
            self.report_view.set_edit_callback(self._on_edit_dashboard)

    def _on_chat_fail(self, msg: str):
        self._stop_progress()
        self.chat_panel.set_generating(False)
        self._set_status(f"Error: {msg}", error=True)

    # ─── Verify DEs ──────────────────────────────────────────────────────────

    def _on_verify_des(self, html: str):
        """Parse HTML for analytics API calls, cross-check DE IDs with metadata."""
        import re
        ids_found: set[str] = set()
        for m in re.finditer(
            r'dimension=dx(?:%3A|:)([\w;%]+)', html, re.IGNORECASE
        ):
            raw = m.group(1).replace('%3B', ';').replace('%3A', ':')
            for uid in re.split(r'[;,]', raw):
                uid = uid.strip()
                if len(uid) == 11 and uid.isalnum():
                    ids_found.add(uid)

        if not ids_found:
            QMessageBox.information(
                self, "Verify DEs",
                "No analytics calls found in the HTML.\n"
                "The report may use hardcoded sample data — check the prompt."
            )
            return

        meta = self._metadata or {}
        all_items = (
            meta.get("data_elements", []) +
            meta.get("program_stage_data_elements", []) +
            meta.get("indicators", []) +
            meta.get("program_indicators", [])
        )
        id_to_name = {it.get("id"): it.get("displayName", "?") for it in all_items}

        url = self.url_entry.text().strip()

        # Load history before this run so we can show cumulative counts
        from dhis2.de_preferences import load_verify_log, save_verify_results
        verify_log = load_verify_log(url) if url else {}

        valid_uids:   set[str] = set()
        invalid_uids: set[str] = set()
        ok_lines:  list[str] = []
        bad_lines: list[str] = []

        for uid in sorted(ids_found):
            name = id_to_name.get(uid)
            hist = verify_log.get(uid, {})
            if name:
                valid_uids.add(uid)
                times = hist.get("valid", 0) + 1
                ok_lines.append(f"  ✓  {uid}  →  {name}  [used {times}×]")
            else:
                invalid_uids.add(uid)
                times = hist.get("invalid", 0) + 1
                bad_lines.append(
                    f"  ✗  {uid}  →  NOT IN METADATA"
                    + (f"  [invalid {times}×]" if times > 1 else "")
                )

        # Persist results
        if url and (valid_uids or invalid_uids):
            save_verify_results(url, valid_uids, invalid_uids, id_to_name)

        sections = []
        if ok_lines:
            sections.append(f"Valid ({len(ok_lines)}):\n" + "\n".join(ok_lines))
        if bad_lines:
            sections.append(
                f"⚠ INVALID ({len(bad_lines)}) — data will be empty or wrong:\n"
                + "\n".join(bad_lines)
            )
        sections.append("Results saved — will warn if these UIDs appear in future reports.")

        QMessageBox.information(self, "Verify DEs in Report", "\n\n".join(sections))

    # ─── Viz Builder callbacks ────────────────────────────────────────────────

    def _on_chart_saved(self, chart: dict):
        """Chart saved to library — refresh Dashboard Builder library."""
        self._dashboard_builder.refresh_library()
        self._set_status(f"Chart '{chart.get('name', chart.get('title'))}' saved to library.")

    def _on_add_to_dashboard(self, config: dict):
        """Add chart directly to Dashboard Builder canvas."""
        self._dashboard_builder.add_card(config)
        self._set_status(f"Added '{config.get('title', '?')}' to dashboard.")

    def _on_add_card(self, config: dict):
        """Legacy alias — forward to dashboard builder."""
        self._dashboard_builder.add_card(config)

    def _on_fixed_preview(self, config: dict):
        """Preview handled internally by ChartEditorPanel — no-op here."""
        pass

    def _on_ai_generate(self, config: dict):
        """Generate a single chart card with AI."""
        if not self._metadata:
            self._set_status("Connect to DHIS2 first.", error=True)
            return
        api_key = self.apikey_entry.text().strip() or self._api_key
        if not api_key:
            self._set_status("Enter Anthropic API key.", error=True)
            return
        self._set_status("Generating AI chart…")
        self._start_progress()
        threading.Thread(
            target=self._ai_generate_worker,
            args=(config, api_key),
            daemon=True).start()

    def _ai_generate_worker(self, config: dict, api_key: str):
        try:
            from llm.context_builder import build_context
            from llm.dashboard_generator import generate_from_chart_configs
            from dhis2.metadata import get_program_stage_data_elements
            from pathlib import Path
            import datetime

            meta = self._metadata or {}

            # Enrich config with program/stage UIDs
            psde_list = meta.get("program_stage_data_elements", [])
            de_uid = config.get("de_uid", "")
            if de_uid and not config.get("stage_uid"):
                match = next((d for d in psde_list if d.get("id") == de_uid), None)
                if match:
                    config["prog_uid"]   = match.get("program", {}).get("id", "")
                    config["stage_uid"]  = match.get("stage",   {}).get("id", "")
                    config["prog_name"]  = match.get("program", {}).get("displayName", "")
                    config["stage_name"] = match.get("stage",   {}).get("displayName", "")

            ctx = build_context(meta)
            model = self._get_model()

            # Build a chart config compatible with generate_from_chart_configs
            chart_cfg = {
                "index":      1,
                "title":      config.get("title", "Chart"),
                "chart_type": config.get("template_label", "bar_monthly"),
                "metric_uid": config.get("de_uid", ""),
                "prog_uid":   config.get("prog_uid", ""),
                "stage_uid":  config.get("stage_uid", ""),
                "prog_name":  config.get("prog_name", ""),
                "stage_name": config.get("stage_name", ""),
                "notes":      config.get("ai_desc", ""),
            }

            url = self.url_entry.text().strip()
            analytics_params = {"base_url": url}

            html = generate_from_chart_configs(
                [chart_cfg], ctx,
                context_hint=config.get("ai_desc", ""),
                analytics_params=analytics_params,
                api_key=api_key, model=model)

            # Save to debug folder
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_dir = Path(__file__).parent.parent / "debug"
            debug_dir.mkdir(exist_ok=True)
            out_path = debug_dir / f"{ts}_ai_card.html"
            out_path.write_text(html, encoding="utf-8")

            config["mode"] = "ai"
            config["html_path"] = str(out_path)

            self._sig_call_main.emit(lambda: self._on_ai_generate_done(config, out_path))

        except Exception as exc:
            import traceback; traceback.print_exc()
            exc_msg = str(exc)
            self._sig_call_main.emit(lambda: self._on_ai_generate_fail(exc_msg))

    def _on_ai_generate_done(self, config: dict, html_path):
        self._stop_progress()
        self._dashboard_builder.add_card(config)
        self._set_status(f"AI chart generated — '{config.get('title', '')}'. Added to dashboard.")
        import webbrowser
        webbrowser.open(html_path.as_uri() if hasattr(html_path, "as_uri") else str(html_path))

    def _on_ai_generate_fail(self, msg: str):
        self._stop_progress()
        self._set_status(f"AI generate failed: {msg}", error=True)

    def _on_export(self, cards: list[dict], filters: dict | None = None,
                   custom_css: str = ""):
        """Export all dashboard cards to a full HTML file and open in browser."""
        if not cards:
            self._set_status("No cards to export.", error=True)
            return
        import webbrowser, datetime
        from pathlib import Path
        from charts.fixed_templates import assemble_dashboard

        # Only pre-rendered AI cards (mode=ai WITH an html_path) open separately;
        # AI-chat cards are normal fixed-template configs and get assembled like the rest.
        fixed    = [c for c in cards if not (c.get("mode") == "ai" and c.get("html_path"))]
        ai_paths = [c.get("html_path") for c in cards if c.get("mode") == "ai" and c.get("html_path")]

        title = "Dashboard"
        html = assemble_dashboard(fixed, title=title, filters=filters, custom_css=custom_css)

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = Path(__file__).parent.parent / "debug"
        debug_dir.mkdir(exist_ok=True)
        out_path = debug_dir / f"{ts}_dashboard.html"
        out_path.write_text(html, encoding="utf-8")

        webbrowser.open(out_path.as_uri())
        self._set_status(f"Dashboard exported → {out_path.name}")
        if ai_paths:
            self._set_status(
                f"Fixed cards exported. AI cards ({len(ai_paths)}) open separately.")
            for p in ai_paths:
                webbrowser.open(Path(p).as_uri())

    def _on_deploy_dashboard(self, report_name: str, cards: list[dict], filters: dict | None = None,
                             custom_css: str = ""):
        """Assemble dashboard HTML and deploy to DHIS2 as an HTML report object."""
        if not self._client:
            self._set_status("Connect to DHIS2 first.", error=True)
            return
        if not cards:
            self._set_status("No cards to deploy.", error=True)
            return

        import datetime
        from pathlib import Path
        from charts.fixed_templates import assemble_dashboard
        from llm.html_utils import fix_cdn_links

        fixed = [c for c in cards if not (c.get("mode") == "ai" and c.get("html_path"))]
        html = assemble_dashboard(fixed, title=report_name, filters=filters, custom_css=custom_css)
        html = fix_cdn_links(html)

        self._set_status("Deploying to DHIS2…")
        self._start_progress()
        threading.Thread(
            target=self._deploy_worker,
            args=(report_name, html),
            daemon=True).start()


# ── Stub classes to prevent AttributeError in legacy callback chain ──────────

class _ReportViewStub:
    """Minimal stub so methods that call self.report_view.X() don't crash."""
    _html: str = ""
    _edit_cb = None

    def get_html(self) -> str:
        return self._html

    def show(self, html: str):
        self._html = html

    def clear(self):
        self._html = ""

    def get_report_name(self) -> str:
        return ""

    def focus_report_name(self):
        pass

    def set_edit_callback(self, cb):
        self._edit_cb = cb


class _ChatPanelStub:
    """Minimal stub for chat_panel references."""
    _messages: list = []

    def get_messages(self) -> list:
        return list(self._messages)

    def set_generating(self, state: bool):
        pass

    def add_system_note(self, text: str):
        pass

    def add_assistant_message(self, text: str):
        pass

    def add_welcome_message(self, text: str):
        pass

    def set_hint(self, text: str):
        pass

    def clear(self):
        self._messages = []


class _QuickFormStub:
    """Minimal stub for quick_form references."""

    def get_scope(self) -> tuple:
        return ("", "")

    def get_analytics_params(self) -> dict:
        return {}

    def get_state(self) -> dict:
        return {}

    def set_metadata(self, metadata: dict):
        pass

    def restore_state(self, state: dict):
        pass

    def reset(self):
        pass

    def show(self):
        pass

    def hide(self):
        pass

    def winfo_ismapped(self) -> bool:
        return False

    def grid_remove(self):
        pass

    def grid(self):
        pass

    def _on_generate_click(self):
        pass


class _TabsStub:
    """Minimal stub for self.tabs.set() calls."""

    def set(self, value: str):
        pass
