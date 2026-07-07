"""
test_table_checklist.py — option-by-option visual verification for TablePlugin.

Run:  python test_table_checklist.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from charts.plugins.table_view import TablePlugin
from test_checklist_base import ChecklistRunner

M1 = [{"uid": "de1", "type": "aggregate", "name": "Cases", "agg": "SUM"}]


def cfg(po=None):
    return {"metrics": M1, "plugin_options": po or {}}


CHECKS = [
    # ── smoke test ────────────────────────────────────────────────────────────
    ("default", "Baseline smoke test",
     cfg({}),
     cfg({"theme": "Default", "stripe": "On", "border": "Light", "font_size": "Medium"}),
     "Both: 6-row aggregated table, dark header, striped rows, light border. Should look identical."),

    # ── mode ──────────────────────────────────────────────────────────────────
    ("mode", "Raw vs Aggregated",
     cfg({"mode": "Aggregated"}),
     cfg({"mode": "Raw"}),
     "LEFT: org-unit rows with period columns. RIGHT: flat rows with Facility/Period/Age/Sex/Cases columns."),

    # ── theme ─────────────────────────────────────────────────────────────────
    ("theme", "Blue vs Light",
     cfg({"theme": "Light"}),
     cfg({"theme": "Blue"}),
     "LEFT: light grey header with dark text. RIGHT: dark navy-blue header with white text."),

    ("theme", "Green vs Light",
     cfg({"theme": "Light"}),
     cfg({"theme": "Green"}),
     "LEFT: light grey header. RIGHT: green header with white text."),

    ("theme", "Default vs Light",
     cfg({"theme": "Light"}),
     cfg({"theme": "Default"}),
     "LEFT: light grey header with dark text. RIGHT: dark charcoal header with white text."),

    ("theme", "Dark vs Light",
     cfg({"theme": "Light"}),
     cfg({"theme": "Dark"}),
     "LEFT: light grey header. RIGHT: near-black header with off-white text."),

    # ── heatmap ───────────────────────────────────────────────────────────────
    ("heatmap", "On vs Off",
     cfg({"heatmap": "Off"}),
     cfg({"heatmap": "On"}),
     "LEFT: plain white cells. RIGHT: numeric cells shaded — higher values darker blue."),

    # ── stripe ────────────────────────────────────────────────────────────────
    ("stripe", "Off vs On",
     cfg({"stripe": "On"}),
     cfg({"stripe": "Off"}),
     "LEFT: alternating grey/white rows. RIGHT: all rows plain white (no zebra stripe)."),

    # ── border ────────────────────────────────────────────────────────────────
    ("border", "None vs Light",
     cfg({"border": "Light"}),
     cfg({"border": "None"}),
     "LEFT: thin grey cell borders visible. RIGHT: NO borders between cells."),

    ("border", "Dark vs Light",
     cfg({"border": "Light"}),
     cfg({"border": "Dark"}),
     "LEFT: thin 1px light grey borders. RIGHT: thicker 2px dark borders — noticeably bolder."),

    # ── font_size ─────────────────────────────────────────────────────────────
    ("font_size", "Small vs Medium",
     cfg({"font_size": "Medium"}),
     cfg({"font_size": "Small"}),
     "LEFT: medium text (13px). RIGHT: noticeably smaller text (11px)."),

    ("font_size", "Large vs Medium",
     cfg({"font_size": "Medium"}),
     cfg({"font_size": "Large"}),
     "LEFT: medium text (13px). RIGHT: noticeably larger text (15px)."),
]


if __name__ == "__main__":
    runner = ChecklistRunner(
        plugin      = TablePlugin,
        checks      = CHECKS,
        html_path   = Path("C:/Temp/table_checklist.html"),
        mjs_path    = Path("C:/Temp/screenshot_table.mjs"),
        full_png    = Path("C:/Temp/table_checklist_full.png"),
        boxes_json  = Path("C:/Temp/table_checklist_boxes.json"),
        crop_dir    = Path("C:/Temp/table_checks"),
        chart_title = "Data Table — Option Checklist",
        port        = 9230,
    )
    runner.run()
