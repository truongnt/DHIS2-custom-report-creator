"""
DashboardBuilderPanel — Superset-inspired dashboard assembler.

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
import tkinter.messagebox as msgbox
import customtkinter as ctk

DHIS2_BLUE = "#1a6fa8"
PANEL_BG   = "#f7f9fc"
BORDER_CLR = "#d0dde8"


class DashboardBuilderPanel(ctk.CTkFrame):
    def __init__(self, master, callbacks: dict, **kw):
        kw.setdefault("fg_color", PANEL_BG)
        kw.setdefault("corner_radius", 0)
        super().__init__(master, **kw)
        self._callbacks = callbacks
        self._cards: list[dict] = []
        self._build()
        self.refresh_library()

    # ─── Build ───────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=240)
        self.grid_columnconfigure(1, weight=1)

        # Divider between library and canvas
        ctk.CTkFrame(self, width=1, fg_color=BORDER_CLR,
                     corner_radius=0).grid(row=0, column=0, sticky="nse")

        self._build_library()
        self._build_canvas()

    # ── Left: Chart Library ───────────────────────────────────────────────

    def _build_library(self):
        lib = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=0)
        lib.grid(row=0, column=0, sticky="nsew")
        lib.grid_rowconfigure(1, weight=1)
        lib.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(lib, fg_color="#e8eef5", corner_radius=0, height=36)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Chart Library",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#3a5068").grid(
            row=0, column=0, padx=14, pady=6, sticky="w")

        # Scrollable chart list
        self._lib_scroll = ctk.CTkScrollableFrame(
            lib, fg_color=PANEL_BG, corner_radius=0,
            scrollbar_button_color="#c0cdd8")
        self._lib_scroll.grid(row=1, column=0, sticky="nsew")
        self._lib_scroll.grid_columnconfigure(0, weight=1)

        self._lib_empty_lbl = ctk.CTkLabel(
            self._lib_scroll,
            text="No saved charts yet.\nBuild a chart and click\n'Save to Library'.",
            font=ctk.CTkFont(size=11), text_color="#8aa3b8", justify="center")
        self._lib_empty_lbl.grid(row=0, column=0, pady=24)

        # Footer: refresh + go to editor
        footer = ctk.CTkFrame(lib, fg_color="#e8eef5", corner_radius=0, height=40)
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_propagate(False)
        ctk.CTkButton(
            footer, text="↺ Refresh", height=26, width=90,
            fg_color="transparent", border_width=1, border_color="#c0cdd8",
            text_color="#5a7a9a", hover_color="#d8e4f0",
            font=ctk.CTkFont(size=11),
            command=self.refresh_library).pack(side="left", padx=8, pady=7)
        ctk.CTkButton(
            footer, text="← Chart Editor", height=26,
            fg_color="transparent", border_width=1, border_color=DHIS2_BLUE,
            text_color=DHIS2_BLUE, hover_color="#e8f0f8",
            font=ctk.CTkFont(size=11),
            command=lambda: self._callbacks.get("on_switch_to_editor", lambda: None)()
        ).pack(side="right", padx=8, pady=7)

    # ── Right: Dashboard Canvas ───────────────────────────────────────────

    def _build_canvas(self):
        canvas = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=0)
        canvas.grid(row=0, column=1, sticky="nsew")
        canvas.grid_rowconfigure(1, weight=1)
        canvas.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(canvas, fg_color="#e8eef5", corner_radius=0, height=36)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Dashboard Canvas",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#3a5068").grid(
            row=0, column=0, padx=14, pady=6, sticky="w")
        self._card_count_lbl = ctk.CTkLabel(
            hdr, text="0 charts",
            font=ctk.CTkFont(size=10), text_color="#8aa3b8")
        self._card_count_lbl.grid(row=0, column=1, padx=14, pady=6, sticky="e")

        # Card scroll area
        self._card_scroll = ctk.CTkScrollableFrame(
            canvas, fg_color=PANEL_BG, corner_radius=0,
            scrollbar_button_color="#c0cdd8")
        self._card_scroll.grid(row=1, column=0, sticky="nsew")
        self._card_scroll.grid_columnconfigure(0, weight=1)

        self._no_cards_lbl = ctk.CTkLabel(
            self._card_scroll,
            text="No charts yet.\nAdd charts from the library\nor use Chart Editor.",
            font=ctk.CTkFont(size=12), text_color="#8aa3b8", justify="center")
        self._no_cards_lbl.grid(row=0, column=0, pady=32)

        # Bottom: report name + actions
        bottom = ctk.CTkFrame(canvas, fg_color="#e8eef5", corner_radius=0)
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)

        rn_row = ctk.CTkFrame(bottom, fg_color="transparent")
        rn_row.grid(row=0, column=0, padx=12, pady=(6, 2), sticky="ew")
        rn_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(rn_row, text="Report name:",
                     font=ctk.CTkFont(size=10), text_color="#5a7a9a",
                     width=95).grid(row=0, column=0, sticky="w")
        self._report_name_entry = ctk.CTkEntry(
            rn_row, height=26, font=ctk.CTkFont(size=11),
            placeholder_text="My Dashboard")
        self._report_name_entry.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        ab = ctk.CTkFrame(bottom, fg_color="transparent")
        ab.grid(row=1, column=0, padx=12, pady=(2, 8), sticky="ew")
        ab.grid_columnconfigure(0, weight=1)
        ab.grid_columnconfigure(1, weight=1)

        self._export_btn = ctk.CTkButton(
            ab, text="⬇ Export HTML", height=34,
            fg_color="#2980b9", hover_color="#1e6b99",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_export, state="disabled")
        self._export_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        self._deploy_btn = ctk.CTkButton(
            ab, text="🚀 Deploy to DHIS2", height=34,
            fg_color="#27ae60", hover_color="#1e8449",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_deploy, state="disabled")
        self._deploy_btn.grid(row=0, column=1, sticky="ew", padx=(3, 0))

        # Clear button
        ctk.CTkButton(
            bottom, text="🗑 Clear all", height=24,
            fg_color="transparent", border_width=1, border_color="#e74c3c",
            text_color="#e74c3c", hover_color="#fdecea",
            font=ctk.CTkFont(size=10),
            command=self._on_clear_all).grid(
            row=2, column=0, padx=12, pady=(0, 6), sticky="e")

    # ─── Library ─────────────────────────────────────────────────────────────

    def refresh_library(self):
        from config.chart_library import load_charts
        for w in self._lib_scroll.winfo_children():
            w.destroy()
        charts = load_charts()
        if not charts:
            self._lib_empty_lbl = ctk.CTkLabel(
                self._lib_scroll,
                text="No saved charts yet.\nBuild a chart and click\n'Save to Library'.",
                font=ctk.CTkFont(size=11), text_color="#8aa3b8", justify="center")
            self._lib_empty_lbl.grid(row=0, column=0, pady=24)
            return
        for i, chart in enumerate(charts):
            self._build_library_card(i, chart)

    def _build_library_card(self, row: int, chart: dict):
        rf = ctk.CTkFrame(self._lib_scroll, fg_color="white",
                           border_color=BORDER_CLR, border_width=1, corner_radius=6)
        rf.grid(row=row, column=0, padx=6, pady=3, sticky="ew")
        rf.grid_columnconfigure(0, weight=1)

        tmpl_label = chart.get("template_label", chart.get("template_id", "?"))
        ctk.CTkLabel(rf,
                     text=chart.get("name") or chart.get("title", "?"),
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#1e2d3d", anchor="w"
                     ).grid(row=0, column=0, padx=8, pady=(5, 1), sticky="w")
        ctk.CTkLabel(rf,
                     text=tmpl_label,
                     font=ctk.CTkFont(size=9), text_color="#8aa3b8", anchor="w"
                     ).grid(row=1, column=0, padx=8, pady=(0, 5), sticky="w")

        btn_col = ctk.CTkFrame(rf, fg_color="transparent")
        btn_col.grid(row=0, column=1, rowspan=2, padx=6, pady=4)
        ctk.CTkButton(
            btn_col, text="+ Add", width=52, height=26,
            fg_color=DHIS2_BLUE, hover_color="#155a8a",
            font=ctk.CTkFont(size=10),
            command=lambda c=chart: self.add_card(c)
        ).pack(pady=(0, 2))
        ctk.CTkButton(
            btn_col, text="✕", width=52, height=22,
            fg_color="transparent", hover_color="#f5c6cb",
            text_color="#c0392b", border_width=1, border_color="#e0b0b0",
            font=ctk.CTkFont(size=9),
            command=lambda c=chart: self._delete_library_chart(c)
        ).pack()

    def _delete_library_chart(self, chart: dict):
        if msgbox.askyesno("Delete Chart",
                           f"Delete '{chart.get('name', chart.get('title'))}' from library?"):
            from config.chart_library import delete_chart
            delete_chart(chart["id"])
            self.refresh_library()

    # ─── Dashboard Canvas ─────────────────────────────────────────────────────

    def add_card(self, cfg: dict):
        if hasattr(self, "_no_cards_lbl") and self._no_cards_lbl.winfo_exists():
            self._no_cards_lbl.grid_remove()
        self._cards.append(cfg)
        idx = len(self._cards) - 1
        rf = ctk.CTkFrame(self._card_scroll, fg_color="white",
                           border_color=BORDER_CLR, border_width=1, corner_radius=6)
        rf.grid(row=idx, column=0, padx=6, pady=3, sticky="ew")
        rf.grid_columnconfigure(0, weight=1)

        color_dot = "●"
        chart_color = cfg.get("chart_color", "#3498db")
        name = cfg.get("name") or cfg.get("title", "?")
        mode_lbl = "AI" if cfg.get("mode") == "ai" else "Fixed"
        src_n = len(cfg.get("de_sources", [])) or 1

        ctk.CTkLabel(rf,
                     text=f"{color_dot}  {name}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=chart_color, anchor="w"
                     ).grid(row=0, column=0, padx=8, pady=(5, 1), sticky="w")
        ctk.CTkLabel(rf,
                     text=f"{cfg.get('template_label', '')}  •  col-{cfg.get('col_width', 6)}  •  {src_n} src  •  {mode_lbl}",
                     font=ctk.CTkFont(size=9), text_color="#8aa3b8", anchor="w"
                     ).grid(row=1, column=0, padx=8, pady=(0, 5), sticky="w")
        ctk.CTkButton(rf, text="✕", width=24, height=24,
                      fg_color="#f0f4f8", hover_color="#f5c6cb",
                      text_color="#c0392b", font=ctk.CTkFont(size=10),
                      command=lambda i=idx, f=rf: self._remove_card(i, f)
                      ).grid(row=0, column=1, rowspan=2, padx=6)

        self._export_btn.configure(state="normal")
        self._deploy_btn.configure(state="normal")
        count = len(self._cards)
        self._card_count_lbl.configure(
            text=f"{count} chart{'s' if count != 1 else ''}")

    def _remove_card(self, idx: int, frame):
        if 0 <= idx < len(self._cards):
            self._cards[idx] = None
        frame.destroy()
        self._cards = [c for c in self._cards if c is not None]
        count = len(self._cards)
        self._card_count_lbl.configure(
            text=f"{count} chart{'s' if count != 1 else ''}")
        if not self._cards:
            self._no_cards_lbl = ctk.CTkLabel(
                self._card_scroll,
                text="No charts yet.\nAdd charts from the library\nor use Chart Editor.",
                font=ctk.CTkFont(size=12), text_color="#8aa3b8", justify="center")
            self._no_cards_lbl.grid(row=0, column=0, pady=32)
            self._export_btn.configure(state="disabled")
            self._deploy_btn.configure(state="disabled")

    def _on_clear_all(self):
        if self._cards and msgbox.askyesno("Clear Dashboard",
                                           "Remove all charts from this dashboard?"):
            for w in self._card_scroll.winfo_children():
                w.destroy()
            self._cards = []
            self._card_count_lbl.configure(text="0 charts")
            self._no_cards_lbl = ctk.CTkLabel(
                self._card_scroll,
                text="No charts yet.\nAdd charts from the library\nor use Chart Editor.",
                font=ctk.CTkFont(size=12), text_color="#8aa3b8", justify="center")
            self._no_cards_lbl.grid(row=0, column=0, pady=32)
            self._export_btn.configure(state="disabled")
            self._deploy_btn.configure(state="disabled")

    # ─── Export / Deploy ──────────────────────────────────────────────────────

    def _on_export(self):
        cb = self._callbacks.get("on_export")
        if cb:
            cb(list(self._cards))

    def _on_deploy(self):
        name = self._report_name_entry.get().strip()
        if not name:
            msgbox.showwarning("Deploy", "Enter a report name first.")
            self._report_name_entry.focus()
            return
        cb = self._callbacks.get("on_deploy")
        if cb:
            cb(name, list(self._cards))

    def get_cards(self) -> list[dict]:
        return list(self._cards)
