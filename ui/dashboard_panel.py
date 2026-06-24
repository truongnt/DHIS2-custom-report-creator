"""DashboardPanel — panel bên phải gom nhiều chart thành dashboard."""
from __future__ import annotations
import tkinter.messagebox as msgbox
import customtkinter as ctk
from typing import Callable

DHIS2_BLUE = "#1a6fa8"
PANEL_BG   = "#f7f9fc"
BORDER_CLR = "#d0dde8"


class DashboardPanel(ctk.CTkFrame):
    """
    callbacks keys:
      on_export(cards)
      on_deploy(name, cards)
    """
    def __init__(self, master, callbacks: dict[str, Callable], **kw):
        kw.setdefault("fg_color", PANEL_BG)
        kw.setdefault("corner_radius", 0)
        super().__init__(master, **kw)
        self._callbacks = callbacks
        self._cards: list[dict] = []
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color="#e8eef5", corner_radius=0, height=36)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Dashboard",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#3a5068").grid(row=0, column=0, padx=14, pady=6, sticky="w")
        self._count_lbl = ctk.CTkLabel(hdr, text="0 charts",
                                        font=ctk.CTkFont(size=10), text_color="#8aa3b8")
        self._count_lbl.grid(row=0, column=1, padx=10, pady=6, sticky="e")

        # Card scroll list
        self._card_scroll = ctk.CTkScrollableFrame(
            self, fg_color=PANEL_BG, corner_radius=0,
            scrollbar_button_color="#c0cdd8")
        self._card_scroll.grid(row=1, column=0, sticky="nsew")
        self._card_scroll.grid_columnconfigure(0, weight=1)

        self._no_cards_lbl = ctk.CTkLabel(
            self._card_scroll,
            text="No charts yet.\nBuild a viz and click '+ Add'.",
            font=ctk.CTkFont(size=11), text_color="#8aa3b8", justify="center")
        self._no_cards_lbl.grid(row=0, column=0, pady=24)

        # Bottom bar
        bottom = ctk.CTkFrame(self, fg_color="#e8eef5", corner_radius=0)
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)

        rn_row = ctk.CTkFrame(bottom, fg_color="transparent")
        rn_row.grid(row=0, column=0, padx=10, pady=(6, 2), sticky="ew")
        rn_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(rn_row, text="Report name:",
                     font=ctk.CTkFont(size=10), text_color="#5a7a9a",
                     width=90).grid(row=0, column=0, sticky="w")
        self._report_name_entry = ctk.CTkEntry(
            rn_row, height=26, font=ctk.CTkFont(size=11),
            placeholder_text="My Dashboard")
        self._report_name_entry.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        ab = ctk.CTkFrame(bottom, fg_color="transparent")
        ab.grid(row=1, column=0, padx=10, pady=(2, 8), sticky="ew")
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

    def add_card(self, cfg: dict):
        if hasattr(self, "_no_cards_lbl") and self._no_cards_lbl.winfo_exists():
            self._no_cards_lbl.grid_remove()
        self._cards.append(cfg)
        idx = len(self._cards) - 1
        rf = ctk.CTkFrame(self._card_scroll, fg_color="white",
                           border_color=BORDER_CLR, border_width=1, corner_radius=6)
        rf.grid(row=idx, column=0, padx=6, pady=3, sticky="ew")
        rf.grid_columnconfigure(0, weight=1)
        mode_lbl = "AI" if cfg.get("mode") == "ai" else "Fixed"
        src_n = len(cfg.get("de_sources", [])) or 1
        ctk.CTkLabel(rf, text=cfg.get("title", "?"),
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#1e2d3d", anchor="w"
                     ).grid(row=0, column=0, padx=8, pady=(5, 1), sticky="w")
        ctk.CTkLabel(rf,
                     text=f"{cfg.get('template_label', '')}  •  {src_n} src  •  {mode_lbl}",
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
        self._count_lbl.configure(text=f"{count} chart{'s' if count != 1 else ''}")

    def _remove_card(self, idx: int, frame):
        if 0 <= idx < len(self._cards):
            self._cards[idx] = None
        frame.destroy()
        self._cards = [c for c in self._cards if c is not None]
        count = len(self._cards)
        self._count_lbl.configure(text=f"{count} chart{'s' if count != 1 else ''}")
        if not self._cards:
            self._no_cards_lbl = ctk.CTkLabel(
                self._card_scroll,
                text="No charts yet.\nBuild a viz and click '+ Add'.",
                font=ctk.CTkFont(size=11), text_color="#8aa3b8", justify="center")
            self._no_cards_lbl.grid(row=0, column=0, pady=24)
            self._export_btn.configure(state="disabled")
            self._deploy_btn.configure(state="disabled")

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
