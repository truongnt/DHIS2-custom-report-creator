"""
DashboardBuilder — drag-and-drop dashboard layout editor.

Layout:
  ┌─────────────┬──────────────────────────────┬────────────────┐
  │  Palette    │    Dashboard Canvas           │  Card Config   │
  │  (chart     │    (drag-drop, resize)        │  (selected     │
  │   types     │                               │   card props)  │
  │   with      │                               │                │
  │   previews) │                               │                │
  └─────────────┴──────────────────────────────┴────────────────┘
  [  Cancel  ]                                    [ Generate ▶ ]

Dashboard canvas:
  - Each card = header bar + chart preview + resize handle
  - Drag header to move
  - Drag bottom-right triangle to resize
  - Double-click card to configure indicators
  - Right-click → delete

Result: list of DashCard dicts describing the layout
"""
from __future__ import annotations
import tkinter as tk
import customtkinter as ctk
from dataclasses import dataclass, field, asdict
from typing import Optional
import uuid

from charts.templates import CATEGORIES, TEMPLATES, get_by_id, get_by_category
from charts.preview_canvas import draw_chart_preview

DHIS2_BLUE  = "#1a6fa8"
SIDEBAR_BG  = "#1e2d3d"
CARD_BG     = "#ffffff"
CARD_HDR    = "#1a6fa8"
CARD_SEL    = "#e8f4fd"
CANVAS_BG   = "#f0f4f8"
GRID_COLOR  = "#dde6ee"
GRID_SNAP   = 20          # pixels per grid unit
MIN_CARD_W  = 160
MIN_CARD_H  = 120
DEF_CARD_W  = 280
DEF_CARD_H  = 200
HANDLE_SIZE = 12           # resize handle corner size
HDR_HEIGHT  = 24


@dataclass
class DashCard:
    id:          str
    template_id: str
    title:       str
    x:           int = 20
    y:           int = 20
    w:           int = DEF_CARD_W
    h:           int = DEF_CARD_H
    pinned:      dict = field(default_factory=lambda: {
        "indicators": [], "program_indicators": [], "data_elements": []
    })
    # canvas item ids (not serialised)
    _items: list = field(default_factory=list, repr=False)


class DashboardBuilder(ctk.CTkToplevel):
    def __init__(self, parent, metadata: dict, pinned: dict,
                  existing_layout: list[DashCard] | None = None):
        super().__init__(parent)
        self.title("Dashboard Builder")
        self.geometry("1200x720")
        self.minsize(900, 580)
        self.grab_set()
        self.focus_force()

        self._metadata = metadata
        self._global_pinned = pinned   # from app-level metadata selector
        self._cards: list[DashCard] = list(existing_layout or [])
        self.result: list[dict] | None = None   # set on OK

        # Drag state
        self._drag_card: Optional[DashCard] = None
        self._drag_ox = self._drag_oy = 0
        # Resize state
        self._resize_card: Optional[DashCard] = None
        self._resize_ox = self._resize_oy = 0
        self._resize_ow = self._resize_oh = 0
        # Selected card
        self._selected: Optional[DashCard] = None
        # Palette drag
        self._palette_drag_tid: Optional[str] = None

        self._build()
        self._redraw_all()

    # ─── Layout ──────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_palette()
        self._build_canvas_area()
        self._build_config_panel()
        self._build_bottom_bar()

    # ── Palette (left) ────────────────────────────────────────────────────────

    def _build_palette(self):
        palette = ctk.CTkFrame(self, width=190, fg_color=SIDEBAR_BG,
                                corner_radius=0)
        palette.grid(row=0, column=0, sticky="nsew")
        palette.grid_propagate(False)
        palette.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(palette, text="Chart Library",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="white").grid(
            row=0, column=0, padx=12, pady=(12, 6), sticky="w")

        scroll = ctk.CTkScrollableFrame(palette, fg_color="transparent",
                                          corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew", padx=4)
        palette.grid_columnconfigure(0, weight=1)

        for cat in CATEGORIES:
            # Category header
            cat_lbl = ctk.CTkLabel(scroll,
                                    text=f"{cat['icon']} {cat['name']}",
                                    font=ctk.CTkFont(size=10, weight="bold"),
                                    text_color="#8aa3b8", anchor="w")
            cat_lbl.pack(fill="x", padx=8, pady=(10, 2))

            for tmpl in get_by_category(cat["id"]):
                self._build_palette_tile(scroll, tmpl, cat["color"])

    def _build_palette_tile(self, parent, tmpl: dict, cat_color: str):
        tile = tk.Frame(parent, bg="#253545", cursor="hand2",
                         relief="flat", bd=0)
        tile.pack(fill="x", padx=6, pady=3)

        # Mini canvas preview
        preview = tk.Canvas(tile, width=168, height=72,
                            bg="#1e2d3d", highlightthickness=0)
        preview.pack(fill="x")
        draw_chart_preview(preview, tmpl["id"], 2, 2, 164, 68)

        # Label row
        lbl_frame = tk.Frame(tile, bg="#253545")
        lbl_frame.pack(fill="x", padx=6, pady=(2, 5))
        tk.Label(lbl_frame, text=tmpl["name"],
                 font=("Segoe UI", 8, "bold"),
                 fg="white", bg="#253545", anchor="w").pack(side="left")

        # Drag from palette to canvas
        for widget in (tile, preview, lbl_frame):
            widget.bind("<ButtonPress-1>",
                        lambda e, tid=tmpl["id"]: self._palette_drag_start(e, tid))
            widget.bind("<B1-Motion>",   self._palette_drag_motion)
            widget.bind("<ButtonRelease-1>", self._palette_drag_drop)

        # Hover highlight
        def on_enter(e, t=tile): t.config(bg="#2d4a62")
        def on_leave(e, t=tile): t.config(bg="#253545")
        for widget in (tile, preview, lbl_frame):
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)

    # ── Dashboard Canvas (center) ─────────────────────────────────────────────

    def _build_canvas_area(self):
        frame = ctk.CTkFrame(self, fg_color=CANVAS_BG, corner_radius=0)
        frame.grid(row=0, column=1, sticky="nsew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(frame, bg=CANVAS_BG,
                                  scrollregion=(0, 0, 2000, 1600),
                                  highlightthickness=0, cursor="arrow")
        vsb = ttk_scrollbar(frame, self._canvas, "vertical")
        hsb = ttk_scrollbar(frame, self._canvas, "horizontal")
        self._canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._canvas.bind("<ButtonPress-1>",   self._canvas_click)
        self._canvas.bind("<B1-Motion>",       self._canvas_drag)
        self._canvas.bind("<ButtonRelease-1>", self._canvas_release)
        self._canvas.bind("<Double-Button-1>", self._canvas_dbl)
        self._canvas.bind("<Button-3>",        self._canvas_right_click)
        self._canvas.bind("<Configure>",       lambda e: self._draw_grid())
        self._draw_grid()

    # ── Config panel (right) ──────────────────────────────────────────────────

    def _build_config_panel(self):
        self._cfg_panel = ctk.CTkFrame(self, width=210, fg_color="white",
                                        corner_radius=0,
                                        border_width=1, border_color="#d0dde8")
        self._cfg_panel.grid(row=0, column=2, sticky="nsew")
        self._cfg_panel.grid_propagate(False)
        self._cfg_panel.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(self._cfg_panel, text="Card Properties",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#1e2d3d").grid(
            row=0, column=0, padx=12, pady=(12, 6), sticky="w")

        ctk.CTkLabel(self._cfg_panel, text="Title",
                     font=ctk.CTkFont(size=11), text_color="#4a6278").grid(
            row=1, column=0, padx=12, sticky="w")
        self._cfg_title = ctk.CTkEntry(self._cfg_panel, width=180, height=28,
                                        font=ctk.CTkFont(size=11),
                                        state="disabled")
        self._cfg_title.grid(row=2, column=0, padx=12, pady=(2, 8))

        ctk.CTkLabel(self._cfg_panel, text="Chart type",
                     font=ctk.CTkFont(size=11), text_color="#4a6278").grid(
            row=3, column=0, padx=12, sticky="w")
        self._cfg_type_lbl = ctk.CTkLabel(self._cfg_panel, text="—",
                                           font=ctk.CTkFont(size=11),
                                           text_color="#1e2d3d")
        self._cfg_type_lbl.grid(row=4, column=0, padx=12, pady=(2, 8), sticky="w")

        ctk.CTkLabel(self._cfg_panel, text="Pinned indicators for this card",
                     font=ctk.CTkFont(size=11), text_color="#4a6278",
                     wraplength=185, justify="left").grid(
            row=5, column=0, padx=12, sticky="w")
        self._cfg_pin_lbl = ctk.CTkLabel(self._cfg_panel, text="None",
                                          font=ctk.CTkFont(size=10),
                                          text_color="#8aa3b8",
                                          wraplength=185, justify="left")
        self._cfg_pin_lbl.grid(row=6, column=0, padx=12, pady=(2, 4), sticky="w")

        self._cfg_pin_btn = ctk.CTkButton(
            self._cfg_panel, text="Select Indicators…", width=180, height=28,
            fg_color="transparent", border_width=1, border_color=DHIS2_BLUE,
            text_color=DHIS2_BLUE, hover_color="#e8f0f8",
            state="disabled",
            command=self._on_configure_pins)
        self._cfg_pin_btn.grid(row=7, column=0, padx=12, pady=(0, 8))

        self._cfg_del_btn = ctk.CTkButton(
            self._cfg_panel, text="Delete Card", width=180, height=28,
            fg_color="transparent", border_width=1, border_color="#e74c3c",
            text_color="#e74c3c", hover_color="#fdecea",
            state="disabled",
            command=self._delete_selected)
        self._cfg_del_btn.grid(row=8, column=0, padx=12)

        # Hint
        ctk.CTkLabel(self._cfg_panel,
                     text="← Drag chart from library\nor double-click to configure",
                     font=ctk.CTkFont(size=10), text_color="#b0c0d0",
                     justify="center").grid(
            row=10, column=0, padx=12, pady=20)

    def _build_bottom_bar(self):
        bar = ctk.CTkFrame(self, height=48, fg_color="#f0f4f8", corner_radius=0)
        bar.grid(row=1, column=0, columnspan=3, sticky="ew")
        bar.grid_propagate(False)

        ctk.CTkLabel(bar,
                     text="Drag charts from library onto canvas. Drag header to move. Drag ◢ to resize.",
                     font=ctk.CTkFont(size=11), text_color="#6b8299").pack(
            side="left", padx=16)

        ctk.CTkButton(bar, text="Cancel", width=80, height=34,
                      fg_color="transparent", border_width=1,
                      border_color="#d0dde8", text_color="#4a6278",
                      hover_color="#e8f0f8",
                      command=self._on_cancel).pack(
            side="right", padx=(0, 16), pady=7)

        ctk.CTkButton(bar, text="Build Dashboard ▶", width=160, height=34,
                      fg_color=DHIS2_BLUE, hover_color="#155a8a",
                      command=self._on_ok).pack(
            side="right", padx=(0, 8), pady=7)

        ctk.CTkButton(bar, text="Clear All", width=80, height=34,
                      fg_color="transparent", border_width=1,
                      border_color="#e74c3c", text_color="#e74c3c",
                      hover_color="#fdecea",
                      command=self._clear_all).pack(
            side="right", padx=(0, 8), pady=7)

    # ─── Grid drawing ─────────────────────────────────────────────────────────

    def _draw_grid(self):
        self._canvas.delete("grid")
        w = max(2000, self._canvas.winfo_width())
        h = max(1600, self._canvas.winfo_height())
        for gx in range(0, w, GRID_SNAP):
            self._canvas.create_line(gx, 0, gx, h,
                                      fill=GRID_COLOR, tags="grid", width=1 if gx % 100 == 0 else 0)
        for gy in range(0, h, GRID_SNAP):
            self._canvas.create_line(0, gy, w, gy,
                                      fill=GRID_COLOR, tags="grid", width=1 if gy % 100 == 0 else 0)
        self._canvas.tag_lower("grid")

    # ─── Card drawing ─────────────────────────────────────────────────────────

    def _redraw_all(self):
        self._canvas.delete("card")
        self._draw_grid()
        for card in self._cards:
            self._draw_card(card)

    def _draw_card(self, card: DashCard):
        # Remove old items for this card
        self._canvas.delete(f"card_{card.id}")

        x, y, w, h = card.x, card.y, card.w, card.h
        is_sel = (card is self._selected)
        border = DHIS2_BLUE if is_sel else "#c8d8e8"
        bw     = 2          if is_sel else 1

        tag = f"card_{card.id}"
        tags = ("card", tag)

        # Shadow
        self._canvas.create_rectangle(x + 3, y + 3, x + w + 3, y + h + 3,
                                       fill="#00000015", outline="", tags=tags)
        # Main body
        self._canvas.create_rectangle(x, y, x + w, y + h,
                                       fill=CARD_SEL if is_sel else CARD_BG,
                                       outline=border, width=bw, tags=tags)

        # Header bar
        hdr_color = DHIS2_BLUE if is_sel else "#2a4a6a"
        self._canvas.create_rectangle(x, y, x + w, y + HDR_HEIGHT,
                                       fill=hdr_color, outline="", tags=("card", tag, f"hdr_{card.id}"))

        # Title in header
        title = card.title[:28] + ("…" if len(card.title) > 28 else "")
        self._canvas.create_text(x + 8, y + HDR_HEIGHT / 2,
                                  text=title, fill="white",
                                  font=("Segoe UI", 8, "bold"),
                                  anchor="w", tags=tags)

        # Chart type badge
        tmpl = get_by_id(card.template_id)
        if tmpl:
            badge = tmpl["name"][:16]
            self._canvas.create_text(x + w - 6, y + HDR_HEIGHT / 2,
                                      text=badge, fill="#ffffff99",
                                      font=("Segoe UI", 7),
                                      anchor="e", tags=tags)

        # Chart preview drawing
        preview_y = y + HDR_HEIGHT + 4
        preview_h = h - HDR_HEIGHT - 22
        if preview_h > 20:
            draw_chart_preview(self._canvas, card.template_id,
                                x + 6, preview_y, w - 12, preview_h)

        # Pin count indicator
        pin_count = sum(len(v) for v in card.pinned.values())
        pin_text = f"★ {pin_count} pinned" if pin_count else "⚠ no indicators"
        pin_color = DHIS2_BLUE if pin_count else "#e74c3c"
        self._canvas.create_text(x + 6, y + h - 10,
                                  text=pin_text, fill=pin_color,
                                  font=("Segoe UI", 7), anchor="w", tags=tags)

        # Resize handle (bottom-right triangle)
        self._canvas.create_polygon(
            x + w - HANDLE_SIZE, y + h,
            x + w, y + h - HANDLE_SIZE,
            x + w, y + h,
            fill=DHIS2_BLUE, outline="",
            tags=("card", tag, f"resize_{card.id}"),
        )
        self._canvas.create_text(x + w - 5, y + h - 5,
                                  text="◢", fill="white",
                                  font=("Segoe UI", 7), tags=tags)

        self._canvas.tag_raise(tag, "grid")

    def _snap(self, v: int) -> int:
        return round(v / GRID_SNAP) * GRID_SNAP

    # ─── Palette drag → canvas ────────────────────────────────────────────────

    def _palette_drag_start(self, event, template_id: str):
        self._palette_drag_tid = template_id

    def _palette_drag_motion(self, event):
        pass  # could show a ghost widget — skip for simplicity

    def _palette_drag_drop(self, event):
        tid = self._palette_drag_tid
        self._palette_drag_tid = None
        if not tid:
            return
        # Translate screen coords to canvas coords
        cx = self._canvas.canvasx(self._canvas.winfo_rootx() - self.winfo_rootx() +
                                   self._canvas.winfo_x() + self._canvas.winfo_width() // 2)
        cy = self._canvas.canvasy(self._canvas.winfo_rooty() - self.winfo_rooty() +
                                   self._canvas.winfo_y() + self._canvas.winfo_height() // 2)
        self._add_card(tid, int(cx), int(cy))

    def _add_card(self, template_id: str, cx: int, cy: int):
        tmpl = get_by_id(template_id)
        title = tmpl["name"] if tmpl else template_id
        card = DashCard(
            id=str(uuid.uuid4())[:8],
            template_id=template_id,
            title=title,
            x=self._snap(max(0, cx - DEF_CARD_W // 2)),
            y=self._snap(max(0, cy - DEF_CARD_H // 2)),
            w=DEF_CARD_W,
            h=DEF_CARD_H,
            pinned={k: list(v) for k, v in self._global_pinned.items()},
        )
        self._cards.append(card)
        self._select(card)
        self._redraw_all()

    # ─── Canvas mouse events ──────────────────────────────────────────────────

    def _canvas_click(self, event):
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)
        card = self._card_at(cx, cy)
        if card:
            self._select(card)
            # Check if clicking resize handle
            if (cx > card.x + card.w - HANDLE_SIZE - 4 and
                    cy > card.y + card.h - HANDLE_SIZE - 4):
                self._resize_card = card
                self._resize_ox = cx
                self._resize_oy = cy
                self._resize_ow = card.w
                self._resize_oh = card.h
                self._canvas.config(cursor="sizing")
            else:
                # Start drag
                self._drag_card = card
                self._drag_ox = cx - card.x
                self._drag_oy = cy - card.y
                self._canvas.config(cursor="fleur")
        else:
            self._select(None)

    def _canvas_drag(self, event):
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)
        if self._drag_card:
            card = self._drag_card
            card.x = self._snap(max(0, int(cx - self._drag_ox)))
            card.y = self._snap(max(0, int(cy - self._drag_oy)))
            self._draw_card(card)
        elif self._resize_card:
            card = self._resize_card
            dx = cx - self._resize_ox
            dy = cy - self._resize_oy
            card.w = self._snap(max(MIN_CARD_W, self._resize_ow + int(dx)))
            card.h = self._snap(max(MIN_CARD_H, self._resize_oh + int(dy)))
            self._draw_card(card)

    def _canvas_release(self, event):
        self._drag_card   = None
        self._resize_card = None
        self._canvas.config(cursor="arrow")

    def _canvas_dbl(self, event):
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)
        card = self._card_at(cx, cy)
        if card:
            self._on_configure_pins(card)

    def _canvas_right_click(self, event):
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)
        card = self._card_at(cx, cy)
        if card:
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="Configure Indicators…",
                             command=lambda: self._on_configure_pins(card))
            menu.add_separator()
            menu.add_command(label="Delete Card",
                             command=lambda: self._delete_card(card))
            menu.tk_popup(event.x_root, event.y_root)

    def _card_at(self, cx: float, cy: float) -> Optional[DashCard]:
        """Return topmost card under canvas point, or None."""
        for card in reversed(self._cards):
            if (card.x <= cx <= card.x + card.w and
                    card.y <= cy <= card.y + card.h):
                return card
        return None

    # ─── Selection ────────────────────────────────────────────────────────────

    def _select(self, card: Optional[DashCard]):
        prev = self._selected
        self._selected = card
        if prev and prev is not card:
            self._draw_card(prev)
        if card:
            self._draw_card(card)
            self._update_config_panel(card)
        else:
            self._clear_config_panel()

    def _update_config_panel(self, card: DashCard):
        self._cfg_title.configure(state="normal")
        self._cfg_title.delete(0, "end")
        self._cfg_title.insert(0, card.title)
        self._cfg_title.configure(state="normal")
        # Save title on change
        self._cfg_title.bind("<FocusOut>", lambda e, c=card: self._save_title(c))
        self._cfg_title.bind("<Return>",   lambda e, c=card: self._save_title(c))

        tmpl = get_by_id(card.template_id)
        self._cfg_type_lbl.configure(text=tmpl["name"] if tmpl else "?")

        pin_count = sum(len(v) for v in card.pinned.values())
        self._cfg_pin_lbl.configure(
            text=f"{pin_count} items pinned" if pin_count else "None — click to select",
            text_color=DHIS2_BLUE if pin_count else "#e74c3c")

        self._cfg_pin_btn.configure(state="normal")
        self._cfg_del_btn.configure(state="normal")

    def _clear_config_panel(self):
        self._cfg_title.configure(state="disabled")
        self._cfg_title.delete(0, "end") if self._cfg_title.cget("state") == "normal" else None
        self._cfg_type_lbl.configure(text="—")
        self._cfg_pin_lbl.configure(text="Select a card", text_color="#8aa3b8")
        self._cfg_pin_btn.configure(state="disabled")
        self._cfg_del_btn.configure(state="disabled")

    def _save_title(self, card: DashCard):
        title = self._cfg_title.get().strip()
        if title:
            card.title = title
            self._draw_card(card)

    # ─── Configure indicators for a card ─────────────────────────────────────

    def _on_configure_pins(self, card: DashCard = None):
        card = card or self._selected
        if not card:
            return
        from ui.metadata_selector import MetadataSelector
        from dhis2.usage_tracker import get_counts
        counts = {}  # no URL context here, skip usage counts in builder
        sel = MetadataSelector(self, self._metadata, counts, card.pinned)
        self.wait_window(sel)
        if sel.result is not None:
            card.pinned = sel.result
            self._draw_card(card)
            if self._selected is card:
                self._update_config_panel(card)

    # ─── Delete ───────────────────────────────────────────────────────────────

    def _delete_selected(self):
        if self._selected:
            self._delete_card(self._selected)

    def _delete_card(self, card: DashCard):
        self._canvas.delete(f"card_{card.id}")
        self._cards.remove(card)
        if self._selected is card:
            self._selected = None
            self._clear_config_panel()

    def _clear_all(self):
        self._cards.clear()
        self._selected = None
        self._clear_config_panel()
        self._redraw_all()

    # ─── OK / Cancel ─────────────────────────────────────────────────────────

    def _on_ok(self):
        if not self._cards:
            import tkinter.messagebox as mb
            mb.showwarning("Empty dashboard",
                           "Add at least one chart card before building.",
                           parent=self)
            return
        # Save current title if editing
        if self._selected:
            self._save_title(self._selected)
        self.result = [asdict(c) for c in self._cards]
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


# ─── Scrollbar helper (avoids ttk import at top level) ───────────────────────

def ttk_scrollbar(parent, canvas, orient):
    from tkinter import ttk
    if orient == "vertical":
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    else:
        sb = ttk.Scrollbar(parent, orient="horizontal", command=canvas.xview)
    return sb
