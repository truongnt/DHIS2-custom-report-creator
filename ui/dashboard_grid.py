"""
GridCanvas — a 12-column dashboard grid (Superset-style) for the manual builder.

Layout model: an ordered list of items, each {cfg, w, h, card}. Positions (x=col,
y=row) are derived by left-to-right auto-flow that wraps at 12 columns — so removing
or resizing a card reflows the rest (REQ-DASH-GRID-04/05).

Each card is a lightweight config tile (title + meta + type hint) with three resize
grips placed as REAL layout cells (not overlays, so nothing can cover them):
  - right edge  → width  (column span)   cursor: ↔ SizeHor
  - bottom edge → height (row units)     cursor: ↕ SizeVer
  - corner      → both                   cursor: ↘ SizeFDiag
plus ⊟/⊞ width buttons and an ✕ remove button. The actual chart renders via the
"👁 Preview" button on the toolbar (opens the assembled dashboard in the browser),
mirroring the Chart Editor's preview.

Card widgets are persistent (cached per item) so a reflow repositions them without
recreating them. Mouse-drag gestures (sidebar→canvas add, body reorder, grip resize)
are wired but verified manually; the math they call is covered by tests.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QMimeData, Signal
from PySide6.QtGui import QFont, QDrag, QCursor
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QGridLayout, QHBoxLayout,
    QVBoxLayout, QScrollArea, QSizePolicy,
)

DHIS2_BLUE = "#1a6fa8"
PANEL_BG   = "#f7f9fc"
BORDER_CLR = "#d0dde8"

MIME_LIB_CHART = "application/x-autoreport-chart"     # drag from library (carries chart id)
MIME_GRID_MOVE = "application/x-autoreport-grid-move" # internal reorder (carries item index)

ROW_PX = 150          # one "row unit" of card height
MAX_ROWS = 6          # height clamp (row units)


class _EdgeGrip(QFrame):
    """A draggable resize strip on a card edge/corner (REQ-DASH-GRID-03).

    axis: 'h' (width), 'v' (height), or 'both' (corner).
    """
    _CURSOR = {
        "h":    Qt.CursorShape.SizeHorCursor,
        "v":    Qt.CursorShape.SizeVerCursor,
        "both": Qt.CursorShape.SizeFDiagCursor,
    }

    def __init__(self, card: "_GridCard", axis: str):
        super().__init__(card)
        self._card = card
        self._axis = axis
        self.setCursor(QCursor(self._CURSOR[axis]))
        if axis == "h":
            self.setFixedWidth(7)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            self.setToolTip("Drag to resize width")
        elif axis == "v":
            self.setFixedHeight(7)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.setToolTip("Drag to resize height")
        else:
            self.setFixedSize(14, 14)
            self.setToolTip("Drag to resize")
        self._tint(False)
        self._px = self._py = 0
        self._pw = self._ph = 1

    def _tint(self, on: bool):
        self.setStyleSheet(
            f"background-color: {'#cfe0f0' if on else 'transparent'};"
            "border: none; border-radius: 2px;")

    def enterEvent(self, ev):
        self._tint(True); super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._tint(False); super().leaveEvent(ev)

    def mousePressEvent(self, ev):
        p = ev.globalPosition().toPoint()
        self._px, self._py = p.x(), p.y()
        self._pw = self._card._canvas.width_of(self._card)
        self._ph = self._card._canvas.height_of(self._card)
        ev.accept()

    def mouseMoveEvent(self, ev):
        if not (ev.buttons() & Qt.MouseButton.LeftButton):
            return
        p = ev.globalPosition().toPoint()
        canvas = self._card._canvas
        if self._axis in ("h", "both"):
            dcols = round((p.x() - self._px) / max(1.0, canvas.column_pixel_width()))
            canvas.set_width_of(self._card, self._pw + dcols)
        if self._axis in ("v", "both"):
            drows = round((p.y() - self._py) / ROW_PX)
            canvas.set_height_of(self._card, self._ph + drows)
        ev.accept()


class _GridCard(QFrame):
    """A lightweight config tile with edge/corner resize grips."""

    def __init__(self, canvas: "GridCanvas", cfg: dict):
        super().__init__()
        self._canvas = canvas
        self._cfg = cfg
        self.setStyleSheet(
            "QFrame {"
            "  background-color: white;"
            f" border: 1px dashed {DHIS2_BLUE};"     # dashed = edit mode (REQ-DASH-GRID-06)
            "  border-radius: 6px;"
            "}"
        )
        # Fixed vertical size + AlignTop placement → each card's height is INDEPENDENT
        # (QGridLayout rows share height, so without this a tall card would stretch its
        #  row-mates; fixed height + top alignment lets neighbours keep their own height).
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(ROW_PX)

        # Internal grid: content (0,0) + right grip (0,1) + bottom grip (1,0) + corner (1,1)
        g = QGridLayout(self)
        g.setContentsMargins(2, 2, 2, 2)
        g.setSpacing(0)
        g.setRowStretch(0, 1)
        g.setColumnStretch(0, 1)
        g.addWidget(self._build_content(cfg), 0, 0)
        g.addWidget(_EdgeGrip(self, "h"),    0, 1)
        g.addWidget(_EdgeGrip(self, "v"),    1, 0)
        g.addWidget(_EdgeGrip(self, "both"), 1, 1)

    def _build_content(self, cfg: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet("border: none; background: transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 6, 4, 4)
        v.setSpacing(2)

        top = QHBoxLayout(); top.setContentsMargins(0, 0, 0, 0); top.setSpacing(4)
        color = cfg.get("chart_color", "#3498db")
        name = cfg.get("name") or cfg.get("title", "?")
        title = QLabel(f"●  {name}")
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {color}; border: none;")
        top.addWidget(title, 1)

        # Width controls — plain "−"/"+" render on every font (⊟/⊞ often showed blank).
        for sym, delta, tip in (("-", -1, "Narrow (-1 column)"), ("+", +1, "Widen (+1 column)")):
            b = QPushButton(sym)
            b.setFixedSize(20, 20); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(tip)
            b.setStyleSheet(
                "QPushButton { background: #eef4fa; border: none; border-radius: 3px;"
                "  color: #4a6a80; font-size: 14px; font-weight: bold; }"
                "QPushButton:hover { background: #d8e8f6; }")
            b.clicked.connect(lambda _=False, d=delta: self._canvas.nudge_width_of(self, d))
            top.addWidget(b)

        opn = QPushButton("Edit"); opn.setFixedHeight(20); opn.setCursor(Qt.CursorShape.PointingHandCursor)
        opn.setToolTip("Open this chart in the Chart Editor")
        opn.setStyleSheet(
            "QPushButton { background: #eef4fa; border: none; border-radius: 3px; color: #1a6fa8;"
            "  font-size: 10px; font-weight: bold; padding: 0 7px; }"
            "QPushButton:hover { background: #d8e8f6; }")
        opn.clicked.connect(lambda: self._canvas.open_card(self))
        top.addWidget(opn)

        rm = QPushButton("✕"); rm.setObjectName("cardRemoveBtn")
        rm.setFixedSize(20, 20); rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setToolTip("Remove chart from dashboard")
        rm.setStyleSheet(
            "QPushButton#cardRemoveBtn { background: #f0f4f8; border: none; border-radius: 3px;"
            "  color: #c0392b; font-size: 14px; font-weight: bold; min-width: 0px; padding: 0px; }"
            "QPushButton#cardRemoveBtn:hover { background: #f5c6cb; }")
        rm.clicked.connect(lambda: self._canvas.remove_card(self))
        top.addWidget(rm)
        v.addLayout(top)

        tmpl = cfg.get("template_label", cfg.get("template_id", ""))
        self._meta = QLabel(f"{tmpl}  •  col-{cfg.get('col_width', 6)}")
        self._meta.setFont(QFont("Segoe UI", 8))
        self._meta.setStyleSheet("color: #8aa3b8; border: none;")
        v.addWidget(self._meta)

        hint = QLabel("📊  " + (tmpl or "chart"))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #c2cfdb; border: none;")
        hint.setFont(QFont("Segoe UI", 11))
        v.addWidget(hint, 1)
        return w

    def set_width_label(self, w: int) -> None:
        tmpl = self._cfg.get("template_label", self._cfg.get("template_id", ""))
        self._meta.setText(f"{tmpl}  •  col-{w}")

    # ── Reorder: drag the card body ──────────────────────────────────────────
    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(MIME_GRID_MOVE, str(self._canvas.index_of(self)).encode())
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)
        super().mouseMoveEvent(ev)


class GridCanvas(QScrollArea):
    """Scrollable 12-column grid. Holds the ordered layout model for manual mode."""

    COLS = 12
    changed = Signal()          # emitted whenever the model changes (add/remove/resize/move)
    external_drop = Signal(str) # a library chart id was dropped onto the canvas (REQ-DASH-GRID-02)
    open_chart = Signal(dict)   # user clicked a card's "open in editor" button → its cfg

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._items: list[dict] = []        # [{"cfg", "w", "h", "card"}]
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAcceptDrops(True)
        self.setStyleSheet(f"QScrollArea {{ background-color: {PANEL_BG}; border: none; }}")

        self._host = QWidget()
        self._host.setStyleSheet(f"background-color: {PANEL_BG};")
        self._grid = QGridLayout(self._host)
        self._grid.setContentsMargins(8, 8, 8, 8)
        self._grid.setSpacing(8)
        for c in range(self.COLS):
            self._grid.setColumnStretch(c, 1)

        self._empty = QLabel("Drag and drop charts from the left to build your dashboard.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setFont(QFont("Segoe UI", 11))
        self._empty.setStyleSheet(f"color: #8aa3b8; padding: 40px; background: {PANEL_BG};")
        self._grid.addWidget(self._empty, 0, 0, 1, self.COLS)

        self.setWidget(self._host)

    # ── Helpers tying a card widget back to its model item ──────────────────────

    def _item_for(self, card: _GridCard) -> dict | None:
        return next((it for it in self._items if it.get("card") is card), None)

    def index_of(self, card: _GridCard) -> int:
        for i, it in enumerate(self._items):
            if it.get("card") is card:
                return i
        return -1

    def width_of(self, card: _GridCard) -> int:
        it = self._item_for(card)
        return it["w"] if it else 6

    def height_of(self, card: _GridCard) -> int:
        it = self._item_for(card)
        return it["h"] if it else 1

    def column_pixel_width(self) -> float:
        return max(1.0, self.viewport().width() / self.COLS)

    # ── Model operations ───────────────────────────────────────────────────────

    def add_card(self, cfg: dict, w: int = 6) -> int:
        """Append a card; width/height from cfg['col_width']/['layout'], stamped back."""
        layout = cfg.get("layout") or {}
        w = max(1, min(self.COLS, int(cfg.get("col_width") or layout.get("w") or w)))
        h = max(1, min(MAX_ROWS, int(layout.get("h") or 1)))
        cfg["col_width"] = w
        self._items.append({"cfg": cfg, "w": w, "h": h, "card": None})
        self._relayout()
        self.changed.emit()
        return len(self._items) - 1

    def remove_at(self, index: int) -> None:
        if 0 <= index < len(self._items):
            self._discard_card(self._items.pop(index))
            self._relayout()
            self.changed.emit()

    def open_card(self, card: "_GridCard") -> None:
        """Emit the card's chart config so the host can open it in the Chart Editor."""
        self.open_chart.emit(dict(card._cfg))

    def remove_card(self, card: _GridCard) -> None:
        self.remove_at(self.index_of(card))

    def set_width(self, index: int, w: int) -> None:
        if 0 <= index < len(self._items):
            w = max(1, min(self.COLS, int(w)))
            it = self._items[index]
            if w == it["w"]:
                return
            it["w"] = w
            it["cfg"]["col_width"] = w           # keep cfg in sync for export/persist
            if it.get("card"):
                it["card"].set_width_label(w)
            self._relayout()
            self.changed.emit()

    def set_height(self, index: int, h: int) -> None:
        if 0 <= index < len(self._items):
            h = max(1, min(MAX_ROWS, int(h)))
            it = self._items[index]
            if h == it["h"]:
                return
            it["h"] = h
            it["cfg"].setdefault("layout", {})["h"] = h   # keep cfg in sync for export/persist
            self._relayout()
            self.changed.emit()

    def set_width_of(self, card: _GridCard, w: int) -> None:
        self.set_width(self.index_of(card), w)

    def set_height_of(self, card: _GridCard, h: int) -> None:
        self.set_height(self.index_of(card), h)

    def nudge_width_of(self, card: _GridCard, delta: int) -> None:
        i = self.index_of(card)
        if i >= 0:
            self.set_width(i, self._items[i]["w"] + delta)

    def move(self, frm: int, to: int) -> None:
        n = len(self._items)
        if 0 <= frm < n and 0 <= to < n and frm != to:
            self._items.insert(to, self._items.pop(frm))
            self._relayout()
            self.changed.emit()

    def clear(self) -> None:
        for it in self._items:
            self._discard_card(it)
        self._items.clear()
        self._relayout()
        self.changed.emit()

    def cards(self) -> list[dict]:
        return [it["cfg"] for it in self._items]

    def layout_specs(self) -> list[dict]:
        """Derived {x,y,w,h} per card from left-to-right auto-flow (REQ-DASH-GRID-01)."""
        specs, col, row = [], 0, 0
        for it in self._items:
            w = it["w"]
            if col + w > self.COLS:
                col, row = 0, row + 1
            specs.append({"x": col, "y": row, "w": w, "h": it["h"]})
            col += w
        return specs

    def cards_with_layout(self) -> list[dict]:
        return [{**it["cfg"], "layout": spec}
                for it, spec in zip(self._items, self.layout_specs())]

    def count(self) -> int:
        return len(self._items)

    # ── Rendering (persistent cards) ─────────────────────────────────────────────

    def _discard_card(self, item: dict) -> None:
        card = item.get("card")
        if card is not None:
            card.setParent(None)
            card.deleteLater()
            item["card"] = None

    def _relayout(self) -> None:
        while self._grid.count():
            self._grid.takeAt(0)

        # Keep the placeholder parented to the host at ALL times. Reparenting it to None
        # and calling .show() could pop it as a separate top-level window (it inherits
        # the app name as its title) — observed when loading a saved dashboard.
        if self._empty.parent() is not self._host:
            self._empty.setParent(self._host)

        if not self._items:
            self._grid.addWidget(self._empty, 0, 0, 1, self.COLS)
            self._empty.setVisible(True)
            return

        self._empty.setVisible(False)

        for it, spec in zip(self._items, self.layout_specs()):
            if it.get("card") is None:
                it["card"] = _GridCard(self, it["cfg"])
            card = it["card"]
            card.set_width_label(it["w"])
            card.setFixedHeight(ROW_PX * it["h"])           # independent height (px)
            # rowSpan stays 1; height is controlled by the fixed pixel height above so a
            # tall card never forces its row-mates to match. AlignTop keeps short cards up.
            self._grid.addWidget(card, spec["y"], spec["x"], 1, spec["w"],
                                 Qt.AlignmentFlag.AlignTop)
            card.show()

    # ── Drag-and-drop wiring (gesture verified manually) ─────────────────────────

    def dragEnterEvent(self, ev):
        md = ev.mimeData()
        if md.hasFormat(MIME_LIB_CHART) or md.hasFormat(MIME_GRID_MOVE):
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev):
        ev.acceptProposedAction()

    def dropEvent(self, ev):
        md = ev.mimeData()
        if md.hasFormat(MIME_GRID_MOVE):
            frm = int(bytes(md.data(MIME_GRID_MOVE)).decode() or -1)
            self.move(frm, self._drop_target_index(ev))
            ev.acceptProposedAction()
        elif md.hasFormat(MIME_LIB_CHART):
            chart_id = bytes(md.data(MIME_LIB_CHART)).decode()
            self.external_drop.emit(chart_id)   # panel resolves the id → add_card
            ev.acceptProposedAction()

    def _drop_target_index(self, ev) -> int:
        y = ev.position().toPoint().y() if hasattr(ev, "position") else 0
        n = 0
        for it in self._items:
            card = it.get("card")
            if card is not None:
                if y < card.y() + card.height() / 2:
                    return n
                n += 1
        return max(0, len(self._items) - 1)
