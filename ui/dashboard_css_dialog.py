"""CustomCssDialog — edit a dashboard's shared CSS (REQ-DASH-CSS-02, -06).

Superset-style "Edit CSS": one raw CSS block applied to the whole dashboard page.
The user can start from the dashboard's real base styles or from a ready-made theme
template (STYLE_TEMPLATES) and then tweak freely.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from ui.qt_utils import DHIS2_BLUE, PANEL_BG, style_dialog_buttons


def card_spacing_css(px: int) -> str:
    """CSS controlling the gap between dashboard cards (Bootstrap grid gutters).

    Bootstrap 5 rows derive horizontal/vertical spacing from --bs-gutter-x/-y, but the
    cards also carry a fixed `mb-4` bottom margin that would stack on top of the vertical
    gutter. We neutralise `mb-4` so the gap is EXACTLY `px` on both axes (REQ-DASH-CSS-08).
    """
    return ("/* Gap between cards */\n"
            f".container-fluid .row {{ --bs-gutter-x:{px}px; --bs-gutter-y:{px}px; }}\n"
            f'.container-fluid .row > [class*="col-"] {{ margin-bottom:0 !important; }}')

# ── Style templates ─────────────────────────────────────────────────────────
# "Base" mirrors the real default styles baked into charts.fixed_templates._PAGE_SHELL
# (body / #controls / .card-header / .chart-wrapper …). Editing these overrides the
# defaults. #controls is styled inline on the element, so it needs !important to win.
# Every rule is on ONE line with a trailing comment saying what it does (REQ-DASH-CSS-12).
_BASE_CSS = """\
/* ==== Dashboard default styles — change values to override ==== */
body                  { background:#f0f4f8; }                              /* page background */
#controls             { background:#f0f4f8 !important; }                   /* filter bar background */
#controls             { border-bottom:1px solid #d0dde8 !important; }      /* filter bar bottom border */
.card-header          { background:#1a6fa8; }                             /* card title background */
.card-header          { color:#fff; }                                     /* card title text colour */
.card-header          { padding:8px 14px; }                               /* card title padding */
.card-header h6       { font-size:13px; font-weight:600; }                /* card title font size & weight */
.card                 { box-shadow:0 1px 3px rgba(0,0,0,.08); }           /* subtle card shadow */
.card-body            { padding:12px; }                                   /* card body (chart area) padding */
.chart-wrapper        { position:relative; }                              /* chart container */
.container-fluid .row                    { --bs-gutter-x:24px; --bs-gutter-y:24px; }  /* horizontal & vertical gap between cards */
.container-fluid .row > [class*="col-"]  { margin-bottom:0 !important; }              /* drop mb-4 so gap equals the gutter exactly */"""

_DARK_CSS = """\
/* ==== Dark theme ==== */
body              { background:#0f1720; }                    /* dark page background */
body              { color:#e6edf3; }                         /* light text on dark background */
#controls         { background:#111c28 !important; }         /* dark filter bar background */
#controls         { color:#cbd5e1 !important; }              /* filter bar text colour */
#controls         { border-bottom:1px solid #22303c !important; }  /* filter bar bottom border */
#controls select  { background:#1b2733; color:#e6edf3; border-color:#33465a; }  /* filter dropdowns */
.card             { background:#111c28; border:1px solid #22303c; }  /* dark card background & border */
.card-header      { background:#16324a; }                    /* card title background */
.card-header      { color:#eaf2f8; }                         /* card title text */
.card-body        { background:#111c28; }                    /* card body background */
.demo-banner      { background:#2a2410; color:#e8d48a; border-color:#5a4b12; }  /* "sample data" banner tuned for dark */"""

_COMPACT_CSS = """\
/* ==== Compact — fit more cards on screen ==== */
.container-fluid  { padding:6px !important; }        /* shrink outer container padding */
.card             { margin-bottom:8px !important; }  /* reduce gap below each card */
.card-header      { padding:4px 10px; }              /* shrink card title padding */
.card-header h6   { font-size:12px; }                /* smaller card title text */
.card-body        { padding:6px !important; }        /* shrink card body padding */
#controls         { padding:4px 12px !important; }   /* shrink filter bar padding */"""

_ROUNDED_CSS = """\
/* ==== Soft / rounded — rounded cards, soft shadow ==== */
body           { background:#eef3f8; }                       /* light page background */
.card          { border:none; }                              /* remove card border */
.card          { border-radius:14px; overflow:hidden; }      /* round corners & clip overflow */
.card          { box-shadow:0 6px 18px rgba(20,60,90,.12); } /* soft drop shadow */
.card-header   { background:linear-gradient(90deg,#1a6fa8,#2b90cf); }  /* blue gradient title */"""

_GREEN_CSS = """\
/* ==== Health green ==== */
body         { background:#f1f7f3; }                              /* light green page background */
#controls    { background:#e8f5ee !important; }                   /* light green filter bar */
#controls    { border-bottom:1px solid #b7dfc9 !important; }      /* filter bar bottom border */
.card-header { background:#1b7f5b; }                              /* green card title */
#loadBtn     { background:#1b7f5b !important; }                   /* green "Load data" button */"""

_PRINT_CSS = """\
/* ==== Print / report — white background, clear borders, PDF-friendly ==== */
body           { background:#ffffff; }                            /* white background */
#controls      { background:#ffffff !important; }                 /* white filter bar */
#controls      { border-bottom:1px solid #ccc !important; }       /* filter bar bottom border */
.card          { border:1px solid #ccc; box-shadow:none; }        /* grey border, no shadow */
.card          { break-inside:avoid; }                            /* avoid splitting a card across pages */
.card-header   { background:#ffffff; color:#1a3550; }             /* white title, dark text */
.card-header   { border-bottom:2px solid #1a6fa8; }               /* underline under title */
.card-header h6{ color:#1a3550; }                                 /* title text colour */"""

# Ordered mapping shown in the template dropdown.
STYLE_TEMPLATES: dict[str, str] = {
    "Base (current defaults)": _BASE_CSS,
    "Dark": _DARK_CSS,
    "Compact": _COMPACT_CSS,
    "Rounded / soft": _ROUNDED_CSS,
    "Health green": _GREEN_CSS,
    "Print / report": _PRINT_CSS,
}

_PICK_HINT = "— Insert a style template… —"

# ── Filter-bar layouts ───────────────────────────────────────────────────────
# The filter bar is the #controls element. These snippets re-lay-it-out and DO NOT set
# colours, so they combine cleanly with any theme template above (REQ-DASH-CSS-13).
# Axes offered: position top/left/right · orientation horizontal/vertical ·
#   "sticky" (stays pinned while scrolling) vs "scroll" (scrolls away with the page).
# NOTE: #controls has INLINE styles (position:sticky, top:0, align-items:center…), and inline
# beats an id selector — so layout-critical props below use !important to actually win.
_FILTER_TOP_STICKY = """\
/* ==== Filter bar: TOP · HORIZONTAL · STICKY (pinned while scrolling) ==== */
#controls        { position:sticky !important; top:0 !important; z-index:100; }  /* pin to top on scroll */
#controls        { flex-direction:row !important; flex-wrap:wrap; }              /* lay filters out in a row */
.container-fluid { margin-left:0; margin-right:0; }                             /* content uses full width */"""

_FILTER_TOP_SCROLL = """\
/* ==== Filter bar: TOP · HORIZONTAL · SCROLL (scrolls away with the page) ==== */
#controls        { position:static !important; }                     /* NOT pinned — scrolls with the page */
#controls        { flex-direction:row !important; flex-wrap:wrap; }   /* lay filters out in a row */
.container-fluid { margin-left:0; margin-right:0; }                  /* content uses full width */"""

_FILTER_LEFT_STICKY = """\
/* ==== Filter bar: LEFT · VERTICAL · STICKY (fixed left column) ==== */
#controls        { position:fixed !important; top:0 !important; left:0; bottom:0; width:220px; }  /* fixed left column */
#controls        { flex-direction:column !important; align-items:stretch !important; overflow:auto; }  /* stack vertically, scroll if long */
#controls        { border-bottom:none; border-right:1px solid #d0dde8; }                          /* divider on the right */
#controls select { width:100%; }                                                                  /* dropdowns fill the column */
.container-fluid { margin-left:220px; }                                                           /* leave room for the filter column */"""

_FILTER_LEFT_SCROLL = """\
/* ==== Filter bar: LEFT · VERTICAL · SCROLL (left column, scrolls with the page) ==== */
#controls        { position:static !important; float:left; width:220px; }                         /* left column, NOT pinned */
#controls        { flex-direction:column !important; align-items:stretch !important; }             /* stack vertically */
#controls        { border-bottom:none; border-right:1px solid #d0dde8; }                          /* divider on the right */
#controls select { width:100%; }                                                                  /* dropdowns fill the column */
.container-fluid { margin-left:220px; }                                                           /* leave room for the filter column */"""

_FILTER_RIGHT_STICKY = """\
/* ==== Filter bar: RIGHT · VERTICAL · STICKY (fixed right column) ==== */
#controls        { position:fixed !important; top:0 !important; right:0; bottom:0; width:220px; }  /* fixed right column */
#controls        { flex-direction:column !important; align-items:stretch !important; overflow:auto; }  /* stack vertically, scroll if long */
#controls        { border-bottom:none; border-left:1px solid #d0dde8; }                           /* divider on the left */
#controls select { width:100%; }                                                                  /* dropdowns fill the column */
.container-fluid { margin-right:220px; }                                                          /* leave room for the filter column */"""

_FILTER_RIGHT_SCROLL = """\
/* ==== Filter bar: RIGHT · VERTICAL · SCROLL (right column, scrolls with the page) ==== */
#controls        { position:static !important; float:right; width:220px; }                        /* right column, NOT pinned */
#controls        { flex-direction:column !important; align-items:stretch !important; }             /* stack vertically */
#controls        { border-bottom:none; border-left:1px solid #d0dde8; }                           /* divider on the left */
#controls select { width:100%; }                                                                  /* dropdowns fill the column */
.container-fluid { margin-right:220px; }                                                          /* leave room for the filter column */"""

# Ordered mapping shown in the "Filter bar" dropdown (each position has sticky & scroll).
FILTER_LAYOUTS: dict[str, str] = {
    "Top bar · sticky": _FILTER_TOP_STICKY,
    "Top bar · scroll": _FILTER_TOP_SCROLL,
    "Left sidebar · sticky": _FILTER_LEFT_STICKY,
    "Left sidebar · scroll": _FILTER_LEFT_SCROLL,
    "Right sidebar · sticky": _FILTER_RIGHT_STICKY,
    "Right sidebar · scroll": _FILTER_RIGHT_SCROLL,
}

_FILTER_HINT = "— Filter bar layout… —"


class CustomCssDialog(QDialog):
    """Modal editor for the dashboard-level custom CSS string."""

    def __init__(self, parent, css: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Custom CSS")
        self.resize(560, 500)
        self.result_css: str | None = None
        self._build(css)

    def _build(self, css: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QFrame()
        hdr.setFixedHeight(40)
        hdr.setStyleSheet(f"background-color: {DHIS2_BLUE};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 14, 0)
        lbl = QLabel("🎨 Dashboard CSS")
        lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl.setStyleSheet("color: white; background: transparent;")
        hl.addWidget(lbl)
        root.addWidget(hdr)

        body = QWidget()
        body.setStyleSheet(f"background-color: {PANEL_BG};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(8)

        hint = QLabel("Applied to the whole page on Preview / Export / Deploy "
                      "(placed after the default styles, so it overrides them).")
        hint.setWordWrap(True)
        hint.setFont(QFont("Segoe UI", 9))
        hint.setStyleSheet("color:#5a7a9a; background:transparent;")
        bl.addWidget(hint)

        # Template picker row (REQ-DASH-CSS-06).
        pick_row = QHBoxLayout()
        pick_row.setSpacing(8)
        pick_lbl = QLabel("Template:")
        pick_lbl.setFont(QFont("Segoe UI", 9))
        pick_lbl.setStyleSheet("color:#3a5068; background:transparent;")
        pick_row.addWidget(pick_lbl)
        self._tmpl = QComboBox()
        self._tmpl.setStyleSheet(
            "QComboBox { border:1px solid #c0cdd8; border-radius:4px; padding:3px 8px;"
            "  background:white; color:#1e2d3d; }"
            "QComboBox QAbstractItemView { background:white; color:#1e2d3d;"
            "  selection-background-color:#1a6fa8; selection-color:white; }")
        self._rebuild_combo()
        self._tmpl.activated.connect(self._on_pick_template)
        pick_row.addWidget(self._tmpl, 1)
        bl.addLayout(pick_row)

        # Tools row: colour picker. (Card spacing lives in the Base template's editable
        # gutter line — no separate control needed.)
        tools_row = QHBoxLayout()
        tools_row.setSpacing(8)
        _btn_qss = (
            "QPushButton { background:white; border:1px solid #7a9ab0; border-radius:4px;"
            "  color:#2c4257; padding:3px 10px; }"
            "QPushButton:hover { background:#e0ecf4; }")

        color_btn = QPushButton("🎨 Insert colour…")
        color_btn.setStyleSheet(_btn_qss)
        color_btn.setToolTip("Pick a colour and insert its hex code at the cursor")
        color_btn.clicked.connect(self._on_pick_color)
        tools_row.addWidget(color_btn)
        tools_row.addStretch(1)
        bl.addLayout(tools_row)

        # Filter-bar layout row (REQ-DASH-CSS-13) — position/orientation/sticky presets.
        filt_row = QHBoxLayout()
        filt_row.setSpacing(8)
        filt_lbl = QLabel("Filter bar:")
        filt_lbl.setFont(QFont("Segoe UI", 9))
        filt_lbl.setStyleSheet("color:#3a5068; background:transparent;")
        filt_row.addWidget(filt_lbl)
        self._filt = QComboBox()
        self._filt.addItem(_FILTER_HINT)
        for name in FILTER_LAYOUTS:
            self._filt.addItem(name)
        self._filt.setStyleSheet(self._tmpl.styleSheet())
        self._filt.setToolTip("Insert filter-bar layout CSS (top/left/right, horizontal/vertical, sticky/scroll)")
        self._filt.activated.connect(self._on_pick_filter_layout)
        filt_row.addWidget(self._filt, 1)
        bl.addLayout(filt_row)

        self._edit = QPlainTextEdit(css)
        self._edit.setPlaceholderText(
            "Pick a template above to start, or type CSS directly.\n"
            "Example selectors: body, #controls, .card, .card-header, .chart-wrapper")
        self._edit.setFont(QFont("Consolas", 10))
        self._edit.setStyleSheet(
            "QPlainTextEdit { border:1px solid #c0cdd8; border-radius:4px;"
            "  background:white; color:#1e2d3d; padding:6px; }"
            "QPlainTextEdit:focus { border-color:#1a6fa8; }")
        bl.addWidget(self._edit, 1)
        root.addWidget(body, 1)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.button(QDialogButtonBox.StandardButton.Ok).setText("Apply")
        box.accepted.connect(self._on_ok)
        box.rejected.connect(self.reject)
        root.addWidget(style_dialog_buttons(box))
        # Opening → show which template the current CSS matches (REQ-DASH-CSS-11).
        self._select_template_for(css)
        self._edit.setFocus()

    # ── Template registry (built-in + user-saved) ───────────────────────────
    def _all_templates(self) -> dict[str, str]:
        """Built-in themes merged with the user's saved templates (REQ-DASH-CSS-10)."""
        from config.css_template_library import load_css_templates
        merged = dict(STYLE_TEMPLATES)
        merged.update(load_css_templates())
        return merged

    def _rebuild_combo(self, select: str | None = None) -> None:
        """Repopulate the dropdown: hint + built-ins + user templates."""
        self._tmpl.blockSignals(True)
        self._tmpl.clear()
        self._tmpl.addItem(_PICK_HINT)
        for name in self._all_templates():
            self._tmpl.addItem(name)
        if select:
            i = self._tmpl.findText(select)
            self._tmpl.setCurrentIndex(i if i >= 0 else 0)
        self._tmpl.blockSignals(False)

    def _match_template_name(self, css: str) -> str | None:
        """Name of the template whose CSS equals `css` (trimmed), else None."""
        target = (css or "").strip()
        if not target:
            return None
        for name, body in self._all_templates().items():
            if body.strip() == target:
                return name
        return None

    def _select_template_for(self, css: str) -> None:
        """Point the combo at the template matching `css`, or the hint if none."""
        name = self._match_template_name(css)
        i = self._tmpl.findText(name) if name else 0
        self._tmpl.blockSignals(True)
        self._tmpl.setCurrentIndex(i if i >= 0 else 0)
        self._tmpl.blockSignals(False)

    # ── Actions ──────────────────────────────────────────────────────────────
    def _on_pick_template(self, index: int) -> None:
        """Load a template into the editor (index 0 is the hint)."""
        if index > 0:
            self.apply_template(self._tmpl.itemText(index))
        # Keep the combo honest about what's actually in the editor.
        self._select_template_for(self._edit.toPlainText())

    def apply_template(self, name: str) -> bool:
        """Replace the editor content with template `name` (confirm if there's unsaved text).

        Returns True if the editor was replaced.
        """
        css = self._all_templates().get(name)
        if css is None:
            return False
        if self._edit.toPlainText().strip() and self._edit.toPlainText().strip() != css.strip():
            if QMessageBox.question(
                self, "Insert template",
                f"Replace the current CSS with the “{name}” template?",
            ) != QMessageBox.StandardButton.Yes:
                return False
        self._edit.setPlainText(css)
        self._select_template_for(css)
        return True

    def insert_at_cursor(self, text: str) -> None:
        """Insert `text` at the editor's cursor (or replace the selection)."""
        cur = self._edit.textCursor()
        cur.insertText(text)
        self._edit.setTextCursor(cur)
        self._edit.setFocus()

    def _on_pick_color(self) -> None:
        """Open a colour picker and insert the chosen hex at the cursor (REQ-DASH-CSS-07)."""
        col = QColorDialog.getColor(QColor("#1a6fa8"), self, "Pick a colour")
        if col.isValid():
            self.insert_at_cursor(col.name())    # "#rrggbb"

    def _append_block(self, snippet: str) -> None:
        """Append a CSS block at the END of the editor, keeping the cursor there."""
        existing = self._edit.toPlainText().rstrip()
        combined = (existing + "\n\n" + snippet + "\n") if existing else (snippet + "\n")
        self._edit.setPlainText(combined)
        cur = self._edit.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        self._edit.setTextCursor(cur)
        self._select_template_for(self._edit.toPlainText())

    def _on_pick_filter_layout(self, index: int) -> None:
        """Append the chosen filter-bar layout CSS (index 0 is the hint — no-op)."""
        if index <= 0:
            return
        name = self._filt.itemText(index)
        snippet = FILTER_LAYOUTS.get(name)
        if snippet:
            self._append_block(snippet)
        self._filt.setCurrentIndex(0)   # reset so the same layout can be re-picked

    def _maybe_offer_save_template(self, css: str) -> None:
        """If the user edited a template into something new, offer to save it as a new
        template under a name they choose (REQ-DASH-CSS-10)."""
        if not css or self._match_template_name(css):
            return                                   # empty, or already a known template
        base = self._tmpl.currentText()
        if base == _PICK_HINT:
            return                                   # typed from scratch — don't nag
        name, ok = QInputDialog.getText(
            self, "Save as new template",
            f"You edited the “{base}” template.\nName it to save as a new template (leave blank to skip):",
            text=f"{base} (custom)")
        if ok and name.strip():
            from config.css_template_library import save_css_template
            save_css_template(name.strip(), css)
            self._rebuild_combo(select=name.strip())

    def _on_ok(self) -> None:
        css = self._edit.toPlainText().strip()
        self._maybe_offer_save_template(css)
        self.result_css = css
        self.accept()

    @classmethod
    def prompt(cls, parent, css: str = "") -> str | None:
        """Show modally. Returns the edited CSS (may be '') or None if cancelled."""
        dlg = cls(parent, css)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.result_css
        return None
