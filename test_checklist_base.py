"""
Shared infrastructure for plugin checklist tests.

Usage:
    from test_checklist_base import ChecklistRunner

    runner = ChecklistRunner(
        plugin      = MyPlugin,
        checks      = CHECKS,       # list of 5-tuples
        html_path   = Path("C:/Temp/my_checklist.html"),
        mjs_path    = Path("C:/Temp/screenshot_my.mjs"),
        full_png    = Path("C:/Temp/my_checklist_full.png"),
        boxes_json  = Path("C:/Temp/my_checklist_boxes.json"),
        crop_dir    = Path("C:/Temp/my_checks"),
        chart_title = "My Chart — Option Checklist",
    )
    runner.run()
"""
import subprocess, sys, json, re
from pathlib import Path

CHARTJS    = Path("C:/Temp/chartjs/chart.umd.min.js")
DATALABELS = Path("C:/Temp/chartjs/chartjs-datalabels.min.js")
NODE       = Path(r"C:\Program Files\nodejs\node.exe")


class ChecklistRunner:
    def __init__(self, *, plugin, checks, html_path, mjs_path,
                 full_png, boxes_json, crop_dir, chart_title, port,
                 fixtures: dict | None = None):
        """
        fixtures : optional dict mapping URL-pattern substring -> JSON-serialisable object.
          When provided the HTML page sets PREVIEW=false and dhis2Get() intercepts
          requests: if the URL contains a key, it returns the mapped value instead
          of calling the real API. This lets real-data code paths be tested without
          a live DHIS2 connection.
          Example:
            fixtures={
              "events/aggregate/progUID": <dict loaded from test_fixture.json>,
            }
        """
        self.plugin      = plugin
        self.checks      = checks
        self.html_path   = html_path
        self.mjs_path    = mjs_path
        self.full_png    = full_png
        self.boxes_json  = boxes_json
        self.crop_dir    = crop_dir
        self.chart_title = chart_title
        self.port        = port
        self.fixtures    = fixtures or {}

    def _dhis2get_js(self) -> str:
        """Return JS dhis2Get() implementation.
        - No fixtures: throws (PREVIEW mode)
        - With fixtures: intercepts URL by key substring, returns pre-loaded JSON.
        """
        import json as _json
        if not self.fixtures:
            return "async function dhis2Get(){throw new Error('PREVIEW mode');}"
        fixtures_js = _json.dumps(self.fixtures)
        return f"""\
    const _FIXTURES = {fixtures_js};
    async function dhis2Get(url) {{
      for (const [key, data] of Object.entries(_FIXTURES)) {{
        if (url.includes(key)) return data;
      }}
      throw new Error('No fixture matched: ' + url);
    }}"""

    def build_html(self):
        chartjs_src    = CHARTJS.read_text(encoding="utf-8")
        datalabels_src = DATALABELS.read_text(encoding="utf-8")

        divs, js_blocks, inits = [], [], []

        for i, (group, name, base_cfg, test_cfg, expect) in enumerate(self.checks):
            n0, n1 = i * 2, i * 2 + 1
            js_blocks.append(self.plugin.build_js(n=n0, config={**base_cfg}))
            js_blocks.append(self.plugin.build_js(n=n1, config={**test_cfg}))
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

            divs.append(f"""
<div data-pair="{i}"
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
  <title>{self.chart_title}</title>
  <style>
    body{{font-family:Arial,sans-serif;background:#f0f2f5;
         max-width:1060px;margin:0 auto;padding:14px;}}
  </style>
</head>
<body>
  <h2 style="margin-bottom:10px;">{self.chart_title} (BEFORE vs AFTER)</h2>
  {''.join(divs)}
  <script>{chartjs_src}</script>
  <script>{datalabels_src}</script>
  <script>
    Chart.register(ChartDataLabels);
    Chart.defaults.animation = false;
    Chart.defaults.animations = false;
    Chart.defaults.transitions = {{}};
    const PREVIEW = {str(not bool(self.fixtures)).lower()};
    function formatPeriodLabel(pe){{
      const mm=pe.match(/^(\\d{{4}})(\\d{{2}})$/);
      if(mm){{const M=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
              return M[parseInt(mm[2],10)-1]+' '+mm[1];}}
      const qm=pe.match(/^(\\d{{4}})Q(\\d)$/);
      if(qm) return 'Q'+qm[2]+' '+qm[1];
      return pe;
    }}
    function resolveRelativePeriod(pe){{return pe;}}
    {self._dhis2get_js()}
    {''.join(js_blocks)}
  </script>
  <script>{'  '.join(inits)}</script>
</body>
</html>"""

    def build_mjs(self):
        html_url = "file:///" + str(self.html_path).replace("\\", "/")
        out_png  = str(self.full_png).replace("\\", "/")
        out_json = str(self.boxes_json).replace("\\", "/")
        return f"""/**
 * CDP screenshot for {self.chart_title}.
 */
import {{ spawn, execSync }} from 'child_process';
import {{ writeFileSync }} from 'fs';

const HTML_FILE = {repr(str(self.html_path))};
const OUT_PNG   = {repr(str(self.full_png))};
const OUT_JSON  = {repr(str(self.boxes_json))};
const CHROME    = 'C:\\\\Program Files\\\\Google\\\\Chrome\\\\Application\\\\chrome.exe';
const PORT      = {self.port};
const FILE_URL  = 'file:///' + HTML_FILE.replace(/\\\\/g, '/');

function sleep(ms) {{ return new Promise(r => setTimeout(r, ms)); }}

let _id = 0;
function send(ws, method, params = {{}}) {{
  const id = ++_id;
  return new Promise((resolve, reject) => {{
    const onMsg = (e) => {{
      const d = JSON.parse(e.data);
      if (d.id === id) {{
        ws.removeEventListener('message', onMsg);
        if (d.error) reject(new Error(JSON.stringify(d.error)));
        else resolve(d.result);
      }}
    }};
    ws.addEventListener('message', onMsg);
    ws.send(JSON.stringify({{ id, method, params }}));
  }});
}}

async function fetchTargets() {{
  for (let i = 0; i < 12; i++) {{
    try {{
      const res = await fetch(`http://localhost:${{PORT}}/json`);
      const arr = await res.json();
      if (arr.length) return arr;
    }} catch (_) {{}}
    await sleep(400);
  }}
  return [];
}}

async function main() {{
  try {{ execSync(`taskkill /F /IM chrome.exe 2>nul`); }} catch (_) {{}}
  await sleep(600);

  const chrome = spawn(CHROME, [
    '--headless=new', '--disable-gpu', '--no-sandbox',
    '--disable-dev-shm-usage',
    `--remote-debugging-port=${{PORT}}`,
    '--window-size=1080,900',
    FILE_URL,
  ], {{ stdio: 'ignore', detached: false }});

  await sleep(3500);

  const targets = await fetchTargets();
  let target = targets.find(t => t.url && t.url.startsWith('file://'));
  if (!target) target = targets.find(t => t.type === 'page');
  if (!target) {{ console.error('No CDP target found'); chrome.kill(); process.exit(1); }}

  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => {{
    ws.addEventListener('open', res);
    ws.addEventListener('error', rej);
  }});

  await send(ws, 'Runtime.enable');
  await send(ws, 'Page.enable');
  await sleep(2500);

  const dims = await send(ws, 'Runtime.evaluate', {{
    expression: `JSON.stringify({{w: document.body.scrollWidth, h: document.body.scrollHeight}})`,
    returnByValue: true,
  }});
  const {{ w, h }} = JSON.parse(dims.result.value);
  console.log(`Page size: ${{w}}x${{h}}`);

  await send(ws, 'Emulation.setDeviceMetricsOverride', {{
    width: 1080, height: h, deviceScaleFactor: 1, mobile: false,
  }});

  const shot = await send(ws, 'Page.captureScreenshot', {{
    format: 'png', captureBeyondViewport: true,
  }});
  const buf = Buffer.from(shot.data, 'base64');
  writeFileSync(OUT_PNG, buf);
  console.log(`Screenshot: ${{OUT_PNG}}  (${{buf.length.toLocaleString()}} bytes)  ${{w}}x${{h}}`);

  const boxExpr = `JSON.stringify(
    Array.from(document.querySelectorAll('[data-pair]')).map(el => {{
      const r = el.getBoundingClientRect();
      return {{
        pair: parseInt(el.dataset.pair),
        top:  Math.round(r.top  + window.scrollY),
        left: Math.round(r.left + window.scrollX),
        w:    Math.round(r.width),
        h:    Math.round(r.height)
      }};
    }})
  )`;
  const boxRes = await send(ws, 'Runtime.evaluate', {{ expression: boxExpr, returnByValue: true }});
  writeFileSync(OUT_JSON, boxRes.result.value);
  console.log(`Boxes JSON: ${{OUT_JSON}}`);

  ws.close();
  chrome.kill();
}}

main().catch(e => {{ console.error(e.stack || e); process.exit(1); }});
"""

    def run(self):
        self.crop_dir.mkdir(parents=True, exist_ok=True)

        print(f"Building checklist HTML ({len(self.checks)} pairs, {len(self.checks)*2} charts)…")
        html = self.build_html()
        self.html_path.write_text(html, encoding="utf-8")
        print(f"  {len(html):,} bytes  | {self.html_path}")

        # JS syntax check
        scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
        custom  = "\n".join(scripts[2:])
        tmp_js  = self.html_path.with_suffix(".js")
        tmp_js.write_text(custom, encoding="utf-8")
        r = subprocess.run(["node", "--check", str(tmp_js)], capture_output=True, text=True)
        if r.returncode != 0:
            print("JS SYNTAX ERROR:", r.stderr[:600])
            sys.exit(1)
        print("  JS syntax OK")

        # Write MJS screenshot script
        self.mjs_path.write_text(self.build_mjs(), encoding="utf-8")

        # Screenshot via CDP
        print("\nScreenshotting via CDP…")
        r2 = subprocess.run([str(NODE), str(self.mjs_path)],
                            timeout=70, capture_output=True, text=True)
        print(r2.stdout.strip())
        if r2.returncode != 0:
            print("CDP error:", r2.stderr[:400])
            sys.exit(1)

        if not self.full_png.exists() or self.full_png.stat().st_size < 10_000:
            print("ERROR: screenshot missing or too small"); sys.exit(1)

        boxes = json.loads(self.boxes_json.read_text())
        from PIL import Image
        img  = Image.open(self.full_png)
        W, H = img.size
        print(f"  Image: {W}x{H}px, {len(boxes)} pairs")

        crops = []
        for box in sorted(boxes, key=lambda b: b["pair"]):
            i    = box["pair"]
            x0   = max(0, box["left"] - 4)
            y0   = max(0, box["top"]  - 4)
            x1   = min(W, x0 + box["w"] + 8)
            y1   = min(H, y0 + box["h"] + 8)
            crop = img.crop((x0, y0, x1, y1))
            group, name = self.checks[i][0], self.checks[i][1]
            slug  = f"{i+1:02d}_{group}_{name}".replace(" ","_").replace("/","_").replace("%","pct")[:50]
            out   = self.crop_dir / f"{slug}.png"
            crop.save(out)
            crops.append((i, group, name, self.checks[i][4], out))
            print(f"  [{i+1:02d}] {group:14s} | {name:35s}  -> {out.name}")

        print(f"\nDone — {len(crops)} pair images in {self.crop_dir}")
        return crops
