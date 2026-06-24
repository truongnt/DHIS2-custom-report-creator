import copy
import customtkinter as ctk
import tkinter.messagebox as msgbox
import threading
import os
from dotenv import load_dotenv

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


class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DHIS2 Auto Report")
        self.after(0, lambda: self.state("zoomed"))  # maximize on startup
        self.minsize(1024, 640)

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

        self._build_layout()
        self._lock_ui()          # locked until DHIS2 connect succeeds
        self._load_saved_credentials()

    def _lock_ui(self):
        """No-op — nav buttons handle access control."""
        pass

    def _unlock_ui(self):
        """Enable Chart Editor and Dashboard nav buttons after connect."""
        for key in ("chart_editor", "dashboard"):
            if key in self._nav_btns:
                self._nav_btns[key].configure(state="normal")

    def _invalidate_ctx_caches(self):
        """Clear cached contexts — call when metadata or pinned items change."""
        self._full_ctx    = None
        self._summary_ctx = None
        self._scoped_context = None

    # ─── Layout ──────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._active_panel: str = "config"
        self._build_navbar()
        self._build_content()

    # ─── Left navigation bar ─────────────────────────────────────────────────

    def _build_navbar(self):
        nav = ctk.CTkFrame(self, width=160, corner_radius=0, fg_color=SIDEBAR_BG)
        nav.grid(row=0, column=0, sticky="nsew")
        nav.grid_propagate(False)
        nav.grid_columnconfigure(0, weight=1)
        nav.grid_rowconfigure(10, weight=1)   # spacer pushes footer down
        self._navbar = nav

        # App title
        ctk.CTkLabel(nav, text="DHIS2\nAuto Report",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=SIDEBAR_FG, justify="center").grid(
            row=0, column=0, padx=12, pady=(16, 10), sticky="ew")

        ctk.CTkFrame(nav, height=1, fg_color="#2a4a6a").grid(
            row=1, column=0, sticky="ew", padx=12, pady=(0, 6))

        # Nav items
        NAV_ITEMS = [
            ("config",       "⚙",  "Login & Config"),
            ("chart_editor", "📊", "Viz Builder"),
            ("dashboard",    "🗂", "Dashboard"),
        ]
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        for i, (key, icon, label) in enumerate(NAV_ITEMS):
            btn = ctk.CTkButton(
                nav, text=f"  {icon}  {label}",
                height=42, anchor="w",
                fg_color="transparent",
                hover_color="#253d52",
                text_color="#8aa3b8",
                font=ctk.CTkFont(size=12),
                corner_radius=6,
                command=lambda k=key: self._show_panel(k))
            btn.grid(row=i + 2, column=0, padx=8, pady=2, sticky="ew")
            self._nav_btns[key] = btn

        # Disable builder panels until connected
        self._nav_btns["chart_editor"].configure(state="disabled")
        self._nav_btns["dashboard"].configure(state="disabled")

        # Version footer
        ctk.CTkLabel(nav, text="v0.1.0 — CHAI Laos",
                     text_color="#4a6278",
                     font=ctk.CTkFont(size=9)).grid(
            row=11, column=0, padx=14, pady=(0, 12), sticky="sw")

    def _show_panel(self, name: str):
        self._config_panel.grid_remove()
        self._chart_editor.grid_remove()
        self._dashboard_builder.grid_remove()

        if name == "config":
            self._config_panel.grid()
        elif name == "chart_editor":
            self._chart_editor.grid()
        elif name == "dashboard":
            self._dashboard_builder.grid()
            self._dashboard_builder.refresh_library()

        self._active_panel = name
        for key, btn in self._nav_btns.items():
            if key == name:
                btn.configure(fg_color=DHIS2_BLUE, text_color="white",
                               hover_color="#155a8a")
            else:
                btn.configure(fg_color="transparent", text_color="#8aa3b8",
                               hover_color="#253d52")

    # ─── Content area ─────────────────────────────────────────────────────────

    def _build_content(self):
        content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        self._main_frame = content   # kept for any overlay refs

        # ── Config panel ──────────────────────────────────────────────────────
        self._config_panel = ctk.CTkFrame(
            content, corner_radius=0, fg_color="#f7f9fc")
        self._config_panel.grid(row=0, column=0, sticky="nsew")
        self._config_panel.grid_rowconfigure(0, weight=1)
        self._config_panel.grid_columnconfigure(0, weight=1)
        self._build_config_content(self._config_panel)

        # ── Chart Editor ──────────────────────────────────────────────────────
        self._chart_editor = ChartEditorPanel(
            content,
            callbacks={
                "on_chart_saved":         self._on_chart_saved,
                "on_add_to_dashboard":    self._on_add_to_dashboard,
                "on_generate_ai":         self._on_ai_generate,
                "on_switch_to_dashboard": lambda: self._show_panel("dashboard"),
                "get_api_key": lambda: self.apikey_entry.get().strip() or self._api_key,
                "get_model":   self._get_model,
            })
        self._chart_editor.grid(row=0, column=0, sticky="nsew")
        self._chart_editor.grid_remove()
        self._viz_panel = self._chart_editor   # alias for load_metadata

        # ── Dashboard Builder ─────────────────────────────────────────────────
        self._dashboard_builder = DashboardBuilderPanel(
            content,
            callbacks={
                "on_export":           self._on_export,
                "on_deploy":           self._on_deploy_dashboard,
                "on_switch_to_editor": lambda: self._show_panel("chart_editor"),
            })
        self._dashboard_builder.grid(row=0, column=0, sticky="nsew")
        self._dashboard_builder.grid_remove()
        self._dashboard_panel = self._dashboard_builder  # alias

        self._build_statusbar(content)
        # Highlight default panel
        self._show_panel("config")

    def _build_config_content(self, parent):
        """Config panel content — same as old sidebar but in full content area."""
        cf_outer = ctk.CTkScrollableFrame(
            parent, fg_color=SIDEBAR_BG, corner_radius=0,
            scrollbar_button_color="#2a4a6a",
            scrollbar_button_hover_color="#3a5a7a")
        cf_outer.grid(row=0, column=0, sticky="nsew")
        cf_outer.grid_columnconfigure(0, weight=1)
        cf = cf_outer

        # ── DHIS2 Connection section ──────────────────────────────────────────
        self._sb_section(cf, "DHIS2 Connection", row=0)

        # Saved profiles row
        prof_row = ctk.CTkFrame(cf, fg_color="transparent")
        prof_row.grid(row=1, column=0, padx=16, pady=(2, 4), sticky="ew")
        prof_row.grid_columnconfigure(0, weight=1)

        self.profile_var = ctk.StringVar(value="— Saved profiles —")
        self.profile_menu = ctk.CTkOptionMenu(
            prof_row, variable=self.profile_var,
            values=["— Saved profiles —"],
            height=28, font=ctk.CTkFont(size=11),
            fg_color="#253d52", button_color="#2a4a6a",
            button_hover_color="#1a3a5a",
            command=self._on_profile_selected)
        self.profile_menu.grid(row=0, column=0, sticky="ew")

        self.del_profile_btn = ctk.CTkButton(
            prof_row, text="✕", width=28, height=28,
            fg_color="#3a2020", hover_color="#5a2020",
            font=ctk.CTkFont(size=11),
            command=self._on_delete_profile)
        self.del_profile_btn.grid(row=0, column=1, padx=(4, 0))
        self._set_tooltip(self.del_profile_btn, "Delete selected profile")

        # ── Login fields (collapsible) ────────────────────────────────────────
        self._login_frame = ctk.CTkFrame(cf, fg_color="transparent")
        self._login_frame.grid(row=2, column=0, sticky="ew")
        self._login_frame.grid_columnconfigure(0, weight=1)
        lf = self._login_frame

        ctk.CTkLabel(lf, text="Server URL", text_color=SIDEBAR_FG,
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=16, sticky="w")
        self.url_entry = ctk.CTkEntry(lf, placeholder_text="https://hmis.example.org",
                                      height=32)
        self.url_entry.grid(row=1, column=0, padx=16, pady=(2, 6), sticky="ew")

        ctk.CTkLabel(lf, text="Username", text_color=SIDEBAR_FG,
                     font=ctk.CTkFont(size=12)).grid(row=2, column=0, padx=16, sticky="w")
        self.user_entry = ctk.CTkEntry(lf, placeholder_text="admin", height=32)
        self.user_entry.grid(row=3, column=0, padx=16, pady=(2, 6), sticky="ew")

        ctk.CTkLabel(lf, text="Password", text_color=SIDEBAR_FG,
                     font=ctk.CTkFont(size=12)).grid(row=4, column=0, padx=16, sticky="w")
        self.pass_entry = ctk.CTkEntry(lf, placeholder_text="••••••••",
                                       show="*", height=32)
        self.pass_entry.grid(row=5, column=0, padx=16, pady=(2, 6), sticky="ew")

        btn_row = ctk.CTkFrame(lf, fg_color="transparent")
        btn_row.grid(row=6, column=0, padx=16, pady=(0, 6), sticky="w")

        self.connect_btn = ctk.CTkButton(
            btn_row, text="Connect", width=140, height=34,
            fg_color=DHIS2_BLUE, hover_color="#155a8a",
            command=self._on_connect)
        self.connect_btn.pack(side="left")

        self.save_profile_btn = ctk.CTkButton(
            btn_row, text="💾", width=34, height=34,
            fg_color="#1a5a2a", hover_color="#145020",
            font=ctk.CTkFont(size=14),
            command=self._on_save_profile)
        self.save_profile_btn.pack(side="left", padx=(4, 0))
        self._set_tooltip(self.save_profile_btn, "Save credentials to Windows Credential Manager")

        self.refresh_btn = ctk.CTkButton(
            btn_row, text="↻", width=34, height=34,
            fg_color="#2a4a6a", hover_color="#1a3a5a",
            font=ctk.CTkFont(size=16),
            command=self._on_refresh_metadata)
        self.refresh_btn.pack(side="left", padx=(4, 0))
        self._set_tooltip(self.refresh_btn, "Force re-fetch metadata from server")

        # ── Post-connect widgets ──────────────────────────────────────────────
        self.change_conn_btn = ctk.CTkButton(
            cf, text="↺ Change connection", height=28,
            fg_color="transparent", border_width=1, border_color="#4a6278",
            text_color="#8aa3b8", hover_color="#253d52",
            font=ctk.CTkFont(size=11),
            command=self._on_change_connection)
        self.change_conn_btn.grid(row=3, column=0, padx=16, pady=(0, 4), sticky="ew")
        self.change_conn_btn.grid_remove()

        self.conn_status = ctk.CTkLabel(cf, text="● Not connected",
                                        text_color="#8aa3b8",
                                        font=ctk.CTkFont(size=11))
        self.conn_status.grid(row=4, column=0, padx=16, pady=(0, 2), sticky="w")

        self.cache_lbl = ctk.CTkLabel(cf, text="", text_color="#4a6278",
                                       font=ctk.CTkFont(size=10))
        self.cache_lbl.grid(row=5, column=0, padx=16, pady=(0, 4), sticky="w")

        self.filter_btn = ctk.CTkButton(
            cf, text="⚙ Filters & Load Metadata",
            height=34, fg_color="#2a4a6a", hover_color="#1a3a5a",
            state="disabled", command=self._on_open_filter_config)
        self.filter_btn.grid(row=6, column=0, padx=16, pady=(0, 2), sticky="ew")

        self.filter_summary_lbl = ctk.CTkLabel(
            cf, text="", text_color="#f39c12",
            font=ctk.CTkFont(size=10), wraplength=240, justify="left")
        self.filter_summary_lbl.grid(row=7, column=0, padx=16, pady=(0, 8), sticky="w")

        # ── Anthropic API Key ─────────────────────────────────────────────────
        self._sb_section(cf, "Anthropic API Key", row=8)

        apikey_row = ctk.CTkFrame(cf, fg_color="transparent")
        apikey_row.grid(row=9, column=0, padx=16, pady=(4, 0), sticky="ew")
        apikey_row.grid_columnconfigure(0, weight=1)

        self.apikey_entry = ctk.CTkEntry(apikey_row, placeholder_text="sk-ant-…",
                                          show="*", height=32)
        self.apikey_entry.grid(row=0, column=0, sticky="ew")
        if self._api_key:
            self.apikey_entry.insert(0, self._api_key)

        self.save_apikey_btn = ctk.CTkButton(
            apikey_row, text="💾", width=34, height=32,
            fg_color="#1a5a2a", hover_color="#145020",
            font=ctk.CTkFont(size=14),
            command=self._on_save_api_key)
        self.save_apikey_btn.grid(row=0, column=1, padx=(4, 0))
        self._set_tooltip(self.save_apikey_btn, "Save API key to Windows Credential Manager")

        # ── AI Model ─────────────────────────────────────────────────────────
        self._sb_section(cf, "AI Model", row=10)

        self._MODEL_OPTIONS = {
            "Haiku 4.5  (fast, cheap)":  "claude-haiku-4-5-20251001",
            "Sonnet 4.6  (balanced)":    "claude-sonnet-4-6",
            "Opus 4.7  (best quality)":  "claude-opus-4-7",
        }
        self._model_var = ctk.StringVar(value=list(self._MODEL_OPTIONS.keys())[0])
        ctk.CTkOptionMenu(
            cf, variable=self._model_var,
            values=list(self._MODEL_OPTIONS.keys()),
            height=30,
            fg_color="white", button_color="#b8cfe8", button_hover_color="#9abcd8",
            text_color="#1e2d3d", dropdown_fg_color="white", dropdown_text_color="#1e2d3d",
            font=ctk.CTkFont(size=11),
        ).grid(row=11, column=0, padx=16, pady=(2, 0), sticky="ew")

        # Footer
        ctk.CTkLabel(cf, text="v0.1.0 — CHAI Laos",
                     text_color="#4a6278",
                     font=ctk.CTkFont(size=10)).grid(
            row=12, column=0, padx=16, pady=(16, 12), sticky="w")

    def _sb_section(self, parent, label: str, row: int):
        ctk.CTkLabel(parent, text=label,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#8aa3b8").grid(
            row=row, column=0, padx=20, pady=(8, 2), sticky="w")

    def _get_model(self) -> str:
        return self._MODEL_OPTIONS.get(self._model_var.get(), "claude-haiku-4-5-20251001")

    def _set_tooltip(self, widget, text: str):
        # Simple hover tooltip via label — lightweight, no extra lib needed
        tip = None
        def show(e):
            nonlocal tip
            tip = ctk.CTkLabel(self, text=text, fg_color="#333",
                                text_color="white", corner_radius=4,
                                font=ctk.CTkFont(size=10))
            tip.place(x=e.x_root - self.winfo_rootx() + 12,
                      y=e.y_root - self.winfo_rooty() + 12)
        def hide(e):
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None
        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)


    def _build_statusbar(self, parent):
        sb = ctk.CTkFrame(parent, height=28, corner_radius=0, fg_color="#eef2f7")
        sb.grid(row=1, column=0, sticky="ew")  # content frame only has col 0
        sb.grid_propagate(False)
        self.status_label = ctk.CTkLabel(sb, text="Ready",
                                          font=ctk.CTkFont(size=11),
                                          text_color="#6b8299")
        self.status_label.pack(side="left", padx=16)
        self.progress = ctk.CTkProgressBar(sb, width=160, height=10,
                                            mode="indeterminate")
        self.progress.pack(side="right", padx=16, pady=8)
        self.progress.stop()
        self.progress.set(0)

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
                self.apikey_entry.delete(0, "end")
                self.apikey_entry.insert(0, saved_key)

        # Auto-connect using first saved profile
        if self._profiles:
            p = self._profiles[0]
            self.profile_var.set(profile_label(p))
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, p["url"])
            self.user_entry.delete(0, "end")
            self.user_entry.insert(0, p["username"])
            pwd = load_password(p["url"], p["username"])
            self.pass_entry.delete(0, "end")
            if pwd:
                self.pass_entry.insert(0, pwd)
                self.after(200, self._on_connect)

    def _refresh_profile_menu(self):
        from config.credentials import profile_label
        labels = ["— Saved profiles —"] + [profile_label(p) for p in self._profiles]
        self.profile_menu.configure(values=labels)
        self.profile_var.set(labels[0])

    def _on_profile_selected(self, label: str):
        if label == "— Saved profiles —":
            return
        from config.credentials import load_profiles, load_password, profile_label
        self._profiles = load_profiles()
        for p in self._profiles:
            if profile_label(p) == label:
                # Ensure entries are editable before filling
                for w in (self.url_entry, self.user_entry, self.pass_entry):
                    w.configure(state="normal")
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, p["url"])
                self.user_entry.delete(0, "end")
                self.user_entry.insert(0, p["username"])
                pwd = load_password(p["url"], p["username"])
                self.pass_entry.delete(0, "end")
                if pwd:
                    self.pass_entry.insert(0, pwd)
                # Reset connect button in case it shows "✓ Connected"
                self.connect_btn.configure(
                    state="normal", text="Connect",
                    fg_color=DHIS2_BLUE, hover_color="#155a8a")
                self.change_conn_btn.grid_remove()
                # Auto-connect after filling credentials
                self.after(100, self._on_connect)
                break

    def _on_save_profile(self):
        url  = self.url_entry.get().strip()
        user = self.user_entry.get().strip()
        pwd  = self.pass_entry.get()
        if not (url and user):
            self._set_status("Enter URL and username before saving.", error=True)
            return
        from config.credentials import save_profile, load_profiles
        save_profile(url, user, pwd)
        self._profiles = load_profiles()
        self._refresh_profile_menu()
        self._set_status(f"Profile saved: {user} @ {url}")

    def _on_delete_profile(self):
        label = self.profile_var.get()
        if label == "— Saved profiles —":
            return
        from config.credentials import delete_profile, load_profiles, profile_label
        self._profiles = load_profiles()
        for p in self._profiles:
            if profile_label(p) == label:
                if msgbox.askyesno("Delete profile",
                                   f"Delete saved profile:\n{label}\n\n"
                                   "Password will be removed from Windows Credential Manager."):
                    delete_profile(p["url"], p["username"])
                    self._profiles = load_profiles()
                    self._refresh_profile_menu()
                    self._set_status("Profile deleted.")
                return

    def _on_save_api_key(self):
        key = self.apikey_entry.get().strip()
        if not key:
            self._set_status("Enter API key first.", error=True)
            return
        from config.credentials import save_api_key
        save_api_key(key)
        self._set_status("Anthropic API key saved to Windows Credential Manager.")

    # ─── Connect (cache-first) ────────────────────────────────────────────────

    def _on_connect(self):
        url  = self.url_entry.get().strip()
        user = self.user_entry.get().strip()
        pwd  = self.pass_entry.get()
        if not (url and user and pwd):
            self._set_status("Fill in URL, username, and password.", error=True)
            return

        self.connect_btn.configure(state="disabled", text="Connecting…")
        self._set_status("Testing connection…")
        self._start_progress()
        threading.Thread(target=self._connect_worker,
                         args=(url, user, pwd, False), daemon=True).start()

    def _on_refresh_metadata(self):
        url  = self.url_entry.get().strip()
        user = self.user_entry.get().strip()
        pwd  = self.pass_entry.get()
        if not (url and user and pwd):
            self._set_status("Fill in connection details first.", error=True)
            return
        self.refresh_btn.configure(state="disabled")
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
            self.after(0, self._set_status, f"Connected as {display}. Loading filter options…")
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
                self.after(0, self._on_connect_done, display, count, cached_at, True)
                return

            # No cache — fetch with current filter config
            self.after(0, self._set_status, "Fetching metadata…")
            metadata = fetch_all(client, self._filter_cfg)
            cache_save(url, metadata)
            self._metadata   = metadata
            self._filter_cfg = metadata.get("_filter_config", {})
            self._invalidate_ctx_caches()

            count = (len(metadata.get("indicators", [])) +
                     len(metadata.get("program_indicators", [])))
            self.after(0, self._on_connect_done, display, count, None, False)

        except Exception as exc:
            self.after(0, self._on_connect_fail, str(exc))

    def _on_connect_done(self, display: str, count: int,
                          cached_at: str | None, from_cache: bool = False):
        self._stop_progress()
        # Show connected state — disable login fields until "Change" is clicked
        self.connect_btn.configure(
            state="disabled", text="✓ Connected",
            fg_color="#27ae60", hover_color="#1e8449")
        self._login_frame.grid_remove()   # hide URL/user/pass fields
        self.change_conn_btn.grid()
        self.refresh_btn.configure(state="normal")
        self.filter_btn.configure(state="normal")
        n_de   = len((self._metadata or {}).get("data_elements", []))
        n_prog = len((self._metadata or {}).get("programs", []))
        status_text = f"● {display}  ({n_de} DEs"
        if n_prog:
            status_text += f" | {n_prog} programs"
        status_text += ")"
        self.conn_status.configure(text=status_text, text_color="#2ecc71")
        if from_cache and cached_at:
            self.cache_lbl.configure(text=f"Cached — {cached_at}", text_color="#f39c12")
            self._set_status(f"Using cached metadata from {cached_at}. Press ↻ or reconfigure filters.")
        else:
            self.cache_lbl.configure(text="Metadata freshly loaded.", text_color="#27ae60")
            self._set_status(f"Ready — {n_de} data elements, {n_prog} programs loaded.")
        self._update_filter_summary()
        self._unlock_ui()   # enables Chart Editor + Dashboard nav buttons
        if self._metadata:
            self._viz_panel.load_metadata(self._metadata)
        # Auto-switch to Chart Editor after successful login
        self._show_panel("chart_editor")

    def _on_connect_fail(self, msg: str):
        self._stop_progress()
        self.connect_btn.configure(
            state="normal", text="Connect",
            fg_color=DHIS2_BLUE, hover_color="#155a8a")
        self.refresh_btn.configure(state="normal")
        self.conn_status.configure(text="● Connection failed", text_color="#e74c3c")
        self._set_status(f"Connection failed: {msg}", error=True)

    def _on_change_connection(self):
        """Switch to config panel so user can change connection."""
        self._show_panel("config")
        self._login_frame.grid()
        self.url_entry.configure(state="normal")
        self.user_entry.configure(state="normal")
        self.pass_entry.configure(state="normal")
        self.connect_btn.configure(
            state="normal", text="Connect",
            fg_color=DHIS2_BLUE, hover_color="#155a8a")
        self.change_conn_btn.grid_remove()

    # ─── Filter Config & Load Metadata ───────────────────────────────────────

    def _on_open_filter_config(self):
        if not self._client:
            self._set_status("Connect first.", error=True)
            return

        from ui.filter_config_dialog import FilterConfigDialog
        dlg = FilterConfigDialog(self,
                                  self._filter_options or {},
                                  self._filter_cfg)
        self.wait_window(dlg)

        if dlg.result is None:
            return  # cancelled

        self._filter_cfg = dlg.result
        self._update_filter_summary()
        self._set_status("Filter configured. Loading metadata…")
        self._start_progress()
        self.filter_btn.configure(state="disabled", text="Loading…")

        threading.Thread(target=self._load_metadata_worker, daemon=True).start()

    def _load_metadata_worker(self):
        try:
            from dhis2.metadata import fetch_all
            from dhis2.cache import save as cache_save, save_filter_cfg

            url      = self.url_entry.get().strip()
            metadata = fetch_all(self._client, self._filter_cfg)
            cache_save(url, metadata)
            save_filter_cfg(url, self._filter_cfg)   # persist filter separately
            self._metadata   = metadata
            self._filter_cfg = metadata.get("_filter_config", {})
            self._invalidate_ctx_caches()

            count = (len(metadata.get("indicators", [])) +
                     len(metadata.get("program_indicators", [])))
            self.after(0, self._on_metadata_loaded, count)
        except Exception as exc:
            import traceback; traceback.print_exc()
            self.after(0, self._on_metadata_load_fail, str(exc))

    def _on_metadata_loaded(self, count: int):
        self._stop_progress()
        self.filter_btn.configure(state="normal",
                                   text="⚙ Configure Filters & Load Metadata")
        self.cache_lbl.configure(text="Metadata freshly loaded.", text_color="#27ae60")
        self._update_filter_summary()
        n_de = len((self._metadata or {}).get("data_elements", []))
        self._set_status(f"Metadata loaded — {n_de} data elements.")
        if self._metadata:
            self._viz_panel.load_metadata(self._metadata)

    def _on_metadata_load_fail(self, msg: str):
        self._stop_progress()
        self.filter_btn.configure(state="normal",
                                   text="⚙ Configure Filters & Load Metadata")
        self._set_status(f"Metadata load failed: {msg}", error=True)

    def _update_filter_summary(self):
        cfg = self._filter_cfg
        if not cfg:
            self.filter_summary_lbl.configure(text="")
            return
        parts = []
        if cfg.get("indicator_group_ids"):
            parts.append(f"{len(cfg['indicator_group_ids'])} ind.groups")
        if cfg.get("de_group_ids"):
            parts.append(f"{len(cfg['de_group_ids'])} DE groups")
        if cfg.get("program_ids"):
            parts.append(f"{len(cfg['program_ids'])} programs")
        kws = [v for k, v in cfg.items() if k.endswith("_name") and v]
        if kws:
            parts.append(f"keywords: {', '.join(kws)}")
        if parts:
            self.filter_summary_lbl.configure(
                text="Filters: " + " | ".join(parts),
                text_color="#f39c12")
        else:
            self.filter_summary_lbl.configure(
                text="No filters — all metadata loaded",
                text_color="#8aa3b8")

    # ─── Metadata Selector ───────────────────────────────────────────────────

    def _on_open_selector(self):
        if not self._metadata:
            self._set_status("Connect to DHIS2 first to load metadata.", error=True)
            return

        from dhis2.usage_tracker import get_counts
        url    = self.url_entry.get().strip()
        counts = get_counts(url)

        from ui.metadata_selector import MetadataSelector
        sel = MetadataSelector(self, self._metadata, counts, self._pinned)
        self.wait_window(sel)

        if sel.result is not None:
            self._pinned = sel.result
            self._invalidate_ctx_caches()
            self._refresh_pin_count()

    def _refresh_pin_count(self):
        if not hasattr(self, "pin_count_lbl"):
            return
        total = sum(len(v) for v in self._pinned.values())
        if total == 0:
            self.pin_count_lbl.configure(text="No items pinned", text_color="#8aa3b8")
        else:
            parts = []
            labels = {"data_elements": "DE", "program_stage_data_elements": "stage DE", "tracked_entity_attributes": "TEA"}
            for k, short in labels.items():
                n = len(self._pinned.get(k, []))
                if n:
                    parts.append(f"{n} {short}")
            self.pin_count_lbl.configure(
                text="★ Pinned: " + ", ".join(parts),
                text_color=DHIS2_BLUE)

    # ─── Dashboard Builder ───────────────────────────────────────────────────

    def _on_open_dashboard_builder(self):
        if not self._metadata:
            self._set_status("Connect to DHIS2 and load metadata first.", error=True)
            return
        from ui.dashboard_builder import DashboardBuilder
        existing = self._dashboard_layout  # pass existing layout to edit
        dlg = DashboardBuilder(self, self._metadata, self._pinned, existing)
        self.wait_window(dlg)
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
        self.wait_window(dlg)
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
            if msgbox.askyesno(
                "Regenerate",
                f"{n_changed} card(s) changed.\n\n"
                f"Yes  → Regenerate only changed card(s) — faster\n"
                f"No   → Regenerate entire dashboard",
            ):
                self._regenerate_changed_cards(new_layout, changed_ids)
                return

        # Full regeneration
        self._on_generate()

    def _regenerate_changed_cards(self, new_layout: list[dict], changed_ids: set[str]):
        """Regenerate only the changed cards and splice them into the existing HTML."""
        api_key = self.apikey_entry.get().strip()
        if not api_key:
            self._set_status("Enter Anthropic API key.", error=True)
            return
        current_html = self.report_view.get_html()
        if not current_html:
            return

        n = len(changed_ids)
        self.generate_btn.configure(state="disabled", text="Regenerating…")
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

            url    = self.url_entry.get().strip()
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
                self.after(0, self._set_status, f"Regenerating card {chart_idx}…")
                fragment = regenerate_single_card(card, chart_idx, context, bs,
                                                  api_key=api_key, model=model)
                try:
                    html = splice_card_in_html(html, cid, fragment)
                except ValueError:
                    # Markers not found — fall back to full regen silently
                    self.after(0, self._set_status,
                               "Edit markers missing — regenerating full dashboard…")
                    self.after(0, self._on_generate)
                    return

            self.after(0, self._on_regen_cards_done, html, new_layout)

        except Exception as exc:
            self.after(0, self._on_generate_fail, str(exc))

    def _on_regen_cards_done(self, html: str, new_layout: list[dict]):
        self._stop_progress()
        self.generate_btn.configure(state="normal", text="Generate from chat ▶")
        self.report_view.show(html)
        self._last_generated_layout = copy.deepcopy(new_layout)
        self.report_view.set_edit_callback(self._on_edit_dashboard)
        self._set_status("Card(s) regenerated. Preview or Deploy to DHIS2.")

    # ─── Chart Library (single chart fallback) ──────────────────────────────

    def _on_open_chart_library(self):
        from ui.chart_library import ChartLibrary
        current = None
        if self._dashboard_layout and len(self._dashboard_layout) == 1:
            current = self._dashboard_layout[0].get("template_id")
        lib = ChartLibrary(self, current)
        self.wait_window(lib)
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
        api_key = self.apikey_entry.get().strip()
        if not api_key:
            self._set_status("Enter your Anthropic API key.", error=True)
            return

        messages = self.chat_panel.get_messages()
        if not messages:
            # Chat empty — delegate to form if it's visible
            if self.quick_form.winfo_ismapped():
                self.quick_form._on_generate_click()
            else:
                self._set_status("Enter a request in chat before generating.", error=True)
            return

        self.generate_btn.configure(state="disabled", text="Generating…")
        self._set_status("Building context…")
        self._start_progress()
        self.report_view.clear()
        self.chat_panel.set_generating(True)
        self.quick_form.grid_remove()

        model = self._get_model()
        scope = self.quick_form.get_scope()
        threading.Thread(target=self._generate_worker, args=(api_key, model, scope), daemon=True).start()

    def _generate_worker(self, api_key: str, model: str = "claude-haiku-4-5-20251001",
                         scope: tuple[str, str] = ("", "")):
        try:
            from llm.context_builder import build_context, filter_metadata_by_scope
            from dhis2.usage_tracker import get_counts
            url    = self.url_entry.get().strip()
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
                    self.after(0, self._set_status, "Loading option sets…")
                    enrich_with_option_sets(self._client, scoped_meta)
                base_ctx = build_context(
                    scoped_meta, url, pinned=merged_pinned, usage_counts=counts)
            else:
                base_ctx = self._full_ctx

            # LLM filter — further compress to only what the conversation needs
            from llm.chat_generator import filter_metadata_context
            self.after(0, self._set_status, "Filtering metadata to report scope…")
            self._scoped_context = filter_metadata_context(messages, base_ctx, api_key)

            context = self._scoped_context

            # Extract prompt string for layout-based modes (join all user messages)
            prompt = " ".join(m["content"] for m in messages if m["role"] == "user")

            layout = self._dashboard_layout
            if layout and len(layout) > 1:
                from llm.dashboard_generator import generate_dashboard_html
                n = len(layout)
                self.after(0, self._set_status, f"Calling Claude to build {n}-chart dashboard…")
                html = generate_dashboard_html(prompt, layout, context, api_key=api_key, model=model)

            elif layout and len(layout) == 1:
                from llm.report_generator import generate_report_html
                from charts.templates import get_by_id
                card = layout[0]
                tmpl = get_by_id(card.get("template_id", ""))
                if tmpl:
                    self.after(0, self._set_status, f"Filling template '{tmpl['name']}' with Claude…")
                    html = generate_report_html(
                        prompt, context, api_key=api_key,
                        template_html=tmpl["html"], template_name=tmpl["name"],
                        model=model,
                    )
                else:
                    self.after(0, self._set_status, "Calling Claude to generate HTML…")
                    html = generate_report_html(prompt, context, api_key=api_key, model=model)

            else:
                from llm.chat_generator import generate_from_chat
                self.after(0, self._set_status, "Calling Claude to generate HTML from chat…")
                html = generate_from_chat(messages, context, api_key, model=model)

            self.after(0, self._on_generate_done, html)

        except Exception as exc:
            self.after(0, self._on_generate_fail, str(exc))

    def _on_generate_done(self, html: str):
        self._stop_progress()
        self.generate_btn.configure(state="normal", text="Generate from chat ▶")
        self.chat_panel.set_generating(False)
        self.report_view.show(html)
        self.tabs.set("📄 Preview")
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
        self.generate_btn.configure(state="normal", text="Generate from chat ▶")
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
            if not msgbox.askyesno(
                "Warning: broken CDN links detected",
                "The HTML still contains '_files/' references that could not be\n"
                "auto-fixed. Bootstrap or Chart.js may not load in DHIS2.\n\n"
                "Continue deploying anyway?",
            ):
                return

        self._set_status("Deploying to DHIS2…")
        self._start_progress()
        threading.Thread(target=self._deploy_worker, args=(name, html), daemon=True).start()

    def _deploy_worker(self, name: str, html: str):
        try:
            from dhis2.report_api import create_report, report_url
            from dhis2.usage_tracker import record_usage
            from llm.html_utils import fix_cdn_links

            html = fix_cdn_links(html)  # ensure CDN links are correct before deploying
            result = create_report(self._client, name, html)
            uid    = (result.get("response", {}).get("uid") or result.get("uid") or "")
            base   = self.url_entry.get().strip()
            url    = report_url(base, uid) if uid else base

            # Record usage for pinned indicators
            record_usage(base, self._pinned)

            self.after(0, self._on_deploy_done, name, uid, url)
        except Exception as exc:
            self.after(0, self._on_deploy_fail, str(exc))

    def _on_deploy_done(self, name: str, uid: str, url: str):
        self._stop_progress()
        self._set_status(f"Deployed: '{name}'  (UID: {uid})")
        # Refresh pin count label (usage counts updated)
        self._refresh_pin_count()
        import webbrowser
        if msgbox.askyesno("Deploy successful",
                           f"Report '{name}' created in DHIS2.\nUID: {uid}\n\nOpen in DHIS2 now?"):
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
        url = self.url_entry.get().strip()
        if url:
            try:
                from dhis2.de_preferences import load_form_state
                self.quick_form.restore_state(load_form_state(url))
            except Exception:
                pass
        self.quick_form.grid()
        self.generate_btn.configure(text="Generate Dashboard ▶")
        self.chat_panel.add_welcome_message(
            "Hello! Fill in the form below and click \"Build Request\" — "
            "or type directly in the chat.")

    def _on_form_generate(self, configs: list[dict],
                          scope: tuple, scope_text: str):
        """Called when user clicks 'Generate Dashboard' in the form panel."""
        api_key = self.apikey_entry.get().strip()
        if not api_key:
            self._set_status("Enter your Anthropic API key.", error=True)
            return
        if not self._metadata:
            self._set_status("Connect to DHIS2 and load metadata first.", error=True)
            return

        # Save form state
        url = self.url_entry.get().strip()
        if url:
            try:
                from dhis2.de_preferences import save_form_state
                save_form_state(url, self.quick_form.get_state())
            except Exception:
                pass

        analytics_params = self.quick_form.get_analytics_params()
        self.generate_btn.configure(state="disabled", text="Generating…")
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

            url    = self.url_entry.get().strip()
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
            # program_stage_data_elements is only fetched at startup when
            # program_ids is in the filter config. If the user selected a
            # program in the form that wasn't in the initial fetch, we need
            # to fetch its DEs now so the dropdown and analytics work.
            if prog_name and self._client and not scoped_meta.get("program_stage_data_elements"):
                prog_uid = next(
                    (p.get("id") for p in base_meta.get("programs", [])
                     if p.get("displayName") == prog_name), None)
                if prog_uid:
                    self.after(0, self._set_status, f"Loading data elements for {prog_name}…")
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
                        self.after(0, self.quick_form.set_metadata, base_meta)

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
            # Data stays in DHIS2; the generated HTML fetches it at runtime.
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

            self.after(0, self._set_status, "Calling Claude to build dashboard…")
            html = generate_from_chart_configs(
                configs, context,
                context_hint=scope_text,
                analytics_params=analytics_params,
                api_key=api_key, model=model)
            self.after(0, self._on_form_generate_done, html)

        except Exception as exc:
            self.after(0, self._on_form_generate_fail, str(exc))

    def _on_form_generate_fail(self, msg: str):
        self._stop_progress()
        self.generate_btn.configure(state="normal", text="Generate Dashboard ▶")
        self._set_status(f"Generation failed: {msg}", error=True)

    def _on_form_generate_done(self, html: str):
        self._stop_progress()
        self.generate_btn.configure(state="normal", text="Generate from chat ▶")
        self.quick_form.grid_remove()
        self.report_view.show(html)
        self.tabs.set("📄 Preview")
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
        api_key = self.apikey_entry.get().strip()
        current_html = self.report_view.get_html()

        if current_html:
            # Phase 2 — refine existing HTML
            if not api_key:
                self._set_status("Enter Anthropic API key to refine.", error=True)
                return
            self.tabs.set("💬 Chat")
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
                url    = self.url_entry.get().strip()
                counts = get_counts(url)
                merged = _merge_pinned(self._dashboard_layout, self._pinned)
                self._summary_ctx = build_summary_context(
                    self._metadata or {}, url, pinned=merged, usage_counts=counts)

            messages = self.chat_panel.get_messages()
            response = chat_plan(messages, self._summary_ctx, api_key, model=model)
            self.after(0, self._on_chat_plan_done, response)
        except Exception as exc:
            self.after(0, self._on_chat_fail, str(exc))

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
                url    = self.url_entry.get().strip()
                counts = get_counts(url)
                merged = _merge_pinned(self._dashboard_layout, self._pinned)
                context = build_context(self._metadata or {}, url, pinned=merged, usage_counts=counts)

            html = refine_from_chat(request, current_html, context, api_key, model=model)
            self.after(0, self._on_refine_done, html)
        except Exception as exc:
            self.after(0, self._on_chat_fail, str(exc))

    def _on_refine_done(self, html: str):
        self._stop_progress()
        self.chat_panel.set_generating(False)
        self.report_view.show(html)
        self.tabs.set("📄 Preview")
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
            msgbox.showinfo(
                "Verify DEs",
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

        url = self.url_entry.get().strip()

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

        msgbox.showinfo("Verify DEs in Report", "\n\n".join(sections))

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
        api_key = self.apikey_entry.get().strip() or self._api_key
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

            url = self.url_entry.get().strip()
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

            self.after(0, self._on_ai_generate_done, config, out_path)

        except Exception as exc:
            import traceback; traceback.print_exc()
            self.after(0, self._on_ai_generate_fail, str(exc))

    def _on_ai_generate_done(self, config: dict, html_path):
        self._stop_progress()
        self._dashboard_builder.add_card(config)
        self._set_status(f"AI chart generated — '{config.get('title', '')}'. Added to dashboard.")
        import webbrowser
        webbrowser.open(html_path.as_uri() if hasattr(html_path, "as_uri") else str(html_path))

    def _on_ai_generate_fail(self, msg: str):
        self._stop_progress()
        self._set_status(f"AI generate failed: {msg}", error=True)

    def _on_export(self, cards: list[dict]):
        """Export all dashboard cards to a full HTML file and open in browser."""
        if not cards:
            self._set_status("No cards to export.", error=True)
            return
        import webbrowser, datetime
        from pathlib import Path
        from charts.fixed_templates import assemble_dashboard

        fixed  = [c for c in cards if c.get("mode") != "ai"]
        ai_paths = [c.get("html_path") for c in cards if c.get("mode") == "ai" and c.get("html_path")]

        title = "Dashboard"
        html = assemble_dashboard(fixed, title=title)

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

    def _on_deploy_dashboard(self, report_name: str, cards: list[dict]):
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

        fixed = [c for c in cards if c.get("mode") != "ai"]
        html = assemble_dashboard(fixed, title=report_name)
        html = fix_cdn_links(html)

        self._set_status("Deploying to DHIS2…")
        self._start_progress()
        threading.Thread(
            target=self._deploy_worker,
            args=(report_name, html),
            daemon=True).start()

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, error: bool = False):
        color = "#e74c3c" if error else "#6b8299"
        self.status_label.configure(text=msg, text_color=color)

    def _start_progress(self):
        self.progress.configure(mode="indeterminate")
        self.progress.start()

    def _stop_progress(self):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(1)
