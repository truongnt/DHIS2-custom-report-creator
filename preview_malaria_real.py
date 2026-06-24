"""
Tạo preview chart với dữ liệu thật từ test_fixture_malaria.json
và mở thẳng trong browser.

Chạy: python preview_malaria_real.py
"""
import sys, json, webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from charts.plugins.bar import BarPlugin

FIXTURE_PATH = Path("C:/Temp/test_fixture_malaria.json")
if not FIXTURE_PATH.exists():
    print(f"Chưa có fixture: {FIXTURE_PATH}")
    print("Chạy trước: python run_malaria_real_test.py")
    sys.exit(1)

fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
print(f"Fixture: {len(fixture.get('rows',[]))} rows")

PROG  = "yAKTrPUMAuU"
STAGE = "h86ikuTvjuP"
DE    = "qf5LcIDIXSJ"
OPTIONS = [
    {"code": "PF", "name": "P. falciparum"},
    {"code": "PV", "name": "P. vivax"},
    {"code": "PO", "name": "P. ovale"},
    {"code": "PM", "name": "P. malariae"},
    {"code": "PK", "name": "P. knowlesi"},
    {"code": "Mixed", "name": "Mixed"},
]

config = {
    "metrics": [{
        "uid": DE, "type": "tracker_numeric", "name": "Cases",
        "agg": "COUNT", "prog_uid": PROG, "stage_uid": STAGE,
    }],
    "dimensions": {"dimension": {
        "uid": DE, "type": "tracker_option",
        "prog_uid": PROG, "stage_uid": STAGE,
        "options": OPTIONS,
    }},
    "plugin_options": {
        "stack_mode":   "Stack",
        "show_legend":  True,
        "show_values":  True,
        "only_total":   True,
        "color_scheme": "Default",
    },
}

js = BarPlugin.build_js(n=0, config=config)

fixture_key = f"aggregate/{PROG}"
fixtures_js = json.dumps({fixture_key: fixture})

CHARTJS    = Path("C:/Temp/chartjs/chart.umd.min.js").read_text(encoding="utf-8")
DATALABELS = Path("C:/Temp/chartjs/chartjs-datalabels.min.js").read_text(encoding="utf-8")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Malaria — Diagnosis Test Result</title>
  <style>
    body{{font-family:Arial,sans-serif;background:#f0f2f5;margin:0;padding:24px;}}
    h2{{color:#2c3e50;margin:0 0 4px 0;font-size:18px;}}
    p{{color:#7f8c8d;margin:0 0 16px 0;font-size:12px;}}
    .card{{background:#fff;border-radius:8px;
           box-shadow:0 2px 10px rgba(0,0,0,.12);
           padding:20px 24px;max-width:960px;}}
    .chart-wrap{{position:relative;height:400px;width:100%;margin-top:12px;}}
  </style>
</head>
<body>
  <div class="card">
    <h2>Malaria Case Register — Diagnosis Test Result</h2>
    <p>Laos HMIS &nbsp;·&nbsp; Last 12 months &nbsp;·&nbsp;
       Stacked by parasite species &nbsp;·&nbsp;
       <strong>Real data from DHIS2</strong> ({len(fixture.get('rows',[]))} rows)</p>
    <div id="loading0" style="color:#aaa;text-align:center;padding:40px 0;">Loading…</div>
    <div id="error0"   style="display:none;color:red;font-size:12px;padding:8px;"></div>
    <div id="demoBanner0" style="display:none;"></div>
    <div class="chart-wrap">
      <canvas id="chart0"></canvas>
    </div>
  </div>

  <script>{CHARTJS}</script>
  <script>{DATALABELS}</script>
  <script>
    Chart.register(ChartDataLabels);
    Chart.defaults.animation = false;
    const PREVIEW = false;
    function formatPeriodLabel(pe){{
      const mm=pe.match(/^(\\d{{4}})(\\d{{2}})$/);
      if(mm){{const M=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
              return M[parseInt(mm[2],10)-1]+' '+mm[1];}}
      return pe;
    }}
    function resolveRelativePeriod(pe){{return pe;}}
    const _FIXTURES={fixtures_js};
    async function dhis2Get(url){{
      for(const [k,d] of Object.entries(_FIXTURES)){{
        if(url.includes(k)) return d;
      }}
      throw new Error('No fixture: '+url);
    }}
    {js}
  </script>
  <script>initChart0('USER_ORGUNIT','LAST_12_MONTHS');</script>
</body>
</html>"""

out = Path("C:/Temp/malaria_real_preview.html")
out.write_text(html, encoding="utf-8")
webbrowser.open(out.as_uri())
print(f"Opened: {out}")
