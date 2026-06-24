"""
ChartEditorPanel — chart editor.

Layout:
  ┌──────────────────────────────────────────────────────────────────┐
  │  1. Chart Type (4-col grid)                                      │
  │  2. Source (full-width)                                          │
  │  3. Metrics (DE checkboxes + agg pickers)                        │
  │     Dimensions (time grain + breakdown)                          │
  │  4. Style                                                        │
  │  5. Chart Options                                                │
  │  🤖 AI Customize                                                 │
  │                                                                  │
  │  [💾 Save]  [+ Dashboard]  [🌐 Preview in Browser]              │
  └──────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations
import tkinter as tk
import tkinter.simpledialog as sd
import tkinter.messagebox as msgbox
import customtkinter as ctk
from typing import Callable

from charts.fixed_templates import FIXED_TEMPLATES
from charts.preview_canvas import draw_chart_preview

DHIS2_BLUE  = "#1a6fa8"
PANEL_BG    = "#f7f9fc"
BORDER_CLR  = "#d0dde8"

COLOR_PRESETS = [
    ("#3498db", "Blue"),
    ("#e74c3c", "Red"),
    ("#27ae60", "Green"),
    ("#8e44ad", "Purple"),
    ("#e67e22", "Orange"),
    ("#1abc9c", "Teal"),
    ("#1a6fa8", "DHIS2"),
    ("#f39c12", "Yellow"),
]

COL_WIDTH_OPTIONS = {
    "Full  (12)":   12,
    "Half  (6)":     6,
    "Third (4)":     4,
}

CHART_STYLE_CONFIGS: dict[str, list[dict]] = {
    # ── Unified bar plugin ─────────────────────────────────────────────────────
    "bar": [
        {"id": "show_values",    "label": "Show value labels",     "type": "check",   "default": False},
        {"id": "show_legend",    "label": "Show legend",           "type": "check",   "default": True},
        {"id": "only_total",     "label": "Stack total only",      "type": "check",   "default": True},
        {"id": "rich_tooltip",   "label": "Rich tooltip",          "type": "check",   "default": True},
        {"id": "tooltip_total",  "label": "Tooltip show total",    "type": "check",   "default": True},
        {"id": "log_scale",      "label": "Log scale Y",           "type": "check",   "default": False},
        {"id": "legend_pos",     "label": "Legend position",       "type": "segment", "values": ["Bottom","Top","Left","Right"], "default": "Bottom"},
        {"id": "x_rotation",     "label": "X label rotation",      "type": "segment", "values": ["0","45","90"], "default": "45"},
        {"id": "x_interval",     "label": "X label interval",      "type": "segment", "values": ["Auto","All"], "default": "Auto"},
        {"id": "y_format",       "label": "Y format",              "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
        {"id": "bar_width",      "label": "Bar width",             "type": "segment", "values": ["Auto","Thin","Normal","Wide"], "default": "Auto"},
        {"id": "x_title",        "label": "X axis title",          "type": "entry",   "default": ""},
        {"id": "y_title",        "label": "Y axis title",          "type": "entry",   "default": ""},
    ],
    # ── Legacy plugins ─────────────────────────────────────────────────────────
    "ft_bar_monthly": [
        {"id": "show_values",  "label": "Show values on bars",  "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "stack",        "label": "Stacked bars",         "type": "check",   "default": False},
        {"id": "bar_width",    "label": "Bar width",            "type": "segment", "values": ["Thin","Normal","Wide"], "default": "Normal"},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
        {"id": "y_label",      "label": "Y axis label",         "type": "entry",   "default": ""},
    ],
    "ft_line_trend": [
        {"id": "show_values",  "label": "Show values",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "smooth",       "label": "Smooth line",          "type": "check",   "default": True},
        {"id": "fill_area",    "label": "Fill area under line", "type": "check",   "default": False},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
        {"id": "y_label",      "label": "Y axis label",         "type": "entry",   "default": ""},
    ],
    "ft_stacked_cat": [
        {"id": "show_values",  "label": "Show values",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
    ],
    "ft_pie_cat": [
        {"id": "show_values",  "label": "Show values on slices","type": "check",   "default": False},
        {"id": "donut",        "label": "Donut style",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
    ],
    "ft_bar_ou": [
        {"id": "show_values",  "label": "Show values",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "bar_width",    "label": "Bar width",            "type": "segment", "values": ["Thin","Normal","Wide"], "default": "Normal"},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
    ],
    "ft_scorecard": [
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
    ],
    "ft_line_multi": [
        {"id": "show_values",  "label": "Show values",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "smooth",       "label": "Smooth lines",         "type": "check",   "default": True},
        {"id": "fill_area",    "label": "Fill area",            "type": "check",   "default": False},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
        {"id": "y_label",      "label": "Y axis label",         "type": "entry",   "default": ""},
    ],
    "ft_grouped_bar": [
        {"id": "show_values",  "label": "Show values",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "bar_width",    "label": "Bar width",            "type": "segment", "values": ["Thin","Normal","Wide"], "default": "Normal"},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
    ],
    "ft_combined_bar_line": [
        {"id": "show_values",  "label": "Show values",          "type": "check",   "default": False},
        {"id": "hide_legend",  "label": "Hide legend",          "type": "check",   "default": False},
        {"id": "num_format",   "label": "Number format",        "type": "segment", "values": ["Default","1,234","1.2K","%"], "default": "Default"},
    ],
}


def _option_to_chartjs(opt_id: str, value) -> dict:
    from llm.chart_customizer import deep_merge
    if opt_id == "show_values" and value:
        return {"plugins": {"showValues": {"display": True, "color": "#333", "fontSize": 11}}}
    if opt_id == "hide_legend" and value:
        return {"plugins": {"legend": {"display": False}}}
    if opt_id == "stack" and value:
        return {"scales": {"x": {"stacked": True}, "y": {"stacked": True}}}
    if opt_id == "bar_width":
        w = {"Thin": 14, "Normal": 26, "Wide": 40}.get(value, 26)
        return {"datasets": [{"barThickness": w, "maxBarThickness": w + 8}]}
    if opt_id == "smooth":
        return {"datasets": [{"tension": 0.4 if value else 0}]}
    if opt_id == "fill_area":
        return {"datasets": [{"fill": bool(value)}]}
    if opt_id == "donut" and value:
        return {"cutout": "50%"}
    if opt_id == "y_label" and value:
        return {"scales": {"y": {"title": {"display": True, "text": value}}}}
    if opt_id == "num_format" and value != "Default":
        return {"numFormat": value}
    return {}


class ChartEditorPanel(ctk.CTkFrame):
    def __init__(self, master, callbacks: dict[str, Callable], **kw):
        kw.setdefault("fg_color", PANEL_BG)
        kw.setdefault("corner_radius", 0)
        super().__init__(master, **kw)

        self._callbacks = callbacks
        self._custom_options: dict = {}
        self._chat_history: list[tuple[str, str]] = []
        self._metadata: dict = {}
        self._programs: list[dict] = []
        self._agg_des:  list[dict] = []
        self._current_de_items: list[dict] = []
        self._de_checkboxes: list[tuple[dict, ctk.CTkCheckBox, tk.BooleanVar]] = []
        self._selected_template: dict | None = None
        self._selected_plugin: str | None = None
        self._max_des = 1
        self._min_des = 1
        self._selected_color = COLOR_PRESETS[0][0]
        self._color_btns: list[tuple[str, tk.Frame]] = []
        self._chart_tiles: dict[str, tk.Frame] = {}
        self._quick_options: dict = {}
        self._chart_options: dict = {}
        self._option_vars: dict = {}
        self._ai_chat_visible = False
        self._preview_refresh_id = None

        # New plugin-aware state
        self._metric_rows: list[tuple[dict, ctk.CTkCheckBox, tk.BooleanVar, ctk.CTkOptionMenu | None, tk.StringVar | None]] = []
        self._selected_metrics: list[dict] = []
        self._time_grain_var: tk.StringVar | None = None
        self._breakdown_var: tk.StringVar | None = None
        # Dimensions extras
        self._dimension_var: tk.StringVar | None = None   # single dimension field
        self._filter_rows: list[dict] = []   # each: {frame, de_var, op_var, val_var, de_map}
        self._row_limit_var: tk.StringVar | None = None
        self._sort_by_var: tk.StringVar | None = None
        self._sort_dir_var: tk.StringVar | None = None
        # SelectControl vars (plugin_options: stack_mode, orientation, x_axis, …)
        self._select_vars: dict[str, tk.StringVar] = {}

        self._build()

    # ─── Build ───────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Left controls (full width) ─────────────────────────────────────────
        left = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)
        self._left = left

        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(left, fg_color="#e8eef5", corner_radius=0, height=36)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Chart Editor",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#3a5068").pack(side="left", padx=12, pady=6)
        self._my_charts_btn = ctk.CTkButton(
            hdr, text="📚 My Charts ▶", height=24, width=110,
            fg_color="transparent", hover_color="#d0dde8",
            text_color="#5a7a9a", font=ctk.CTkFont(size=10),
            corner_radius=4, command=self._toggle_my_charts)
        self._my_charts_btn.pack(side="right", padx=8)

        # ── My Charts panel (collapsible) ─────────────────────────────────────
        self._my_charts_panel = ctk.CTkFrame(
            left, fg_color="#f0f4f8",
            border_color=BORDER_CLR, border_width=1, corner_radius=0)
        self._my_charts_panel.grid(row=1, column=0, sticky="ew")
        self._my_charts_panel.grid_columnconfigure(0, weight=1)
        self._my_charts_panel.grid_remove()
        self._my_charts_visible = False
        self._build_my_charts_content(self._my_charts_panel)

        # ── Main scrollable content ────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(
            left, fg_color=PANEL_BG, corner_radius=0,
            scrollbar_button_color="#c0cdd8")
        scroll.grid(row=2, column=0, sticky="nsew")
        # 2-column layout: left = data, right = style+options
        scroll.grid_columnconfigure(0, weight=1, minsize=300)
        scroll.grid_columnconfigure(1, weight=1, minsize=300)
        self._scroll = scroll

        # Row 0: Chart Type — full width
        ct_wrap = tk.Frame(scroll, bg=PANEL_BG)
        ct_wrap.grid(row=0, column=0, columnspan=2, sticky="ew")
        ct_wrap.grid_columnconfigure(0, weight=1)
        self._build_chart_type_section(ct_wrap)

        # 1px horizontal divider between chart type and data/style columns
        tk.Frame(scroll, bg=BORDER_CLR, height=1).grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=8)

        # Left column (rows 2+): Source + Metrics + Dimensions
        src_wrap = tk.Frame(scroll, bg=PANEL_BG)
        src_wrap.grid(row=2, column=0, sticky="new", padx=(0, 4))
        src_wrap.grid_columnconfigure(0, weight=1)
        self._build_source_section(src_wrap)

        metrics_wrap = tk.Frame(scroll, bg=PANEL_BG)
        metrics_wrap.grid(row=3, column=0, sticky="new", padx=(0, 4))
        metrics_wrap.grid_columnconfigure(0, weight=1)
        self._build_metrics_section(metrics_wrap)

        dims_wrap = tk.Frame(scroll, bg=PANEL_BG)
        dims_wrap.grid(row=4, column=0, sticky="new", padx=(0, 4))
        dims_wrap.grid_columnconfigure(0, weight=1)
        self._build_dimensions_section(dims_wrap)

        # Vertical separator between columns
        tk.Frame(scroll, bg=BORDER_CLR, width=1).grid(
            row=2, column=0, rowspan=4, sticky="nse")

        # Right column (rows 2+): Style + Options + AI Chat (merged)
        style_wrap = tk.Frame(scroll, bg=PANEL_BG)
        style_wrap.grid(row=2, column=1, rowspan=4, sticky="new", padx=(4, 0))
        style_wrap.grid_columnconfigure(0, weight=1)
        self._build_style_section(style_wrap)

        self._build_actions(left)

    # ── My Charts panel ────────────────────────────────────────────────────────

    def _build_my_charts_content(self, parent):
        self._mc_scroll = ctk.CTkScrollableFrame(
            parent, fg_color="transparent", corner_radius=0,
            scrollbar_button_color="#c0cdd8", height=80,
            orientation="horizontal")
        self._mc_scroll.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self._mc_empty_lbl = ctk.CTkLabel(
            self._mc_scroll, text="No saved charts yet.",
            font=ctk.CTkFont(size=10), text_color="#8aa3b8")
        self._mc_empty_lbl.pack(padx=8, pady=8)

    def _toggle_my_charts(self):
        self._my_charts_visible = not self._my_charts_visible
        if self._my_charts_visible:
            self._my_charts_panel.grid()
            self._my_charts_btn.configure(text="📚 My Charts ▼")
            self._refresh_my_charts()
        else:
            self._my_charts_panel.grid_remove()
            self._my_charts_btn.configure(text="📚 My Charts ▶")

    def _refresh_my_charts(self):
        from config.chart_library import load_charts
        for w in self._mc_scroll.winfo_children():
            w.destroy()
        charts = load_charts()
        if not charts:
            ctk.CTkLabel(self._mc_scroll, text="No saved charts yet.",
                         font=ctk.CTkFont(size=10), text_color="#8aa3b8"
                         ).pack(padx=8, pady=8)
            return
        for chart in charts:
            self._build_my_chart_card(chart)

    def _build_my_chart_card(self, chart: dict):
        card = ctk.CTkFrame(
            self._mc_scroll, fg_color="white",
            border_color=BORDER_CLR, border_width=1, corner_radius=6,
            width=130)
        card.pack(side="left", padx=3, pady=3, fill="y")
        card.pack_propagate(False)

        tmpl_icon = next((t["icon"] for t in FIXED_TEMPLATES
                          if t["id"] == chart.get("template_id")), "📊")
        name = (chart.get("name") or chart.get("title", "?"))[:16]
        ctk.CTkLabel(card, text=f"{tmpl_icon} {name}",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#1e2d3d", wraplength=118, justify="left"
                     ).pack(padx=6, pady=(5, 1), anchor="w")
        ctk.CTkLabel(card,
                     text=chart.get("template_label", "")[:20],
                     font=ctk.CTkFont(size=9), text_color="#8aa3b8"
                     ).pack(padx=6, anchor="w")
        ctk.CTkButton(
            card, text="Load ↩", height=22, width=80,
            fg_color=DHIS2_BLUE, hover_color="#155a8a",
            font=ctk.CTkFont(size=10),
            command=lambda c=chart: self._load_chart_config(c)
        ).pack(padx=6, pady=(3, 6), anchor="w")

    def _load_chart_config(self, chart: dict):
        tmpl = next((t for t in FIXED_TEMPLATES
                     if t["id"] == chart.get("template_id")), None)
        if tmpl:
            self._on_chart_type_click(tmpl)

        self._title_entry.delete(0, "end")
        self._title_entry.insert(0, chart.get("title") or chart.get("name", ""))

        color = chart.get("chart_color")
        if color:
            self._on_color_select(color)

        col_seg = {12: "Full", 6: "Half", 4: "Third"}
        self._col_width_var.set(col_seg.get(chart.get("col_width", 6), "Half"))

        self._custom_options = dict(chart.get("custom_options", {}))
        if self._custom_options:
            self._chat_display_text = "AI customizations loaded from saved chart.\n"
            self._chat_display.configure(state="normal")
            self._chat_display.delete("1.0", "end")
            self._chat_display.insert("end", self._chat_display_text)
            self._chat_display.configure(state="disabled")

        sources = chart.get("de_sources", [])
        if sources:
            first_de = sources[0]
            de_type = first_de.get("type", "")
            prog_name = first_de.get("prog_name", "")
            if de_type in ("tracker_option", "tracker_numeric") and prog_name:
                self._src_prog_var.set(True)
                self._src_agg_var.set(False)
                prog = next((p for p in self._programs
                             if p["displayName"] == prog_name), None)
                if prog:
                    self._prog_var.set(prog_name)
                    self._on_prog_selected()
            elif de_type == "aggregate":
                self._src_prog_var.set(False)
                self._src_agg_var.set(True)
                self._on_src_check()

            saved_uids = {d.get("uid") for d in sources}
            self.after(100, lambda: self._try_select_saved_des(saved_uids))

    def _try_select_saved_des(self, uids: set):
        for de, _, var in self._de_checkboxes:
            if de["uid"] in uids:
                var.set(True)
        self._on_de_check()

    # ── 1. Chart Type section (bigger tiles, 4 cols) ───────────────────────────

    def _build_chart_type_section(self, parent):
        self._sec_lbl(parent, 0, "1. Chart Type")

        outer = ctk.CTkFrame(parent, fg_color="white",
                              border_color=BORDER_CLR, border_width=1, corner_radius=8)
        outer.grid(row=1, column=0, padx=10, pady=(2, 8), sticky="ew")
        outer.grid_columnconfigure(0, weight=1)

        # Collapsed summary row (shown after selection)
        self._chart_sel_row = tk.Frame(outer, bg="white")
        self._chart_sel_row.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 4))
        self._chart_sel_row.grid_remove()
        self._chart_sel_row.grid_columnconfigure(0, weight=1)

        self._chart_sel_lbl = tk.Label(
            self._chart_sel_row, text="", font=("Segoe UI", 11, "bold"),
            fg=DHIS2_BLUE, bg="white", anchor="w")
        self._chart_sel_lbl.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            self._chart_sel_row, text="Change ▼", width=80, height=26,
            fg_color="#e8eef5", hover_color="#d0dde8",
            text_color="#5a7a9a", border_width=1, border_color=BORDER_CLR,
            font=ctk.CTkFont(size=10),
            command=self._expand_chart_grid
        ).grid(row=0, column=1, padx=(8, 0))

        # Expanded grid (shown by default, collapses after pick)
        self._chart_grid_outer = tk.Frame(outer, bg="white")
        self._chart_grid_outer.grid(row=1, column=0, padx=8, pady=(6, 8), sticky="ew")

        self._chart_info_lbl = tk.Label(
            self._chart_grid_outer,
            text="← Select a chart type to begin",
            font=("Segoe UI", 9), fg="#8aa3b8", bg="white", anchor="w")
        self._chart_info_lbl.pack(anchor="w", padx=2, pady=(0, 6))

        # 4 columns, larger tiles
        COLS = 4
        CW, CH = 88, 56
        grid_frame = tk.Frame(self._chart_grid_outer, bg="white")
        grid_frame.pack(anchor="w")

        visible = [t for t in FIXED_TEMPLATES
                   if not (t.get("plugin") and getattr(t["plugin"], "hidden", False))]
        for i, tmpl in enumerate(visible):
            r, c = divmod(i, COLS)
            tile = tk.Frame(grid_frame, bg="white", cursor="hand2",
                             relief="flat", bd=0,
                             highlightbackground=BORDER_CLR,
                             highlightthickness=1)
            tile.grid(row=r, column=c, padx=2, pady=2)

            cvs = tk.Canvas(tile, width=CW, height=CH, bg="#f0f4f8",
                             highlightthickness=0)
            cvs.pack(padx=1, pady=(2, 0))
            draw_chart_preview(cvs, tmpl.get("preview_id", "bar_monthly"),
                                2, 2, CW - 4, CH - 4)

            lbl = tk.Label(tile, text=f"{tmpl['icon']} {tmpl['label'][:13]}",
                            font=("Segoe UI", 8), fg="#3a5068", bg="white",
                            anchor="center", wraplength=CW - 4)
            lbl.pack(padx=1, pady=(2, 3))

            for w in (tile, cvs, lbl):
                w.bind("<Button-1>",
                       lambda e, t=tmpl: self._on_chart_type_click(t))
                w.bind("<Enter>",
                       lambda e, f=tile: self._tile_hover(f, True))
                w.bind("<Leave>",
                       lambda e, f=tile, tid=tmpl["id"]:
                       self._tile_hover(f, False, tid))

            self._chart_tiles[tmpl["id"]] = tile

    def _tile_hover(self, tile: tk.Frame, entering: bool, tid: str = ""):
        if entering:
            tile.config(bg="#e8f0f8")
            for w in tile.winfo_children():
                if isinstance(w, (tk.Canvas, tk.Label)):
                    w.config(bg="#e8f0f8")
        else:
            sel = self._selected_template
            if sel and sel["id"] == tid:
                return  # keep highlighted
            tile.config(bg="white")
            for w in tile.winfo_children():
                if isinstance(w, (tk.Canvas, tk.Label)):
                    w.config(bg="white")

    def _collapse_chart_grid(self):
        tmpl = self._selected_template
        if not tmpl:
            return
        self._chart_grid_outer.grid_remove()
        self._chart_sel_lbl.config(text=f"{tmpl['icon']}  {tmpl['label']}")
        self._chart_info_lbl.config(text=tmpl.get("description", "")[:60])
        self._chart_sel_row.grid()

    def _expand_chart_grid(self):
        self._chart_sel_row.grid_remove()
        self._chart_grid_outer.grid()

    # ── 2. Source section (full-width) ─────────────────────────────────────────

    def _build_source_section(self, parent):
        self._sec_lbl(parent, 0, "2. Source")

        outer = ctk.CTkFrame(parent, fg_color="white",
                              border_color=BORDER_CLR, border_width=1, corner_radius=8)
        outer.grid(row=1, column=0, padx=10, pady=(2, 8), sticky="ew")
        outer.grid_columnconfigure(0, weight=1)

        # Checkboxes row
        cb_row = ctk.CTkFrame(outer, fg_color="transparent")
        cb_row.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="w")

        self._src_prog_var = tk.BooleanVar(value=True)
        self._src_agg_var  = tk.BooleanVar(value=False)
        self._src_prog_cb  = ctk.CTkCheckBox(
            cb_row, text="Program (Tracker)",
            variable=self._src_prog_var, font=ctk.CTkFont(size=12),
            command=self._on_src_check)
        self._src_prog_cb.pack(side="left", padx=(0, 20))
        self._src_agg_cb = ctk.CTkCheckBox(
            cb_row, text="Aggregate Dataset",
            variable=self._src_agg_var, font=ctk.CTkFont(size=12),
            command=self._on_src_check)
        self._src_agg_cb.pack(side="left")

        # Dropdowns (full width)
        pf = ctk.CTkFrame(outer, fg_color="transparent")
        pf.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="ew")
        pf.grid_columnconfigure(0, weight=1)

        self._prog_var = tk.StringVar(value="—")
        self._prog_menu = ctk.CTkOptionMenu(
            pf, variable=self._prog_var, values=["—"],
            height=30, font=ctk.CTkFont(size=11),
            fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d",
            command=self._on_prog_selected)
        self._prog_menu.grid(row=0, column=0, sticky="ew")

        self._stage_var = tk.StringVar(value="—")
        self._stage_menu = ctk.CTkOptionMenu(
            pf, variable=self._stage_var, values=["—"],
            height=30, font=ctk.CTkFont(size=11),
            fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d",
            command=self._on_stage_selected)
        self._stage_menu.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        self._agg_search_var = tk.StringVar()
        self._agg_search_var.trace_add("write", lambda *_: self._refresh_metrics_display())
        self._agg_search_entry = ctk.CTkEntry(
            pf, textvariable=self._agg_search_var,
            placeholder_text="🔍 Search aggregate DEs...", height=30,
            font=ctk.CTkFont(size=11))
        self._agg_search_entry.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self._agg_search_entry.grid_remove()

    # ── 3. Metrics section ─────────────────────────────────────────────────────

    def _build_metrics_section(self, parent):
        self._metrics_section_lbl = ctk.CTkLabel(
            parent, text="3. METRICS  (TICK 1)",
            font=ctk.CTkFont(size=9, weight="bold"), text_color="#8aa3b8")
        self._metrics_section_lbl.grid(row=0, column=0, padx=12, pady=(6, 2), sticky="w")

        metrics_outer = ctk.CTkFrame(parent, fg_color="white",
                                     border_color=BORDER_CLR, border_width=1, corner_radius=8)
        metrics_outer.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="ew")
        metrics_outer.grid_columnconfigure(0, weight=1)

        # Search bar
        de_sr = ctk.CTkFrame(metrics_outer, fg_color="white")
        de_sr.grid(row=0, column=0, sticky="ew", padx=4, pady=(6, 0))
        de_sr.grid_columnconfigure(0, weight=1)
        self._de_search_var = tk.StringVar()
        self._de_search_var.trace_add(
            "write",
            lambda *_: self._populate_de_list(
                [i for i in self._current_de_items
                 if self._de_search_var.get().strip().lower() in i["name"].lower()],
                {de["uid"] for de, _, v in self._de_checkboxes if v.get()}))
        ctk.CTkEntry(de_sr, textvariable=self._de_search_var,
                     placeholder_text="🔍 Filter DEs...", height=26,
                     font=ctk.CTkFont(size=10)).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(de_sr, text="✕", width=26, height=26,
                      fg_color="#e8eef5", hover_color="#d0dde8",
                      text_color="#5a7a9a", font=ctk.CTkFont(size=10),
                      command=lambda: self._de_search_var.set("")
                      ).grid(row=0, column=1, padx=(2, 0))

        self._metrics_scroll = ctk.CTkScrollableFrame(
            metrics_outer, fg_color="white", corner_radius=0,
            scrollbar_button_color="#c0cdd8", height=140)
        self._metrics_scroll.grid(row=1, column=0, sticky="ew", padx=2, pady=(2, 4))
        self._metrics_scroll.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self._metrics_scroll, text="Select chart type first",
                     font=ctk.CTkFont(size=10), text_color="#8aa3b8"
                     ).grid(row=0, column=0, pady=12)

        # Keep _de_scroll as alias for backward compat with _clear_de_list / _populate_de_list
        self._de_scroll = self._metrics_scroll

        self._sel_lbl = ctk.CTkLabel(
            parent, text="", font=ctk.CTkFont(size=10),
            text_color="#1565c0", fg_color="transparent",
            wraplength=400, justify="left")
        self._sel_lbl.grid(row=2, column=0, padx=10, pady=(0, 4), sticky="w")

        # Keep _de_section_lbl as alias for backward compat
        self._de_section_lbl = self._metrics_section_lbl

    # ── Dimensions section ─────────────────────────────────────────────────────

    def _build_dimensions_section(self, parent):
        ctk.CTkLabel(parent, text="DIMENSIONS",
                     font=ctk.CTkFont(size=9, weight="bold"), text_color="#8aa3b8"
                     ).grid(row=0, column=0, padx=12, pady=(6, 2), sticky="w")

        dims_outer = ctk.CTkFrame(parent, fg_color="white",
                                   border_color=BORDER_CLR, border_width=1, corner_radius=8)
        dims_outer.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="ew")
        dims_outer.grid_columnconfigure(0, weight=1)

        # ── SelectControls (stack_mode / orientation / x_axis — from plugin.options) ──
        self._select_controls_frame = tk.Frame(dims_outer, bg="white")
        self._select_controls_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(4, 0))
        self._select_controls_frame.grid_remove()  # hidden until plugin has options

        # ── Time grain (hidden until plugin has time_grain) ────────────────────
        self._time_grain_row = tk.Frame(dims_outer, bg="white")
        self._time_grain_row.grid(row=1, column=0, sticky="ew", padx=8, pady=(2, 2))
        self._time_grain_row.grid_columnconfigure(1, weight=1)
        tk.Label(self._time_grain_row, text="Time grain:", font=("Segoe UI", 9),
                 fg="#5a7a9a", bg="white").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._time_grain_var = tk.StringVar(value="Monthly")
        ctk.CTkSegmentedButton(
            self._time_grain_row, values=["Monthly", "Quarterly", "Yearly"],
            variable=self._time_grain_var,
            height=24, font=ctk.CTkFont(size=10),
            fg_color="#e8eef5",
            selected_color=DHIS2_BLUE, selected_hover_color="#155a8a",
            unselected_color="#e8eef5", unselected_hover_color="#d0dde8",
            text_color="#3a5068",
        ).grid(row=0, column=1, sticky="w")
        self._time_grain_row.grid_remove()

        # ── Dimension — single field picker (option-set DE → split/breakdown) ───
        self._dimension_row = tk.Frame(dims_outer, bg="white")
        self._dimension_row.grid(row=2, column=0, sticky="ew", padx=8, pady=(2, 4))
        self._dimension_row.grid_columnconfigure(1, weight=1)
        tk.Label(self._dimension_row, text="Dimension:", font=("Segoe UI", 9),
                 fg="#5a7a9a", bg="white").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._dimension_var = tk.StringVar(value="—")
        self._dimension_menu = ctk.CTkOptionMenu(
            self._dimension_row, variable=self._dimension_var, values=["—"],
            height=26, font=ctk.CTkFont(size=10),
            fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d")
        self._dimension_menu.grid(row=0, column=1, sticky="ew")
        self._dim_hint_lbl = tk.Label(
            self._dimension_row,
            text="", font=("Segoe UI", 8), fg="#8aa3b8", bg="white")
        self._dim_hint_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(1, 0))
        self._dimension_row.grid_remove()

        # ── Filters ────────────────────────────────────────────────────────────
        tk.Frame(dims_outer, bg=BORDER_CLR, height=1).grid(
            row=3, column=0, sticky="ew", padx=8, pady=(4, 0))
        filter_hdr = tk.Frame(dims_outer, bg="white")
        filter_hdr.grid(row=4, column=0, sticky="ew", padx=8, pady=(2, 0))
        filter_hdr.grid_columnconfigure(0, weight=1)
        tk.Label(filter_hdr, text="Filters", font=("Segoe UI", 8, "bold"),
                 fg="#8aa3b8", bg="white").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            filter_hdr, text="+ Add filter", width=80, height=20,
            fg_color="transparent", border_width=1, border_color="#c5d3e0",
            text_color="#5a7a9a", hover_color="#f0f4f8",
            font=ctk.CTkFont(size=9),
            command=self._add_filter_row
        ).grid(row=0, column=1)
        self._filter_rows_frame = tk.Frame(dims_outer, bg="white")
        self._filter_rows_frame.grid(row=5, column=0, sticky="ew", padx=8, pady=(2, 0))
        self._filter_rows_frame.grid_columnconfigure(1, weight=1)

        # ── Options (row limit + sort) ─────────────────────────────────────────
        tk.Frame(dims_outer, bg=BORDER_CLR, height=1).grid(
            row=6, column=0, sticky="ew", padx=8, pady=(4, 0))
        opts = tk.Frame(dims_outer, bg="white")
        opts.grid(row=7, column=0, sticky="ew", padx=8, pady=(4, 8))
        tk.Label(opts, text="Limit:", font=("Segoe UI", 9), fg="#5a7a9a", bg="white"
                 ).grid(row=0, column=0, sticky="w", padx=(0, 2))
        self._row_limit_var = tk.StringVar(value="All")
        ctk.CTkOptionMenu(
            opts, variable=self._row_limit_var,
            values=["10", "20", "50", "100", "200", "All"],
            width=64, height=22, font=ctk.CTkFont(size=9),
            fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d"
        ).grid(row=0, column=1, padx=(0, 10))
        tk.Label(opts, text="Sort:", font=("Segoe UI", 9), fg="#5a7a9a", bg="white"
                 ).grid(row=0, column=2, sticky="w", padx=(0, 2))
        self._sort_by_var = tk.StringVar(value="None")
        ctk.CTkOptionMenu(
            opts, variable=self._sort_by_var, values=["None", "Value", "Label"],
            width=72, height=22, font=ctk.CTkFont(size=9),
            fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d"
        ).grid(row=0, column=3, padx=(0, 4))
        self._sort_dir_var = tk.StringVar(value="Desc")
        ctk.CTkOptionMenu(
            opts, variable=self._sort_dir_var, values=["Desc", "Asc"],
            width=60, height=22, font=ctk.CTkFont(size=9),
            fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d"
        ).grid(row=0, column=4)

        # ── Backward-compat: keep breakdown_var for _build_config ─────────────
        self._breakdown_var = tk.StringVar(value="—")

    # ── 4. Style & Options (merged) + AI Chat ──────────────────────────────────

    def _build_style_section(self, parent):
        self._sec_lbl(parent, 0, "4. Style & Options")

        # ── Color row ──────────────────────────────────────────────────────────
        tk.Label(parent, text="Color", font=("Segoe UI", 9),
                 fg="#5a7a9a", bg=PANEL_BG).grid(row=1, column=0, padx=12, pady=(4, 0), sticky="w")
        cf = tk.Frame(parent, bg=PANEL_BG)
        cf.grid(row=2, column=0, padx=12, pady=(0, 4), sticky="w")
        for i, (hex_c, _) in enumerate(COLOR_PRESETS):
            b = tk.Frame(cf, bg=hex_c, width=20, height=20, cursor="hand2",
                          highlightthickness=2, highlightbackground=hex_c)
            b.grid(row=0, column=i, padx=1)
            b.bind("<Button-1>", lambda e, c=hex_c: self._on_color_select(c))
            b.grid_propagate(False)
            self._color_btns.append((hex_c, b))
        self._on_color_select(self._selected_color)

        # ── Title + Col width ──────────────────────────────────────────────────
        row_b = tk.Frame(parent, bg=PANEL_BG)
        row_b.grid(row=3, column=0, padx=12, pady=(0, 4), sticky="ew")
        row_b.grid_columnconfigure(0, weight=1)

        tk.Label(row_b, text="Title", font=("Segoe UI", 9),
                 fg="#5a7a9a", bg=PANEL_BG).grid(row=0, column=0, sticky="w")
        self._title_entry = ctk.CTkEntry(
            row_b, height=26, font=ctk.CTkFont(size=11),
            placeholder_text="Auto from DE name")
        self._title_entry.grid(row=1, column=0, sticky="ew", pady=(0, 4))

        tk.Label(row_b, text="Col width", font=("Segoe UI", 9),
                 fg="#5a7a9a", bg=PANEL_BG).grid(row=2, column=0, sticky="w")
        self._col_width_var = tk.StringVar(value="Half")
        ctk.CTkSegmentedButton(
            row_b, values=["Full", "Half", "Third"],
            variable=self._col_width_var,
            height=22, font=ctk.CTkFont(size=10),
            fg_color="#e8eef5",
            selected_color=DHIS2_BLUE, selected_hover_color="#155a8a",
            unselected_color="#e8eef5", unselected_hover_color="#d0dde8",
            text_color="#3a5068",
        ).grid(row=3, column=0, sticky="w", pady=(0, 4))

        # ── Mode ───────────────────────────────────────────────────────────────
        mg = tk.Frame(parent, bg=PANEL_BG)
        mg.grid(row=4, column=0, padx=12, pady=(0, 4), sticky="w")
        tk.Label(mg, text="Mode", font=("Segoe UI", 9),
                 fg="#5a7a9a", bg=PANEL_BG).pack(anchor="w")
        self._mode_var = tk.StringVar(value="fixed")
        mf = tk.Frame(mg, bg=PANEL_BG)
        mf.pack(anchor="w")
        ctk.CTkRadioButton(mf, text="Fixed", variable=self._mode_var,
                            value="fixed", font=ctk.CTkFont(size=10),
                            command=self._on_mode_change).pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(mf, text="AI", variable=self._mode_var,
                            value="ai", font=ctk.CTkFont(size=10),
                            command=self._on_mode_change).pack(side="left")

        self._ai_desc = ctk.CTkTextbox(
            parent, height=32, font=ctk.CTkFont(size=10), wrap="word")
        self._ai_desc.grid(row=5, column=0, padx=10, pady=(0, 4), sticky="ew")
        self._ai_desc.grid_remove()

        # ── Chart Options (merged, no separate header) ─────────────────────────
        ctk.CTkFrame(parent, height=1, fg_color=BORDER_CLR,
                     corner_radius=0).grid(row=6, column=0, sticky="ew", padx=8, pady=(4, 0))
        self._chart_opts_hdr = ctk.CTkLabel(
            parent, text="CHART OPTIONS",
            font=ctk.CTkFont(size=9, weight="bold"), text_color="#8aa3b8")
        self._chart_opts_hdr.grid(row=7, column=0, padx=12, pady=(5, 0), sticky="w")

        self._dyn_opts_frame = tk.Frame(parent, bg=PANEL_BG)
        self._dyn_opts_frame.grid(row=8, column=0, padx=12, pady=(2, 4), sticky="ew")
        tk.Label(self._dyn_opts_frame, text="← Select a chart type",
                 font=("Segoe UI", 9), fg="#8aa3b8", bg=PANEL_BG).pack(anchor="w")

        # ── AI Chat (collapsible) ──────────────────────────────────────────────
        self._ai_chat_toggle_btn = ctk.CTkButton(
            parent, text="🤖  AI Customize  ▶", height=28, anchor="w",
            fg_color="transparent", hover_color="#e8eef5",
            text_color=DHIS2_BLUE, font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=0, command=self._toggle_ai_chat)
        self._ai_chat_toggle_btn.grid(row=10, column=0, padx=4, pady=(2, 0), sticky="ew")

        self._ai_chat_panel = ctk.CTkFrame(parent, fg_color="transparent")
        self._ai_chat_panel.grid(row=11, column=0, padx=10, pady=(2, 10), sticky="ew")
        self._ai_chat_panel.grid_columnconfigure(0, weight=1)
        self._ai_chat_panel.grid_remove()

        self._chat_display = ctk.CTkTextbox(
            self._ai_chat_panel, height=64, font=ctk.CTkFont(size=10),
            fg_color="#f8fafc", border_color=BORDER_CLR, border_width=1,
            text_color="#2c3e50", state="disabled", wrap="word")
        self._chat_display.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 3))
        self._chat_display_text = ""

        inp = ctk.CTkFrame(self._ai_chat_panel, fg_color="transparent")
        inp.grid(row=1, column=0, sticky="ew")
        inp.grid_columnconfigure(0, weight=1)
        self._ai_input = ctk.CTkEntry(
            inp, height=26, font=ctk.CTkFont(size=10),
            placeholder_text="show labels, thinner bars, no grid…")
        self._ai_input.grid(row=0, column=0, sticky="ew")
        self._ai_input.bind("<Return>", lambda e: self._on_ai_customize())
        ctk.CTkButton(inp, text="Send", width=52, height=26,
                      fg_color=DHIS2_BLUE, hover_color="#155a8a",
                      font=ctk.CTkFont(size=10),
                      command=self._on_ai_customize
                      ).grid(row=0, column=1, padx=(4, 0))

        ctk.CTkButton(
            self._ai_chat_panel, text="↺ Reset all", height=22,
            fg_color="transparent", border_width=1, border_color="#e74c3c",
            text_color="#e74c3c", hover_color="#fdecea",
            font=ctk.CTkFont(size=9),
            command=self._on_reset_customization
        ).grid(row=2, column=0, pady=(4, 0), sticky="w")

    def _toggle_ai_chat(self):
        self._ai_chat_visible = not self._ai_chat_visible
        if self._ai_chat_visible:
            self._ai_chat_panel.grid()
            self._ai_chat_toggle_btn.configure(text="🤖  AI Customize  ▼")
        else:
            self._ai_chat_panel.grid_remove()
            self._ai_chat_toggle_btn.configure(text="🤖  AI Customize  ▶")

    # ── Action buttons ──────────────────────────────────────────────────────────

    def _build_actions(self, parent):
        bar = ctk.CTkFrame(parent, fg_color="#e8eef5", corner_radius=0, height=46)
        bar.grid(row=3, column=0, sticky="ew")
        bar.grid_propagate(False)

        btn_row = ctk.CTkFrame(bar, fg_color="transparent")
        btn_row.pack(side="left", padx=10, pady=8)

        ctk.CTkButton(
            btn_row, text="💾 Save", width=90, height=30,
            fg_color="#8e44ad", hover_color="#6c3483",
            font=ctk.CTkFont(size=12),
            command=self._on_save).pack(side="left")

        ctk.CTkButton(
            btn_row, text="+ Add to Dashboard", height=30,
            fg_color="#27ae60", hover_color="#1e8449",
            font=ctk.CTkFont(size=12),
            command=self._on_add_to_dashboard).pack(side="left", padx=(6, 0))

        ctk.CTkButton(
            btn_row, text="🌐 Preview in Browser", height=30,
            fg_color="transparent", border_width=1, border_color=DHIS2_BLUE,
            text_color=DHIS2_BLUE, hover_color="#e8f0f8",
            font=ctk.CTkFont(size=12),
            command=self._on_preview_browser).pack(side="left", padx=(6, 0))

    # ─── Metadata ────────────────────────────────────────────────────────────────

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
            os_data = de.get("optionSet") or {}
            options = [
                {"code": o.get("code", ""), "name": o.get("displayName", o.get("code", ""))}
                for o in os_data.get("options", [])
            ]
            sm[sid]["des"].append({
                "uid": de["id"], "name": de.get("displayName", de["id"]),
                "type": "tracker_option" if os_data else "tracker_numeric",
                "prog_uid": pid, "prog_name": pname,
                "stage_uid": sid, "stage_name": sname,
                "options": options,   # baked option values — empty list for numeric DEs
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

        names = ["— Select program —"] + [p["displayName"] for p in self._programs]
        self._prog_menu.configure(values=names)
        self._prog_var.set(names[0])
        self._stage_var.set("—")
        self._stage_menu.configure(values=["—"])

    # ─── Source logic ─────────────────────────────────────────────────────────────

    def _on_src_check(self):
        prog = self._src_prog_var.get()
        agg  = self._src_agg_var.get()
        if prog:
            self._prog_menu.grid()
            self._stage_menu.grid()
        else:
            self._prog_menu.grid_remove()
            self._stage_menu.grid_remove()
        if agg:
            self._agg_search_entry.grid()
        else:
            self._agg_search_entry.grid_remove()
            self._agg_search_var.set("")
        if not prog and not agg:
            self._clear_de_list()
        else:
            self._refresh_metrics_display()  # updates _current_de_items + builds widgets once

    def _on_prog_selected(self, _=None):
        prog = next((p for p in self._programs
                     if p["displayName"] == self._prog_var.get()), None)
        if not prog:
            self._refresh_de_list()
            return
        self._current_prog = prog
        names = ["— All stages —"] + [s["displayName"] for s in prog["stages"]]
        self._stage_menu.configure(values=names)
        self._stage_var.set(names[0])
        self._refresh_de_list()

    def _on_stage_selected(self, _=None):
        # Update data immediately, defer widget build to after UI settles
        self._refresh_de_list()
        self.after_idle(self._refresh_metrics_display)
        self.after_idle(self._refresh_dimensions_display)

    def _refresh_de_list(self):
        """Update _current_de_items from current source selection. No widget creation."""
        for_types = self._selected_template["for_types"] if self._selected_template else \
                    {"tracker_option", "tracker_numeric", "aggregate"}
        items: list[dict] = []
        if self._src_prog_var.get():
            prog = getattr(self, "_current_prog", None)
            if prog:
                sname = self._stage_var.get()
                if sname in ("— All stages —", "—", ""):
                    prog_des = [de for s in prog["stages"] for de in s["des"]]
                else:
                    stage = next((s for s in prog["stages"]
                                  if s["displayName"] == sname), None)
                    prog_des = stage["des"] if stage else []
                items.extend(de for de in prog_des if de["type"] in for_types)
        if self._src_agg_var.get():
            q = self._agg_search_var.get().strip().lower()
            items.extend(de for de in self._agg_des
                         if "aggregate" in for_types and (not q or q in de["name"].lower()))
        self._current_de_items = items

    # ─── Chart type selection ──────────────────────────────────────────────────────

    def _on_chart_type_click(self, tmpl: dict):
        self._selected_template = tmpl
        self._min_des = tmpl.get("min_sources", 1)
        self._max_des = tmpl.get("max_sources", 1 if not tmpl.get("multi") else 3)

        # Extract plugin from template
        plugin = tmpl.get("plugin")
        self._selected_plugin = plugin

        if self._min_des == self._max_des:
            lbl = str(self._max_des)
        else:
            lbl = f"{self._min_des}–{self._max_des}"
        self._metrics_section_lbl.configure(text=f"3. METRICS  (tick {lbl})")
        self._chart_info_lbl.configure(
            text=tmpl.get("description", ""), fg="#5a7a9a")

        prog_ok = bool({"tracker_option", "tracker_numeric"} & tmpl["for_types"])
        agg_ok  = "aggregate" in tmpl["for_types"]
        self._src_prog_cb.configure(state="normal" if prog_ok else "disabled")
        self._src_agg_cb.configure(state="normal" if agg_ok else "disabled")
        if not prog_ok:
            self._src_prog_var.set(False)
        if not agg_ok:
            self._src_agg_var.set(False)
        if not self._src_prog_var.get() and not self._src_agg_var.get():
            if prog_ok:
                self._src_prog_var.set(True)
            elif agg_ok:
                self._src_agg_var.set(True)

        # Enforce DE max
        sel = self._get_selected_des()
        if len(sel) > self._max_des:
            count = 0
            for _, _, v in self._de_checkboxes:
                if v.get():
                    count += 1
                    if count > self._max_des:
                        v.set(False)

        # Highlight selected tile
        for tid, tile in self._chart_tiles.items():
            if tid == tmpl["id"]:
                tile.config(highlightbackground=DHIS2_BLUE, highlightthickness=2)
                tile.config(bg="#e8f0f8")
                for w in tile.winfo_children():
                    if isinstance(w, (tk.Canvas, tk.Label)):
                        w.config(bg="#e8f0f8")
            else:
                tile.config(highlightbackground=BORDER_CLR, highlightthickness=1, bg="white")
                for w in tile.winfo_children():
                    if isinstance(w, (tk.Canvas, tk.Label)):
                        w.config(bg="white")

        self._on_src_check()
        self._collapse_chart_grid()
        self._rebuild_chart_options()
        self._refresh_metrics_display()
        self._refresh_dimensions_display()
        self._auto_preview()

    def _restore_tile_bg(self, tile: tk.Frame, tid: str):
        sel = self._selected_template
        if sel and sel["id"] == tid:
            return
        tile.config(bg="white")
        for w in tile.winfo_children():
            if isinstance(w, (tk.Canvas, tk.Label)):
                w.config(bg="white")

    # ─── Metrics display ──────────────────────────────────────────────────────────

    def _refresh_metrics_display(self):
        """Rebuild metrics_scroll content based on current plugin + available DEs."""
        # Rebuild DE list first so _de_checkboxes is current
        self._refresh_de_list()

        # Clear and rebuild metric_rows in the scroll
        for w in self._metrics_scroll.winfo_children():
            w.destroy()
        self._metric_rows = []

        if not self._current_de_items:
            ctk.CTkLabel(self._metrics_scroll, text="Select source first",
                         font=ctk.CTkFont(size=10), text_color="#8aa3b8"
                         ).grid(row=0, column=0, pady=12)
            return

        # Rebuild checkboxes with optional agg picker
        existing_checked = {de["uid"] for de, _, v in self._de_checkboxes if v.get()}
        self._de_checkboxes = []

        for i, de in enumerate(self._current_de_items):
            var = tk.BooleanVar(value=de["uid"] in existing_checked)

            row_frame = tk.Frame(self._metrics_scroll, bg="white")
            row_frame.grid(row=i, column=0, sticky="ew", padx=2, pady=1)
            row_frame.grid_columnconfigure(0, weight=1)

            cb = ctk.CTkCheckBox(
                row_frame, text=de["name"], variable=var,
                font=ctk.CTkFont(size=10), checkbox_width=14, checkbox_height=14,
                command=self._on_de_check)
            cb.grid(row=0, column=0, sticky="w", padx=(4, 2))

            # Agg picker: shown for numeric types, hidden for tracker_option
            de_type = de.get("type", "")
            needs_agg = de_type in ("tracker_numeric", "aggregate", "indicator")
            agg_var: tk.StringVar | None = None
            agg_menu: ctk.CTkOptionMenu | None = None

            if needs_agg:
                agg_var = tk.StringVar(value="SUM")
                agg_menu = ctk.CTkOptionMenu(
                    row_frame, variable=agg_var,
                    values=["SUM", "COUNT", "AVG", "MIN", "MAX"],
                    width=80, height=22, font=ctk.CTkFont(size=9),
                    fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d",
                    command=lambda _: self._on_de_check())
                agg_menu.grid(row=0, column=1, padx=(2, 4), sticky="e")

            self._de_checkboxes.append((de, cb, var))
            self._metric_rows.append((de, cb, var, agg_menu, agg_var))

    # ─── Dimensions display ────────────────────────────────────────────────────────

    def _refresh_dimensions_display(self):
        """Update SelectControls, time grain visibility, dimension picker, filter lists."""
        plugin_cls = self._selected_template.get("plugin") if self._selected_template else None

        # ── SelectControls (stack_mode, orientation, x_axis …) ─────────────────
        for w in self._select_controls_frame.winfo_children():
            w.destroy()
        if plugin_cls and getattr(plugin_cls, "options", []):
            self._select_controls_frame.grid()
            old_vals = {k: v.get() for k, v in self._select_vars.items()}
            self._select_vars = {}
            for sc in plugin_cls.options:
                prev = old_vals.get(sc.id, sc.default)
                val  = prev if prev in sc.choices else sc.default
                var  = tk.StringVar(value=val)
                self._select_vars[sc.id] = var
                row = tk.Frame(self._select_controls_frame, bg="white")
                row.pack(anchor="w", fill="x", pady=1)
                tk.Label(row, text=sc.label + ":", font=("Segoe UI", 9),
                         fg="#5a7a9a", bg="white").pack(side="left", padx=(0, 6))
                ctk.CTkSegmentedButton(
                    row, values=list(sc.choices), variable=var,
                    height=22, font=ctk.CTkFont(size=10),
                    fg_color="#e8eef5",
                    selected_color=DHIS2_BLUE, selected_hover_color="#155a8a",
                    unselected_color="#e8eef5", unselected_hover_color="#d0dde8",
                    text_color="#3a5068",
                    command=lambda *_: self._on_select_control_change(),
                ).pack(side="left")
        else:
            self._select_controls_frame.grid_remove()
            self._select_vars = {}

        has_time_grain = False
        if plugin_cls:
            has_time_grain = plugin_cls.time_grain is not None
        elif self._selected_template:
            tid = self._selected_template.get("id", "")
            has_time_grain = any(x in tid for x in (
                "monthly", "trend", "line", "multi", "stacked", "grouped", "combined"))

        # Time grain
        if has_time_grain:
            self._time_grain_row.grid()
        else:
            self._time_grain_row.grid_remove()

        # Dimension dropdown — always show when a chart type is selected.
        # Plugin's dimensions list provides a hint; picker is optional for all chart types.
        dim_hint = ""
        if plugin_cls and plugin_cls.dimensions:
            dim_hint = plugin_cls.dimensions[0].hint
        elif self._selected_template:
            tid = self._selected_template.get("id", "")
            if "stacked" in tid:
                dim_hint = "Each option value becomes one stack layer"
            elif "pie" in tid:
                dim_hint = "Each option value becomes one pie slice"
            elif "line" in tid:
                dim_hint = "Split into multiple lines by option value"

        # All DEs available as dimension — user picks any field; option-set DEs
        # produce legend from option values, numeric DEs group by value ranges.
        dim_names = ["—"] + [d["name"] for d in self._current_de_items]
        self._dimension_menu.configure(values=dim_names)
        if self._dimension_var.get() not in dim_names:
            self._dimension_var.set("—")
        self._dim_hint_lbl.config(text=dim_hint)
        if self._selected_template:
            self._dimension_row.grid()
        else:
            self._dimension_row.grid_remove()

        # Refresh filter DE dropdowns to match current DE items
        de_names = ["—"] + [d["name"] for d in self._current_de_items]
        de_map   = {d["name"]: d for d in self._current_de_items}
        for r in self._filter_rows:
            r["de_var"].set(r["de_var"].get() if r["de_var"].get() in de_names else "—")
            r["de_menu"].configure(values=de_names)
            r["de_map"] = de_map

    # ─── Filter rows ──────────────────────────────────────────────────────────────

    _FILTER_OPS = ["EQ", "≠ (NE)", "IN", ">", "≥", "<", "≤", "LIKE"]
    _OP_MAP = {"EQ": "EQ", "≠ (NE)": "NE", "IN": "IN",
               ">": "GT", "≥": "GE", "<": "LT", "≤": "LE", "LIKE": "LIKE"}

    def _add_filter_row(self):
        de_names = ["—"] + [d["name"] for d in self._current_de_items]
        de_map   = {d["name"]: d for d in self._current_de_items}
        idx = len(self._filter_rows)

        row = tk.Frame(self._filter_rows_frame, bg="white")
        row.grid(row=idx, column=0, sticky="ew", pady=2)
        row.grid_columnconfigure(1, weight=1)

        de_var = tk.StringVar(value="—")
        de_menu = ctk.CTkOptionMenu(
            row, variable=de_var, values=de_names,
            width=110, height=22, font=ctk.CTkFont(size=9),
            fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d")
        de_menu.grid(row=0, column=0, padx=(0, 3))

        op_var = tk.StringVar(value="EQ")
        ctk.CTkOptionMenu(
            row, variable=op_var, values=self._FILTER_OPS,
            width=70, height=22, font=ctk.CTkFont(size=9),
            fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d"
        ).grid(row=0, column=1, padx=(0, 3))

        val_var = tk.StringVar()
        ctk.CTkEntry(
            row, textvariable=val_var, height=22,
            font=ctk.CTkFont(size=9), placeholder_text="value"
        ).grid(row=0, column=2, sticky="ew", padx=(0, 3))

        row_data = dict(frame=row, de_var=de_var, de_menu=de_menu,
                        op_var=op_var, val_var=val_var, de_map=de_map)

        ctk.CTkButton(
            row, text="✕", width=22, height=22,
            fg_color="#f0f4f8", hover_color="#e8eef5",
            text_color="#8aa3b8", font=ctk.CTkFont(size=10),
            command=lambda r=row_data: self._remove_filter_row(r)
        ).grid(row=0, column=3)

        self._filter_rows.append(row_data)

    def _on_select_control_change(self, *_):
        """Called when any SelectControl (stack_mode, orientation, x_axis) changes."""
        self._schedule_preview_refresh()

    def _remove_filter_row(self, row_data: dict):
        row_data["frame"].destroy()
        self._filter_rows = [r for r in self._filter_rows if r is not row_data]
        # Re-grid remaining rows
        for i, r in enumerate(self._filter_rows):
            r["frame"].grid(row=i, column=0, sticky="ew", pady=2)

    # ─── DE list ──────────────────────────────────────────────────────────────────

    def _clear_de_list(self, msg: str = "Select chart type first"):
        for w in self._metrics_scroll.winfo_children():
            w.destroy()
        self._de_checkboxes = []
        self._metric_rows = []
        self._current_de_items = []
        ctk.CTkLabel(self._metrics_scroll, text=msg,
                     font=ctk.CTkFont(size=10), text_color="#8aa3b8"
                     ).grid(row=0, column=0, pady=10)
        self._sel_lbl.configure(text="", fg_color="transparent")

    def _populate_de_list(self, items: list[dict],
                          preserve_checked: set[str] | None = None):
        self._current_de_items = items
        checked = preserve_checked or {de["uid"] for de, _, v in self._de_checkboxes if v.get()}
        for w in self._metrics_scroll.winfo_children():
            w.destroy()
        self._de_checkboxes = []
        self._metric_rows = []
        if not items:
            ctk.CTkLabel(self._metrics_scroll, text="No results",
                         font=ctk.CTkFont(size=10), text_color="#8aa3b8"
                         ).grid(row=0, column=0, pady=8)
            return
        for i, de in enumerate(items):
            var = tk.BooleanVar(value=de["uid"] in checked)

            row_frame = tk.Frame(self._metrics_scroll, bg="white")
            row_frame.grid(row=i, column=0, sticky="ew", padx=2, pady=1)
            row_frame.grid_columnconfigure(0, weight=1)

            cb = ctk.CTkCheckBox(
                row_frame, text=de["name"], variable=var,
                font=ctk.CTkFont(size=10), checkbox_width=14, checkbox_height=14,
                command=self._on_de_check)
            cb.grid(row=0, column=0, sticky="w", padx=(4, 2))

            de_type = de.get("type", "")
            needs_agg = de_type in ("tracker_numeric", "aggregate", "indicator")
            agg_var: tk.StringVar | None = None
            agg_menu: ctk.CTkOptionMenu | None = None

            if needs_agg:
                agg_var = tk.StringVar(value="SUM")
                agg_menu = ctk.CTkOptionMenu(
                    row_frame, variable=agg_var,
                    values=["SUM", "COUNT", "AVG", "MIN", "MAX"],
                    width=80, height=22, font=ctk.CTkFont(size=9),
                    fg_color="white", button_color="#c5d3e0", text_color="#1e2d3d",
                    command=lambda _: self._on_de_check())
                agg_menu.grid(row=0, column=1, padx=(2, 4), sticky="e")

            self._de_checkboxes.append((de, cb, var))
            self._metric_rows.append((de, cb, var, agg_menu, agg_var))

    def _on_de_check(self):
        if len(self._get_selected_des()) > self._max_des:
            count = 0
            for _, _, v in self._de_checkboxes:
                if v.get():
                    count += 1
                    if count > self._max_des:
                        v.set(False)

        # Collect selected metrics with agg type
        self._selected_metrics = [
            {
                "uid": de["uid"],
                "name": de["name"],
                "type": de["type"],
                "agg": agg_var.get() if agg_var is not None else "COUNT",
            }
            for de, _, var, _, agg_var in self._metric_rows if var.get()
        ]

        sel = self._get_selected_des()
        if not sel:
            self._sel_lbl.configure(text="", fg_color="transparent")
        else:
            self._sel_lbl.configure(
                text="  ✓ " + " + ".join(d["name"][:22] for d in sel) + "  ",
                fg_color="#e3f2fd", text_color="#1565c0")
        if self._mode_var.get() == "fixed" and len(sel) >= self._min_des:
            self._auto_preview()

    def _get_selected_des(self) -> list[dict]:
        return [de for de, _, v in self._de_checkboxes if v.get()]

    # ─── Dynamic Chart Options ─────────────────────────────────────────────────────

    def _rebuild_chart_options(self):
        for w in self._dyn_opts_frame.winfo_children():
            w.destroy()
        self._option_vars = {}
        self._chart_options = {}

        tmpl = self._selected_template
        if not tmpl:
            tk.Label(self._dyn_opts_frame, text="← Select a chart type to see options",
                     font=("Segoe UI", 9), fg="#8aa3b8", bg=PANEL_BG).pack(anchor="w")
            return

        config = CHART_STYLE_CONFIGS.get(tmpl["id"], [])
        if not config:
            tk.Label(self._dyn_opts_frame, text="No style options for this chart type.",
                     font=("Segoe UI", 9), fg="#8aa3b8", bg=PANEL_BG).pack(anchor="w")
            return

        check_opts = [o for o in config if o["type"] == "check"]
        other_opts = [o for o in config if o["type"] != "check"]

        if check_opts:
            for row_i in range(0, len(check_opts), 2):
                row_f = tk.Frame(self._dyn_opts_frame, bg=PANEL_BG)
                row_f.pack(anchor="w", fill="x", pady=1)
                for opt in check_opts[row_i:row_i + 2]:
                    var = tk.BooleanVar(value=opt.get("default", False))
                    self._option_vars[opt["id"]] = var
                    ctk.CTkCheckBox(
                        row_f, text=opt["label"], variable=var,
                        font=ctk.CTkFont(size=10),
                        checkbox_width=14, checkbox_height=14,
                        command=self._apply_chart_options,
                    ).pack(side="left", padx=(0, 14))

        for opt in other_opts:
            row_f = tk.Frame(self._dyn_opts_frame, bg=PANEL_BG)
            row_f.pack(anchor="w", fill="x", pady=2)
            tk.Label(row_f, text=opt["label"] + ":",
                     font=("Segoe UI", 9), fg="#5a7a9a", bg=PANEL_BG
                     ).pack(side="left", padx=(0, 6))

            if opt["type"] == "segment":
                var = tk.StringVar(value=opt.get("default", opt["values"][0]))
                self._option_vars[opt["id"]] = var
                ctk.CTkSegmentedButton(
                    row_f, values=opt["values"], variable=var,
                    height=22, font=ctk.CTkFont(size=10),
                    fg_color="#e8eef5",
                    selected_color=DHIS2_BLUE, selected_hover_color="#155a8a",
                    unselected_color="#e8eef5", unselected_hover_color="#d0dde8",
                    text_color="#3a5068",
                    command=lambda _: self._apply_chart_options(),
                ).pack(side="left")

            elif opt["type"] == "entry":
                var = tk.StringVar(value=opt.get("default", ""))
                self._option_vars[opt["id"]] = var
                e = ctk.CTkEntry(row_f, textvariable=var, width=180, height=24,
                                 font=ctk.CTkFont(size=10),
                                 placeholder_text=opt.get("hint", opt["label"]))
                e.pack(side="left")
                e.bind("<FocusOut>", lambda ev: self._apply_chart_options())
                e.bind("<Return>", lambda ev: self._apply_chart_options())

    def _apply_chart_options(self, *_):
        from llm.chart_customizer import deep_merge
        opts: dict = {}
        for opt_id, var in self._option_vars.items():
            patch = _option_to_chartjs(opt_id, var.get())
            if patch:
                opts = deep_merge(opts, patch)
        self._chart_options = opts
        self._schedule_preview_refresh()

    # ─── Style controls ────────────────────────────────────────────────────────────

    def _on_color_select(self, color: str):
        self._selected_color = color
        for hex_c, frame in self._color_btns:
            frame.config(highlightbackground="white" if hex_c == color else hex_c,
                         highlightthickness=3 if hex_c == color else 1)
        self._schedule_preview_refresh()

    def _on_mode_change(self):
        if self._mode_var.get() == "ai":
            self._ai_desc.grid()
        else:
            self._ai_desc.grid_remove()

    # ─── Preview ───────────────────────────────────────────────────────────────────

    def _auto_preview(self):
        self._schedule_preview_refresh()

    def _schedule_preview_refresh(self):
        if self._preview_refresh_id:
            try:
                self.after_cancel(self._preview_refresh_id)
            except Exception:
                pass
        self._preview_refresh_id = self.after(400, self._do_refresh)

    def _do_refresh(self):
        self._preview_refresh_id = None
        from ui.preview_server import _browser_opened
        if _browser_opened:
            self._on_preview_browser()

    def _on_preview_browser(self):
        cfg = self._build_config()
        if not cfg:
            msgbox.showwarning("Preview", "Select chart type and data element(s) first.")
            return
        # ── DEBUG: log config sent to preview ─────────────────────────────────
        import json as _json_dbg, sys as _sys_dbg
        po  = cfg.get("plugin_options") or {}
        dim = (cfg.get("dimensions") or {}).get("dimension")
        src = cfg.get("source") or {}
        print("─" * 60, file=_sys_dbg.stderr)
        print(f"[PREVIEW] plugin_id   : {cfg.get('plugin_id')}", file=_sys_dbg.stderr)
        print(f"[PREVIEW] stack_mode  : {po.get('stack_mode')}", file=_sys_dbg.stderr)
        print(f"[PREVIEW] source.prog : {src.get('prog_uid')}", file=_sys_dbg.stderr)
        print(f"[PREVIEW] dimension   : {_json_dbg.dumps(dim, default=str)}", file=_sys_dbg.stderr)
        print(f"[PREVIEW] metrics     : {[{k:v for k,v in m.items() if k in ('uid','type','prog_uid')} for m in (cfg.get('metrics') or [])]}", file=_sys_dbg.stderr)
        print(f"[PREVIEW] plugin_opts : {_json_dbg.dumps(po)}", file=_sys_dbg.stderr)
        print("─" * 60, file=_sys_dbg.stderr)
        # ──────────────────────────────────────────────────────────────────────
        from charts.fixed_templates import generate_preview_page
        from ui.preview_window import update_preview
        html = generate_preview_page(cfg, title=cfg["title"])
        update_preview(html, title=cfg.get("title", "Chart Preview"))

    # ─── AI Customize ──────────────────────────────────────────────────────────────

    def _append_chat(self, role: str, text: str):
        prefix = "You: " if role == "user" else "AI: "
        self._chat_display_text += f"{prefix}{text}\n"
        self._chat_display.configure(state="normal")
        self._chat_display.delete("1.0", "end")
        self._chat_display.insert("end", self._chat_display_text)
        self._chat_display.configure(state="disabled")
        self._chat_display.see("end")

    def _on_ai_customize(self):
        request = self._ai_input.get().strip()
        if not request:
            return
        tmpl = self._selected_template
        if not tmpl:
            self._append_chat("ai", "⚠ Select a chart type first.")
            return

        api_key = self._callbacks.get("get_api_key", lambda: "")()
        if not api_key:
            self._append_chat("ai", "⚠ No Anthropic API key — enter it in the sidebar.")
            return

        self._append_chat("user", request)
        self._ai_input.delete(0, "end")
        self._append_chat("ai", "⏳ Thinking…")

        import threading
        threading.Thread(
            target=self._ai_customize_worker,
            args=(request, tmpl, api_key),
            daemon=True
        ).start()

    def _ai_customize_worker(self, request: str, tmpl: dict, api_key: str):
        try:
            from llm.chart_customizer import customize_chart, deep_merge
            model = self._callbacks.get("get_model", lambda: "claude-haiku-4-5-20251001")()
            patch = customize_chart(
                template_label=tmpl["label"],
                current_custom_options=self._custom_options,
                user_request=request,
                api_key=api_key,
                model=model,
            )
            self._custom_options = deep_merge(self._custom_options, patch)
            import json
            summary = json.dumps(patch, ensure_ascii=False)
            self.after(0, self._on_ai_customize_done, summary)
        except Exception as exc:
            self.after(0, self._on_ai_customize_done, f"Error: {exc}")

    def _on_ai_customize_done(self, summary: str):
        lines = self._chat_display_text.rstrip("\n").split("\n")
        if lines and "⏳" in lines[-1]:
            lines = lines[:-1]
        self._chat_display_text = "\n".join(lines) + "\n"
        self._append_chat("ai", f"✓ Applied: {summary[:120]}{'…' if len(summary) > 120 else ''}")
        self._schedule_preview_refresh()

    def _on_reset_customization(self):
        self._custom_options = {}
        self._quick_options  = {}
        self._chart_options  = {}
        self._chat_history   = []
        self._chat_display_text = ""
        self._chat_display.configure(state="normal")
        self._chat_display.delete("1.0", "end")
        self._chat_display.configure(state="disabled")
        self._rebuild_chart_options()

    # ─── Build config ──────────────────────────────────────────────────────────────

    def _build_config(self) -> dict | None:
        tmpl = self._selected_template
        if not tmpl:
            return None
        sel = self._get_selected_des()
        if len(sel) < self._min_des:
            return None
        de   = sel[0]
        title = self._title_entry.get().strip()
        if not title:
            title = de["name"] if len(sel) == 1 else \
                    " vs ".join(d["name"][:20] for d in sel[:2])
        seg_to_key = {"Full": "Full  (12)", "Half": "Half  (6)", "Third": "Third (4)"}
        col_w = COL_WIDTH_OPTIONS.get(seg_to_key.get(self._col_width_var.get(), "Half  (6)"), 6)
        from llm.chart_customizer import deep_merge
        user_opts = deep_merge(self._custom_options,
                               deep_merge(self._quick_options, self._chart_options))
        # Only apply single color override when no dimension is configured.
        # With a dimension, the JS uses PALETTE[i] per series — a single color
        # override would make all series the same colour.
        _has_dim = bool(self._dimension_var and self._dimension_var.get() not in ("—", ""))
        if de.get("type") not in ("tracker_option",) and not _has_dim:
            color_base = {"datasets": [{"backgroundColor": self._selected_color,
                                         "borderColor":     self._selected_color}]}
            merged_opts = deep_merge(color_base, user_opts)
        else:
            merged_opts = user_opts

        # Collect current metrics (with agg) — fall back to plain sel if metric_rows empty
        metrics = self._selected_metrics if self._selected_metrics else [
            {"uid": d["uid"], "name": d["name"], "type": d["type"], "agg": "SUM"}
            for d in sel
        ]

        # Resolve dimension field (single option-set DE for split/breakdown)
        dimension_de = None
        if self._dimension_var and self._dimension_var.get() != "—":
            dim_name = self._dimension_var.get()
            dimension_de = next(
                (d for d in self._current_de_items if d["name"] == dim_name), None)
        group_by = [dimension_de] if dimension_de else []  # backward compat alias

        # Collect filter rows
        op_map = self.__class__._OP_MAP if hasattr(self.__class__, "_OP_MAP") else {}
        filters = []
        for r in self._filter_rows:
            de_name = r["de_var"].get()
            if de_name == "—":
                continue
            de_obj = r["de_map"].get(de_name, {})
            val = r["val_var"].get().strip()
            if not val:
                continue
            op_display = r["op_var"].get()
            op_dhis2 = op_map.get(op_display, op_display)
            filters.append({
                "de_uid":  de_obj.get("uid", ""),
                "de_name": de_name,
                "de_type": de_obj.get("type", ""),
                "op":      op_dhis2,
                "value":   val,
            })

        # Row limit / sort
        limit_raw = self._row_limit_var.get() if self._row_limit_var else "All"
        row_limit = 0 if limit_raw == "All" else int(limit_raw)

        # Source info from first selected DE
        plugin_id = tmpl["id"].replace("ft_", "") if tmpl else None

        # ── plugin_options: SelectControls + style options (raw values for bar plugin) ──
        plugin_options: dict = {}
        for k, var in self._select_vars.items():
            plugin_options[k] = var.get()
        for opt_id, var in self._option_vars.items():
            plugin_options[opt_id] = var.get()

        return {
            # ── New plugin-aware fields ──────────────────────────────────────
            "plugin_id":     plugin_id,
            "plugin_options": plugin_options,
            "source": {
                "type":      de.get("type", ""),
                "prog_uid":  de.get("prog_uid", ""),
                "prog_name": de.get("prog_name", ""),
                "stage_uid": de.get("stage_uid", ""),
                "stage_name": de.get("stage_name", ""),
            },
            "metrics": metrics,
            "dimensions": {
                "time_grain": self._time_grain_var.get() if self._time_grain_var else "Monthly",
                "dimension":  dimension_de,   # single split-by field (option-set DE or None)
                "group_by":   group_by,       # same as [dimension_de] for backward compat
                "filters":    filters,
                "row_limit":  row_limit,
                "sort_by":    self._sort_by_var.get() if self._sort_by_var else "None",
                "sort_dir":   self._sort_dir_var.get() if self._sort_dir_var else "Asc",
                "breakdown":  None,
            },
            # ── Backward-compat fields (kept for existing consumers) ──────────
            "template_id":    tmpl["id"],
            "template_label": tmpl["label"],
            "title":          title,
            "mode":           self._mode_var.get(),
            "col_width":      col_w,
            "chart_color":    self._selected_color,
            "custom_options": merged_opts,
            "de_sources":     self._selected_metrics if self._selected_metrics else sel,
            "de_uid":         metrics[0]["uid"]  if metrics else "",
            "de_name":        metrics[0]["name"] if metrics else "",
            "de_type":        metrics[0]["type"] if metrics else "",
            "prog_uid":       de.get("prog_uid", ""),
            "prog_name":      de.get("prog_name", ""),
            "stage_uid":      de.get("stage_uid", ""),
            "stage_name":     de.get("stage_name", ""),
        }

    # ─── Actions ───────────────────────────────────────────────────────────────────

    def _on_save(self):
        cfg = self._build_config()
        if not cfg:
            msgbox.showwarning("Save Chart",
                               "Select a chart type and data element(s) first.")
            return
        if self._mode_var.get() == "ai":
            cfg["ai_desc"] = self._ai_desc.get("1.0", "end").strip()
        name = sd.askstring("Save Chart", "Chart name:",
                            initialvalue=cfg["title"],
                            parent=self)
        if not name:
            return
        cfg["name"] = name
        from config.chart_library import save_chart
        saved = save_chart(cfg)
        cb = self._callbacks.get("on_chart_saved")
        if cb:
            cb(saved)

    def _on_add_to_dashboard(self):
        cfg = self._build_config()
        if not cfg:
            msgbox.showwarning("Add to Dashboard",
                               "Select a chart type and data element(s) first.")
            return
        if self._mode_var.get() == "ai":
            cfg["ai_desc"] = self._ai_desc.get("1.0", "end").strip()
            ai_cb = self._callbacks.get("on_generate_ai")
            if ai_cb:
                ai_cb(cfg)
            return
        cfg.setdefault("name", cfg["title"])
        cb = self._callbacks.get("on_add_to_dashboard")
        if cb:
            cb(cfg)
        sw = self._callbacks.get("on_switch_to_dashboard")
        if sw:
            sw()

    # ─── Helpers ───────────────────────────────────────────────────────────────────

    def _sec_lbl(self, parent, row, text):
        ctk.CTkLabel(parent, text=text.upper(),
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color="#8aa3b8").grid(
            row=row, column=0, padx=12, pady=(8, 2), sticky="w")
