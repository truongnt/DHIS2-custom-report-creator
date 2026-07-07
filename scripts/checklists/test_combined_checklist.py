"""
test_combined_checklist.py — option-by-option visual verification for CombinedBarLinePlugin.

Run:  python test_combined_checklist.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from charts.plugins.combined_bar_line import CombinedBarLinePlugin
from test_checklist_base import ChecklistRunner

M2 = [
    {"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"},
    {"uid":"de2","type":"aggregate","name":"Rate","agg":"SUM"},
]


def cfg(po=None):
    return {"metrics": M2, "plugin_options": po or {}}


CHECKS = [
    # ── smoke test ────────────────────────────────────────────────────────────
    ("default", "Baseline smoke test",
     cfg({}),
     cfg({"show_legend":"Bottom"}),
     "Both: blue bars with red line overlay, legend at bottom. Should look identical."),

    # ── color_scheme ──────────────────────────────────────────────────────────
    ("color_scheme", "DHIS2 vs Default",
     cfg({"color_scheme":"Default","show_legend":"Bottom"}),
     cfg({"color_scheme":"DHIS2","show_legend":"Bottom"}),
     "LEFT: red line + blue bars. RIGHT: DHIS2 colors (dark-blue line + teal bars)."),

    ("color_scheme", "Warm vs Default",
     cfg({"color_scheme":"Default","show_legend":"Bottom"}),
     cfg({"color_scheme":"Warm","show_legend":"Bottom"}),
     "RIGHT: warm reds/oranges for both bar and line colors."),

    ("color_scheme", "Cool vs Default",
     cfg({"color_scheme":"Default","show_legend":"Bottom"}),
     cfg({"color_scheme":"Cool","show_legend":"Bottom"}),
     "RIGHT: cool blues/cyans for both bar and line colors."),

    # ── show_legend ───────────────────────────────────────────────────────────
    ("show_legend", "Off vs Bottom",
     cfg({"show_legend":"Bottom"}),
     cfg({"show_legend":"Off"}),
     "LEFT: Cases/Rate legend visible. RIGHT: NO legend shown."),

    ("show_legend", "Top vs Bottom",
     cfg({"show_legend":"Bottom"}),
     cfg({"show_legend":"Top"}),
     "LEFT: legend BELOW chart. RIGHT: legend ABOVE chart."),

    ("show_legend", "Right vs Bottom",
     cfg({"show_legend":"Bottom"}),
     cfg({"show_legend":"Right"}),
     "LEFT: legend below. RIGHT: legend on RIGHT SIDE."),

    # ── show_values ───────────────────────────────────────────────────────────
    ("show_values", "On vs Off",
     cfg({"show_values":"Off"}),
     cfg({"show_values":"On"}),
     "LEFT: no labels. RIGHT: numeric value label on each bar and line point."),

    # ── y_format ─────────────────────────────────────────────────────────────
    ("y_format", "1,234 comma (x10 data via y_format test)",
     cfg({"y_format":"Default","show_values":"On","demo_y_scale":10}),
     cfg({"y_format":"1,234","show_values":"On","demo_y_scale":10}),
     "RIGHT: Y-axis ticks and data labels use comma separator (e.g. 1,200)."),

    ("y_format", "1.2K suffix",
     cfg({"y_format":"Default","show_values":"On","demo_y_scale":10}),
     cfg({"y_format":"1.2K","show_values":"On","demo_y_scale":10}),
     "RIGHT: Y-axis ticks and data labels use K suffix (e.g. 1.2K)."),

    # ── x_rotation ────────────────────────────────────────────────────────────
    ("x_rotation", "45 degrees vs 0",
     cfg({"x_rotation":"0"}),
     cfg({"x_rotation":"45"}),
     "LEFT: X labels horizontal. RIGHT: X labels at 45-degree diagonal."),

    ("x_rotation", "90 degrees vs 0",
     cfg({"x_rotation":"0"}),
     cfg({"x_rotation":"90"}),
     "LEFT: X labels flat. RIGHT: X labels fully vertical."),

    # ── dual_y_axis ───────────────────────────────────────────────────────────
    ("dual_y_axis", "Yes vs No",
     cfg({"dual_y_axis":"No","show_legend":"Bottom"}),
     cfg({"dual_y_axis":"Yes","show_legend":"Bottom"}),
     "LEFT: single Y axis on left. RIGHT: TWO Y axes — left for bars, right for line."),

    # ── axis titles ───────────────────────────────────────────────────────────
    ("x_title", "'Month' vs none",
     cfg({}),
     cfg({"x_title":"Month"}),
     "RIGHT: text 'Month' appears below the X-axis."),

    ("y_title", "'Cases' vs none",
     cfg({}),
     cfg({"y_title":"Cases"}),
     "RIGHT: text 'Cases' appears rotated on the left Y-axis."),
]


if __name__ == "__main__":
    runner = ChecklistRunner(
        plugin      = CombinedBarLinePlugin,
        checks      = CHECKS,
        html_path   = Path("C:/Temp/combined_checklist.html"),
        mjs_path    = Path("C:/Temp/screenshot_combined.mjs"),
        full_png    = Path("C:/Temp/combined_checklist_full.png"),
        boxes_json  = Path("C:/Temp/combined_checklist_boxes.json"),
        crop_dir    = Path("C:/Temp/combined_checks"),
        chart_title = "Combined Bar+Line — Option Checklist",
        port        = 9229,
    )
    runner.run()
