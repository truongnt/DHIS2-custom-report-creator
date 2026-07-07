"""
test_bar_checklist.py — Option-by-option visual verification.

Each test = BEFORE (baseline) on LEFT vs AFTER (option changed) on RIGHT.
One screenshot per pair, analysed individually.

Run:  python test_bar_checklist.py
"""
import subprocess, sys, json, re
from pathlib import Path

REPO       = Path(__file__).parent.parent.parent
CHARTJS    = Path("C:/Temp/chartjs/chart.umd.min.js")
DATALABELS = Path("C:/Temp/chartjs/chartjs-datalabels.min.js")
OUT_HTML   = Path("C:/Temp/bar_checklist.html")
CDP_SCRIPT = Path("C:/Temp/screenshot_checklist.mjs")
FULL_PNG   = Path("C:/Temp/bar_checklist_full.png")
BOXES_JSON = Path("C:/Temp/bar_checklist_boxes.json")
CROP_DIR   = Path("C:/Temp/bar_checks")
NODE       = Path(r"C:\Program Files\nodejs\node.exe")

sys.path.insert(0, str(REPO))
from charts.plugins.bar import BarPlugin

# ── Shared config builders ─────────────────────────────────────────────────────

M2 = [  # 2 aggregate metrics
    {"uid":"de1","type":"aggregate","name":"Series A","agg":"SUM"},
    {"uid":"de2","type":"aggregate","name":"Series B","agg":"SUM"},
]
M1 = [{"uid":"de1","type":"aggregate","name":"Cases","agg":"SUM"}]

DIM = {
    "uid":"dim1","type":"tracker_option","prog_uid":"p1","stage_uid":"s1",
    "options":[
        {"code":"A","name":"Cat A"},{"code":"B","name":"Cat B"},
        {"code":"C","name":"Cat C"},{"code":"D","name":"Cat D"},
        {"code":"E","name":"Cat E"},{"code":"F","name":"Cat F"},
    ]
}


def cfg(metrics=None, po=None, dim=None):
    c = {"metrics": metrics or M1, "plugin_options": po or {}}
    if dim:
        c["dimensions"] = {"dimension": dim}
    return c


# ── Checklist ──────────────────────────────────────────────────────────────────
# Each entry: (group, option_name, base_config, test_config, expected_visual_diff)

CHECKS = [
    # ── stack_mode ────────────────────────────────────────────────────────────
    ("stack_mode", "Stack vs None",
     cfg(M2, {"stack_mode":"None","show_legend":True}),
     cfg(M2, {"stack_mode":"Stack","show_legend":True}),
     "LEFT: 2 bars side-by-side each month. RIGHT: 2 bars STACKED on top of each other."),

    ("stack_mode", "Expand 100% vs None",
     cfg(M2, {"stack_mode":"None","show_legend":True}),
     cfg(M2, {"stack_mode":"Expand","show_values":True,"y_format":"%","show_legend":True}),
     "LEFT: variable bar heights. RIGHT: every bar reaches 100%, labels show %."),

    # ── orientation ───────────────────────────────────────────────────────────
    ("orientation", "Horizontal vs Vertical",
     cfg(M2, {"orientation":"Vertical","show_legend":True}),
     cfg(M2, {"orientation":"Horizontal","show_legend":True}),
     "LEFT: bars go UP. RIGHT: bars go SIDEWAYS (horizontal)."),

    # ── show_values ───────────────────────────────────────────────────────────
    ("show_values", "Labels ON vs OFF",
     cfg(M2, {"show_values":False}),
     cfg(M2, {"show_values":True}),
     "LEFT: no numbers. RIGHT: numeric value label on every bar."),

    ("only_total", "only_total=True vs False (stacked)",
     cfg(M2, {"stack_mode":"Stack","show_values":True,"only_total":False,"show_legend":True}),
     cfg(M2, {"stack_mode":"Stack","show_values":True,"only_total":True,"show_legend":True}),
     "LEFT: label on EACH segment. RIGHT: ONE total label on top of full stack."),

    # ── axis titles ───────────────────────────────────────────────────────────
    ("x_title", "x_title 'Month' (vs none)",
     cfg(M1, {}),
     cfg(M1, {"x_title":"Month"}),
     "RIGHT: text 'Month' appears below the X-axis. LEFT: no such label."),

    ("y_title", "y_title 'Cases' (vs none)",
     cfg(M1, {}),
     cfg(M1, {"y_title":"Cases"}),
     "RIGHT: text 'Cases' appears rotated on the left Y-axis. LEFT: no such label."),

    # ── legend ────────────────────────────────────────────────────────────────
    ("show_legend", "Legend OFF vs ON",
     cfg(M2, {"show_legend":True}),
     cfg(M2, {"show_legend":False}),
     "LEFT: legend row visible below chart. RIGHT: NO legend at all."),

    ("legend_pos", "Legend Top vs Bottom",
     cfg(M2, {"show_legend":True,"legend_pos":"Bottom"}),
     cfg(M2, {"show_legend":True,"legend_pos":"Top"}),
     "LEFT: legend BELOW chart. RIGHT: legend ABOVE chart."),

    ("legend_pos", "Legend Right vs Bottom",
     cfg(M2, {"show_legend":True,"legend_pos":"Bottom"}),
     cfg(M2, {"show_legend":True,"legend_pos":"Right"}),
     "LEFT: legend below. RIGHT: legend on the RIGHT SIDE (vertical)."),

    # ── y_format ─────────────────────────────────────────────────────────────
    ("y_format", "1,234 comma separator (x50 data)",
     cfg(M1, {"show_values":True,"demo_y_scale":50,"y_format":"Default"}),
     cfg(M1, {"show_values":True,"demo_y_scale":50,"y_format":"1,234"}),
     "LEFT: labels like 2750. RIGHT: labels like 2,750 (with comma)."),

    ("y_format", "1.2K K-suffix (x50 data)",
     cfg(M1, {"show_values":True,"demo_y_scale":50,"y_format":"Default"}),
     cfg(M1, {"show_values":True,"demo_y_scale":50,"y_format":"1.2K"}),
     "LEFT: labels like 2750. RIGHT: labels like 2.8K (K suffix)."),

    ("y_format", "% percent (Expand mode)",
     cfg(M2, {"stack_mode":"Expand","show_values":True,"y_format":"Default"}),
     cfg(M2, {"stack_mode":"Expand","show_values":True,"y_format":"%"}),
     "LEFT: labels like 57.1. RIGHT: labels like 57.1% (with % sign)."),

    # ── bar_width ─────────────────────────────────────────────────────────────
    ("bar_width", "Thin (12px) vs Auto",
     cfg(M1, {"bar_width":"Auto"}),
     cfg(M1, {"bar_width":"Thin"}),
     "LEFT: default width. RIGHT: bars are noticeably THINNER."),

    ("bar_width", "Wide (36px) vs Auto",
     cfg(M1, {"bar_width":"Auto"}),
     cfg(M1, {"bar_width":"Wide"}),
     "LEFT: default width. RIGHT: bars are noticeably WIDER."),

    # ── x_rotation ────────────────────────────────────────────────────────────
    ("x_rotation", "45 degrees vs 0",
     cfg(M1, {"x_rotation":"0"}),
     cfg(M1, {"x_rotation":"45"}),
     "LEFT: X labels horizontal/flat. RIGHT: X labels at 45-degree diagonal."),

    ("x_rotation", "90 degrees vs 0",
     cfg(M1, {"x_rotation":"0"}),
     cfg(M1, {"x_rotation":"90"}),
     "LEFT: X labels flat. RIGHT: X labels fully vertical (90 degrees)."),

    # ── x_interval ────────────────────────────────────────────────────────────
    ("x_interval", "All labels vs Auto",
     cfg(M1, {"x_interval":"Auto"}),
     cfg(M1, {"x_interval":"All"}),
     "RIGHT: forced to show ALL tick labels (no auto-skip). For 12-month data both may look same."),

    # ── log_scale ─────────────────────────────────────────────────────────────
    ("log_scale", "Log scale ON vs OFF (x50 data)",
     cfg(M1, {"log_scale":False,"demo_y_scale":50}),
     cfg(M1, {"log_scale":True,"demo_y_scale":50}),
     "LEFT: Y-axis evenly spaced (linear). RIGHT: Y-axis logarithmic (uneven tick spacing)."),

    # ── color_scheme ──────────────────────────────────────────────────────────
    ("color_scheme", "DHIS2 vs Default",
     cfg(M2, {"color_scheme":"Default","show_legend":True}),
     cfg(M2, {"color_scheme":"DHIS2","show_legend":True}),
     "LEFT: red+blue. RIGHT: dark-blue+teal."),

    ("color_scheme", "Warm vs Default",
     cfg(M2, {"color_scheme":"Default","show_legend":True}),
     cfg(M2, {"color_scheme":"Warm","show_legend":True}),
     "LEFT: red+blue. RIGHT: dark-red+red-orange (both warm)."),

    ("color_scheme", "Cool vs Default",
     cfg(M2, {"color_scheme":"Default","show_legend":True}),
     cfg(M2, {"color_scheme":"Cool","show_legend":True}),
     "LEFT: red+blue. RIGHT: blue+cyan (both cool)."),

    ("color_scheme", "Pastel vs Default",
     cfg(M2, {"color_scheme":"Default","show_legend":True}),
     cfg(M2, {"color_scheme":"Pastel","show_legend":True}),
     "LEFT: red+blue. RIGHT: soft pink+light-blue (pastel)."),

    # ── x_axis = Org Unit ─────────────────────────────────────────────────────
    ("x_axis", "Org Unit vs Period",
     cfg(M1, {"x_axis":"Period","show_values":True}),
     cfg(M1, {"x_axis":"Org Unit","show_values":True}),
     "LEFT: 12 month bars. RIGHT: 6 district bars (District A to F)."),

    # ── dimension + stack ─────────────────────────────────────────────────────
    ("dim+stack", "Dim Stack vs Dim None",
     cfg(M1, {"stack_mode":"None","show_legend":True}, DIM),
     cfg(M1, {"stack_mode":"Stack","show_values":True,"only_total":True,"show_legend":True}, DIM),
     "LEFT: 6 category series side-by-side. RIGHT: 6 categories STACKED with total label."),

    ("dim+expand", "Dim Expand 100% vs None",
     cfg(M1, {"stack_mode":"None","show_legend":True}, DIM),
     cfg(M1, {"stack_mode":"Expand","show_values":True,"y_format":"%","show_legend":True}, DIM),
     "LEFT: side-by-side, variable heights. RIGHT: all bars reach 100%, categories stacked."),

    # ── series_limit ──────────────────────────────────────────────────────────
    ("series_limit", "Limit 3 vs All (dim mode)",
     cfg(M1, {"series_limit":"All","show_legend":True}, DIM),
     cfg(M1, {"series_limit":"3","show_legend":True}, DIM),
     "LEFT: 6 coloured series. RIGHT: only 3 series (Cat A, B, C — top by value)."),
]


# ── HTML builder ───────────────────────────────────────────────────────────────

def build_html(checks):
    chartjs_src    = CHARTJS.read_text(encoding="utf-8")
    datalabels_src = DATALABELS.read_text(encoding="utf-8")

    divs, js_blocks, inits = [], [], []

    for i, (group, name, base_cfg, test_cfg, expect) in enumerate(checks):
        n0 = i * 2       # baseline chart index
        n1 = i * 2 + 1   # test chart index

        js_blocks.append(BarPlugin.build_js(n=n0, config={**base_cfg}))
        js_blocks.append(BarPlugin.build_js(n=n1, config={**test_cfg}))
        inits += [
            f"initChart{n0}('USER_ORGUNIT','LAST_12_MONTHS');",
            f"initChart{n1}('USER_ORGUNIT','LAST_12_MONTHS');",
        ]

        def chart_cell(n, label, color, bg):
            return f"""
      <div style="flex:1;min-width:0;">
        <div style="font-size:10px;color:{color};background:{bg};
                    padding:3px 8px;border-radius:3px;margin-bottom:4px;">{label}</div>
        <div id="loading{n}" style="color:#ccc;text-align:center;padding:16px 0;">Loading…</div>
        <div id="error{n}"   style="display:none;color:red;font-size:10px;"></div>
        <div id="demoBanner{n}" style="display:none;"></div>
        <div style="position:relative;height:220px;width:100%;">
          <canvas id="chart{n}" style="display:none;"></canvas>
        </div>
      </div>"""

        slug = name.replace(" ", "_").replace("/", "_").replace("%","pct")[:30]
        divs.append(f"""
<div data-pair="{i}" data-slug="{slug}"
     style="background:#fff;border-radius:6px;box-shadow:0 1px 6px rgba(0,0,0,.12);
            margin-bottom:14px;padding:10px 12px;">
  <div style="font-size:11px;font-weight:bold;color:#fff;background:#2c3e50;
              padding:3px 10px;border-radius:4px;margin-bottom:8px;">
    [{i+1:02d}] {group} — {name}
  </div>
  <div style="display:flex;gap:10px;">
    {chart_cell(n0, "BEFORE (baseline)", "#27ae60", "#eafaf1")}
    {chart_cell(n1, f"AFTER: {name}", "#e74c3c", "#fdf2f8")}
  </div>
  <div style="font-size:9px;color:#888;margin-top:4px;font-style:italic;">
    {expect}</div>
</div>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Bar Checklist</title>
  <style>
    body{{font-family:Arial,sans-serif;background:#f0f2f5;
         max-width:1060px;margin:0 auto;padding:14px;}}
  </style>
</head>
<body>
  <h2 style="margin-bottom:10px;">Bar Chart — Option Checklist (BEFORE vs AFTER)</h2>
  {''.join(divs)}
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
  <script>{'  '.join(inits)}</script>
</body>
</html>"""


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    CROP_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Building checklist HTML ({len(CHECKS)} pairs, {len(CHECKS)*2} charts)…")
    html = build_html(CHECKS)
    OUT_HTML.write_text(html, encoding="utf-8")

    # JS syntax check
    scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
    custom  = "\n".join(scripts[2:])
    tmp_js  = Path("C:/Temp/bar_checklist_js.js")
    tmp_js.write_text(custom, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(tmp_js)], capture_output=True, text=True)
    if r.returncode != 0:
        print("JS SYNTAX ERROR:", r.stderr[:600])
        sys.exit(1)
    print(f"  {len(html):,} bytes  |  JS syntax OK")

    # Screenshot via CDP
    print("\nScreenshotting via CDP…")
    r2 = subprocess.run([str(NODE), str(CDP_SCRIPT)], timeout=70, capture_output=True, text=True)
    print(r2.stdout.strip())
    if r2.returncode != 0:
        print("CDP error:", r2.stderr[:400])
        sys.exit(1)

    if not FULL_PNG.exists() or FULL_PNG.stat().st_size < 50_000:
        print("ERROR: screenshot missing or too small"); sys.exit(1)

    # Load bounding boxes + full image
    boxes = json.loads(BOXES_JSON.read_text())
    from PIL import Image
    img = Image.open(FULL_PNG)
    W, H = img.size
    print(f"  Image: {W}×{H}px, {len(boxes)} pairs")

    # Crop and save each pair
    crops = []
    for box in sorted(boxes, key=lambda b: b["pair"]):
        i    = box["pair"]
        x0   = max(0, box["left"] - 4)
        y0   = max(0, box["top"]  - 4)
        x1   = min(W, x0 + box["w"] + 8)
        y1   = min(H, y0 + box["h"] + 8)
        crop = img.crop((x0, y0, x1, y1))
        group, name = CHECKS[i][0], CHECKS[i][1]
        slug  = f"{i+1:02d}_{group}_{name}".replace(" ","_").replace("/","_").replace("%","pct")[:50]
        out   = CROP_DIR / f"{slug}.png"
        crop.save(out)
        crops.append((i, group, name, CHECKS[i][4], out))
        print(f"  [{i+1:02d}] {group:12s} | {name:35s}  -> {out.name}")

    return crops


if __name__ == "__main__":
    crops = main()
    print(f"\nDone — {len(crops)} pair images in {CROP_DIR}")
    print("Now read each image to verify BEFORE vs AFTER.")
