import copy
import customtkinter as ctk
import tkinter.messagebox as msgbox
import threading
import os
from dotenv import load_dotenv

from ui.report_view import ReportView
from ui.chat_panel import ChatPanel

load_dotenv()


def _merge_pinned(layout: list[dict] | None,
                  global_pinned: dict) -> dict:
    """Union all pinned UIDs from dashboard cards + global pin list."""
    merged: dict[str, list] = {
        "indicators": list(global_pinned.get("indicators", [])),
        "program_indicators": list(global_pinned.get("program_indicators", [])),
        "data_elements": list(global_pinned.get("data_elements", [])),
    }
    if not layout:
        return merged
    for card in layout:
        for key in ("indicators", "program_indicators", "data_elements"):
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
        self.geometry("1280x820")
        self.minsize(1024, 640)

        self._client           = None   # DHIS2Client once connected
        self._metadata         = None   # loaded metadata dict
        self._filter_options   = None   # {indicator_groups, de_groups, programs}
        self._filter_cfg: dict = {}     # current FilterConfig applied to last load
        self._pinned: dict[str, list[str]] = {
            "indicators": [], "program_indicators": [], "data_elements": []
        }
        self._dashboard_layout: list[dict] | None = None  # cards from DashboardBuilder
        self._last_generated_layout: list[dict] | None = None  # layout used for current HTML
        self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._profiles: list[dict] = []   # loaded from credentials store

        self._build_layout()
        self._load_saved_credentials()

    # ─── Layout ──────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=290, corner_radius=0, fg_color=SIDEBAR_BG)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_rowconfigure(17, weight=1)
        sb.grid_propagate(False)

        ctk.CTkLabel(sb, text="DHIS2\nAuto Report",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=SIDEBAR_FG).grid(
            row=0, column=0, padx=20, pady=(24, 14), sticky="w")

        # ── DHIS2 Connection ──
        self._sb_section(sb, "DHIS2 Connection", row=1)

        # Saved profiles row
        prof_row = ctk.CTkFrame(sb, fg_color="transparent")
        prof_row.grid(row=2, column=0, padx=20, pady=(2, 6), sticky="ew")
        prof_row.grid_columnconfigure(0, weight=1)

        self.profile_var = ctk.StringVar(value="— Saved profiles —")
        self.profile_menu = ctk.CTkOptionMenu(
            prof_row,
            variable=self.profile_var,
            values=["— Saved profiles —"],
            width=210, height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#253d52", button_color="#2a4a6a",
            button_hover_color="#1a3a5a",
            command=self._on_profile_selected,
        )
        self.profile_menu.grid(row=0, column=0, sticky="ew")

        self.del_profile_btn = ctk.CTkButton(
            prof_row, text="✕", width=28, height=28,
            fg_color="#3a2020", hover_color="#5a2020",
            font=ctk.CTkFont(size=11),
            command=self._on_delete_profile,
        )
        self.del_profile_btn.grid(row=0, column=1, padx=(4, 0))
        self._set_tooltip(self.del_profile_btn, "Delete selected profile")

        ctk.CTkLabel(sb, text="Server URL", text_color=SIDEBAR_FG,
                     font=ctk.CTkFont(size=12)).grid(row=3, column=0, padx=20, sticky="w")
        self.url_entry = ctk.CTkEntry(sb, placeholder_text="https://hmis.example.org",
                                      width=250, height=32)
        self.url_entry.grid(row=4, column=0, padx=20, pady=(2, 8), sticky="w")

        ctk.CTkLabel(sb, text="Username", text_color=SIDEBAR_FG,
                     font=ctk.CTkFont(size=12)).grid(row=5, column=0, padx=20, sticky="w")
        self.user_entry = ctk.CTkEntry(sb, placeholder_text="admin",
                                       width=250, height=32)
        self.user_entry.grid(row=6, column=0, padx=20, pady=(2, 8), sticky="w")

        ctk.CTkLabel(sb, text="Password", text_color=SIDEBAR_FG,
                     font=ctk.CTkFont(size=12)).grid(row=7, column=0, padx=20, sticky="w")
        self.pass_entry = ctk.CTkEntry(sb, placeholder_text="••••••••",
                                       show="*", width=250, height=32)
        self.pass_entry.grid(row=8, column=0, padx=20, pady=(2, 6), sticky="w")

        # Connect row: Connect + Refresh + Save
        btn_row = ctk.CTkFrame(sb, fg_color="transparent")
        btn_row.grid(row=9, column=0, padx=20, pady=(0, 4), sticky="w")

        self.connect_btn = ctk.CTkButton(
            btn_row, text="Connect", width=148, height=34,
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

        # Connection status
        self.conn_status = ctk.CTkLabel(sb, text="● Not connected",
                                        text_color="#8aa3b8",
                                        font=ctk.CTkFont(size=11))
        self.conn_status.grid(row=10, column=0, padx=20, pady=(0, 2), sticky="w")

        # Cache age label
        self.cache_lbl = ctk.CTkLabel(sb, text="",
                                       text_color="#4a6278",
                                       font=ctk.CTkFont(size=10))
        self.cache_lbl.grid(row=11, column=0, padx=20, pady=(0, 6), sticky="w")

        # Filter + Load Metadata button (enabled after connect)
        self.filter_btn = ctk.CTkButton(
            sb, text="⚙ Configure Filters & Load Metadata",
            width=250, height=34,
            fg_color="#2a4a6a", hover_color="#1a3a5a",
            state="disabled",
            command=self._on_open_filter_config)
        self.filter_btn.grid(row=12, column=0, padx=20, pady=(0, 2), sticky="w")

        self.filter_summary_lbl = ctk.CTkLabel(
            sb, text="", text_color="#f39c12",
            font=ctk.CTkFont(size=10), wraplength=240, justify="left")
        self.filter_summary_lbl.grid(row=13, column=0, padx=20, pady=(0, 10), sticky="w")

        # ── Anthropic API Key ──
        self._sb_section(sb, "Anthropic API Key", row=14)

        apikey_row = ctk.CTkFrame(sb, fg_color="transparent")
        apikey_row.grid(row=15, column=0, padx=20, pady=(4, 0), sticky="w")

        self.apikey_entry = ctk.CTkEntry(apikey_row, placeholder_text="sk-ant-…",
                                          show="*", width=210, height=32)
        self.apikey_entry.pack(side="left")
        if self._api_key:
            self.apikey_entry.insert(0, self._api_key)

        self.save_apikey_btn = ctk.CTkButton(
            apikey_row, text="💾", width=34, height=32,
            fg_color="#1a5a2a", hover_color="#145020",
            font=ctk.CTkFont(size=14),
            command=self._on_save_api_key)
        self.save_apikey_btn.pack(side="left", padx=(4, 0))
        self._set_tooltip(self.save_apikey_btn, "Save API key to Windows Credential Manager")

        # Footer
        ctk.CTkLabel(sb, text="v0.1.0 — CHAI Laos",
                     text_color="#4a6278",
                     font=ctk.CTkFont(size=10)).grid(
            row=18, column=0, padx=20, pady=(0, 12), sticky="sw")

    def _sb_section(self, parent, label: str, row: int):
        ctk.CTkLabel(parent, text=label,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#8aa3b8").grid(
            row=row, column=0, padx=20, pady=(8, 2), sticky="w")

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

    def _build_main(self):
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        topbar = ctk.CTkFrame(main, height=52, corner_radius=0, fg_color="#f0f4f8")
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_propagate(False)
        ctk.CTkLabel(topbar, text="Generate Report",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#1e2d3d").grid(
            row=0, column=0, padx=20, pady=12, sticky="w")

        content = ctk.CTkFrame(main, corner_radius=0, fg_color="white")
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_rowconfigure(0, weight=2)   # chat area
        content.grid_rowconfigure(1, weight=3)   # report area
        content.grid_columnconfigure(0, weight=1)

        self._build_prompt_area(content)
        self._build_report_area(content)
        self._build_statusbar(main)

    def _build_prompt_area(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, padx=20, pady=(12, 4), sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        # Chat panel
        self.chat_panel = ChatPanel(frame)
        self.chat_panel.grid(row=0, column=0, sticky="nsew")
        self.chat_panel.set_send_callback(self._on_chat_send)

        # Meta row: pin + report name
        meta_row = ctk.CTkFrame(frame, fg_color="transparent")
        meta_row.grid(row=1, column=0, pady=(6, 0), sticky="ew")
        meta_row.grid_columnconfigure(2, weight=1)

        self.pin_btn = ctk.CTkButton(
            meta_row, text="☰ Pin Metadata", width=130, height=30,
            fg_color="#e8f0f8", text_color=DHIS2_BLUE,
            border_width=1, border_color=DHIS2_BLUE,
            hover_color="#d0e4f4",
            command=self._on_open_selector)
        self.pin_btn.grid(row=0, column=0, padx=(0, 8))

        self.pin_count_lbl = ctk.CTkLabel(
            meta_row, text="No items pinned",
            font=ctk.CTkFont(size=11), text_color="#8aa3b8")
        self.pin_count_lbl.grid(row=0, column=1, padx=(0, 16))

        ctk.CTkLabel(meta_row, text="Report name:",
                     font=ctk.CTkFont(size=12), text_color="#4a6278").grid(
            row=0, column=2, sticky="e", padx=(0, 6))

        self.report_name_entry = ctk.CTkEntry(
            meta_row, placeholder_text="My Custom Report",
            width=220, height=30, font=ctk.CTkFont(size=12))
        self.report_name_entry.grid(row=0, column=3)

        # Chart selector row
        chart_row = ctk.CTkFrame(frame, fg_color="transparent")
        chart_row.grid(row=2, column=0, pady=(4, 0), sticky="ew")
        chart_row.grid_columnconfigure(2, weight=1)

        self.dashboard_btn = ctk.CTkButton(
            chart_row, text="🏗 Build Dashboard", width=150, height=30,
            fg_color=DHIS2_BLUE, text_color="white",
            hover_color="#155a8a",
            command=self._on_open_dashboard_builder)
        self.dashboard_btn.grid(row=0, column=0, padx=(0, 6))

        self.chart_btn = ctk.CTkButton(
            chart_row, text="📊 Single Chart", width=120, height=30,
            fg_color="#e8f0f8", text_color=DHIS2_BLUE,
            border_width=1, border_color=DHIS2_BLUE,
            hover_color="#d0e4f4",
            command=self._on_open_chart_library)
        self.chart_btn.grid(row=0, column=1, padx=(0, 10))

        self.chart_lbl = ctk.CTkLabel(
            chart_row, text="No layout — LLM sẽ tự chọn chart type",
            font=ctk.CTkFont(size=11), text_color="#8aa3b8", anchor="w")
        self.chart_lbl.grid(row=0, column=2, sticky="w")

        # Action buttons row
        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.grid(row=3, column=0, pady=(6, 4), sticky="e")

        self.clear_btn = ctk.CTkButton(
            btn_row, text="Clear", width=80, height=34,
            fg_color="transparent", border_width=1, border_color="#c8d8e8",
            text_color="#1e2d3d", hover_color="#e8f0f8",
            command=self._on_clear)
        self.clear_btn.pack(side="left", padx=(0, 8))

        self.generate_btn = ctk.CTkButton(
            btn_row, text="Generate HTML Report ▶", width=195, height=34,
            fg_color=DHIS2_BLUE, hover_color="#155a8a",
            command=self._on_generate)
        self.generate_btn.pack(side="left")

    def _build_report_area(self, parent):
        self.report_view = ReportView(parent)
        self.report_view.set_deploy_callback(self._on_deploy)
        self.report_view.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="nsew")

    def _build_statusbar(self, parent):
        sb = ctk.CTkFrame(parent, height=28, corner_radius=0, fg_color="#eef2f7")
        sb.grid(row=2, column=0, sticky="ew")
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
        """On startup: populate profile dropdown and restore API key."""
        from config.credentials import load_profiles, load_api_key
        self._profiles = load_profiles()
        self._refresh_profile_menu()

        # Restore API key if not already set via .env
        if not self._api_key:
            saved_key = load_api_key()
            if saved_key:
                self._api_key = saved_key
                self.apikey_entry.delete(0, "end")
                self.apikey_entry.insert(0, saved_key)

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
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, p["url"])
                self.user_entry.delete(0, "end")
                self.user_entry.insert(0, p["username"])
                pwd = load_password(p["url"], p["username"])
                self.pass_entry.delete(0, "end")
                if pwd:
                    self.pass_entry.insert(0, pwd)
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
            cached_meta, cached_at = cache_load(url)
            if cached_meta and not force_refresh:
                self._metadata    = cached_meta
                self._filter_cfg  = cached_meta.get("_filter_config", {})
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

            count = (len(metadata.get("indicators", [])) +
                     len(metadata.get("program_indicators", [])))
            self.after(0, self._on_connect_done, display, count, None, False)

        except Exception as exc:
            self.after(0, self._on_connect_fail, str(exc))

    def _on_connect_done(self, display: str, count: int,
                          cached_at: str | None, from_cache: bool = False):
        self._stop_progress()
        self.connect_btn.configure(state="normal", text="Connect")
        self.refresh_btn.configure(state="normal")
        self.filter_btn.configure(state="normal")
        self.conn_status.configure(
            text=f"● {display}  ({count} indicators)",
            text_color="#2ecc71")
        if from_cache and cached_at:
            self.cache_lbl.configure(
                text=f"Cached — {cached_at}",
                text_color="#f39c12")
            self._set_status(f"Using cached metadata from {cached_at}. Press ↻ or reconfigure filters.")
        else:
            self.cache_lbl.configure(text="Metadata freshly loaded.", text_color="#27ae60")
            self._set_status(f"Ready — {count} indicators loaded.")
        self._update_filter_summary()

    def _on_connect_fail(self, msg: str):
        self._stop_progress()
        self.connect_btn.configure(state="normal", text="Connect")
        self.refresh_btn.configure(state="normal")
        self.conn_status.configure(text="● Connection failed", text_color="#e74c3c")
        self._set_status(f"Connection failed: {msg}", error=True)

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
            from dhis2.cache import save as cache_save

            url      = self.url_entry.get().strip()
            metadata = fetch_all(self._client, self._filter_cfg)
            cache_save(url, metadata)
            self._metadata   = metadata
            self._filter_cfg = metadata.get("_filter_config", {})

            count = (len(metadata.get("indicators", [])) +
                     len(metadata.get("program_indicators", [])))
            self.after(0, self._on_metadata_loaded, count)
        except Exception as exc:
            self.after(0, self._on_metadata_load_fail, str(exc))

    def _on_metadata_loaded(self, count: int):
        self._stop_progress()
        self.filter_btn.configure(state="normal",
                                   text="⚙ Configure Filters & Load Metadata")
        self.cache_lbl.configure(text="Metadata freshly loaded.", text_color="#27ae60")
        self._update_filter_summary()
        self._set_status(f"Metadata loaded — {count} indicators/program indicators.")

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
                text="Filter: " + " | ".join(parts),
                text_color="#f39c12")
        else:
            self.filter_summary_lbl.configure(
                text="No filters — all metadata",
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
            self._refresh_pin_count()

    def _refresh_pin_count(self):
        total = sum(len(v) for v in self._pinned.values())
        if total == 0:
            self.pin_count_lbl.configure(text="No items pinned", text_color="#8aa3b8")
        else:
            parts = []
            labels = {"indicators": "ind", "program_indicators": "prog", "data_elements": "DE"}
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
            n = len(dlg.result)
            self.chart_lbl.configure(
                text=f"🏗 Dashboard: {n} chart{'s' if n != 1 else ''}",
                text_color=DHIS2_BLUE)
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

        # Update chart label
        n = len(new_layout)
        self.chart_lbl.configure(
            text=f"🏗 Dashboard: {n} chart{'s' if n != 1 else ''}",
            text_color=DHIS2_BLUE)

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
            args=(new_layout, changed_ids, current_html, api_key),
            daemon=True,
        ).start()

    def _regen_cards_worker(self, new_layout, changed_ids, current_html, api_key):
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
                                                  api_key=api_key)
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
        self.generate_btn.configure(state="normal", text="Generate HTML Report ▶")
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
            self.chart_lbl.configure(
                text=f"📊 Single chart: {name}",
                text_color=DHIS2_BLUE)

    # ─── Generate ────────────────────────────────────────────────────────────

    def _on_generate(self):
        api_key = self.apikey_entry.get().strip()
        if not api_key:
            self._set_status("Enter your Anthropic API key.", error=True)
            return

        messages = self.chat_panel.get_messages()
        if not messages:
            self._set_status("Nhập yêu cầu trong chat trước khi generate.", error=True)
            return

        total_pinned = sum(len(v) for v in self._pinned.values())
        if total_pinned == 0 and self._metadata:
            if not msgbox.askyesno(
                "No indicators pinned",
                "No indicators/data elements are pinned.\n"
                "The LLM will pick from all available metadata — results may be imprecise.\n\n"
                "Continue anyway?"
            ):
                return

        self.generate_btn.configure(state="disabled", text="Generating…")
        self._set_status("Building context…")
        self._start_progress()
        self.report_view.clear()
        self.chat_panel.set_generating(True)

        threading.Thread(target=self._generate_worker, args=(api_key,), daemon=True).start()

    def _generate_worker(self, api_key: str):
        try:
            from llm.context_builder import build_context
            from dhis2.usage_tracker import get_counts

            url      = self.url_entry.get().strip()
            counts   = get_counts(url)
            metadata = self._metadata or {}
            merged_pinned = _merge_pinned(self._dashboard_layout, self._pinned)
            context = build_context(metadata, url, pinned=merged_pinned, usage_counts=counts)

            messages = self.chat_panel.get_messages()
            # Extract prompt string for layout-based modes (join all user messages)
            prompt = " ".join(m["content"] for m in messages if m["role"] == "user")

            layout = self._dashboard_layout
            if layout and len(layout) > 1:
                from llm.dashboard_generator import generate_dashboard_html
                n = len(layout)
                self.after(0, self._set_status, f"Calling Claude to build {n}-chart dashboard…")
                html = generate_dashboard_html(prompt, layout, context, api_key=api_key)

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
                    )
                else:
                    self.after(0, self._set_status, "Calling Claude to generate HTML…")
                    html = generate_report_html(prompt, context, api_key=api_key)

            else:
                from llm.chat_generator import generate_from_chat
                self.after(0, self._set_status, "Calling Claude to generate HTML from chat…")
                html = generate_from_chat(messages, context, api_key)

            self.after(0, self._on_generate_done, html)

        except Exception as exc:
            self.after(0, self._on_generate_fail, str(exc))

    def _on_generate_done(self, html: str):
        self._stop_progress()
        self.generate_btn.configure(state="normal", text="Generate HTML Report ▶")
        self.chat_panel.set_generating(False)
        self.report_view.show(html)
        self.chat_panel.add_system_note("HTML đã được tạo — gửi tin nhắn để chỉnh sửa")
        self.chat_panel.set_hint("Refine mode — gửi yêu cầu chỉnh sửa")

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
        self.generate_btn.configure(state="normal", text="Generate HTML Report ▶")
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
        name = self.report_name_entry.get().strip()
        if not name:
            self._set_status("Enter a report name before deploying.", error=True)
            return

        # Warn if HTML looks like a browser-saved "Complete" page
        if "_files/" in html:
            if not msgbox.askyesno(
                "Warning: broken CDN links detected",
                "The HTML contains '_files/' references — it looks like a\n"
                "browser-saved page where CDN links were replaced with local paths.\n\n"
                "Bootstrap and Chart.js may NOT load when deployed to DHIS2.\n\n"
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
        self.chat_panel.set_hint("Mô tả báo cáo → nhấn Generate")
        self._set_status("Ready")

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
            self.chat_panel.set_generating(True)
            self._start_progress()
            self._set_status("Refining report…")
            threading.Thread(
                target=self._refine_worker,
                args=(text, api_key, current_html),
                daemon=True,
            ).start()

        elif self._metadata and api_key:
            # Phase 1 — planning, ask LLM for clarification
            self.chat_panel.set_generating(True)
            self._set_status("Thinking…")
            threading.Thread(
                target=self._chat_plan_worker,
                args=(api_key,),
                daemon=True,
            ).start()

        else:
            # No connection or no API key — message stored, no LLM response
            hint = "Connect to DHIS2 and enter API key for AI assistance."
            self._set_status(hint)

    def _chat_plan_worker(self, api_key: str):
        try:
            from llm.context_builder import build_context
            from llm.chat_generator import chat_plan
            from dhis2.usage_tracker import get_counts

            url    = self.url_entry.get().strip()
            counts = get_counts(url)
            merged = _merge_pinned(self._dashboard_layout, self._pinned)
            context = build_context(self._metadata or {}, url, pinned=merged, usage_counts=counts)

            messages = self.chat_panel.get_messages()
            response = chat_plan(messages, context, api_key)
            self.after(0, self._on_chat_plan_done, response)
        except Exception as exc:
            self.after(0, self._on_chat_fail, str(exc))

    def _on_chat_plan_done(self, response: str):
        self.chat_panel.set_generating(False)
        self.chat_panel.add_assistant_message(response)
        self._set_status("Ready — nhấn Generate khi đã đủ yêu cầu.")

    def _refine_worker(self, request: str, api_key: str, current_html: str):
        try:
            from llm.context_builder import build_context
            from llm.chat_generator import refine_from_chat
            from dhis2.usage_tracker import get_counts

            url    = self.url_entry.get().strip()
            counts = get_counts(url)
            merged = _merge_pinned(self._dashboard_layout, self._pinned)
            context = build_context(self._metadata or {}, url, pinned=merged, usage_counts=counts)

            html = refine_from_chat(request, current_html, context, api_key)
            self.after(0, self._on_refine_done, html)
        except Exception as exc:
            self.after(0, self._on_chat_fail, str(exc))

    def _on_refine_done(self, html: str):
        self._stop_progress()
        self.chat_panel.set_generating(False)
        self.report_view.show(html)
        self.chat_panel.add_system_note("HTML đã cập nhật")
        self._set_status("Report refined. Preview or Deploy to DHIS2.")
        # Re-apply edit dashboard tracking if applicable
        if self._dashboard_layout and len(self._dashboard_layout) > 1:
            self.report_view.set_edit_callback(self._on_edit_dashboard)

    def _on_chat_fail(self, msg: str):
        self._stop_progress()
        self.chat_panel.set_generating(False)
        self._set_status(f"Error: {msg}", error=True)

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
