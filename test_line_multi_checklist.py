"""
test_line_multi_checklist.py — option-by-option visual verification for LineMultiPlugin.

Run:  python test_line_multi_checklist.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).parent
sys.path.insert(0, str(REPO))

from charts.plugins.line_multi import LineMultiPlugin
from test_checklist_base import ChecklistRunner

M2 = [
    {"uid":"de1","type":"aggregate","name":"Series A","agg":"SUM"},
    {"uid":"de2","type":"aggregate","name":"Series B","agg":"SUM"},
]


def cfg(po=None):
    return {"metrics": M2, "plugin_options": po or {}}


CHECKS = [
    # ── smoke test ────────────────────────────────────────────────────────────
    ("default", "Baseline smoke test",
     cfg({}),
     cfg({"show_legend":"Bottom"}),
     "Both charts: 2 smooth lines, legend at bottom. Should look nearly identical."),

    # ── color_scheme ──────────────────────────────────────────────────────────
    ("color_scheme", "DHIS2 vs Default",
     cfg({"color_scheme":"Default","show_legend":"Bottom"}),
     cfg({"color_scheme":"DHIS2","show_legend":"Bottom"}),
     "LEFT: red+blue lines. RIGHT: dark-blue+teal lines."),

    ("color_scheme", "Warm vs Default",
     cfg({"color_scheme":"Default","show_legend":"Bottom"}),
     cfg({"color_scheme":"Warm","show_legend":"Bottom"}),
     "LEFT: red+blue. RIGHT: dark-red+orange (warm tones)."),

    ("color_scheme", "Cool vs Default",
     cfg({"color_scheme":"Default","show_legend":"Bottom"}),
     cfg({"color_scheme":"Cool","show_legend":"Bottom"}),
     "LEFT: red+blue. RIGHT: blue+cyan (both cool tones)."),

    # ── line_tension ──────────────────────────────────────────────────────────
    ("line_tension", "Straight vs Smooth",
     cfg({"line_tension":"Smooth"}),
     cfg({"line_tension":"Straight"}),
     "LEFT: curved lines between points. RIGHT: STRAIGHT line segments."),

    # ── fill_area ─────────────────────────────────────────────────────────────
    ("fill_area", "Fill vs None",
     cfg({"fill_area":"None"}),
     cfg({"fill_area":"Fill"}),
     "LEFT: lines only, transparent. RIGHT: filled/shaded area under each line."),

    # ── show_legend ───────────────────────────────────────────────────────────
    ("show_legend", "Off vs Bottom",
     cfg({"show_legend":"Bottom"}),
     cfg({"show_legend":"Off"}),
     "LEFT: Series A / Series B legend visible. RIGHT: NO legend shown."),

    ("show_legend", "Top vs Bottom",
     cfg({"show_legend":"Bottom"}),
     cfg({"show_legend":"Top"}),
     "LEFT: legend BELOW chart. RIGHT: legend ABOVE chart."),

    ("show_legend", "Right vs Bottom",
     cfg({"show_legend":"Bottom"}),
     cfg({"show_legend":"Right"}),
     "LEFT: legend below. RIGHT: legend on RIGHT SIDE (vertical)."),

    # ── show_values ───────────────────────────────────────────────────────────
    ("show_values", "On vs Off",
     cfg({"show_values":"Off"}),
     cfg({"show_values":"On"}),
     "LEFT: no number labels. RIGHT: value label near each data point."),

    # ── y_format ─────────────────────────────────────────────────────────────
    ("y_format", "1,234 comma (x10 data)",
     cfg({"demo_y_scale":10,"show_values":True,"y_format":"Default"}),
     cfg({"demo_y_scale":10,"show_values":True,"y_format":"1,234"}),
     "RIGHT: value labels show comma-separated numbers (e.g. 1,100)."),

    ("y_format", "1.2K suffix (x10 data)",
     cfg({"demo_y_scale":10,"show_values":True,"y_format":"Default"}),
     cfg({"demo_y_scale":10,"show_values":True,"y_format":"1.2K"}),
     "RIGHT: value labels show K suffix (e.g. 1.1K)."),

    ("y_format", "% sign",
     cfg({"show_values":True,"y_format":"Default"}),
     cfg({"show_values":True,"y_format":"%"}),
     "RIGHT: value labels have % appended (e.g. 95%)."),

    # ── x_rotation ────────────────────────────────────────────────────────────
    ("x_rotation", "45 degrees vs 0",
     cfg({"x_rotation":"0"}),
     cfg({"x_rotation":"45"}),
     "LEFT: X labels horizontal. RIGHT: X labels at 45-degree diagonal."),

    ("x_rotation", "90 degrees vs 0",
     cfg({"x_rotation":"0"}),
     cfg({"x_rotation":"90"}),
     "LEFT: X labels flat. RIGHT: X labels fully vertical."),

    # ── log_scale ─────────────────────────────────────────────────────────────
    ("log_scale", "On vs Off (x10 data)",
     cfg({"log_scale":"Off","demo_y_scale":10}),
     cfg({"log_scale":"On","demo_y_scale":10}),
     "LEFT: Y-axis linear, evenly spaced. RIGHT: Y-axis logarithmic."),

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
        plugin      = LineMultiPlugin,
        checks      = CHECKS,
        html_path   = Path("C:/Temp/line_multi_checklist.html"),
        mjs_path    = Path("C:/Temp/screenshot_line_multi.mjs"),
        full_png    = Path("C:/Temp/line_multi_checklist_full.png"),
        boxes_json  = Path("C:/Temp/line_multi_checklist_boxes.json"),
        crop_dir    = Path("C:/Temp/line_multi_checks"),
        chart_title = "Line Multi — Option Checklist",
        port        = 9226,
    )
    runner.run()
