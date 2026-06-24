"""
test_scorecard_checklist.py — option-by-option visual verification for ScorecardPlugin.

Run:  python test_scorecard_checklist.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).parent
sys.path.insert(0, str(REPO))

from charts.plugins.scorecard import ScorecardPlugin
from test_checklist_base import ChecklistRunner

M1 = [{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}]


def cfg(po=None):
    return {"metrics": M1, "title": "KPI Value", "plugin_options": po or {}}


CHECKS = [
    # ── smoke test ────────────────────────────────────────────────────────────
    ("default", "Baseline smoke test",
     cfg({}),
     cfg({"value_color":"Green","font_size":"Large","y_format":"Default"}),
     "Both: large green '1,234' centered with 'KPI Value' label below. Should look identical."),

    # ── y_format ─────────────────────────────────────────────────────────────
    ("y_format", "1,234 format",
     cfg({"y_format":"Default"}),
     cfg({"y_format":"1,234"}),
     "AFTER: sample value shows as '1,234' (comma separator)."),

    ("y_format", "1.2K format",
     cfg({"y_format":"Default"}),
     cfg({"y_format":"1.2K"}),
     "AFTER: sample value shows as '1.2K' (K suffix)."),

    ("y_format", "% format",
     cfg({"y_format":"Default"}),
     cfg({"y_format":"%"}),
     "AFTER: sample value shows as '57%' (percent sign)."),

    # ── value_color ───────────────────────────────────────────────────────────
    ("value_color", "Blue vs Green",
     cfg({"value_color":"Green"}),
     cfg({"value_color":"Blue"}),
     "LEFT: value in GREEN. RIGHT: value in BLUE (#3498db)."),

    ("value_color", "Red vs Green",
     cfg({"value_color":"Green"}),
     cfg({"value_color":"Red"}),
     "LEFT: value in green. RIGHT: value in RED (#e74c3c)."),

    ("value_color", "Orange vs Green",
     cfg({"value_color":"Green"}),
     cfg({"value_color":"Orange"}),
     "LEFT: value in green. RIGHT: value in ORANGE (#f39c12)."),

    # ── font_size ─────────────────────────────────────────────────────────────
    ("font_size", "Medium vs Large",
     cfg({"font_size":"Large"}),
     cfg({"font_size":"Medium"}),
     "LEFT: large bold number (52px). RIGHT: SMALLER number (38px)."),

    ("font_size", "Small vs Large",
     cfg({"font_size":"Large"}),
     cfg({"font_size":"Small"}),
     "LEFT: large bold number. RIGHT: SMALLEST number (28px), noticeably smaller."),
]


if __name__ == "__main__":
    runner = ChecklistRunner(
        plugin      = ScorecardPlugin,
        checks      = CHECKS,
        html_path   = Path("C:/Temp/scorecard_checklist.html"),
        mjs_path    = Path("C:/Temp/screenshot_scorecard.mjs"),
        full_png    = Path("C:/Temp/scorecard_checklist_full.png"),
        boxes_json  = Path("C:/Temp/scorecard_checklist_boxes.json"),
        crop_dir    = Path("C:/Temp/scorecard_checks"),
        chart_title = "Scorecard — Option Checklist",
        port        = 9228,
    )
    runner.run()
