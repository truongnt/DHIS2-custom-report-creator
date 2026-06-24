"""
Draw mini chart previews on a tkinter Canvas.

draw_chart_preview(canvas, template_id, x, y, w, h)
  Draws a representative thumbnail of the chart type at the given bounding box.
  Used both in the palette tiles and in dashboard cards.
"""
from __future__ import annotations
import tkinter as tk
import math

# Palette for previews
_BLUE   = "#1a6fa8"
_GREEN  = "#27ae60"
_ORANGE = "#e67e22"
_PURPLE = "#8e44ad"
_RED    = "#c0392b"
_TEAL   = "#16a085"
_GREY   = "#bdc3c7"
_BG     = "#f8fbff"

_SERIES_COLORS = [_BLUE, _GREEN, _ORANGE, _PURPLE, _RED, _TEAL]


def draw_chart_preview(canvas: tk.Canvas, template_id: str,
                        x: int, y: int, w: int, h: int,
                        color: str | None = None) -> None:
    """Draw a representative preview in the bounding box.
    color: hex color for single-series charts (bar, line, scorecard).
           Multi-series charts (pie, grouped, stacked) keep their palette.
    """
    fn = _DISPATCH.get(template_id, _draw_bar_monthly)
    # Single-series drawers support color override; multi-series ignore it
    _SINGLE_SERIES = {
        "bar_monthly", "line_single", "bar_horizontal_ou", "scorecard", "traffic_light"
    }
    if color and template_id in _SINGLE_SERIES:
        fn(canvas, x, y, w, h, color=color)
    else:
        fn(canvas, x, y, w, h)


# ── helpers ──────────────────────────────────────────────────────────────────

def _lighten(hex_color: str, amount: float = 0.5) -> str:
    """Mix hex_color with white by `amount` (0=original, 1=white)."""
    try:
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return "#d0e8f5"
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r2 = int(r + (255 - r) * amount)
        g2 = int(g + (255 - g) * amount)
        b2 = int(b + (255 - b) * amount)
        return f"#{r2:02x}{g2:02x}{b2:02x}"
    except Exception:
        return "#d0e8f5"


def _pad(x, y, w, h, px=8, py=8):
    return x + px, y + py, w - px * 2, h - py * 2


def _bar(canvas, bx, by, bw, bh, color, alpha_hex="cc"):
    canvas.create_rectangle(bx, by, bx + bw, by + bh,
                             fill=color, outline="", width=0)


def _line_pts(xs, ys, ox, oy):
    return [(ox + x, oy + y) for x, y in zip(xs, ys)]


def _draw_axes(canvas, x, y, w, h, color="#ccc"):
    # X axis
    canvas.create_line(x, y + h, x + w, y + h, fill=color, width=1)
    # Y axis
    canvas.create_line(x, y, x, y + h, fill=color, width=1)


# ── individual drawers ────────────────────────────────────────────────────────

def _draw_line_single(canvas, x, y, w, h, color=None):
    c = color or _BLUE
    # derive a light fill by mixing color toward white
    ix, iy, iw, ih = _pad(x, y, w, h, 10, 10)
    _draw_axes(canvas, ix, iy, iw, ih)
    n = 7
    xs = [ix + i * iw / (n - 1) for i in range(n)]
    raw = [0.7, 0.4, 0.6, 0.3, 0.5, 0.2, 0.45]
    ys = [iy + r * ih for r in raw]
    pts = []
    for px, py2 in zip(xs, ys):
        pts += [px, py2]
    canvas.create_line(pts, fill=c, width=2, smooth=True)
    area = pts + [xs[-1], iy + ih, xs[0], iy + ih]
    canvas.create_polygon(area, fill=_lighten(c), outline="")


def _draw_line_multi(canvas, x, y, w, h):
    ix, iy, iw, ih = _pad(x, y, w, h, 10, 10)
    _draw_axes(canvas, ix, iy, iw, ih)
    n = 6
    xs = [ix + i * iw / (n - 1) for i in range(n)]
    series = [
        ([0.6, 0.3, 0.55, 0.2, 0.45, 0.3], _BLUE),
        ([0.8, 0.6, 0.75, 0.5, 0.65, 0.4], _GREEN),
        ([0.9, 0.75, 0.85, 0.65, 0.8, 0.6], _ORANGE),
    ]
    for raw, color in series:
        ys2 = [iy + r * ih for r in raw]
        pts = []
        for px, py2 in zip(xs, ys2):
            pts += [px, py2]
        canvas.create_line(pts, fill=color, width=2, smooth=True)


def _draw_bar_monthly(canvas, x, y, w, h, color=None):
    c = color or _BLUE
    ix, iy, iw, ih = _pad(x, y, w, h, 10, 10)
    _draw_axes(canvas, ix, iy, iw, ih)
    n = 6
    gap = 3
    bw = (iw - gap * (n - 1)) / n
    heights = [0.6, 0.4, 0.75, 0.5, 0.65, 0.45]
    for i, ratio in enumerate(heights):
        bx = ix + i * (bw + gap)
        bh2 = ih * ratio
        by = iy + ih - bh2
        _bar(canvas, bx, by, bw, bh2, c)


def _draw_bar_grouped(canvas, x, y, w, h):
    ix, iy, iw, ih = _pad(x, y, w, h, 10, 10)
    _draw_axes(canvas, ix, iy, iw, ih)
    groups = 4
    series = 2
    group_w = iw / groups
    bar_w = group_w / (series + 1)
    data = [[0.6, 0.4, 0.7, 0.5], [0.4, 0.7, 0.5, 0.8]]
    colors = [_BLUE, _GREEN]
    for s, (row, color) in enumerate(zip(data, colors)):
        for g, ratio in enumerate(row):
            bx = ix + g * group_w + s * bar_w + bar_w * 0.3
            bh2 = ih * ratio
            _bar(canvas, bx, iy + ih - bh2, bar_w, bh2, color)


def _draw_bar_stacked(canvas, x, y, w, h):
    ix, iy, iw, ih = _pad(x, y, w, h, 10, 10)
    _draw_axes(canvas, ix, iy, iw, ih)
    n = 5
    gap = 4
    bw = (iw - gap * (n - 1)) / n
    # 3 layers per bar
    data = [
        [0.3, 0.25, 0.4, 0.3, 0.35],
        [0.2, 0.3,  0.2, 0.25, 0.2],
        [0.15, 0.2, 0.1, 0.2, 0.15],
    ]
    colors = [_BLUE, _GREEN, _ORANGE]
    for i in range(n):
        base = iy + ih
        bx = ix + i * (bw + gap)
        for s, (row, color) in enumerate(zip(data, colors)):
            seg_h = ih * row[i]
            canvas.create_rectangle(bx, base - seg_h, bx + bw, base,
                                     fill=color, outline="white", width=1)
            base -= seg_h


def _draw_bar_horizontal_ou(canvas, x, y, w, h, color=None):
    c = color or _BLUE
    ix, iy, iw, ih = _pad(x, y, w, h, 22, 8)
    canvas.create_line(ix, iy, ix, iy + ih, fill="#ccc", width=1)
    canvas.create_line(ix, iy + ih, ix + iw, iy + ih, fill="#ccc", width=1)
    rows = 5
    gap = 3
    bar_h = (ih - gap * (rows - 1)) / rows
    widths = [0.9, 0.7, 0.6, 0.45, 0.3]
    shades = [c, _lighten(c, 0.15), _lighten(c, 0.3),
              _lighten(c, 0.45), _lighten(c, 0.6)]
    for i, (ratio, shade) in enumerate(zip(widths, shades)):
        by2 = iy + i * (bar_h + gap)
        bw2 = iw * ratio
        canvas.create_rectangle(ix, by2, ix + bw2, by2 + bar_h,
                                 fill=shade, outline="")
        canvas.create_text(ix - 2, by2 + bar_h / 2,
                            text=["A", "B", "C", "D", "E"][i],
                            anchor="e", font=("Segoe UI", 7), fill="#555")


def _draw_pie(canvas, x, y, w, h):
    cx = x + w / 2
    cy = y + h / 2
    r = min(w, h) / 2 - 8
    slices = [90, 120, 70, 80]
    colors = [_BLUE, _GREEN, _ORANGE, _PURPLE]
    start = 0
    for ext, color in zip(slices, colors):
        canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                          start=start, extent=ext,
                          fill=color, outline="white", width=1)
        start += ext


def _draw_donut(canvas, x, y, w, h):
    cx = x + w / 2
    cy = y + h / 2
    r_out = min(w, h) / 2 - 8
    r_in  = r_out * 0.55
    slices = [110, 90, 80, 80]
    colors = [_BLUE, _GREEN, _ORANGE, _PURPLE]
    start  = 0
    for ext, color in zip(slices, colors):
        canvas.create_arc(cx - r_out, cy - r_out, cx + r_out, cy + r_out,
                          start=start, extent=ext,
                          fill=color, outline="white", width=1)
        start += ext
    # Hollow center
    canvas.create_oval(cx - r_in, cy - r_in, cx + r_in, cy + r_in,
                       fill="white", outline="white")
    canvas.create_text(cx, cy, text="●", font=("Segoe UI", 9, "bold"),
                       fill="#1e2d3d")


def _draw_scorecard(canvas, x, y, w, h, color=None):
    c = color or _BLUE
    cols, rows = 2, 2
    pad = 5
    cw = (w - pad * (cols + 1)) / cols
    ch = (h - pad * (rows + 1)) / rows
    shades = [c, _lighten(c, 0.2), _lighten(c, 0.1), _lighten(c, 0.3)]
    vals   = ["1,240", "87%", "3.2k", "98%"]
    for r in range(rows):
        for ci in range(cols):
            idx  = r * cols + ci
            cx2  = x + pad + ci * (cw + pad)
            cy2  = y + pad + r * (ch + pad)
            canvas.create_rectangle(cx2, cy2, cx2 + cw, cy2 + ch,
                                     fill=shades[idx], outline="")
            canvas.create_text(cx2 + cw / 2, cy2 + ch / 2 - 4,
                                text=vals[idx],
                                font=("Segoe UI", 9, "bold"),
                                fill="white")


def _draw_traffic_light(canvas, x, y, w, h):
    ix, iy, iw, ih = _pad(x, y, w, h, 6, 6)
    rows = 4
    row_h = ih / rows
    colors = [_GREEN, _GREEN, "#f39c12", _RED]
    labels = ["■ 95%", "■ 82%", "■ 76%", "■ 48%"]
    for i, (color, label) in enumerate(zip(colors, labels)):
        ry = iy + i * row_h
        canvas.create_rectangle(ix, ry + 2, ix + iw, ry + row_h - 2,
                                 fill="#f0f4f8", outline="#ddd")
        canvas.create_text(ix + 8, ry + row_h / 2,
                            text=["Indicator A", "Indicator B",
                                  "Indicator C", "Indicator D"][i],
                            anchor="w", font=("Segoe UI", 7), fill="#333")
        canvas.create_text(ix + iw - 6, ry + row_h / 2,
                            text=label, anchor="e",
                            font=("Segoe UI", 7, "bold"), fill=color)


def _draw_data_table(canvas, x, y, w, h):
    ix, iy, iw, ih = _pad(x, y, w, h, 4, 4)
    rows = 5
    cols = 4
    cw   = iw / cols
    rh   = ih / rows
    # Header
    canvas.create_rectangle(ix, iy, ix + iw, iy + rh,
                             fill=_BLUE, outline="")
    for c in range(cols):
        canvas.create_text(ix + c * cw + cw / 2, iy + rh / 2,
                            text=["", "Q1", "Q2", "Q3"][c],
                            font=("Segoe UI", 7, "bold"), fill="white")
    # Body rows
    for r in range(1, rows):
        bg = "#f4f8fc" if r % 2 == 0 else "white"
        canvas.create_rectangle(ix, iy + r * rh, ix + iw, iy + (r + 1) * rh,
                                 fill=bg, outline="#ddd")
        canvas.create_text(ix + 4, iy + r * rh + rh / 2,
                            text=f"Prov {r}", anchor="w",
                            font=("Segoe UI", 7), fill="#333")
        for c in range(1, cols):
            val = str(100 + r * 37 + c * 13)
            canvas.create_text(ix + c * cw + cw / 2, iy + r * rh + rh / 2,
                                text=val, font=("Segoe UI", 7), fill="#333")


def _draw_combined_bar_line(canvas, x, y, w, h):
    ix, iy, iw, ih = _pad(x, y, w, h, 10, 10)
    _draw_axes(canvas, ix, iy, iw, ih)
    n = 6
    gap = 3
    bw = (iw - gap * (n - 1)) / n
    bar_data = [0.5, 0.65, 0.45, 0.7, 0.55, 0.6]
    line_data = [0.3, 0.45, 0.35, 0.55, 0.4, 0.5]

    # Bars
    for i, ratio in enumerate(bar_data):
        bx = ix + i * (bw + gap)
        bh2 = ih * ratio
        _bar(canvas, bx, iy + ih - bh2, bw, bh2, "#6aafcf")

    # Line overlay
    xs = [ix + i * (bw + gap) + bw / 2 for i in range(n)]
    ys = [iy + ih - ih * r for r in line_data]
    pts = []
    for px, py2 in zip(xs, ys):
        pts += [px, py2]
    canvas.create_line(pts, fill=_RED, width=2, smooth=True)
    for px, py2 in zip(xs, ys):
        canvas.create_oval(px - 2, py2 - 2, px + 2, py2 + 2,
                           fill=_RED, outline="white")


def _draw_combined_full(canvas, x, y, w, h):
    # Mini KPI row
    kpi_h = h * 0.28
    for i, color in enumerate([_BLUE, _GREEN, _ORANGE, _PURPLE]):
        kx = x + i * w / 4 + 2
        canvas.create_rectangle(kx, y + 4, kx + w / 4 - 4, y + kpi_h,
                                 fill=color, outline="")
    # Trend chart (left 60%)
    tx, ty, tw, th = x + 2, y + kpi_h + 6, w * 0.58, h - kpi_h - 10
    _draw_axes(canvas, tx, ty, tw, th, "#ddd")
    n = 5
    xs = [tx + i * tw / (n - 1) for i in range(n)]
    for raw, color in [([0.4, 0.6, 0.3, 0.7, 0.5], _BLUE),
                        ([0.6, 0.4, 0.8, 0.5, 0.7], _GREEN)]:
        ys2 = [ty + r * th for r in raw]
        pts = [v for pair in zip(xs, ys2) for v in pair]
        canvas.create_line(pts, fill=color, width=1.5, smooth=True)
    # Donut (right 40%)
    dx = x + w * 0.62
    dy = y + kpi_h + 6
    dw = w * 0.36
    dh = h - kpi_h - 10
    cx2 = dx + dw / 2
    cy2 = dy + dh / 2
    r2  = min(dw, dh) / 2 - 4
    ri  = r2 * 0.5
    for start, ext, color in [(0, 130, _BLUE), (130, 100, _GREEN), (230, 130, _ORANGE)]:
        canvas.create_arc(cx2 - r2, cy2 - r2, cx2 + r2, cy2 + r2,
                          start=start, extent=ext, fill=color, outline="white")
    canvas.create_oval(cx2 - ri, cy2 - ri, cx2 + ri, cy2 + ri,
                       fill="white", outline="white")


_DISPATCH = {
    "line_single":       _draw_line_single,
    "line_multi":        _draw_line_multi,
    "bar_monthly":       _draw_bar_monthly,
    "bar_grouped":       _draw_bar_grouped,
    "bar_stacked":       _draw_bar_stacked,
    "bar_horizontal_ou": _draw_bar_horizontal_ou,
    "pie":               _draw_pie,
    "donut":             _draw_donut,
    "scorecard":         _draw_scorecard,
    "traffic_light":     _draw_traffic_light,
    "data_table":        _draw_data_table,
    "combined_bar_line": _draw_combined_bar_line,
    "combined_full":     _draw_combined_full,
}
