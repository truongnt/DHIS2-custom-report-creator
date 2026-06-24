"""
PreviewPanel — right-side panel showing chart preview.

Fixed templates  → draws via preview_canvas.py (tkinter Canvas, instant).
AI generate      → spinner while waiting, then "Open in browser" button.
"""
from __future__ import annotations
import tkinter as tk
import customtkinter as ctk
import webbrowser
from pathlib import Path

from charts.preview_canvas import draw_chart_preview

DHIS2_BLUE  = "#1a6fa8"
PANEL_BG    = "#f7f9fc"
BORDER_CLR  = "#d0dde8"

# Map fixed template IDs to preview_canvas drawer IDs
_PREVIEW_MAP = {
    "ft_bar_monthly":  "bar_monthly",
    "ft_line_trend":   "line_single",
    "ft_stacked_cat":  "bar_stacked",
    "ft_pie_cat":      "pie",
    "ft_bar_ou":       "bar_horizontal_ou",
    "ft_scorecard":    "scorecard",
}


class PreviewPanel(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", PANEL_BG)
        kw.setdefault("corner_radius", 0)
        super().__init__(master, **kw)

        self._current_html: Path | None = None
        self._canvas_w = 600
        self._canvas_h = 420

        self._build()
        self.show_placeholder()

    # ─── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_rowconfigure(0, weight=0)  # header
        self.grid_rowconfigure(1, weight=1)  # content
        self.grid_columnconfigure(0, weight=1)

        # Header bar
        hdr = ctk.CTkFrame(self, fg_color="#e8eef5", corner_radius=0, height=36)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)

        self._hdr_label = ctk.CTkLabel(
            hdr, text="Preview", font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#3a5068")
        self._hdr_label.grid(row=0, column=0, padx=14, pady=6, sticky="w")

        self._open_btn = ctk.CTkButton(
            hdr, text="Open in browser", width=130, height=26,
            fg_color=DHIS2_BLUE, hover_color="#155a8a",
            font=ctk.CTkFont(size=11),
            command=self._open_browser)
        self._open_btn.grid(row=0, column=1, padx=10, pady=5, sticky="e")
        self._open_btn.grid_remove()

        # Content area
        self._content = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=0)
        self._content.grid(row=1, column=0, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        # Placeholder label
        self._placeholder = ctk.CTkLabel(
            self._content,
            text="Select a data source\nand chart type to preview",
            font=ctk.CTkFont(size=14), text_color="#8aa3b8",
            justify="center")
        self._placeholder.grid(row=0, column=0)

        # Canvas for tkinter-drawn previews
        self._canvas_frame = ctk.CTkFrame(
            self._content, fg_color="white", corner_radius=8,
            border_color=BORDER_CLR, border_width=1)
        self._canvas_frame.grid(row=0, column=0, padx=24, pady=24, sticky="nsew")
        self._canvas_frame.grid_remove()

        self._canvas_frame.grid_rowconfigure(0, weight=0)
        self._canvas_frame.grid_rowconfigure(1, weight=1)
        self._canvas_frame.grid_columnconfigure(0, weight=1)

        self._chart_title_lbl = ctk.CTkLabel(
            self._canvas_frame, text="",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#1e2d3d")
        self._chart_title_lbl.grid(row=0, column=0, pady=(12, 4))

        self._tk_canvas = tk.Canvas(
            self._canvas_frame, bg="white",
            highlightthickness=0,
            width=self._canvas_w, height=self._canvas_h)
        self._tk_canvas.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")

        # Spinner / loading frame
        self._loading_frame = ctk.CTkFrame(self._content, fg_color=PANEL_BG, corner_radius=0)
        self._loading_frame.grid(row=0, column=0)
        self._loading_frame.grid_remove()

        self._spinner_lbl = ctk.CTkLabel(
            self._loading_frame, text="⏳",
            font=ctk.CTkFont(size=36))
        self._spinner_lbl.pack(pady=(60, 8))
        self._loading_msg = ctk.CTkLabel(
            self._loading_frame, text="Generating with AI...",
            font=ctk.CTkFont(size=13), text_color="#5a7a9a")
        self._loading_msg.pack()

        # AI done frame
        self._done_frame = ctk.CTkFrame(self._content, fg_color=PANEL_BG, corner_radius=0)
        self._done_frame.grid(row=0, column=0)
        self._done_frame.grid_remove()

        ctk.CTkLabel(self._done_frame, text="✅",
                     font=ctk.CTkFont(size=36)).pack(pady=(60, 8))
        self._done_msg = ctk.CTkLabel(
            self._done_frame, text="Dashboard generated",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#1e2d3d")
        self._done_msg.pack(pady=(0, 16))
        ctk.CTkButton(
            self._done_frame, text="Open in browser", width=160, height=36,
            fg_color=DHIS2_BLUE, hover_color="#155a8a",
            font=ctk.CTkFont(size=13),
            command=self._open_browser).pack()

    # ─── Public API ───────────────────────────────────────────────────────────

    def show_placeholder(self):
        self._hide_all()
        self._hdr_label.configure(text="Preview")
        self._placeholder.grid()

    def show_chart(self, template_id: str, title: str = ""):
        """Draw a static sample preview for the given fixed template type."""
        self._hide_all()
        drawer_id = _PREVIEW_MAP.get(template_id, "bar_monthly")
        self._chart_title_lbl.configure(text=title or "Sample Preview")
        self._canvas_frame.grid()
        self._hdr_label.configure(text="Preview — sample data")

        # Draw after canvas is visible and has real dimensions
        self._canvas_frame.update_idletasks()
        w = self._tk_canvas.winfo_width() or self._canvas_w
        h = self._tk_canvas.winfo_height() or self._canvas_h
        self._tk_canvas.configure(width=w, height=h)
        self._tk_canvas.delete("all")
        draw_chart_preview(self._tk_canvas, drawer_id, 0, 0, w, h)

    def show_loading(self, msg: str = "Generating with AI..."):
        self._hide_all()
        self._hdr_label.configure(text="Generating...")
        self._loading_msg.configure(text=msg)
        self._loading_frame.grid()

    def show_ai_done(self, html_path: str | Path):
        self._hide_all()
        self._current_html = Path(html_path)
        self._hdr_label.configure(text="AI — ready")
        self._open_btn.grid()
        self._done_frame.grid()

    def show_error(self, msg: str):
        self._hide_all()
        self._hdr_label.configure(text="Error")
        self._placeholder.configure(text=f"⚠ {msg}")
        self._placeholder.grid()

    # ─── Internals ────────────────────────────────────────────────────────────

    def _hide_all(self):
        self._open_btn.grid_remove()
        self._placeholder.grid_remove()
        self._canvas_frame.grid_remove()
        self._loading_frame.grid_remove()
        self._done_frame.grid_remove()

    def _open_browser(self):
        if self._current_html and self._current_html.exists():
            webbrowser.open(self._current_html.as_uri())

    def on_resize(self, event=None):
        """Call when panel resizes to redraw the canvas at correct size."""
        if self._canvas_frame.winfo_ismapped():
            w = self._tk_canvas.winfo_width()
            h = self._tk_canvas.winfo_height()
            if w > 10 and h > 10:
                self._tk_canvas.delete("all")
                # Re-draw — we store last template_id/title for this
                if hasattr(self, "_last_drawer"):
                    draw_chart_preview(self._tk_canvas, self._last_drawer, 0, 0, w, h)

    def show_chart_tracked(self, template_id: str, title: str = ""):
        self._last_drawer = _PREVIEW_MAP.get(template_id, "bar_monthly")
        self.show_chart(template_id, title)
