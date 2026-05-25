"""
ChartLibrary — popup để người dùng duyệt và chọn chart template trước khi Generate.

Layout:
  Left  — danh sách category (sidebar)
  Right — grid card các template của category đang chọn
  Bottom — selected template preview + OK/Cancel
"""
from __future__ import annotations
import customtkinter as ctk
import tkinter as tk
import webbrowser
import tempfile
import os

from charts.templates import CATEGORIES, TEMPLATES, get_by_id, get_by_category

DHIS2_BLUE = "#1a6fa8"
BORDER     = "#d0dde8"

# SVG thumbnails per template id (simple geometric previews)
_THUMBS: dict[str, str] = {
    "line_single":        "📈",
    "line_multi":         "📉",
    "bar_monthly":        "📊",
    "bar_grouped":        "🗂️",
    "bar_stacked":        "🏗️",
    "bar_horizontal_ou":  "↔️",
    "pie":                "🥧",
    "donut":              "🍩",
    "scorecard":          "🎯",
    "traffic_light":      "🚦",
    "data_table":         "📋",
    "combined_bar_line":  "🔀",
    "combined_full":      "🖥️",
}


class ChartLibrary(ctk.CTkToplevel):
    def __init__(self, parent, current_template_id: str | None = None):
        super().__init__(parent)
        self.title("Chart Template Library")
        self.geometry("1020x640")
        self.minsize(860, 520)
        self.grab_set()
        self.focus_force()

        self._selected_id: str | None = current_template_id
        self.result: str | None = None  # template id, set on OK

        self._cat_buttons: dict[str, ctk.CTkButton] = {}
        self._active_cat  = CATEGORIES[0]["id"]
        self._card_frames: list[ctk.CTkFrame] = []

        self._build()
        # restore selection
        if current_template_id:
            tmpl = get_by_id(current_template_id)
            if tmpl:
                self._active_cat = tmpl["category"]
        self._show_category(self._active_cat)

    # ─── Layout ──────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        outer = ctk.CTkFrame(self, fg_color="white", corner_radius=0)
        outer.grid(sticky="nsew")
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(1, weight=1)

        self._build_category_sidebar(outer)
        self._build_content_area(outer)
        self._build_bottom_bar(outer)

    def _build_category_sidebar(self, parent):
        sb = ctk.CTkFrame(parent, width=190, fg_color="#1e2d3d", corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew", rowspan=2)
        sb.grid_propagate(False)
        sb.grid_rowconfigure(len(CATEGORIES) + 1, weight=1)

        ctk.CTkLabel(sb, text="Chart Types",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="white").grid(
            row=0, column=0, padx=14, pady=(16, 10), sticky="w")

        for i, cat in enumerate(CATEGORIES, start=1):
            btn = ctk.CTkButton(
                sb,
                text=f"{cat['icon']}  {cat['name']}",
                width=176, height=38,
                anchor="w",
                fg_color="transparent",
                hover_color="#2a4a6a",
                text_color="white",
                font=ctk.CTkFont(size=12),
                command=lambda cid=cat["id"]: self._show_category(cid),
            )
            btn.grid(row=i, column=0, padx=7, pady=2)
            self._cat_buttons[cat["id"]] = btn

    def _build_content_area(self, parent):
        right = ctk.CTkFrame(parent, fg_color="#f4f8fc", corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Category header
        self._cat_header = ctk.CTkLabel(
            right, text="",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#1e2d3d", anchor="w",
        )
        self._cat_header.grid(row=0, column=0, padx=18, pady=(14, 8), sticky="w")

        self._cat_desc = ctk.CTkLabel(
            right, text="",
            font=ctk.CTkFont(size=11),
            text_color="#6b8299", anchor="w",
        )
        self._cat_desc.grid(row=1, column=0, padx=18, pady=(0, 10), sticky="w")

        # Scrollable card grid
        self._scroll = ctk.CTkScrollableFrame(
            right, fg_color="transparent", corner_radius=0)
        self._scroll.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        right.grid_rowconfigure(2, weight=1)

    def _build_bottom_bar(self, parent):
        bottom = ctk.CTkFrame(parent, fg_color="#f0f4f8",
                               corner_radius=0, height=54)
        bottom.grid(row=1, column=1, sticky="ew")
        bottom.grid_propagate(False)
        bottom.grid_columnconfigure(1, weight=1)

        self._sel_label = ctk.CTkLabel(
            bottom, text="No template selected",
            font=ctk.CTkFont(size=12), text_color="#6b8299")
        self._sel_label.grid(row=0, column=0, padx=16, pady=12, sticky="w")

        self._preview_btn = ctk.CTkButton(
            bottom, text="Preview HTML ↗", width=130, height=34,
            fg_color="transparent", border_width=1,
            border_color=DHIS2_BLUE, text_color=DHIS2_BLUE,
            hover_color="#e8f0f8",
            state="disabled",
            command=self._on_preview,
        )
        self._preview_btn.grid(row=0, column=2, padx=(0, 8), pady=10)

        ctk.CTkButton(
            bottom, text="Cancel", width=80, height=34,
            fg_color="transparent", border_width=1,
            border_color=BORDER, text_color="#4a6278",
            hover_color="#e8f0f8",
            command=self._on_cancel,
        ).grid(row=0, column=3, padx=(0, 8), pady=10)

        self._ok_btn = ctk.CTkButton(
            bottom, text="Use This Template ✓", width=175, height=34,
            fg_color=DHIS2_BLUE, hover_color="#155a8a",
            state="disabled",
            command=self._on_ok,
        )
        self._ok_btn.grid(row=0, column=4, padx=(0, 16), pady=10)

    # ─── Category display ─────────────────────────────────────────────────────

    def _show_category(self, cat_id: str):
        self._active_cat = cat_id

        # Highlight active sidebar button
        for cid, btn in self._cat_buttons.items():
            btn.configure(
                fg_color=DHIS2_BLUE if cid == cat_id else "transparent")

        cat  = next(c for c in CATEGORIES if c["id"] == cat_id)
        tmpl = get_by_category(cat_id)

        self._cat_header.configure(text=f"{cat['icon']}  {cat['name']}")
        self._cat_desc.configure(text=cat["desc"])

        # Clear old cards
        for w in self._scroll.winfo_children():
            w.destroy()

        # Grid 3 columns
        cols = 3
        for i, t in enumerate(tmpl):
            row = i // cols
            col = i % cols
            self._scroll.grid_columnconfigure(col, weight=1)
            self._build_card(self._scroll, t, row, col)

    def _build_card(self, parent, tmpl: dict, row: int, col: int):
        is_selected = tmpl["id"] == self._selected_id
        border_color = DHIS2_BLUE if is_selected else BORDER
        border_width = 2         if is_selected else 1
        bg           = "#e8f4fd" if is_selected else "white"

        card = ctk.CTkFrame(parent, fg_color=bg,
                             border_width=border_width,
                             border_color=border_color,
                             corner_radius=8)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        # Thumbnail
        thumb = ctk.CTkLabel(
            card,
            text=_THUMBS.get(tmpl["id"], "📊"),
            font=ctk.CTkFont(size=38),
        )
        thumb.grid(row=0, column=0, pady=(16, 4))

        # Name
        ctk.CTkLabel(card, text=tmpl["name"],
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#1e2d3d",
                     wraplength=200, justify="center").grid(
            row=1, column=0, padx=10, pady=(0, 4))

        # Short description
        ctk.CTkLabel(card, text=tmpl["short"],
                     font=ctk.CTkFont(size=10),
                     text_color="#6b8299",
                     wraplength=200, justify="center").grid(
            row=2, column=0, padx=10, pady=(0, 4))

        # Best for
        ctk.CTkLabel(card, text=f"✦ {tmpl['best_for']}",
                     font=ctk.CTkFont(size=10),
                     text_color="#8aa3b8",
                     wraplength=200, justify="center").grid(
            row=3, column=0, padx=10, pady=(0, 4))

        # Placeholders badge
        ph = tmpl.get("placeholders", "?")
        ctk.CTkLabel(card,
                     text=f"UIDs: {ph}",
                     font=ctk.CTkFont(size=10),
                     text_color="white",
                     fg_color=DHIS2_BLUE,
                     corner_radius=6,
                     width=70, height=20).grid(
            row=4, column=0, pady=(2, 12))

        # Click anywhere to select
        for widget in (card, thumb):
            widget.bind("<Button-1>", lambda e, tid=tmpl["id"]: self._select(tid))
        card.bind("<Double-1>", lambda e, tid=tmpl["id"]: self._select_and_ok(tid))

    # ─── Selection ───────────────────────────────────────────────────────────

    def _select(self, template_id: str):
        self._selected_id = template_id
        # Refresh cards to update border
        self._show_category(self._active_cat)

        tmpl = get_by_id(template_id)
        if tmpl:
            self._sel_label.configure(
                text=f"Selected: {tmpl['name']}",
                text_color="#1e2d3d")
            self._ok_btn.configure(state="normal")
            self._preview_btn.configure(state="normal")

    def _select_and_ok(self, template_id: str):
        self._select(template_id)
        self._on_ok()

    # ─── Preview ─────────────────────────────────────────────────────────────

    def _on_preview(self):
        if not self._selected_id:
            return
        tmpl = get_by_id(self._selected_id)
        if not tmpl:
            return
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".html", mode="w", encoding="utf-8")
        # Replace placeholders with sample data for preview
        html = tmpl["html"].replace("<!-- REPORT_TITLE -->", tmpl["name"] + " — Preview")
        for ph in ["<!-- INDICATOR_UID -->", "<!-- INDICATOR_UID_1 -->",
                   "<!-- INDICATOR_UID_2 -->", "<!-- INDICATOR_UID_3 -->",
                   "<!-- INDICATOR_UID_4 -->", "<!-- BAR_INDICATOR_UID -->",
                   "<!-- LINE_INDICATOR_UID -->"]:
            html = html.replace(ph, "fbfJHSPpUQD")  # DHIS2 demo indicator
        for ph in ["<!-- TARGET_1 -->", "<!-- TARGET_2 -->", "<!-- TARGET_3 -->"]:
            html = html.replace(ph, "100")
        tmp.write(html)
        tmp.close()
        webbrowser.open(f"file:///{tmp.name.replace(os.sep, '/')}")

    # ─── OK / Cancel ─────────────────────────────────────────────────────────

    def _on_ok(self):
        self.result = self._selected_id
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()
