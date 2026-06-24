"""
VizBuilderPanel — left panel of the viz builder.

Flow (top to bottom):
  1. Chart Type  — pick first; determines how many DEs needed (1 or 2–3)
  2. Source Type — checkboxes: Program (Tracker) + Aggregate Dataset (no Indicator)
  3. Select Source — program/stage dropdowns + aggregate search (shows based on step 2)
  4. Data Elements — checkboxes, limit set by chart type
  5. Mode — Fixed template / AI generate
  6. Title + action buttons

Cards, report name, export and deploy are handled by DashboardPanel (right panel).
"""
from __future__ import annotations
import tkinter as tk
import tkinter.simpledialog as sd
import tkinter.messagebox as msgbox
import customtkinter as ctk
from typing import Callable

from charts.fixed_templates import FIXED_TEMPLATES, get_compatible, get_compatible_multi

DHIS2_BLUE = "#1a6fa8"
PANEL_BG   = "#f7f9fc"
BORDER_CLR = "#d0dde8"

COLOR_PRESETS = [
    ("#3498db", "Blue"),
    ("#e74c3c", "Red"),
    ("#27ae60", "Green"),
    ("#8e44ad", "Purple"),
    ("#e67e22", "Orange"),
    ("#1abc9c", "Teal"),
    ("#1a6fa8", "DHIS2 Blue"),
    ("#f39c12", "Yellow"),
]


class VizBuilderPanel(ctk.CTkFrame):
    """
    callbacks keys:
      on_preview_fixed(config)
      on_generate_ai(config)
      on_add_card(config)
    """

    def __init__(self, master, callbacks: dict[str, Callable], **kw):
        kw.setdefault("fg_color", PANEL_BG)
        kw.setdefault("corner_radius", 0)
        super().__init__(master, **kw)

        self._callbacks = callbacks
        self._metadata: dict = {}
        self._programs:   list[dict] = []
        self._agg_des:    list[dict] = []
        self._current_de_items: list[dict] = []
        self._de_checkboxes: list[tuple[dict, ctk.CTkCheckBox, tk.BooleanVar]] = []
        self._max_des: int = 1
        self._min_des: int = 1
        self._selected_color: str = COLOR_PRESETS[0][0]
        self._color_btns: list[tuple[str, ctk.CTkButton]] = []
        self._card_next_n = 1
        self._sidebar_toggle_cb: Callable | None = None  # set by AppWindow after build

        self._build()
        self._load_saved_templates_ui()

    # ─── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)   # header
        self.grid_rowconfigure(1, weight=1)   # config scroll ← grows

        # ── Row 0: Header ──────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="#e8eef5", corner_radius=0, height=36)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)

        # Sidebar toggle button — hidden initially, shown when sidebar is collapsed
        self._hdr_menu_btn = ctk.CTkButton(
            hdr, text="☰", width=32, height=28,
            fg_color="#d0dde8", hover_color="#b8c8d8",
            text_color="#3a5068", font=ctk.CTkFont(size=13),
            corner_radius=4, command=self._on_menu_btn)
        self._hdr_menu_btn.grid(row=0, column=0, padx=(6, 0), pady=4)
        self._hdr_menu_btn.grid_remove()  # hidden while sidebar visible

        ctk.CTkLabel(hdr, text="Viz Builder",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#3a5068").grid(row=0, column=1, padx=8, pady=6, sticky="w")

        # ── Row 1: Config scrollable frame ────────────────────────────────────
        self._cfg_scroll = ctk.CTkScrollableFrame(
            self, fg_color=PANEL_BG, corner_radius=0,
            scrollbar_button_color="#c0cdd8",
            label_text="")
        self._cfg_scroll.grid(row=1, column=0, sticky="nsew")
        self._cfg_scroll.grid_columnconfigure(0, weight=1)
        cf = self._cfg_scroll

        # --- Saved Templates ---
        self._tmpl_toggle_btn = ctk.CTkButton(
            cf, text="📚 Saved Templates ▶",
            height=26, fg_color="#e8eef5", hover_color="#d4dde8",
            text_color="#3a5068", font=ctk.CTkFont(size=11),
            anchor="w", corner_radius=0,
            command=self._toggle_saved_panel)
        self._tmpl_toggle_btn.grid(row=0, column=0, sticky="ew")

        self._saved_panel = ctk.CTkFrame(cf, fg_color="#f0f5fb",
                                          border_color=BORDER_CLR, border_width=1,
                                          corner_radius=0)
        self._saved_panel.grid(row=1, column=0, sticky="ew")
        self._saved_panel.grid_columnconfigure(0, weight=1)
        self._saved_panel.grid_remove()
        self._saved_visible = False

        self._saved_scroll = ctk.CTkScrollableFrame(
            self._saved_panel, fg_color="#f0f5fb", corner_radius=0,
            scrollbar_button_color="#c0cdd8", height=100)
        self._saved_scroll.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self._saved_scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkFrame(cf, fg_color=BORDER_CLR, height=1,
                     corner_radius=0).grid(row=2, column=0, sticky="ew")

        # --- 1. Chart Type ---
        self._slbl(cf, 3, "1. Chart Type")
        all_vals = ["— Select chart type —"] + [f"{t['icon']} {t['label']}" for t in FIXED_TEMPLATES]
        self._chart_type_var = tk.StringVar(value=all_vals[0])
        self._chart_menu = ctk.CTkOptionMenu(
            cf, variable=self._chart_type_var, values=all_vals,
            height=28, font=ctk.CTkFont(size=11),
            fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d",
            command=self._on_chart_type_change)
        self._chart_menu.grid(row=4, column=0, padx=10, pady=(2, 2), sticky="ew")

        self._chart_info_lbl = ctk.CTkLabel(
            cf, text="← Pick chart type to begin",
            font=ctk.CTkFont(size=10), text_color="#8aa3b8",
            wraplength=290, justify="left")
        self._chart_info_lbl.grid(row=5, column=0, padx=12, pady=(0, 4), sticky="w")

        # --- 2. Source Type (multiple checkboxes) ---
        self._slbl(cf, 6, "2. Source Type")
        src_frame = ctk.CTkFrame(cf, fg_color="transparent")
        src_frame.grid(row=7, column=0, padx=12, pady=(2, 4), sticky="ew")

        self._src_prog_var = tk.BooleanVar(value=True)
        self._src_agg_var  = tk.BooleanVar(value=False)
        self._src_prog_cb = ctk.CTkCheckBox(
            src_frame, text="Program (Tracker)",
            variable=self._src_prog_var, font=ctk.CTkFont(size=11),
            command=self._on_src_check)
        self._src_prog_cb.pack(anchor="w", pady=1)
        self._src_agg_cb = ctk.CTkCheckBox(
            src_frame, text="Aggregate Dataset",
            variable=self._src_agg_var, font=ctk.CTkFont(size=11),
            command=self._on_src_check)
        self._src_agg_cb.pack(anchor="w", pady=1)

        # --- 3. Select Source ---
        self._slbl(cf, 8, "3. Select Source")
        pf = ctk.CTkFrame(cf, fg_color="transparent")
        pf.grid(row=9, column=0, padx=10, pady=(2, 4), sticky="ew")
        pf.grid_columnconfigure(0, weight=1)

        self._prog_var = tk.StringVar(value="—")
        self._prog_menu = ctk.CTkOptionMenu(
            pf, variable=self._prog_var, values=["—"],
            height=28, font=ctk.CTkFont(size=11),
            fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d",
            command=self._on_prog_selected)
        self._prog_menu.grid(row=0, column=0, sticky="ew")

        self._stage_var = tk.StringVar(value="—")
        self._stage_menu = ctk.CTkOptionMenu(
            pf, variable=self._stage_var, values=["—"],
            height=28, font=ctk.CTkFont(size=11),
            fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d",
            command=self._on_stage_selected)
        self._stage_menu.grid(row=1, column=0, sticky="ew", pady=(3, 0))

        self._src_search_var = tk.StringVar()
        self._src_search_var.trace_add("write", self._on_src_search)
        self._src_search_entry = ctk.CTkEntry(
            pf, textvariable=self._src_search_var,
            placeholder_text="🔍 Search aggregate DEs...", height=28,
            font=ctk.CTkFont(size=11))
        self._src_search_entry.grid(row=2, column=0, sticky="ew", pady=(3, 0))
        self._src_search_entry.grid_remove()

        # --- 4. Data Elements ---
        self._de_section_lbl = ctk.CTkLabel(
            cf, text="4. DATA ELEMENTS  (TICK 1)",
            font=ctk.CTkFont(size=9, weight="bold"), text_color="#8aa3b8")
        self._de_section_lbl.grid(row=10, column=0, padx=12, pady=(5, 1), sticky="w")

        de_outer = ctk.CTkFrame(cf, fg_color="white",
                                 border_color=BORDER_CLR, border_width=1, corner_radius=6)
        de_outer.grid(row=11, column=0, padx=10, pady=(0, 4), sticky="ew")
        de_outer.grid_columnconfigure(0, weight=1)

        de_sr = ctk.CTkFrame(de_outer, fg_color="white")
        de_sr.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        de_sr.grid_columnconfigure(0, weight=1)
        self._de_search_var = tk.StringVar()
        self._de_search_var.trace_add("write", self._on_de_search)
        ctk.CTkEntry(de_sr, textvariable=self._de_search_var,
                     placeholder_text="🔍 Filter DEs...", height=26,
                     font=ctk.CTkFont(size=10)).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(de_sr, text="✕", width=24, height=26,
                      fg_color="#e8eef5", hover_color="#d0dde8",
                      text_color="#5a7a9a", font=ctk.CTkFont(size=10),
                      command=lambda: self._de_search_var.set("")
                      ).grid(row=0, column=1, padx=(2, 0))

        self._de_scroll = ctk.CTkScrollableFrame(
            de_outer, fg_color="white", corner_radius=0,
            scrollbar_button_color="#c0cdd8", height=140)
        self._de_scroll.grid(row=1, column=0, sticky="ew", padx=2, pady=(2, 4))
        self._de_scroll.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self._de_scroll, text="Select chart type first",
                     font=ctk.CTkFont(size=10), text_color="#8aa3b8"
                     ).grid(row=0, column=0, pady=12)

        self._sel_lbl = ctk.CTkLabel(
            cf, text="", font=ctk.CTkFont(size=10),
            text_color="#1565c0", fg_color="transparent", corner_radius=4,
            wraplength=290, justify="left")
        self._sel_lbl.grid(row=12, column=0, padx=10, pady=(0, 2), sticky="w")

        # --- 5. Mode ---
        self._slbl(cf, 13, "5. Mode")
        mf = ctk.CTkFrame(cf, fg_color="transparent")
        mf.grid(row=14, column=0, padx=12, pady=(2, 2), sticky="ew")
        self._mode_var = tk.StringVar(value="fixed")
        ctk.CTkRadioButton(mf, text="Fixed template (instant preview)",
                            variable=self._mode_var, value="fixed",
                            font=ctk.CTkFont(size=11),
                            command=self._on_mode_change).pack(anchor="w")
        ctk.CTkRadioButton(mf, text="AI generate (Claude)",
                            variable=self._mode_var, value="ai",
                            font=ctk.CTkFont(size=11),
                            command=self._on_mode_change).pack(anchor="w", pady=(3, 0))

        self._ai_desc_frame = ctk.CTkFrame(cf, fg_color="transparent")
        self._ai_desc_frame.grid(row=15, column=0, padx=10, pady=(0, 2), sticky="ew")
        self._ai_desc_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self._ai_desc_frame, text="Describe:",
                     font=ctk.CTkFont(size=10), text_color="#5a7a9a").pack(anchor="w")
        self._ai_desc = ctk.CTkTextbox(
            self._ai_desc_frame, height=40, font=ctk.CTkFont(size=11), wrap="word")
        self._ai_desc.pack(fill="x", pady=(2, 0))
        self._ai_desc_frame.grid_remove()

        # --- 6. Style / Color ---
        self._slbl(cf, 16, "6. Style")
        color_frame = ctk.CTkFrame(cf, fg_color="transparent")
        color_frame.grid(row=17, column=0, padx=10, pady=(2, 6), sticky="ew")
        for i, (hex_color, name) in enumerate(COLOR_PRESETS):
            btn = ctk.CTkButton(
                color_frame, text="", width=28, height=28,
                fg_color=hex_color, hover_color=hex_color,
                corner_radius=14,
                border_width=3,
                border_color=hex_color,
                command=lambda c=hex_color: self._on_color_select(c))
            btn.grid(row=0, column=i, padx=2)
            self._color_btns.append((hex_color, btn))
        self._on_color_select(self._selected_color)  # highlight default

        # --- 7. Title + action buttons ---
        self._slbl(cf, 18, "7. Title")
        self._title_entry = ctk.CTkEntry(
            cf, height=28, font=ctk.CTkFont(size=11),
            placeholder_text="Auto from DE name")
        self._title_entry.grid(row=19, column=0, padx=10, pady=(2, 4), sticky="ew")

        br = ctk.CTkFrame(cf, fg_color="transparent")
        br.grid(row=20, column=0, padx=10, pady=(0, 8), sticky="ew")
        self._preview_btn = ctk.CTkButton(
            br, text="👁 Preview", width=85, height=30,
            fg_color=DHIS2_BLUE, hover_color="#155a8a",
            font=ctk.CTkFont(size=11), command=self._on_preview)
        self._preview_btn.pack(side="left")
        self._add_btn = ctk.CTkButton(
            br, text="+ Add", width=65, height=30,
            fg_color="#27ae60", hover_color="#1e8449",
            font=ctk.CTkFont(size=11), command=self._on_add)
        self._add_btn.pack(side="left", padx=(4, 0))
        self._save_tmpl_btn = ctk.CTkButton(
            br, text="💾 Save", height=30,
            fg_color="#8e44ad", hover_color="#6c3483",
            font=ctk.CTkFont(size=11), command=self._on_save_template)
        self._save_tmpl_btn.pack(side="left", padx=(4, 0))

    def set_sidebar_toggle(self, callback: Callable):
        """Called by AppWindow to wire up the sidebar ☰ button."""
        self._sidebar_toggle_cb = callback

    def show_menu_btn(self, visible: bool):
        """Show/hide the ☰ button in the header (called when sidebar state changes)."""
        if visible:
            self._hdr_menu_btn.grid()
        else:
            self._hdr_menu_btn.grid_remove()

    def _on_menu_btn(self):
        if self._sidebar_toggle_cb:
            self._sidebar_toggle_cb()

    def _slbl(self, parent, row, text):
        ctk.CTkLabel(parent, text=text.upper(),
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color="#8aa3b8"
                     ).grid(row=row, column=0, padx=12, pady=(5, 1), sticky="w")

    # ─── Saved Templates UI ───────────────────────────────────────────────────

    def _toggle_saved_panel(self):
        self._saved_visible = not self._saved_visible
        if self._saved_visible:
            self._saved_panel.grid()
            self._tmpl_toggle_btn.configure(text="📚 Saved Templates ▼")
        else:
            self._saved_panel.grid_remove()
            self._tmpl_toggle_btn.configure(text="📚 Saved Templates ▶")

    def _load_saved_templates_ui(self):
        from config.saved_templates import load_templates
        for w in self._saved_scroll.winfo_children():
            w.destroy()
        templates = load_templates()
        if not templates:
            ctk.CTkLabel(self._saved_scroll,
                         text="No saved templates yet.",
                         font=ctk.CTkFont(size=10), text_color="#8aa3b8"
                         ).grid(row=0, column=0, pady=10)
            return
        for i, t in enumerate(templates):
            rf = ctk.CTkFrame(self._saved_scroll, fg_color="white",
                               border_color=BORDER_CLR, border_width=1, corner_radius=5)
            rf.grid(row=i, column=0, padx=4, pady=2, sticky="ew")
            rf.grid_columnconfigure(0, weight=1)
            tid_lbl = t.get("template_id", "").replace("ft_", "").replace("_", " ").title()
            ctk.CTkButton(rf,
                          text=f"{tid_lbl}  —  {t['name']}",
                          height=26, fg_color="transparent", hover_color="#e8f0f8",
                          text_color="#1e2d3d", font=ctk.CTkFont(size=10), anchor="w",
                          command=lambda cfg=t: self._apply_saved_template(cfg)
                          ).grid(row=0, column=0, sticky="ew")
            ctk.CTkButton(rf, text="✕", width=22, height=22,
                          fg_color="transparent", hover_color="#f5c6cb",
                          text_color="#c0392b", font=ctk.CTkFont(size=9),
                          command=lambda name=t["name"]: self._delete_saved_template(name)
                          ).grid(row=0, column=1, padx=3)

    def _apply_saved_template(self, cfg: dict):
        tid = cfg.get("template_id", "")
        tmpl = next((t for t in FIXED_TEMPLATES if t["id"] == tid), None)
        if tmpl:
            val = f"{tmpl['icon']} {tmpl['label']}"
            self._chart_type_var.set(val)
            self._on_chart_type_change(val)
        self._title_entry.delete(0, "end")
        self._title_entry.insert(0, cfg.get("title", ""))
        self._mode_var.set(cfg.get("mode", "fixed"))
        self._on_mode_change()
        self._sel_lbl.configure(
            text=f"  Template loaded: {cfg['name']}  ",
            fg_color="#fff3e0", text_color="#e65100")

    def _on_save_template(self):
        tmpl = self._get_selected_template()
        sel = self._get_selected_des()
        if not tmpl or not sel:
            msgbox.showwarning("Save Template", "Select a chart type and data element(s) first.")
            return
        name = sd.askstring("Save Template", "Template name:",
                            initialvalue=self._title_entry.get().strip() or sel[0]["name"])
        if not name:
            return
        from config.saved_templates import save_template
        save_template(self._build_config(tmpl, sel), name)
        self._load_saved_templates_ui()
        if not self._saved_visible:
            self._toggle_saved_panel()

    def _delete_saved_template(self, name: str):
        from config.saved_templates import delete_template
        if msgbox.askyesno("Delete Template", f"Delete '{name}'?"):
            delete_template(name)
            self._load_saved_templates_ui()

    # ─── Metadata loading ─────────────────────────────────────────────────────

    def load_metadata(self, meta: dict):
        self._metadata = meta
        prog_map: dict[str, dict] = {}
        for de in meta.get("program_stage_data_elements", []):
            pid   = de.get("program", {}).get("id", "")
            pname = de.get("program", {}).get("displayName", pid)
            sid   = de.get("stage", {}).get("id", "")
            sname = de.get("stage", {}).get("displayName", sid)
            if pid not in prog_map:
                prog_map[pid] = {"id": pid, "displayName": pname, "stages": {}}
            sm = prog_map[pid]["stages"]
            if sid not in sm:
                sm[sid] = {"id": sid, "displayName": sname, "des": []}
            sm[sid]["des"].append({
                "uid": de["id"], "name": de.get("displayName", de["id"]),
                "type": "tracker_option" if de.get("optionSet") else "tracker_numeric",
                "prog_uid": pid, "prog_name": pname,
                "stage_uid": sid, "stage_name": sname,
            })
        self._programs = sorted(
            [{"id": p["id"], "displayName": p["displayName"],
              "stages": list(p["stages"].values())}
             for p in prog_map.values()],
            key=lambda x: x["displayName"].lower())
        self._agg_des = sorted(
            [{"uid": d["id"], "name": d.get("displayName", d["id"]),
              "type": "aggregate", "prog_uid": "", "stage_uid": ""}
             for d in meta.get("data_elements", [])],
            key=lambda x: x["name"].lower())
        self._init_source_menus()

    def _init_source_menus(self):
        """Populate program dropdown with loaded programs (no DE list refresh)."""
        names = ["— Select program —"] + [p["displayName"] for p in self._programs]
        self._prog_menu.configure(values=names)
        self._prog_var.set(names[0])
        self._stage_var.set("—")
        self._stage_menu.configure(values=["—"])

    # ─── Chart Type ───────────────────────────────────────────────────────────

    def _on_chart_type_change(self, _=None):
        val = self._chart_type_var.get()
        tmpl = next((t for t in FIXED_TEMPLATES if val.endswith(t["label"])), None)

        if not tmpl:
            self._max_des = 1
            self._min_des = 1
            self._chart_info_lbl.configure(
                text="← Pick chart type to begin", text_color="#8aa3b8")
            return

        # DE limits from template
        self._min_des = tmpl.get("min_sources", 1)
        self._max_des = tmpl.get("max_sources", 1 if not tmpl.get("multi") else 3)

        # Update section label
        if self._min_des == self._max_des:
            limit_text = str(self._max_des)
        else:
            limit_text = f"{self._min_des}–{self._max_des}"
        self._de_section_lbl.configure(
            text=f"4. DATA ELEMENTS  (TICK {limit_text})")

        # Chart description
        self._chart_info_lbl.configure(
            text=tmpl.get("description", ""), text_color="#5a7a9a")

        # Enable/disable source type checkboxes based on compatibility
        prog_ok = bool({"tracker_option", "tracker_numeric"} & tmpl["for_types"])
        agg_ok  = "aggregate" in tmpl["for_types"]

        self._src_prog_cb.configure(state="normal" if prog_ok else "disabled")
        self._src_agg_cb.configure(state="normal" if agg_ok else "disabled")

        if not prog_ok:
            self._src_prog_var.set(False)
        if not agg_ok:
            self._src_agg_var.set(False)

        # Ensure at least one compatible source is checked
        if not self._src_prog_var.get() and not self._src_agg_var.get():
            if prog_ok:
                self._src_prog_var.set(True)
            elif agg_ok:
                self._src_agg_var.set(True)

        # Enforce new DE max — uncheck extras
        sel = self._get_selected_des()
        if len(sel) > self._max_des:
            count = 0
            for _, _, var in self._de_checkboxes:
                if var.get():
                    count += 1
                    if count > self._max_des:
                        var.set(False)

        self._on_src_check()

        if self._mode_var.get() == "fixed":
            self._auto_preview()

    # ─── Source type checkboxes ───────────────────────────────────────────────

    def _on_src_check(self):
        """Called when Program or Aggregate checkbox changes."""
        prog = self._src_prog_var.get()
        agg  = self._src_agg_var.get()

        if prog:
            self._prog_menu.grid()
            self._stage_menu.grid()
        else:
            self._prog_menu.grid_remove()
            self._stage_menu.grid_remove()

        if agg:
            self._src_search_entry.grid()
        else:
            self._src_search_entry.grid_remove()
            self._src_search_var.set("")

        if not prog and not agg:
            self._clear_de_list()
            return

        self._refresh_de_list()

    def _on_prog_selected(self, _=None):
        prog = next((p for p in self._programs if p["displayName"] == self._prog_var.get()), None)
        if not prog:
            self._refresh_de_list()
            return
        self._current_prog = prog
        names = ["— All stages —"] + [s["displayName"] for s in prog["stages"]]
        self._stage_menu.configure(values=names)
        self._stage_var.set(names[0])
        self._refresh_de_list()

    def _on_stage_selected(self, _=None):
        self._refresh_de_list()

    def _on_src_search(self, *_):
        self._refresh_de_list()

    def _refresh_de_list(self):
        """Rebuild DE list from currently checked sources, filtered by chart type compatibility."""
        val = self._chart_type_var.get()
        tmpl = next((t for t in FIXED_TEMPLATES if val.endswith(t["label"])), None)
        for_types = tmpl["for_types"] if tmpl else {"tracker_option", "tracker_numeric", "aggregate"}

        items: list[dict] = []

        if self._src_prog_var.get():
            prog = getattr(self, "_current_prog", None)
            if prog:
                sname = self._stage_var.get()
                if sname in ("— All stages —", "—", ""):
                    prog_des = [de for s in prog["stages"] for de in s["des"]]
                else:
                    stage = next((s for s in prog["stages"] if s["displayName"] == sname), None)
                    prog_des = stage["des"] if stage else []
                items.extend(de for de in prog_des if de["type"] in for_types)

        if self._src_agg_var.get():
            q = self._src_search_var.get().strip().lower()
            agg_items = [de for de in self._agg_des
                         if "aggregate" in for_types and (not q or q in de["name"].lower())]
            items.extend(agg_items)

        checked = {de["uid"] for de, _, var in self._de_checkboxes if var.get()}
        self._populate_de_list(items, preserve_checked=checked)

    # ─── DE list ──────────────────────────────────────────────────────────────

    def _on_de_search(self, *_):
        q = self._de_search_var.get().strip().lower()
        checked = {de["uid"] for de, _, var in self._de_checkboxes if var.get()}
        filtered = [i for i in self._current_de_items if not q or q in i["name"].lower()]
        self._populate_de_list(filtered, preserve_checked=checked)

    def _clear_de_list(self, placeholder: str = "Select chart type first"):
        for w in self._de_scroll.winfo_children():
            w.destroy()
        self._de_checkboxes = []
        self._current_de_items = []
        ctk.CTkLabel(self._de_scroll, text=placeholder,
                     font=ctk.CTkFont(size=10), text_color="#8aa3b8"
                     ).grid(row=0, column=0, pady=12)
        self._update_sel_badge()

    def _populate_de_list(self, items: list[dict], preserve_checked: set[str] | None = None):
        self._current_de_items = items
        checked = preserve_checked or {de["uid"] for de, _, var in self._de_checkboxes if var.get()}
        for w in self._de_scroll.winfo_children():
            w.destroy()
        self._de_checkboxes = []
        if not items:
            ctk.CTkLabel(self._de_scroll, text="No results",
                         font=ctk.CTkFont(size=10), text_color="#8aa3b8"
                         ).grid(row=0, column=0, pady=10)
            return
        for i, de in enumerate(items):
            var = tk.BooleanVar(value=de["uid"] in checked)
            cb = ctk.CTkCheckBox(
                self._de_scroll, text=de["name"], variable=var,
                font=ctk.CTkFont(size=10),
                checkbox_width=16, checkbox_height=16,
                command=self._on_de_check)
            cb.grid(row=i, column=0, padx=6, pady=1, sticky="w")
            self._de_checkboxes.append((de, cb, var))

    def _on_de_check(self):
        sel = self._get_selected_des()
        if len(sel) > self._max_des:
            count = 0
            for _, _, var in self._de_checkboxes:
                if var.get():
                    count += 1
                    if count > self._max_des:
                        var.set(False)
            sel = self._get_selected_des()
        self._update_sel_badge()
        if self._mode_var.get() == "fixed" and len(sel) >= self._min_des:
            self._auto_preview()

    def _get_selected_des(self) -> list[dict]:
        return [de for de, _, var in self._de_checkboxes if var.get()]

    def _update_sel_badge(self):
        sel = self._get_selected_des()
        if not sel:
            self._sel_lbl.configure(text="", fg_color="transparent")
        else:
            names = " + ".join(d["name"][:22] for d in sel)
            self._sel_lbl.configure(
                text=f"  ✓ {len(sel)}: {names}  ",
                fg_color="#e3f2fd", text_color="#1565c0")

    # ─── Controls ─────────────────────────────────────────────────────────────

    def _on_color_select(self, color: str):
        self._selected_color = color
        for hex_color, btn in self._color_btns:
            if hex_color == color:
                btn.configure(border_color="white", border_width=3)
            else:
                btn.configure(border_color=hex_color, border_width=2)

    def _on_mode_change(self):
        if self._mode_var.get() == "ai":
            self._ai_desc_frame.grid()
            self._preview_btn.configure(state="disabled")
        else:
            self._ai_desc_frame.grid_remove()
            self._preview_btn.configure(state="normal")
            self._auto_preview()

    def _auto_preview(self):
        tmpl = self._get_selected_template()
        sel = self._get_selected_des()
        if tmpl and sel and len(sel) >= self._min_des:
            cb = self._callbacks.get("on_preview_fixed")
            if cb:
                cb(self._build_config(tmpl, sel))

    def _on_preview(self):
        tmpl = self._get_selected_template()
        sel = self._get_selected_des()
        if not tmpl or not sel:
            return
        cb = self._callbacks.get("on_preview_fixed")
        if cb:
            cb(self._build_config(tmpl, sel))

    def _on_add(self):
        tmpl = self._get_selected_template()
        if not tmpl:
            msgbox.showwarning("Viz Builder", "Select a chart type first.")
            return
        sel = self._get_selected_des()
        if len(sel) < self._min_des:
            needed = f"{self._min_des}" if self._min_des == self._max_des else f"{self._min_des}–{self._max_des}"
            msgbox.showwarning(
                "Viz Builder",
                f"'{tmpl['label']}' needs {needed} data element(s).\n"
                f"Currently {len(sel)} selected.")
            return

        cfg = self._build_config(tmpl, sel)
        cfg["card_id"] = f"card_{self._card_next_n}"
        cfg["n"] = self._card_next_n
        self._card_next_n += 1

        if self._mode_var.get() == "ai":
            cfg["ai_desc"] = self._ai_desc.get("1.0", "end").strip()
            cb = self._callbacks.get("on_generate_ai")
            if cb:
                cb(cfg)
        else:
            cb = self._callbacks.get("on_add_card")
            if cb:
                cb(cfg)

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _get_selected_template(self) -> dict | None:
        val = self._chart_type_var.get()
        return next((t for t in FIXED_TEMPLATES if val.endswith(t["label"])), None)

    def _build_config(self, tmpl: dict, sel: list[dict]) -> dict:
        title = self._title_entry.get().strip()
        if not title:
            title = sel[0]["name"] if len(sel) == 1 else \
                    " vs ".join(d["name"][:20] for d in sel[:2])
        de = sel[0]
        return {
            "template_id":    tmpl["id"],
            "template_label": tmpl["label"],
            "title":          title,
            "mode":           self._mode_var.get(),
            "col_width":      6,
            "chart_color":    self._selected_color,
            "de_sources":     sel,
            "de_uid":         de["uid"],
            "de_name":        de["name"],
            "de_type":        de["type"],
            "prog_uid":       de.get("prog_uid", ""),
            "prog_name":      de.get("prog_name", ""),
            "stage_uid":      de.get("stage_uid", ""),
            "stage_name":     de.get("stage_name", ""),
        }
