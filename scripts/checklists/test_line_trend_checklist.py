"""
test_line_trend_checklist.py — option-by-option visual verification for LineTrendPlugin.

Run:  python test_line_trend_checklist.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from charts.plugins.line_trend import LineTrendPlugin
from test_checklist_base import ChecklistRunner

M1 = [{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}]


def cfg(po=None):
    return {"metrics": M1, "plugin_options": po or {}}


CHECKS = [
    # ── smoke test ────────────────────────────────────────────────────────────
    ("default", "Baseline smoke test",
     cfg({}),
     cfg({"show_legend":"Bottom"}),
     "Both charts: smooth line, Jan-Dec, legend at bottom. Should look identical."),

    # ── color_scheme ──────────────────────────────────────────────────────────
    ("color_scheme", "DHIS2 vs Default",
     cfg({"color_scheme":"Default"}),
     cfg({"color_scheme":"DHIS2"}),
     "LEFT: red line. RIGHT: dark-blue (#147cd7) line."),

    ("color_scheme", "Warm vs Default",
     cfg({"color_scheme":"Default"}),
     cfg({"color_scheme":"Warm"}),
     "LEFT: red line. RIGHT: dark-red (#c0392b) line."),

    ("color_scheme", "Cool vs Default",
     cfg({"color_scheme":"Default"}),
     cfg({"color_scheme":"Cool"}),
     "LEFT: red line. RIGHT: blue (#2980b9) line."),

    # ── line_tension ──────────────────────────────────────────────────────────
    ("line_tension", "Straight vs Smooth",
     cfg({"line_tension":"Smooth"}),
     cfg({"line_tension":"Straight"}),
     "LEFT: curved/smooth line between points. RIGHT: STRAIGHT line segments."),

    # ── fill_area ─────────────────────────────────────────────────────────────
    ("fill_area", "Fill vs None",
     cfg({"fill_area":"None"}),
     cfg({"fill_area":"Fill"}),
     "LEFT: just the line, no fill. RIGHT: area BELOW the line is filled/shaded."),

    # ── show_legend ───────────────────────────────────────────────────────────
    ("show_legend", "Off vs Bottom",
     cfg({"show_legend":"Bottom"}),
     cfg({"show_legend":"Off"}),
     "LEFT: 'Series A' legend visible below chart. RIGHT: NO legend shown."),

    ("show_legend", "Top vs Bottom",
     cfg({"show_legend":"Bottom"}),
     cfg({"show_legend":"Top"}),
     "LEFT: legend BELOW chart. RIGHT: legend ABOVE chart."),

    ("show_legend", "Right vs Bottom",
     cfg({"show_legend":"Bottom"}),
     cfg({"show_legend":"Right"}),
     "LEFT: legend below. RIGHT: legend on the RIGHT SIDE."),

    # ── show_values ───────────────────────────────────────────────────────────
    ("show_values", "On vs Off",
     cfg({"show_values":"Off"}),
     cfg({"show_values":"On"}),
     "LEFT: no numbers on points. RIGHT: numeric value label near each data point."),

    # ── y_format ─────────────────────────────────────────────────────────────
    ("y_format", "1,234 comma (x10 data)",
     cfg({"demo_y_scale":10,"show_values":True,"y_format":"Default"}),
     cfg({"demo_y_scale":10,"show_values":True,"y_format":"1,234"}),
     "LEFT: labels like 950. RIGHT: labels like 950 (or 1,100 with comma separator)."),

    ("y_format", "1.2K suffix (x10 data)",
     cfg({"demo_y_scale":10,"show_values":True,"y_format":"Default"}),
     cfg({"demo_y_scale":10,"show_values":True,"y_format":"1.2K"}),
     "LEFT: labels like 1100. RIGHT: labels like 1.1K (K suffix)."),

    ("y_format", "% sign",
     cfg({"show_values":True,"y_format":"Default"}),
     cfg({"show_values":True,"y_format":"%"}),
     "LEFT: labels like 95. RIGHT: labels like 95% (percent sign appended)."),

    # ── x_rotation ────────────────────────────────────────────────────────────
    ("x_rotation", "45 degrees vs 0",
     cfg({"x_rotation":"0"}),
     cfg({"x_rotation":"45"}),
     "LEFT: X labels horizontal/flat. RIGHT: X labels at 45-degree diagonal."),

    ("x_rotation", "90 degrees vs 0",
     cfg({"x_rotation":"0"}),
     cfg({"x_rotation":"90"}),
     "LEFT: X labels flat. RIGHT: X labels fully vertical (90 degrees)."),

    # ── log_scale ─────────────────────────────────────────────────────────────
    ("log_scale", "On vs Off (x10 data)",
     cfg({"log_scale":"Off","demo_y_scale":10}),
     cfg({"log_scale":"On","demo_y_scale":10}),
     "LEFT: Y-axis evenly spaced. RIGHT: Y-axis logarithmic (uneven tick spacing)."),

    # ── axis titles ───────────────────────────────────────────────────────────
    ("x_title", "'Month' vs none",
     cfg({}),
     cfg({"x_title":"Month"}),
     "RIGHT: text 'Month' appears below the X-axis. LEFT: no such label."),

    ("y_title", "'Cases' vs none",
     cfg({}),
     cfg({"y_title":"Cases"}),
     "RIGHT: text 'Cases' appears rotated on the left Y-axis. LEFT: no such label."),
]


if __name__ == "__main__":
    runner = ChecklistRunner(
        plugin      = LineTrendPlugin,
        checks      = CHECKS,
        html_path   = Path("C:/Temp/line_trend_checklist.html"),
        mjs_path    = Path("C:/Temp/screenshot_line_trend.mjs"),
        full_png    = Path("C:/Temp/line_trend_checklist_full.png"),
        boxes_json  = Path("C:/Temp/line_trend_checklist_boxes.json"),
        crop_dir    = Path("C:/Temp/line_trend_checks"),
        chart_title = "Line Trend — Option Checklist",
        port        = 9225,
    )
    runner.run()
