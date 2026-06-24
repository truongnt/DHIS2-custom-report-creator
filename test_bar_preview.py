"""
Comprehensive visual test for BarPlugin.
Generates a test HTML with all option combinations, screenshots each section
via Chrome CDP, crops into readable slices.

Run:  python test_bar_preview.py
"""
import subprocess, sys, os, time, re, json
from pathlib import Path

REPO       = Path(__file__).parent
CHARTJS    = Path("C:/Temp/chartjs/chart.umd.min.js")
DATALABELS = Path("C:/Temp/chartjs/chartjs-datalabels.min.js")
OUT_HTML   = Path("C:/Temp/bar_preview_test.html")
CDP_SCRIPT = Path("C:/Temp/screenshot_bar.mjs")
NODE       = Path(r"C:\Program Files\nodejs\node.exe")

sys.path.insert(0, str(REPO))
from charts.plugins.bar import BarPlugin

# ── Helper dimension config for dim/OU tests ──────────────────────────────────

DIM_OPT_CFG = {
    "uid": "dim001", "type": "tracker_option",
    "prog_uid": "prog001", "stage_uid": "stg001",
    "options": [
        {"code":"A","name":"Cat A"}, {"code":"B","name":"Cat B"},
        {"code":"C","name":"Cat C"}, {"code":"D","name":"Cat D"},
        {"code":"E","name":"Cat E"}, {"code":"F","name":"Cat F"},
    ],
}

# ── Test scenarios ────────────────────────────────────────────────────────────

GROUPS = [
    # ── Stack mode ────────────────────────────────────────────────────────────
    ("STACK MODE", [
        ("None — side by side", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "show_values":False,"show_legend":True},
            "metrics": [
                {"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"Deaths","agg":"SUM"},
            ],
        }, "Bars side-by-side, NOT stacked"),

        ("Stack — layers", {
            "plugin_options": {"stack_mode":"Stack","orientation":"Vertical",
                               "show_values":True,"only_total":True,"show_legend":True},
            "metrics": [
                {"uid":"de1","type":"aggregate","name":"Mild","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"Severe","agg":"SUM"},
            ],
        }, "Bars stacked, total label on top"),

        ("Expand — 100%", {
            "plugin_options": {"stack_mode":"Expand","orientation":"Vertical",
                               "show_values":True,"only_total":False,"show_legend":True,
                               "y_format":"%"},
            "metrics": [
                {"uid":"de1","type":"aggregate","name":"Mild","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"Severe","agg":"SUM"},
            ],
        }, "Bars reach 100%, labels show % values"),
    ]),

    # ── Orientation ───────────────────────────────────────────────────────────
    ("ORIENTATION", [
        ("Vertical (default)", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical","show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "X-axis = months (Jan…Dec), bars go UP"),

        ("Horizontal", {
            "plugin_options": {"stack_mode":"None","orientation":"Horizontal","show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Y-axis = months, bars go RIGHT"),

        ("Horizontal + Stacked", {
            "plugin_options": {"stack_mode":"Stack","orientation":"Horizontal",
                               "show_values":True,"only_total":True,"show_legend":True},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"Mild","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"Severe","agg":"SUM"},
            ],
        }, "Horizontal stacked bars"),
    ]),

    # ── Value labels ──────────────────────────────────────────────────────────
    ("VALUE LABELS", [
        ("No labels", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "show_values":False,"show_legend":True},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"B","agg":"SUM"},
            ],
        }, "No numbers on bars"),

        ("All labels (not stacked)", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "show_values":True,"show_legend":True},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"B","agg":"SUM"},
            ],
        }, "Number on every bar"),

        ("Only total (stacked)", {
            "plugin_options": {"stack_mode":"Stack","orientation":"Vertical",
                               "show_values":True,"only_total":True,"show_legend":True},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"B","agg":"SUM"},
            ],
        }, "Single total label on top of stack, NOT per-segment"),

        ("All labels (stacked, only_total=False)", {
            "plugin_options": {"stack_mode":"Stack","orientation":"Vertical",
                               "show_values":True,"only_total":False,"show_legend":True},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"B","agg":"SUM"},
            ],
        }, "Label on EACH segment of stack"),
    ]),

    # ── Y format ─────────────────────────────────────────────────────────────
    ("Y FORMAT (small data)", [
        ("Default (raw number)", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "show_values":True,"y_format":"Default"},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Numbers: 40, 55, 30 (raw, no suffix)"),

        ("% (percent) + Expand", {
            "plugin_options": {"stack_mode":"Expand","orientation":"Vertical",
                               "show_values":True,"y_format":"%"},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"B","agg":"SUM"},
            ],
        }, "Y-axis shows 0–100, labels show %"),
    ]),

    # ── Y format LARGE values (demo_y_scale=50 → data 1500-4500) ─────────────
    ("Y FORMAT (large data, scale ×50)", [
        ("1,234 (comma) large data", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "show_values":True,"y_format":"1,234","demo_y_scale":50},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Y-axis ticks like 1,500 / 2,750 — comma separator"),

        ("1.2K (K-suffix) large data", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "show_values":True,"y_format":"1.2K","demo_y_scale":50},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Y-axis ticks like 1.5K / 2.8K — K suffix"),
    ]),

    # ── Legend position ───────────────────────────────────────────────────────
    ("LEGEND POSITION", [
        ("Bottom (default)", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "show_legend":True,"legend_pos":"Bottom"},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"Series A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"Series B","agg":"SUM"},
            ],
        }, "Legend BELOW chart"),

        ("Top", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "show_legend":True,"legend_pos":"Top"},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"Series A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"Series B","agg":"SUM"},
            ],
        }, "Legend ABOVE chart"),

        ("Right", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "show_legend":True,"legend_pos":"Right"},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"Series A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"Series B","agg":"SUM"},
            ],
        }, "Legend on RIGHT side"),
    ]),

    # ── Bar width ─────────────────────────────────────────────────────────────
    ("BAR WIDTH", [
        ("Auto", {
            "plugin_options":{"stack_mode":"None","orientation":"Vertical","bar_width":"Auto"},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Default bar width"),

        ("Thin (12px)", {
            "plugin_options":{"stack_mode":"None","orientation":"Vertical","bar_width":"Thin"},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Noticeably thinner bars"),

        ("Normal (22px)", {
            "plugin_options":{"stack_mode":"None","orientation":"Vertical","bar_width":"Normal"},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Medium-width bars"),

        ("Wide (36px)", {
            "plugin_options":{"stack_mode":"None","orientation":"Vertical","bar_width":"Wide"},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Noticeably wider bars"),
    ]),

    # ── X label rotation ─────────────────────────────────────────────────────
    ("X LABEL ROTATION", [
        ("0° (horizontal labels)", {
            "plugin_options":{"stack_mode":"None","orientation":"Vertical","x_rotation":"0"},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "X labels flat (horizontal)"),

        ("45° (diagonal)", {
            "plugin_options":{"stack_mode":"None","orientation":"Vertical","x_rotation":"45"},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "X labels diagonal"),

        ("90° (vertical)", {
            "plugin_options":{"stack_mode":"None","orientation":"Vertical","x_rotation":"90"},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "X labels vertical"),
    ]),

    # ── Axis titles ──────────────────────────────────────────────────────────
    ("AXIS TITLES", [
        ("X + Y title (vertical)", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "x_title":"Month","y_title":"Case count","show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Label 'Month' below X-axis; 'Case count' on left Y-axis"),

        ("X + Y title (horizontal)", {
            "plugin_options": {"stack_mode":"None","orientation":"Horizontal",
                               "x_title":"Month","y_title":"Case count","show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "In horizontal: 'Month' on Y-axis (categories), 'Case count' on X-axis (values)"),
    ]),

    # ── X interval (tick density) ─────────────────────────────────────────────
    ("X INTERVAL", [
        ("Auto (default — some labels skipped)", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical","x_interval":"Auto"},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Some month labels may be skipped to avoid overlap"),

        ("All — force show every label", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical","x_interval":"All"},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "ALL 12 month labels visible, even if they overlap"),
    ]),

    # ── Dimension + stack (categories stacked, not metrics) ───────────────────
    ("DIMENSION + STACK", [
        ("Dim + Stack (all 6 categories stacked per month)", {
            "plugin_options": {"stack_mode":"Stack","orientation":"Vertical",
                               "show_values":False,"show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
            "dimensions": {"dimension": DIM_OPT_CFG},
        }, "Each bar = sum of Cat A–F stacked; 6 colour layers per month"),

        ("Dim + Stack + only_total labels", {
            "plugin_options": {"stack_mode":"Stack","orientation":"Vertical",
                               "show_values":True,"only_total":True,"show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
            "dimensions": {"dimension": DIM_OPT_CFG},
        }, "Total label on top of each 6-layer stack"),

        ("Dim + Stack + per-segment labels", {
            "plugin_options": {"stack_mode":"Stack","orientation":"Vertical",
                               "show_values":True,"only_total":False,"show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
            "dimensions": {"dimension": DIM_OPT_CFG},
        }, "Label on EACH category segment"),

        ("Dim + Expand 100% (categories)", {
            "plugin_options": {"stack_mode":"Expand","orientation":"Vertical",
                               "show_values":True,"only_total":False,"y_format":"%",
                               "show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
            "dimensions": {"dimension": DIM_OPT_CFG},
        }, "Y-axis 0–100%, 6 category layers fill each bar to 100%"),

        ("Dim + Horizontal + Stack", {
            "plugin_options": {"stack_mode":"Stack","orientation":"Horizontal",
                               "show_values":True,"only_total":True,"show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
            "dimensions": {"dimension": DIM_OPT_CFG},
        }, "Horizontal bars, 6 categories stacked, total label at end"),
    ]),

    # ── Log scale ─────────────────────────────────────────────────────────────
    ("LOG SCALE", [
        ("Log scale OFF (linear)", {
            "plugin_options":{"stack_mode":"None","orientation":"Vertical",
                              "log_scale":False,"show_values":True,"demo_y_scale":50},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Y-axis linear: evenly spaced ticks"),

        ("Log scale ON (logarithmic)", {
            "plugin_options":{"stack_mode":"None","orientation":"Vertical",
                              "log_scale":True,"show_values":True,"demo_y_scale":50},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Y-axis logarithmic: ticks 100, 1000, 10000 (non-linear spacing)"),
    ]),

    # ── Org Unit X Axis ───────────────────────────────────────────────────────
    ("ORG UNIT X AXIS", [
        ("OU — Vertical bars per district", {
            "plugin_options": {"x_axis":"Org Unit","orientation":"Vertical",
                               "show_values":True,"show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "X-axis = District A..F, bars go UP per district"),

        ("OU — Horizontal bars per district", {
            "plugin_options": {"x_axis":"Org Unit","orientation":"Horizontal",
                               "show_values":True,"show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Y-axis = District A..F, bars go RIGHT"),

        ("OU — series_limit 3 (shows top 3 districts)", {
            "plugin_options": {"x_axis":"Org Unit","orientation":"Vertical",
                               "show_values":True,"show_legend":True,"series_limit":"3"},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
        }, "Only 3 districts shown (sorted by value): District C, District A, District E"),
    ]),

    # ── Series limit (dim mode — 6 categories, limit to fewer) ───────────────
    ("SERIES LIMIT (dimension mode)", [
        ("All series — 6 categories", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "series_limit":"All","show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
            "dimensions": {"dimension": DIM_OPT_CFG},
        }, "6 coloured series: Cat A, B, C, D, E, F all visible"),

        ("Limit 3 — top 3 by value", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "series_limit":"3","show_legend":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
            "dimensions": {"dimension": DIM_OPT_CFG},
        }, "Only 3 series shown; Cat D/E/F disappeared"),

        ("Limit 3 + Stack", {
            "plugin_options": {"stack_mode":"Stack","orientation":"Vertical",
                               "series_limit":"3","show_legend":True,
                               "show_values":True,"only_total":True},
            "metrics":[{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}],
            "dimensions": {"dimension": DIM_OPT_CFG},
        }, "Stacked, only top-3 categories, total label on top"),
    ]),

    # ── Color schemes ─────────────────────────────────────────────────────────
    ("COLOR SCHEME", [
        ("Default palette", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "color_scheme":"Default","show_legend":True},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"B","agg":"SUM"},
            ],
        }, "Red + Blue bars (Default palette)"),

        ("DHIS2 palette", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "color_scheme":"DHIS2","show_legend":True},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"B","agg":"SUM"},
            ],
        }, "Dark-blue + Teal bars (DHIS2 palette)"),

        ("Warm palette", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "color_scheme":"Warm","show_legend":True},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"B","agg":"SUM"},
            ],
        }, "Dark-red + Red-orange bars"),

        ("Cool palette", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "color_scheme":"Cool","show_legend":True},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"B","agg":"SUM"},
            ],
        }, "Blue + Teal bars"),

        ("Earth palette", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "color_scheme":"Earth","show_legend":True},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"B","agg":"SUM"},
            ],
        }, "Dark-brown + Burnt-orange bars"),

        ("Pastel palette", {
            "plugin_options": {"stack_mode":"None","orientation":"Vertical",
                               "color_scheme":"Pastel","show_legend":True},
            "metrics":[
                {"uid":"de1","type":"aggregate","name":"A","agg":"SUM"},
                {"uid":"de2","type":"aggregate","name":"B","agg":"SUM"},
            ],
        }, "Light pink + Light blue bars (soft pastel tones)"),
    ]),
]

# ── Flatten into indexed cards ─────────────────────────────────────────────────

def all_cards():
    cards = []
    for group_label, items in GROUPS:
        cards.append(("GROUP_HEADER", group_label, None, None))
        for title, cfg, expect in items:
            cards.append(("CHART", title, cfg, expect))
    return cards


def build_html():
    chartjs_src    = CHARTJS.read_text(encoding="utf-8")
    datalabels_src = DATALABELS.read_text(encoding="utf-8")

    cards      = all_cards()
    html_divs  = []
    js_blocks  = []
    init_lines = []
    chart_idx  = 0

    for kind, title, cfg, _ in cards:
        if kind == "GROUP_HEADER":
            html_divs.append(f"""
  <div style="background:#2c3e50;color:#fff;padding:8px 16px;
              margin:24px 0 8px;font-weight:bold;font-size:13px;
              letter-spacing:.05em;border-radius:4px;">{title}</div>""")
            continue

        n      = chart_idx
        config = {"title": title, **cfg}
        js     = BarPlugin.build_js(n=n, config=config)
        js_blocks.append(js)
        init_lines.append(f"initChart{n}('USER_ORGUNIT','LAST_12_MONTHS');")

        html_divs.append(f"""
  <div style="background:#fff;border-radius:6px;
              box-shadow:0 1px 6px rgba(0,0,0,.12);
              padding:12px 16px;margin-bottom:12px;">
    <div style="font-size:11px;color:#888;margin-bottom:4px;">{title}</div>
    <div id="demoBanner{n}" style="display:none;background:#fffbe6;border:1px solid #ffe58f;
          border-radius:3px;padding:2px 8px;font-size:10px;color:#7c5800;margin-bottom:4px;">
      ⚠ Sample data</div>
    <div id="loading{n}" style="text-align:center;color:#ccc;padding:30px;">Loading…</div>
    <div id="error{n}"   style="display:none;color:red;font-size:11px;"></div>
    <canvas id="chart{n}" style="display:none;height:280px;"></canvas>
  </div>""")
        chart_idx += 1

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Bar Chart Options Test</title>
  <style>
    body{{font-family:Arial,sans-serif;background:#f0f2f5;
         max-width:960px;margin:0 auto;padding:20px;}}
    h2{{color:#333;margin-bottom:4px;}}
  </style>
</head>
<body>
  <h2>Bar Chart — Options Visual Test</h2>
  {''.join(html_divs)}

  <script>{chartjs_src}</script>
  <script>{datalabels_src}</script>
  <script>
    Chart.register(ChartDataLabels);
    Chart.defaults.animation = false;
    Chart.defaults.animations = false;
    Chart.defaults.transitions = {{}};
    const PREVIEW = true;
    function formatPeriodLabel(pe){{
      const mm=pe.match(/^(\\d{{4}})(\\d{{2}})$/);
      if(mm){{const M=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
              return M[parseInt(mm[2],10)-1]+' '+mm[1];}}
      const qm=pe.match(/^(\\d{{4}})Q(\\d)$/);
      if(qm) return 'Q'+qm[2]+' '+qm[1];
      return pe;
    }}
    function resolveRelativePeriod(pe){{return pe;}}
    async function dhis2Get(){{throw new Error('PREVIEW mode');}}
    {''.join(js_blocks)}
  </script>
  <script>
    {'  '.join(init_lines)}
  </script>
</body>
</html>"""


# ── CDP screenshot via Node ────────────────────────────────────────────────────

def main():
    print("Building test HTML…")
    html = build_html()
    OUT_HTML.write_text(html, encoding="utf-8")
    n_charts = sum(1 for k, *_ in all_cards() if k == "CHART")
    print(f"  {len(html):,} bytes, {n_charts} charts")

    # Syntax check
    import re as _re
    scripts = _re.findall(r'<script>(.*?)</script>', html, _re.DOTALL)
    custom  = "\n".join(scripts[2:])
    tmp_js  = Path("C:/Temp/test_chart_js.js")
    tmp_js.write_text(custom, encoding="utf-8")
    r = subprocess.run([r"node", "--check", str(tmp_js)], capture_output=True, text=True)
    if r.returncode != 0:
        print("JS SYNTAX ERROR:", r.stderr[:600])
        sys.exit(1)
    print("  JS syntax OK")

    # Take full-page screenshot via CDP
    print(f"\nTaking full-page screenshot ({n_charts} charts) via CDP…")
    full_png = Path("C:/Temp/bar_preview_chrome.png")
    r2 = subprocess.run([str(NODE), str(CDP_SCRIPT)], timeout=60, capture_output=True, text=True)
    print(r2.stdout.strip())
    if r2.returncode != 0:
        print("CDP error:", r2.stderr[:400])
        return []
    if not full_png.exists() or full_png.stat().st_size < 50_000:
        print("  ERROR: screenshot too small or missing")
        return []
    print(f"  Full page: {full_png.stat().st_size:,} bytes")

    # Crop into sections using PIL
    from PIL import Image
    img = Image.open(full_png)
    W, H = img.size
    print(f"  Image size: {W}×{H}px")

    # 5 equal slices for more charts
    n_slices = 5
    results  = []
    slice_h  = H // n_slices
    for i in range(n_slices):
        y0   = i * slice_h
        y1   = min((i + 1) * slice_h + 80, H)
        crop = img.crop((0, y0, W, y1))
        out  = Path(f"C:/Temp/bar_test_section{i+1}.png")
        crop.save(out)
        results.append((f"section{i+1}", out))
        print(f"  section{i+1}: y={y0}–{y1}  ({out.stat().st_size:,} bytes)")

    return results


if __name__ == "__main__":
    results = main()
    print("\nDone. Screenshots:")
    for name, path in results:
        print(f"  {path}")
