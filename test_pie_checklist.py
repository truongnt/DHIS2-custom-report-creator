"""
test_pie_checklist.py — option-by-option visual verification for PieCatPlugin.

Run:  python test_pie_checklist.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).parent
sys.path.insert(0, str(REPO))

from charts.plugins.pie_cat import PieCatPlugin
from test_checklist_base import ChecklistRunner

DIM = {
    "uid":"dim1","type":"tracker_option","prog_uid":"p1","stage_uid":"s1",
    "options":[
        {"code":"A","name":"Alpha"},{"code":"B","name":"Beta"},
        {"code":"C","name":"Gamma"},{"code":"D","name":"Delta"},{"code":"E","name":"Epsilon"},
    ]
}


def cfg(po=None):
    return {
        "metrics": [],
        "dimensions": {"dimension": DIM},
        "plugin_options": po or {},
    }


CHECKS = [
    # ── smoke test ────────────────────────────────────────────────────────────
    ("default", "Baseline smoke test",
     cfg({}),
     cfg({"show_legend":"Bottom"}),
     "Both charts: 5-slice pie, legend at bottom. Should look identical."),

    # ── color_scheme ──────────────────────────────────────────────────────────
    ("color_scheme", "DHIS2 vs Default",
     cfg({"color_scheme":"Default","show_legend":"Bottom"}),
     cfg({"color_scheme":"DHIS2","show_legend":"Bottom"}),
     "LEFT: red/blue/orange slices. RIGHT: DHIS2 blue/teal/red slices."),

    ("color_scheme", "Warm vs Default",
     cfg({"color_scheme":"Default","show_legend":"Bottom"}),
     cfg({"color_scheme":"Warm","show_legend":"Bottom"}),
     "LEFT: mixed colors. RIGHT: all warm reds/oranges."),

    ("color_scheme", "Pastel vs Default",
     cfg({"color_scheme":"Default","show_legend":"Bottom"}),
     cfg({"color_scheme":"Pastel","show_legend":"Bottom"}),
     "LEFT: vivid colors. RIGHT: soft pastel colors."),

    # ── chart_type ────────────────────────────────────────────────────────────
    ("chart_type", "Donut vs Pie",
     cfg({"chart_type":"Pie"}),
     cfg({"chart_type":"Donut"}),
     "LEFT: solid filled pie. RIGHT: ring/donut shape (center hole)."),

    # ── show_legend ───────────────────────────────────────────────────────────
    ("show_legend", "Off vs Bottom",
     cfg({"show_legend":"Bottom"}),
     cfg({"show_legend":"Off"}),
     "LEFT: Alpha/Beta/Gamma… legend visible below. RIGHT: NO legend."),

    ("show_legend", "Top vs Bottom",
     cfg({"show_legend":"Bottom"}),
     cfg({"show_legend":"Top"}),
     "LEFT: legend BELOW pie. RIGHT: legend ABOVE pie."),

    ("show_legend", "Right vs Bottom",
     cfg({"show_legend":"Bottom"}),
     cfg({"show_legend":"Right"}),
     "LEFT: legend below. RIGHT: legend on RIGHT SIDE."),

    # ── show_values ───────────────────────────────────────────────────────────
    ("show_values", "Percent vs Off",
     cfg({"show_values":"Off"}),
     cfg({"show_values":"Percent"}),
     "LEFT: no labels on slices. RIGHT: percentage label (e.g. 28.0%) on each slice."),

    ("show_values", "Value vs Off",
     cfg({"show_values":"Off"}),
     cfg({"show_values":"Value"}),
     "LEFT: no labels. RIGHT: raw numeric value label on each slice."),
]


if __name__ == "__main__":
    runner = ChecklistRunner(
        plugin      = PieCatPlugin,
        checks      = CHECKS,
        html_path   = Path("C:/Temp/pie_checklist.html"),
        mjs_path    = Path("C:/Temp/screenshot_pie.mjs"),
        full_png    = Path("C:/Temp/pie_checklist_full.png"),
        boxes_json  = Path("C:/Temp/pie_checklist_boxes.json"),
        crop_dir    = Path("C:/Temp/pie_checks"),
        chart_title = "Pie Cat — Option Checklist",
        port        = 9227,
    )
    runner.run()
