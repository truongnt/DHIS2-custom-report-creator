"""
test_bar_real.py — Real-data test for bar chart dimension + stack mode.

Tests _real_js_dim with actual DHIS2 event analytics data loaded from a
JSON fixture file (fetched via fetch_test_fixture.py).

Usage:
  # Step 1: fetch fixture
  python fetch_test_fixture.py --url https://hmis.gov.la/hmis --user U --password P
         --program pUID --stage sUID --de deUID --out C:/Temp/test_fixture_bar_dim.json

  # Step 2: run real-data checklist
  python test_bar_real.py --fixture C:/Temp/test_fixture_bar_dim.json
         --program pUID --stage sUID --de deUID [--options A,B,C]

  Without --fixture, uses built-in synthetic fixture for smoke testing.
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from charts.plugins.bar import BarPlugin
from test_checklist_base import ChecklistRunner

# ── Synthetic fixture for smoke testing without real DHIS2 ────────────────────
# Mimics the DHIS2 event analytics response structure.
# Header name uses "stageUID.deUID" format (the bug that was fixed).

_SYNTHETIC_STAGE = "stageAAA"
_SYNTHETIC_DE    = "deResultBBB"
_DIM_HEADER      = f"{_SYNTHETIC_STAGE}.{_SYNTHETIC_DE}"

SYNTHETIC_FIXTURE = {
    "headers": [
        {"name": "pe",          "column": "Period",       "type": "TEXT"},
        {"name": "ou",          "column": "Org unit",     "type": "TEXT"},
        {"name": _DIM_HEADER,   "column": "Test result",  "type": "TEXT"},
        {"name": "value",       "column": "Value",        "type": "NUMBER"},
    ],
    "metaData": {
        "items": {
            "POS": {"name": "Positive"},
            "NEG": {"name": "Negative"},
            "IND": {"name": "Indeterminate"},
        }
    },
    "rows": [
        # pe,        ou,    dim,   value
        ["202401", "ouABC", "POS", "45"],
        ["202401", "ouABC", "NEG", "120"],
        ["202401", "ouABC", "IND", "8"],
        ["202402", "ouABC", "POS", "52"],
        ["202402", "ouABC", "NEG", "135"],
        ["202402", "ouABC", "IND", "6"],
        ["202403", "ouABC", "POS", "38"],
        ["202403", "ouABC", "NEG", "98"],
        ["202403", "ouABC", "IND", "11"],
        ["202404", "ouABC", "POS", "67"],
        ["202404", "ouABC", "NEG", "148"],
        ["202404", "ouABC", "IND", "5"],
        ["202405", "ouABC", "POS", "71"],
        ["202405", "ouABC", "NEG", "160"],
        ["202405", "ouABC", "IND", "9"],
        ["202406", "ouABC", "POS", "59"],
        ["202406", "ouABC", "NEG", "142"],
        ["202406", "ouABC", "IND", "7"],
    ]
}


def build_checks(prog_uid, stage_uid, de_uid, options, fixture_key):
    """Build BEFORE/AFTER pairs for real-data dim+stack tests."""
    dim = {
        "uid":      de_uid,
        "type":     "tracker_option",
        "prog_uid": prog_uid,
        "stage_uid":stage_uid,
        "options":  options,
    }

    def cfg(po):
        return {
            "metrics": [{"uid": de_uid, "type": "tracker_numeric",
                         "name": "Events", "agg": "COUNT",
                         "prog_uid": prog_uid, "stage_uid": stage_uid}],
            "dimensions": {"dimension": dim},
            "plugin_options": po,
        }

    return [
        ("real_smoke", "Real data renders at all",
         cfg({"show_legend": True}),
         cfg({"show_legend": True, "color_scheme": "DHIS2"}),
         "BOTH: multi-colour stacked/grouped bars from real API data. No error message."),

        ("real_stack", "Stack mode — real data",
         cfg({"stack_mode": "None",  "show_legend": True}),
         cfg({"stack_mode": "Stack", "show_legend": True}),
         "LEFT: categories side-by-side per month. RIGHT: categories STACKED — one column per month."),

        ("real_expand", "Expand 100% — real data",
         cfg({"stack_mode": "None",   "show_legend": True}),
         cfg({"stack_mode": "Expand", "show_legend": True,
              "show_values": True, "y_format": "%"}),
         "RIGHT: every bar reaches 100%, % labels visible, categories proportionally stacked."),

        ("real_legend", "Legend visible — real data",
         cfg({"show_legend": False}),
         cfg({"show_legend": True}),
         "LEFT: NO legend. RIGHT: legend shows each category name with its colour."),

        ("real_values", "Data labels on stacked bars",
         cfg({"stack_mode": "Stack", "show_legend": True, "show_values": False}),
         cfg({"stack_mode": "Stack", "show_legend": True, "show_values": True,
              "only_total": True}),
         "LEFT: no labels. RIGHT: total value label on top of each stacked bar."),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture",  default=None,        help="Path to JSON fixture file")
    ap.add_argument("--program",  default="progAAA",   help="Program UID")
    ap.add_argument("--stage",    default=_SYNTHETIC_STAGE, help="Stage UID")
    ap.add_argument("--de",       default=_SYNTHETIC_DE,    help="Dimension DE UID")
    ap.add_argument("--options",  default="POS,NEG,IND",    help="Option codes (comma-separated)")
    ap.add_argument("--out",      default="C:/Temp",         help="Output directory")
    args = ap.parse_args()

    out = Path(args.out)

    # Load fixture
    if args.fixture and Path(args.fixture).exists():
        fixture_data = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        print(f"Loaded fixture: {args.fixture}  ({len(fixture_data.get('rows',[]))} rows)")
        stage_uid = args.stage
        de_uid    = args.de
    else:
        print("No fixture file — using synthetic fixture.")
        fixture_data = SYNTHETIC_FIXTURE
        stage_uid    = _SYNTHETIC_STAGE
        de_uid       = _SYNTHETIC_DE

    prog_uid = args.program

    # Build options list from fixture metaData or CLI arg
    meta_items = fixture_data.get("metaData", {}).get("items", {})
    option_codes = [c.strip() for c in args.options.split(",") if c.strip()]
    options = [
        {"code": c, "name": meta_items.get(c, {}).get("name", c)}
        for c in option_codes
    ]
    if not options:
        # Auto-detect from fixture rows
        dim_header = next(
            (h["name"] for h in fixture_data["headers"]
             if h["name"] not in ("pe", "ou", "value")), "")
        dim_idx = next(
            (i for i, h in enumerate(fixture_data["headers"]) if h["name"] == dim_header), -1)
        if dim_idx >= 0:
            codes = sorted(set(r[dim_idx] for r in fixture_data["rows"]))
            options = [{"code": c, "name": meta_items.get(c, {}).get("name", c)} for c in codes]
            print(f"Auto-detected {len(options)} option codes: {[o['code'] for o in options]}")

    # Fixture key for dhis2Get interception (use program UID fragment)
    fixture_key = f"aggregate/{prog_uid}"
    fixtures = {fixture_key: fixture_data}

    checks = build_checks(prog_uid, stage_uid, de_uid, options, fixture_key)

    runner = ChecklistRunner(
        plugin      = BarPlugin,
        checks      = checks,
        html_path   = out / "bar_real_checklist.html",
        mjs_path    = out / "screenshot_bar_real.mjs",
        full_png    = out / "bar_real_checklist_full.png",
        boxes_json  = out / "bar_real_checklist_boxes.json",
        crop_dir    = out / "bar_real_checks",
        chart_title = "Bar Chart — Real Data Dim+Stack Test",
        port        = 9231,
        fixtures    = fixtures,
    )
    runner.run()


if __name__ == "__main__":
    main()
