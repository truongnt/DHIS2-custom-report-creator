"""
Chart template library for DHIS2 HTML reports.

Each template is a complete, working DHIS2 HTML report structure.
The LLM fills in:
  - Indicator/data-element UIDs (replacing <!-- INDICATOR_UID --> placeholders)
  - Report title (<!-- REPORT_TITLE -->)
  - Color theme / label customization

Velocity variables already in place:
  - $!{reportingPeriod}   → period UID selected by user in DHIS2
  - $!{organisationUnit}  → org unit UID selected by user in DHIS2

All templates use:
  - Bootstrap 5.3 (CDN)
  - Chart.js 4.4 (CDN)
  - DHIS2 analytics API: ../api/analytics.json  (relative URL, credentials: include)
"""

# ── Category definitions ──────────────────────────────────────────────────────

CATEGORIES = [
    {"id": "time_series",  "name": "Time Series",    "color": "#1a6fa8", "icon": "📈",
     "desc": "Xu hướng theo thời gian (tháng/quý/năm)"},
    {"id": "comparison",   "name": "Comparison",     "color": "#27ae60", "icon": "📊",
     "desc": "So sánh giữa các đơn vị, chỉ số, hoặc kỳ"},
    {"id": "proportion",   "name": "Proportion",     "color": "#8e44ad", "icon": "🥧",
     "desc": "Tỷ lệ, phần trăm, cơ cấu thành phần"},
    {"id": "scorecard",    "name": "Scorecard / KPI","color": "#e67e22", "icon": "🎯",
     "desc": "Chỉ số tổng hợp, đèn giao thông, target vs actual"},
    {"id": "table",        "name": "Data Table",     "color": "#2c3e50", "icon": "📋",
     "desc": "Bảng dữ liệu chi tiết, pivot, cross-tab"},
    {"id": "combined",     "name": "Combined",       "color": "#c0392b", "icon": "🔀",
     "desc": "Kết hợp nhiều loại chart trên cùng một trang"},
    {"id": "map",          "name": "Map / Geo",      "color": "#16a085", "icon": "🗺",
     "desc": "Bản đồ choropleth (area) và bubble point theo đơn vị hành chính"},
    {"id": "advanced",     "name": "Advanced",       "color": "#7f8c8d", "icon": "🕸",
     "desc": "Radar/spider chart, scatter, histogram"},
]

# ── Shared HTML fragments ─────────────────────────────────────────────────────

_HEAD = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><!-- REPORT_TITLE --></title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    body { background: #f8f9fa; font-family: 'Segoe UI', sans-serif; }
    .report-header { background: #1a6fa8; color: #fff; padding: 18px 24px; margin-bottom: 24px; border-radius: 6px; }
    .report-header h2 { margin: 0; font-size: 1.4rem; }
    .report-header small { opacity: .8; font-size: .85rem; }
    .card { border: none; box-shadow: 0 1px 6px rgba(0,0,0,.08); }
    .spinner-wrap { text-align: center; padding: 60px 0; }
    .error-box { border-left: 4px solid #e74c3c; }
  </style>
</head>
<body class="p-3">
<!-- reportingPeriod=$!{reportingPeriod} organisationUnit=$!{organisationUnit} -->"""

_FOOT = """
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""

_LOADER_JS = """
  function showError(id, msg) {
    document.getElementById(id).innerHTML =
      `<div class="alert alert-danger error-box">${msg}</div>`;
  }
  async function dhis2Get(url) {
    const res = await fetch('../' + url, { credentials: 'include' });
    if (!res.ok) throw new Error('HTTP ' + res.status + ': ' + await res.text());
    return res.json();
  }
  function periodLabel(meta, uid) { return meta?.items?.[uid]?.name || uid; }
  function itemLabel(meta, uid)   { return meta?.items?.[uid]?.name || uid; }"""


# ── Template HTML ─────────────────────────────────────────────────────────────

_LINE_SINGLE = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div class="card">
    <div class="card-body">
      <div id="loading" class="spinner-wrap">
        <div class="spinner-border text-primary"></div><p class="mt-2">Loading…</p>
      </div>
      <canvas id="chart" style="display:none; max-height:420px"></canvas>
    </div>
  </div>
</div>
<script>
""" + _LOADER_JS + """
  const DX  = '<!-- INDICATOR_UID -->';   // single indicator UID
  const PE  = '$!{reportingPeriod}' || 'LAST_12_MONTHS';
  const OU  = '$!{organisationUnit}' || 'USER_ORGUNIT';
  const COLOR = '#1a6fa8';

  (async () => {
    try {
      const d = await dhis2Get(
        `api/analytics.json?dimension=dx:${DX}&dimension=pe:${PE}&dimension=ou:${OU}&displayProperty=NAME`
      );
      const periods = [...new Set(d.rows.map(r => r[1]))];
      const values  = periods.map(p => {
        const row = d.rows.find(r => r[1] === p);
        return row ? parseFloat(row[2]) : null;
      });
      document.getElementById('loading').style.display = 'none';
      const cvs = document.getElementById('chart');
      cvs.style.display = 'block';
      new Chart(cvs, {
        type: 'line',
        data: {
          labels: periods.map(p => periodLabel(d.metaData, p)),
          datasets: [{ label: itemLabel(d.metaData, DX), data: values,
            borderColor: COLOR, backgroundColor: COLOR + '22',
            tension: 0.3, fill: true, pointRadius: 4 }]
        },
        options: { responsive: true, plugins: { legend: { position: 'top' } },
                   scales: { y: { beginAtZero: true } } }
      });
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ─────────────────────────────────────────────────────────────────────────────

_LINE_MULTI = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div class="card"><div class="card-body">
    <div id="loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
    <canvas id="chart" style="display:none; max-height:420px"></canvas>
  </div></div>
</div>
<script>
""" + _LOADER_JS + """
  // Replace with 2–5 indicator UIDs separated by semicolons
  const DX_LIST = ['<!-- INDICATOR_UID_1 -->', '<!-- INDICATOR_UID_2 -->'];
  const COLORS  = ['#1a6fa8','#27ae60','#e67e22','#8e44ad','#c0392b'];
  const PE = '$!{reportingPeriod}' || 'LAST_12_MONTHS';
  const OU = '$!{organisationUnit}' || 'USER_ORGUNIT';

  (async () => {
    try {
      const d = await dhis2Get(
        `api/analytics.json?dimension=dx:${DX_LIST.join(';')}&dimension=pe:${PE}&dimension=ou:${OU}&displayProperty=NAME`
      );
      const periods  = [...new Set(d.rows.map(r => r[1]))];
      const datasets = DX_LIST.map((dx, i) => ({
        label: itemLabel(d.metaData, dx),
        data:  periods.map(p => { const r = d.rows.find(x => x[0]===dx && x[1]===p); return r ? parseFloat(r[2]) : null; }),
        borderColor: COLORS[i % COLORS.length],
        backgroundColor: COLORS[i % COLORS.length] + '22',
        tension: 0.3, fill: false, pointRadius: 3,
      }));
      document.getElementById('loading').style.display = 'none';
      const cvs = document.getElementById('chart'); cvs.style.display = 'block';
      new Chart(cvs, {
        type: 'line',
        data: { labels: periods.map(p => periodLabel(d.metaData, p)), datasets },
        options: { responsive: true, plugins: { legend: { position: 'top' } },
                   scales: { y: { beginAtZero: true } } }
      });
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ─────────────────────────────────────────────────────────────────────────────

_BAR_MONTHLY = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div class="card"><div class="card-body">
    <div id="loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
    <canvas id="chart" style="display:none; max-height:420px"></canvas>
  </div></div>
</div>
<script>
""" + _LOADER_JS + """
  const DX    = '<!-- INDICATOR_UID -->';
  const PE    = '$!{reportingPeriod}' || 'LAST_12_MONTHS';
  const OU    = '$!{organisationUnit}' || 'USER_ORGUNIT';
  const COLOR = '#1a6fa8';

  (async () => {
    try {
      const d = await dhis2Get(
        `api/analytics.json?dimension=dx:${DX}&dimension=pe:${PE}&dimension=ou:${OU}&displayProperty=NAME`
      );
      const periods = [...new Set(d.rows.map(r => r[1]))];
      const values  = periods.map(p => { const r = d.rows.find(x => x[1]===p); return r ? parseFloat(r[2]) : 0; });
      document.getElementById('loading').style.display = 'none';
      const cvs = document.getElementById('chart'); cvs.style.display = 'block';
      new Chart(cvs, {
        type: 'bar',
        data: {
          labels: periods.map(p => periodLabel(d.metaData, p)),
          datasets: [{ label: itemLabel(d.metaData, DX), data: values,
            backgroundColor: COLOR + 'cc', borderColor: COLOR, borderWidth: 1 }]
        },
        options: { responsive: true, plugins: { legend: { position: 'top' } },
                   scales: { y: { beginAtZero: true } } }
      });
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ─────────────────────────────────────────────────────────────────────────────

_BAR_GROUPED = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div class="card"><div class="card-body">
    <div id="loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
    <canvas id="chart" style="display:none; max-height:420px"></canvas>
  </div></div>
</div>
<script>
""" + _LOADER_JS + """
  // Multiple indicators grouped side-by-side per period
  const DX_LIST = ['<!-- INDICATOR_UID_1 -->', '<!-- INDICATOR_UID_2 -->'];
  const COLORS  = ['#1a6fa8','#27ae60','#e67e22','#8e44ad'];
  const PE = '$!{reportingPeriod}' || 'LAST_4_QUARTERS';
  const OU = '$!{organisationUnit}' || 'USER_ORGUNIT';

  (async () => {
    try {
      const d = await dhis2Get(
        `api/analytics.json?dimension=dx:${DX_LIST.join(';')}&dimension=pe:${PE}&dimension=ou:${OU}&displayProperty=NAME`
      );
      const periods  = [...new Set(d.rows.map(r => r[1]))];
      const datasets = DX_LIST.map((dx, i) => ({
        label: itemLabel(d.metaData, dx),
        data:  periods.map(p => { const r = d.rows.find(x => x[0]===dx && x[1]===p); return r ? parseFloat(r[2]) : 0; }),
        backgroundColor: COLORS[i % COLORS.length] + 'cc',
        borderColor: COLORS[i % COLORS.length], borderWidth: 1,
      }));
      document.getElementById('loading').style.display = 'none';
      const cvs = document.getElementById('chart'); cvs.style.display = 'block';
      new Chart(cvs, {
        type: 'bar',
        data: { labels: periods.map(p => periodLabel(d.metaData, p)), datasets },
        options: { responsive: true, plugins: { legend: { position: 'top' } },
                   scales: { y: { beginAtZero: true } } }
      });
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ─────────────────────────────────────────────────────────────────────────────

_BAR_STACKED = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div class="card"><div class="card-body">
    <div id="loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
    <canvas id="chart" style="display:none; max-height:420px"></canvas>
  </div></div>
</div>
<script>
""" + _LOADER_JS + """
  const DX_LIST = ['<!-- INDICATOR_UID_1 -->', '<!-- INDICATOR_UID_2 -->', '<!-- INDICATOR_UID_3 -->'];
  const COLORS  = ['#1a6fa8','#27ae60','#e67e22','#8e44ad','#c0392b'];
  const PE = '$!{reportingPeriod}' || 'LAST_12_MONTHS';
  const OU = '$!{organisationUnit}' || 'USER_ORGUNIT';

  (async () => {
    try {
      const d = await dhis2Get(
        `api/analytics.json?dimension=dx:${DX_LIST.join(';')}&dimension=pe:${PE}&dimension=ou:${OU}&displayProperty=NAME`
      );
      const periods  = [...new Set(d.rows.map(r => r[1]))];
      const datasets = DX_LIST.map((dx, i) => ({
        label: itemLabel(d.metaData, dx),
        data:  periods.map(p => { const r = d.rows.find(x => x[0]===dx && x[1]===p); return r ? parseFloat(r[2]) : 0; }),
        backgroundColor: COLORS[i % COLORS.length] + 'cc',
        stack: 'stack0',
      }));
      document.getElementById('loading').style.display = 'none';
      const cvs = document.getElementById('chart'); cvs.style.display = 'block';
      new Chart(cvs, {
        type: 'bar',
        data: { labels: periods.map(p => periodLabel(d.metaData, p)), datasets },
        options: { responsive: true,
          plugins: { legend: { position: 'top' } },
          scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } } }
      });
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ─────────────────────────────────────────────────────────────────────────────

_BAR_HORIZONTAL_OU = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; So sánh theo đơn vị tổ chức</small>
  </div>
  <div class="card"><div class="card-body">
    <div id="loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
    <canvas id="chart" style="display:none; max-height:500px"></canvas>
  </div></div>
</div>
<script>
""" + _LOADER_JS + """
  const DX     = '<!-- INDICATOR_UID -->';
  const PE     = '$!{reportingPeriod}' || 'THIS_YEAR';
  // LEVEL-2 = province, LEVEL-3 = district — adjust to your hierarchy
  const OU     = '$!{organisationUnit}' || 'USER_ORGUNIT';
  const OU_DIM = `${OU};LEVEL-2`;
  const COLOR  = '#1a6fa8';

  (async () => {
    try {
      const d = await dhis2Get(
        `api/analytics.json?dimension=dx:${DX}&dimension=pe:${PE}&dimension=ou:${OU_DIM}&displayProperty=NAME`
      );
      const ous    = [...new Set(d.rows.map(r => r[2]))];
      const values = ous.map(o => { const r = d.rows.find(x => x[2]===o); return r ? parseFloat(r[2]) : 0; });
      // Sort descending
      const sorted = ous.map((o, i) => ({ name: itemLabel(d.metaData, o), val: values[i] }))
                       .sort((a, b) => b.val - a.val);
      document.getElementById('loading').style.display = 'none';
      const cvs = document.getElementById('chart'); cvs.style.display = 'block';
      new Chart(cvs, {
        type: 'bar',
        data: {
          labels: sorted.map(x => x.name),
          datasets: [{ label: itemLabel(d.metaData, DX), data: sorted.map(x => x.val),
            backgroundColor: COLOR + 'cc', borderColor: COLOR, borderWidth: 1 }]
        },
        options: { indexAxis: 'y', responsive: true,
          plugins: { legend: { display: false } },
          scales: { x: { beginAtZero: true } } }
      });
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ─────────────────────────────────────────────────────────────────────────────

_PIE = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div class="row justify-content-center">
    <div class="col-md-7">
      <div class="card"><div class="card-body">
        <div id="loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
        <canvas id="chart" style="display:none; max-height:400px"></canvas>
      </div></div>
    </div>
  </div>
</div>
<script>
""" + _LOADER_JS + """
  // Each UID becomes one slice of the pie
  const DX_LIST = ['<!-- INDICATOR_UID_1 -->', '<!-- INDICATOR_UID_2 -->', '<!-- INDICATOR_UID_3 -->'];
  const COLORS  = ['#1a6fa8','#27ae60','#e67e22','#8e44ad','#c0392b','#16a085'];
  const PE = '$!{reportingPeriod}' || 'THIS_YEAR';
  const OU = '$!{organisationUnit}' || 'USER_ORGUNIT';

  (async () => {
    try {
      const d = await dhis2Get(
        `api/analytics.json?dimension=dx:${DX_LIST.join(';')}&filter=pe:${PE}&filter=ou:${OU}&displayProperty=NAME`
      );
      const labels = DX_LIST.map(dx => itemLabel(d.metaData, dx));
      const values = DX_LIST.map(dx => { const r = d.rows.find(x => x[0]===dx); return r ? parseFloat(r[1]) : 0; });
      document.getElementById('loading').style.display = 'none';
      const cvs = document.getElementById('chart'); cvs.style.display = 'block';
      new Chart(cvs, {
        type: 'pie',
        data: { labels, datasets: [{ data: values, backgroundColor: COLORS, hoverOffset: 10 }] },
        options: { responsive: true, plugins: { legend: { position: 'right' } } }
      });
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ─────────────────────────────────────────────────────────────────────────────

_DONUT = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div class="row justify-content-center">
    <div class="col-md-6">
      <div class="card"><div class="card-body position-relative">
        <div id="loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
        <canvas id="chart" style="display:none; max-height:380px"></canvas>
        <div id="centerLabel" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
             text-align:center;display:none;pointer-events:none">
          <div style="font-size:2rem;font-weight:700;color:#1e2d3d" id="centerVal"></div>
          <div style="font-size:.8rem;color:#6b8299" id="centerTxt">Total</div>
        </div>
      </div></div>
    </div>
  </div>
</div>
<script>
""" + _LOADER_JS + """
  const DX_LIST = ['<!-- INDICATOR_UID_1 -->', '<!-- INDICATOR_UID_2 -->', '<!-- INDICATOR_UID_3 -->'];
  const COLORS  = ['#1a6fa8','#27ae60','#e67e22','#8e44ad','#c0392b'];
  const PE = '$!{reportingPeriod}' || 'THIS_YEAR';
  const OU = '$!{organisationUnit}' || 'USER_ORGUNIT';

  (async () => {
    try {
      const d = await dhis2Get(
        `api/analytics.json?dimension=dx:${DX_LIST.join(';')}&filter=pe:${PE}&filter=ou:${OU}&displayProperty=NAME`
      );
      const values = DX_LIST.map(dx => { const r = d.rows.find(x => x[0]===dx); return r ? parseFloat(r[1]) : 0; });
      const total  = values.reduce((a, b) => a + b, 0);
      document.getElementById('loading').style.display = 'none';
      const cvs = document.getElementById('chart'); cvs.style.display = 'block';
      document.getElementById('centerLabel').style.display = 'block';
      document.getElementById('centerVal').textContent = total.toLocaleString();
      new Chart(cvs, {
        type: 'doughnut',
        data: { labels: DX_LIST.map(dx => itemLabel(d.metaData, dx)),
                datasets: [{ data: values, backgroundColor: COLORS, hoverOffset: 10, cutout: '65%' }] },
        options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
      });
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ─────────────────────────────────────────────────────────────────────────────

_SCORECARD = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div id="loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
  <div id="cards" class="row g-3" style="display:none"></div>
</div>
<script>
""" + _LOADER_JS + """
  // One card per indicator UID
  const DX_LIST = ['<!-- INDICATOR_UID_1 -->', '<!-- INDICATOR_UID_2 -->', '<!-- INDICATOR_UID_3 -->', '<!-- INDICATOR_UID_4 -->'];
  const COLORS  = ['#1a6fa8','#27ae60','#e67e22','#8e44ad'];
  const ICONS   = ['🏥','✅','📊','🎯'];
  const PE = '$!{reportingPeriod}' || 'THIS_YEAR';
  const OU = '$!{organisationUnit}' || 'USER_ORGUNIT';

  (async () => {
    try {
      const d = await dhis2Get(
        `api/analytics.json?dimension=dx:${DX_LIST.join(';')}&filter=pe:${PE}&filter=ou:${OU}&displayProperty=NAME`
      );
      document.getElementById('loading').style.display = 'none';
      const container = document.getElementById('cards'); container.style.display = '';
      DX_LIST.forEach((dx, i) => {
        const row = d.rows.find(x => x[0] === dx);
        const val = row ? parseFloat(row[1]).toLocaleString() : 'N/A';
        const col = document.createElement('div');
        col.className = 'col-6 col-md-3';
        col.innerHTML = `<div class="card h-100 text-white" style="background:${COLORS[i % COLORS.length]}">
          <div class="card-body text-center py-4">
            <div style="font-size:2.5rem">${ICONS[i % ICONS.length]}</div>
            <div style="font-size:2.2rem;font-weight:700;margin:8px 0">${val}</div>
            <div style="font-size:.85rem;opacity:.9">${itemLabel(d.metaData, dx)}</div>
          </div></div>`;
        container.appendChild(col);
      });
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ─────────────────────────────────────────────────────────────────────────────

_TRAFFIC_LIGHT = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div id="loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
  <div id="tbl-wrap" style="display:none">
    <table class="table table-bordered table-hover bg-white shadow-sm rounded">
      <thead class="table-dark"><tr>
        <th>Indicator</th><th class="text-center">Value</th>
        <th class="text-center">Target</th><th class="text-center">Status</th>
      </tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</div>
<script>
""" + _LOADER_JS + """
  // Define indicators + their targets (value ≥ target = green, ≥ 75% = yellow, else red)
  const INDICATORS = [
    { uid: '<!-- INDICATOR_UID_1 -->', target: <!-- TARGET_1 --> },
    { uid: '<!-- INDICATOR_UID_2 -->', target: <!-- TARGET_2 --> },
    { uid: '<!-- INDICATOR_UID_3 -->', target: <!-- TARGET_3 --> },
  ];
  const PE = '$!{reportingPeriod}' || 'THIS_YEAR';
  const OU = '$!{organisationUnit}' || 'USER_ORGUNIT';

  (async () => {
    try {
      const uids = INDICATORS.map(x => x.uid).join(';');
      const d = await dhis2Get(
        `api/analytics.json?dimension=dx:${uids}&filter=pe:${PE}&filter=ou:${OU}&displayProperty=NAME`
      );
      document.getElementById('loading').style.display = 'none';
      document.getElementById('tbl-wrap').style.display = '';
      const tbody = document.getElementById('tbody');
      INDICATORS.forEach(ind => {
        const row = d.rows.find(r => r[0] === ind.uid);
        const val  = row ? parseFloat(row[1]) : null;
        const pct  = ind.target > 0 && val !== null ? val / ind.target : null;
        const [bg, icon] = pct === null ? ['#adb5bd','⚪'] :
                           pct >= 1    ? ['#27ae60','🟢'] :
                           pct >= 0.75 ? ['#f39c12','🟡'] : ['#e74c3c','🔴'];
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${itemLabel(d.metaData, ind.uid)}</td>
          <td class="text-center fw-bold">${val !== null ? val.toLocaleString() : '—'}</td>
          <td class="text-center text-muted">${ind.target.toLocaleString()}</td>
          <td class="text-center"><span class="badge" style="background:${bg};font-size:.95rem">${icon} ${pct !== null ? Math.round(pct*100)+'%' : 'N/A'}</span></td>`;
        tbody.appendChild(tr);
      });
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ─────────────────────────────────────────────────────────────────────────────

_DATA_TABLE = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div id="loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
  <div id="tbl-wrap" style="display:none">
    <div class="card"><div class="card-body p-0">
      <table class="table table-striped table-hover mb-0" id="main-table">
        <thead class="table-primary" id="thead"></thead>
        <tbody id="tbody"></tbody>
        <tfoot class="table-dark fw-bold" id="tfoot"></tfoot>
      </table>
    </div></div>
  </div>
</div>
<script>
""" + _LOADER_JS + """
  // Rows = org units (LEVEL-2), Columns = indicators
  const DX_LIST = ['<!-- INDICATOR_UID_1 -->', '<!-- INDICATOR_UID_2 -->', '<!-- INDICATOR_UID_3 -->'];
  const PE  = '$!{reportingPeriod}' || 'THIS_YEAR';
  const OU  = '$!{organisationUnit}' || 'USER_ORGUNIT';
  const OU_DIM = `${OU};LEVEL-2`;

  (async () => {
    try {
      const d = await dhis2Get(
        `api/analytics.json?dimension=dx:${DX_LIST.join(';')}&dimension=ou:${OU_DIM}&filter=pe:${PE}&displayProperty=NAME`
      );
      const ous = [...new Set(d.rows.map(r => r[1]))];
      // Header
      const thead = document.getElementById('thead');
      thead.innerHTML = '<tr><th>Org Unit</th>' +
        DX_LIST.map(dx => `<th class="text-end">${itemLabel(d.metaData, dx)}</th>`).join('') + '</tr>';
      // Body
      const tbody = document.getElementById('tbody');
      const totals = new Array(DX_LIST.length).fill(0);
      ous.forEach(ou => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${itemLabel(d.metaData, ou)}</td>` +
          DX_LIST.map((dx, i) => {
            const r   = d.rows.find(x => x[0]===dx && x[1]===ou);
            const val = r ? parseFloat(r[2]) : 0;
            totals[i] += val;
            return `<td class="text-end">${val.toLocaleString()}</td>`;
          }).join('');
        tbody.appendChild(tr);
      });
      // Footer totals
      document.getElementById('tfoot').innerHTML = '<tr><td>Total</td>' +
        totals.map(t => `<td class="text-end">${t.toLocaleString()}</td>`).join('') + '</tr>';
      document.getElementById('loading').style.display = 'none';
      document.getElementById('tbl-wrap').style.display = '';
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ─────────────────────────────────────────────────────────────────────────────

_COMBINED_BAR_LINE = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div class="card"><div class="card-body">
    <div id="loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
    <canvas id="chart" style="display:none; max-height:420px"></canvas>
  </div></div>
</div>
<script>
""" + _LOADER_JS + """
  // BAR_UID = count indicator (left y-axis), LINE_UID = rate indicator (right y-axis)
  const BAR_UID  = '<!-- BAR_INDICATOR_UID -->';   // e.g. confirmed malaria cases
  const LINE_UID = '<!-- LINE_INDICATOR_UID -->';   // e.g. positivity rate %
  const PE = '$!{reportingPeriod}' || 'LAST_12_MONTHS';
  const OU = '$!{organisationUnit}' || 'USER_ORGUNIT';

  (async () => {
    try {
      const d = await dhis2Get(
        `api/analytics.json?dimension=dx:${BAR_UID};${LINE_UID}&dimension=pe:${PE}&dimension=ou:${OU}&displayProperty=NAME`
      );
      const periods   = [...new Set(d.rows.map(r => r[1]))];
      const barValues = periods.map(p => { const r = d.rows.find(x => x[0]===BAR_UID  && x[1]===p); return r ? parseFloat(r[2]) : null; });
      const lineValues= periods.map(p => { const r = d.rows.find(x => x[0]===LINE_UID && x[1]===p); return r ? parseFloat(r[2]) : null; });
      document.getElementById('loading').style.display = 'none';
      const cvs = document.getElementById('chart'); cvs.style.display = 'block';
      new Chart(cvs, {
        data: {
          labels: periods.map(p => periodLabel(d.metaData, p)),
          datasets: [
            { type: 'bar',  label: itemLabel(d.metaData, BAR_UID),  data: barValues,
              backgroundColor: '#1a6fa8cc', yAxisID: 'y' },
            { type: 'line', label: itemLabel(d.metaData, LINE_UID), data: lineValues,
              borderColor: '#e74c3c', backgroundColor: 'transparent',
              tension: 0.3, pointRadius: 4, yAxisID: 'y1' },
          ]
        },
        options: {
          responsive: true,
          plugins: { legend: { position: 'top' } },
          scales: {
            y:  { beginAtZero: true, position: 'left',  title: { display: true, text: itemLabel(d.metaData, BAR_UID) } },
            y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false },
                  title: { display: true, text: itemLabel(d.metaData, LINE_UID) } }
          }
        }
      });
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ─────────────────────────────────────────────────────────────────────────────

_COMBINED_FULL = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <!-- KPI row -->
  <div id="kpi-loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
  <div id="kpi-row" class="row g-3 mb-3" style="display:none"></div>
  <!-- Trend chart -->
  <div class="row g-3">
    <div class="col-md-8">
      <div class="card"><div class="card-body">
        <h6 class="card-title fw-bold">Trend Over Time</h6>
        <div id="chart-loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
        <canvas id="trend-chart" style="display:none; max-height:320px"></canvas>
      </div></div>
    </div>
    <div class="col-md-4">
      <div class="card"><div class="card-body">
        <h6 class="card-title fw-bold">Distribution</h6>
        <div id="dist-loading" class="spinner-wrap"><div class="spinner-border text-primary"></div></div>
        <canvas id="dist-chart" style="display:none; max-height:320px"></canvas>
      </div></div>
    </div>
  </div>
</div>
<script>
""" + _LOADER_JS + """
  const KPI_UIDs   = ['<!-- INDICATOR_UID_1 -->', '<!-- INDICATOR_UID_2 -->'];
  const TREND_UIDs = ['<!-- INDICATOR_UID_1 -->', '<!-- INDICATOR_UID_3 -->'];
  const DIST_UIDs  = ['<!-- INDICATOR_UID_1 -->', '<!-- INDICATOR_UID_2 -->', '<!-- INDICATOR_UID_3 -->'];
  const COLORS     = ['#1a6fa8','#27ae60','#e67e22','#8e44ad'];
  const PE  = '$!{reportingPeriod}' || 'LAST_12_MONTHS';
  const OU  = '$!{organisationUnit}' || 'USER_ORGUNIT';

  const allUIDs = [...new Set([...KPI_UIDs, ...TREND_UIDs, ...DIST_UIDs])];

  (async () => {
    try {
      const [dTrend, dPoint] = await Promise.all([
        dhis2Get(`api/analytics.json?dimension=dx:${allUIDs.join(';')}&dimension=pe:${PE}&dimension=ou:${OU}&displayProperty=NAME`),
        dhis2Get(`api/analytics.json?dimension=dx:${allUIDs.join(';')}&filter=pe:${PE}&filter=ou:${OU}&displayProperty=NAME`),
      ]);

      // KPI cards
      document.getElementById('kpi-loading').style.display = 'none';
      const kpiRow = document.getElementById('kpi-row'); kpiRow.style.display = '';
      KPI_UIDs.forEach((dx, i) => {
        const r = dPoint.rows.find(x => x[0]===dx);
        const v = r ? parseFloat(r[1]).toLocaleString() : 'N/A';
        const div = document.createElement('div'); div.className = 'col';
        div.innerHTML = `<div class="card text-white h-100" style="background:${COLORS[i]}">
          <div class="card-body text-center py-3">
            <div style="font-size:2rem;font-weight:700">${v}</div>
            <div style="font-size:.8rem;opacity:.9">${itemLabel(dTrend.metaData, dx)}</div>
          </div></div>`;
        kpiRow.appendChild(div);
      });

      // Trend
      const periods = [...new Set(dTrend.rows.map(r => r[1]))];
      document.getElementById('chart-loading').style.display = 'none';
      const tCvs = document.getElementById('trend-chart'); tCvs.style.display = 'block';
      new Chart(tCvs, {
        type: 'line',
        data: { labels: periods.map(p => periodLabel(dTrend.metaData, p)),
          datasets: TREND_UIDs.map((dx, i) => ({
            label: itemLabel(dTrend.metaData, dx),
            data:  periods.map(p => { const r = dTrend.rows.find(x => x[0]===dx && x[1]===p); return r ? parseFloat(r[2]) : null; }),
            borderColor: COLORS[i], backgroundColor: COLORS[i]+'22', tension: 0.3, fill: true,
          }))},
        options: { responsive: true, plugins: { legend: { position: 'top' } }, scales: { y: { beginAtZero: true } } }
      });

      // Donut
      document.getElementById('dist-loading').style.display = 'none';
      const dCvs = document.getElementById('dist-chart'); dCvs.style.display = 'block';
      new Chart(dCvs, {
        type: 'doughnut',
        data: { labels: DIST_UIDs.map(dx => itemLabel(dPoint.metaData, dx)),
          datasets: [{ data: DIST_UIDs.map(dx => { const r = dPoint.rows.find(x => x[0]===dx); return r ? parseFloat(r[1]) : 0; }),
            backgroundColor: COLORS, hoverOffset: 8 }]},
        options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
      });
    } catch(e) {
      ['kpi-loading','chart-loading','dist-loading'].forEach(id => showError(id, e.message));
    }
  })();
</script>""" + _FOOT


_LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
_LEAFLET_JS  = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"

_MAP_HEAD = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><!-- REPORT_TITLE --></title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="{leaflet_css}"/>
  <script src="{leaflet_js}"></script>
  <style>
    body {{ background:#f8f9fa; font-family:'Segoe UI',sans-serif; }}
    .report-header {{ background:#1a6fa8;color:#fff;padding:14px 20px;margin-bottom:16px;border-radius:6px; }}
    .report-header h2 {{ margin:0;font-size:1.3rem; }}
    .report-header small {{ opacity:.8;font-size:.82rem; }}
    #map {{ height:520px;width:100%;border-radius:4px; }}
    .legend {{ background:white;padding:10px 14px;border-radius:6px;
               box-shadow:0 1px 5px rgba(0,0,0,.2);line-height:1.6;font-size:12px; }}
    .legend-swatch {{ display:inline-block;width:14px;height:14px;
                      margin-right:6px;vertical-align:middle;border-radius:2px; }}
    .spinner-wrap {{ text-align:center;padding:60px 0; }}
  </style>
</head>
<body class="p-3">""".format(leaflet_css=_LEAFLET_CSS, leaflet_js=_LEAFLET_JS)

_MAP_LOADER_JS = """
  async function dhis2Get(url) {
    const r = await fetch('../' + url, {credentials:'include'});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }"""

# ─────────────────────────────────────────────────────────────────────────────
# MAP AREA — choropleth (polygon boundaries coloured by indicator value)
# ─────────────────────────────────────────────────────────────────────────────

_MAP_AREA = _MAP_HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div class="card"><div class="card-body p-2">
    <div id="loading" class="spinner-wrap">
      <div class="spinner-border text-primary"></div><p class="mt-2 text-muted">Loading map…</p>
    </div>
    <div id="map" style="display:none"></div>
  </div></div>
</div>
<script>
""" + _MAP_LOADER_JS + """
  const DX       = '<!-- INDICATOR_UID -->';
  const PE       = '$!{reportingPeriod}' || 'LAST_YEAR';
  const OU_LEVEL = 2;   // 2 = province, 3 = district

  // YlOrRd-inspired colour scale (low=yellow, high=red)
  function choroplethColor(val, min, max) {
    if (val === undefined || isNaN(val)) return '#d3d3d3';
    const t = Math.max(0, Math.min(1, (val - min) / (max - min || 1)));
    const stops = [
      [255,255,178],[254,217,118],[254,178,76],[253,141,60],
      [240,59,32], [189,0,38]
    ];
    const idx = t * (stops.length - 1);
    const lo = stops[Math.floor(idx)], hi = stops[Math.ceil(idx)];
    const f  = idx - Math.floor(idx);
    return 'rgb(' + lo.map((c,i) => Math.round(c + f*(hi[i]-c))).join(',') + ')';
  }

  (async () => {
    try {
      const [geo, ana] = await Promise.all([
        dhis2Get('api/geoFeatures.json?ou=LEVEL-' + OU_LEVEL + '&displayProperty=NAME'),
        dhis2Get('api/analytics.json?dimension=dx:' + DX +
                 '&dimension=pe:' + PE +
                 '&dimension=ou:LEVEL-' + OU_LEVEL + '&displayProperty=NAME')
      ]);

      // Build value map {ouId -> value}
      const vals = {};
      (ana.rows || []).forEach(r => { vals[r[2]] = parseFloat(r[3]); });
      const allV = Object.values(vals).filter(v => !isNaN(v));
      const minV = Math.min(...allV), maxV = Math.max(...allV);

      // Build GeoJSON from DHIS2 polygon geoFeatures (ty===2)
      const features = geo.filter(f => f.ty === 2 && f.co).map(f => ({
        type: 'Feature',
        geometry: JSON.parse(f.co),
        properties: { id: f.id, name: f.na, value: vals[f.id] }
      }));

      document.getElementById('loading').style.display = 'none';
      const mapDiv = document.getElementById('map');
      mapDiv.style.display = 'block';

      const map = L.map('map');
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        {attribution:'© OpenStreetMap contributors', opacity:0.4}).addTo(map);

      const indicatorName = ana.metaData?.items?.[DX]?.name || DX;

      const layer = L.geoJSON({type:'FeatureCollection', features}, {
        style: f => ({
          fillColor: choroplethColor(f.properties.value, minV, maxV),
          fillOpacity: 0.8, weight: 1, color: '#ffffff'
        }),
        onEachFeature: (f, l) => {
          const v = f.properties.value;
          l.bindTooltip(
            '<b>' + f.properties.name + '</b><br>' +
            (v !== undefined && !isNaN(v) ? v.toLocaleString() : 'N/A'),
            {sticky: true}
          );
          l.on({
            mouseover: e => e.target.setStyle({weight:2, fillOpacity:0.95}),
            mouseout:  e => layer.resetStyle(e.target)
          });
        }
      }).addTo(map);

      if (features.length) map.fitBounds(layer.getBounds(), {padding:[20,20]});

      // Legend
      const legend = L.control({position:'bottomright'});
      legend.onAdd = () => {
        const div = L.DomUtil.create('div','legend');
        div.innerHTML = '<b>' + indicatorName + '</b><br>';
        const steps = 5;
        for (let i = steps; i >= 0; i--) {
          const v = minV + (i/steps)*(maxV-minV);
          div.innerHTML +=
            '<span class="legend-swatch" style="background:' +
            choroplethColor(v,minV,maxV) + '"></span>' +
            Math.round(v).toLocaleString() + '<br>';
        }
        return div;
      };
      legend.addTo(map);

    } catch(e) {
      document.getElementById('loading').innerHTML =
        '<div class="alert alert-danger m-3">Error: ' + e.message + '</div>';
    }
  })();
</script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# MAP POINT — bubble map (circle size ∝ indicator value)
# ─────────────────────────────────────────────────────────────────────────────

_MAP_POINT = _MAP_HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div class="card"><div class="card-body p-2">
    <div id="loading" class="spinner-wrap">
      <div class="spinner-border text-primary"></div><p class="mt-2 text-muted">Loading map…</p>
    </div>
    <div id="map" style="display:none"></div>
  </div></div>
</div>
<script>
""" + _MAP_LOADER_JS + """
  const DX       = '<!-- INDICATOR_UID -->';
  const PE       = '$!{reportingPeriod}' || 'LAST_YEAR';
  const OU_LEVEL = 3;   // 3 = district/facility level recommended for point maps

  const MAX_RADIUS = 30;   // px — largest bubble
  const MIN_RADIUS = 4;

  (async () => {
    try {
      const [geo, ana] = await Promise.all([
        dhis2Get('api/geoFeatures.json?ou=LEVEL-' + OU_LEVEL + '&displayProperty=NAME'),
        dhis2Get('api/analytics.json?dimension=dx:' + DX +
                 '&dimension=pe:' + PE +
                 '&dimension=ou:LEVEL-' + OU_LEVEL + '&displayProperty=NAME')
      ]);

      const vals = {};
      (ana.rows || []).forEach(r => { vals[r[2]] = parseFloat(r[3]); });
      const allV = Object.values(vals).filter(v => !isNaN(v));
      const maxV = Math.max(...allV) || 1;

      // Point features: ty === 1 (Point geometry)
      const points = geo.filter(f => f.ty === 1 && f.co).map(f => {
        const coords = JSON.parse(f.co);   // [lon, lat]
        return { id: f.id, name: f.na, lat: coords[1], lon: coords[0], value: vals[f.id] };
      });

      document.getElementById('loading').style.display = 'none';
      const mapDiv = document.getElementById('map');
      mapDiv.style.display = 'block';

      const map = L.map('map');
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        {attribution:'© OpenStreetMap contributors'}).addTo(map);

      const indicatorName = ana.metaData?.items?.[DX]?.name || DX;
      const bounds = [];

      points.forEach(p => {
        const v = p.value;
        const r = (v && !isNaN(v))
          ? MIN_RADIUS + (v / maxV) * (MAX_RADIUS - MIN_RADIUS)
          : MIN_RADIUS;

        const marker = L.circleMarker([p.lat, p.lon], {
          radius: r,
          fillColor: '#1a6fa8', fillOpacity: 0.75,
          color: '#ffffff', weight: 1
        }).addTo(map);

        marker.bindTooltip(
          '<b>' + p.name + '</b><br>' + indicatorName + ': ' +
          (v !== undefined && !isNaN(v) ? v.toLocaleString() : 'N/A'),
          {sticky: true}
        );
        bounds.push([p.lat, p.lon]);
      });

      if (bounds.length) map.fitBounds(bounds, {padding:[20,20]});
      else map.setView([0,0], 5);

      // Legend (size guide)
      const legend = L.control({position:'bottomright'});
      legend.onAdd = () => {
        const div = L.DomUtil.create('div','legend');
        div.innerHTML = '<b>' + indicatorName + '</b><br>';
        [[maxV, MAX_RADIUS], [maxV/2, (MIN_RADIUS+MAX_RADIUS)/2], [0, MIN_RADIUS]].forEach(([v,r]) => {
          div.innerHTML +=
            '<svg width="' + (r*2+2) + '" height="' + (r*2+2) + '" style="vertical-align:middle;margin-right:4px">' +
            '<circle cx="' + (r+1) + '" cy="' + (r+1) + '" r="' + r +
            '" fill="#1a6fa8" fill-opacity=".7" stroke="white" stroke-width="1"/></svg>' +
            Math.round(v).toLocaleString() + '<br>';
        });
        return div;
      };
      legend.addTo(map);

    } catch(e) {
      document.getElementById('loading').innerHTML =
        '<div class="alert alert-danger m-3">Error: ' + e.message + '</div>';
    }
  })();
</script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# RADAR — spider chart comparing multiple indicators or org units
# ─────────────────────────────────────────────────────────────────────────────

_RADAR = _HEAD + """
<div class="container-fluid">
  <div class="report-header">
    <h2><!-- REPORT_TITLE --></h2>
    <small>Period: $!{reportingPeriod} &nbsp;|&nbsp; Org unit: $!{organisationUnit}</small>
  </div>
  <div class="card"><div class="card-body">
    <div id="loading" class="spinner-wrap">
      <div class="spinner-border text-primary"></div><p class="mt-2">Loading…</p>
    </div>
    <canvas id="chart" style="display:none; max-height:480px"></canvas>
  </div></div>
</div>
<script>
""" + _LOADER_JS + """
  // Multiple indicators compared for a single org unit
  const DX_LIST = [
    '<!-- INDICATOR_UID_1 -->',
    '<!-- INDICATOR_UID_2 -->',
    '<!-- INDICATOR_UID_3 -->',
    '<!-- INDICATOR_UID_4 -->',
    '<!-- INDICATOR_UID_5 -->',
  ];
  const PE = '$!{reportingPeriod}' || 'LAST_YEAR';
  const OU = '$!{organisationUnit}' || 'USER_ORGUNIT';

  const COLORS = [
    { border:'#1a6fa8', bg:'rgba(26,111,168,0.15)' },
    { border:'#27ae60', bg:'rgba(39,174,96,0.15)' },
    { border:'#e67e22', bg:'rgba(230,126,34,0.15)' },
  ];

  (async () => {
    try {
      const d = await dhis2Get(
        'api/analytics.json?dimension=dx:' + DX_LIST.join(';') +
        '&dimension=pe:' + PE + '&dimension=ou:' + OU + '&displayProperty=NAME'
      );

      // One dataset per org unit (for multi-OU comparison) or per period
      // Default: compare indicator values for the selected OU
      const labels = DX_LIST.map(uid => d.metaData?.items?.[uid]?.name || uid);

      // Build values: one value per indicator for the selected OU
      const values = DX_LIST.map(uid => {
        const row = (d.rows || []).find(r => r[0] === uid);
        return row ? parseFloat(row[3]) : 0;
      });

      // Normalise to % of max so all axes are comparable
      const maxV = Math.max(...values, 1);
      const normalised = values.map(v => Math.round((v / maxV) * 100));

      document.getElementById('loading').style.display = 'none';
      const cvs = document.getElementById('chart');
      cvs.style.display = 'block';

      new Chart(cvs, {
        type: 'radar',
        data: {
          labels,
          datasets: [{
            label: d.metaData?.items?.[OU]?.name || 'Values',
            data: normalised,
            borderColor: COLORS[0].border,
            backgroundColor: COLORS[0].bg,
            pointBackgroundColor: COLORS[0].border,
            pointRadius: 4, borderWidth: 2,
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: { position:'top' },
            tooltip: {
              callbacks: {
                label: ctx => {
                  const raw = values[ctx.dataIndex];
                  return ctx.dataset.label + ': ' + (raw !== undefined ? raw.toLocaleString() : 'N/A');
                }
              }
            }
          },
          scales: {
            r: {
              beginAtZero: true, max: 100,
              ticks: { stepSize: 20, callback: v => v + '%' },
              pointLabels: { font: { size: 12 } }
            }
          }
        }
      });
    } catch(e) { showError('loading', e.message); }
  })();
</script>""" + _FOOT

# ── Template registry ─────────────────────────────────────────────────────────

TEMPLATES: list[dict] = [
    # ── Time Series ──────────────────────────────────────────────────────────
    {
        "id": "line_single",
        "category": "time_series",
        "name": "Line — Single Indicator",
        "short": "1 chỉ số theo thời gian",
        "best_for": "Theo dõi xu hướng 1 chỉ số qua các tháng/quý",
        "placeholders": 1,
        "html": _LINE_SINGLE,
    },
    {
        "id": "line_multi",
        "category": "time_series",
        "name": "Line — Multi Indicator",
        "short": "2–5 chỉ số cùng trục thời gian",
        "best_for": "So sánh xu hướng nhiều chỉ số cùng lúc",
        "placeholders": "2-5",
        "html": _LINE_MULTI,
    },
    {
        "id": "bar_monthly",
        "category": "time_series",
        "name": "Bar — Monthly Breakdown",
        "short": "Cột đứng theo tháng",
        "best_for": "Phân tích khối lượng công việc hàng tháng",
        "placeholders": 1,
        "html": _BAR_MONTHLY,
    },
    # ── Comparison ───────────────────────────────────────────────────────────
    {
        "id": "bar_grouped",
        "category": "comparison",
        "name": "Bar — Grouped (Multi Indicator)",
        "short": "Cột nhóm so sánh nhiều chỉ số",
        "best_for": "So sánh 2–4 chỉ số qua các kỳ",
        "placeholders": "2-4",
        "html": _BAR_GROUPED,
    },
    {
        "id": "bar_stacked",
        "category": "comparison",
        "name": "Bar — Stacked",
        "short": "Cột xếp chồng thành phần",
        "best_for": "Xem cơ cấu từng thành phần qua thời gian",
        "placeholders": "2-5",
        "html": _BAR_STACKED,
    },
    {
        "id": "bar_horizontal_ou",
        "category": "comparison",
        "name": "Bar Horizontal — By Org Unit",
        "short": "Cột ngang xếp hạng theo đơn vị",
        "best_for": "Xếp hạng tỉnh/huyện theo 1 chỉ số",
        "placeholders": 1,
        "html": _BAR_HORIZONTAL_OU,
    },
    # ── Proportion ───────────────────────────────────────────────────────────
    {
        "id": "pie",
        "category": "proportion",
        "name": "Pie Chart",
        "short": "Biểu đồ tròn tỷ lệ",
        "best_for": "Phân bổ tỷ lệ giữa các thành phần",
        "placeholders": "2-6",
        "html": _PIE,
    },
    {
        "id": "donut",
        "category": "proportion",
        "name": "Donut Chart + Total",
        "short": "Donut với tổng ở giữa",
        "best_for": "Tỷ lệ thành phần + hiển thị tổng số",
        "placeholders": "2-5",
        "html": _DONUT,
    },
    # ── Scorecard / KPI ──────────────────────────────────────────────────────
    {
        "id": "scorecard",
        "category": "scorecard",
        "name": "KPI Scorecard Cards",
        "short": "Thẻ số lớn cho từng chỉ số",
        "best_for": "Dashboard tổng quan với số liệu nổi bật",
        "placeholders": "2-6",
        "html": _SCORECARD,
    },
    {
        "id": "traffic_light",
        "category": "scorecard",
        "name": "Traffic Light Table",
        "short": "Bảng đèn xanh-vàng-đỏ vs target",
        "best_for": "Đánh giá tiến độ so với mục tiêu",
        "placeholders": "2-8",
        "html": _TRAFFIC_LIGHT,
    },
    # ── Table ────────────────────────────────────────────────────────────────
    {
        "id": "data_table",
        "category": "table",
        "name": "Data Table — Org Unit × Indicator",
        "short": "Bảng đơn vị × chỉ số có tổng cộng",
        "best_for": "Báo cáo chi tiết tất cả đơn vị + tổng",
        "placeholders": "2-5",
        "html": _DATA_TABLE,
    },
    # ── Combined ─────────────────────────────────────────────────────────────
    {
        "id": "combined_bar_line",
        "category": "combined",
        "name": "Bar + Line (Dual Axis)",
        "short": "Cột (số lượng) + Đường (tỷ lệ) 2 trục",
        "best_for": "Ca bệnh + tỷ lệ dương tính trên cùng chart",
        "placeholders": 2,
        "html": _COMBINED_BAR_LINE,
    },
    {
        "id": "combined_full",
        "category": "combined",
        "name": "Full Dashboard (KPI + Trend + Donut)",
        "short": "KPI cards + line chart + donut cùng trang",
        "best_for": "Báo cáo tổng hợp đầy đủ 1 trang",
        "placeholders": "3-5",
        "html": _COMBINED_FULL,
    },
    # ── Map ──────────────────────────────────────────────────────────────────
    {
        "id": "map_area",
        "category": "map",
        "name": "Map — Area (Choropleth)",
        "short": "Bản đồ màu theo giá trị chỉ số",
        "best_for": "So sánh tỉnh/huyện trên bản đồ (polygon)",
        "placeholders": 1,
        "html": _MAP_AREA,
    },
    {
        "id": "map_point",
        "category": "map",
        "name": "Map — Bubble Point",
        "short": "Bản đồ bong bóng kích thước theo giá trị",
        "best_for": "Hiển thị cơ sở y tế / điểm dữ liệu theo địa lý",
        "placeholders": 1,
        "html": _MAP_POINT,
    },
    # ── Advanced ─────────────────────────────────────────────────────────────
    {
        "id": "radar",
        "category": "advanced",
        "name": "Radar / Spider Chart",
        "short": "Mạng nhện so sánh nhiều chỉ số",
        "best_for": "So sánh profile giữa các đơn vị hoặc nhiều chỉ số cùng lúc",
        "placeholders": "3-8",
        "html": _RADAR,
    },
]


def get_by_id(template_id: str) -> dict | None:
    return next((t for t in TEMPLATES if t["id"] == template_id), None)


def get_by_category(category_id: str) -> list[dict]:
    return [t for t in TEMPLATES if t["category"] == category_id]


def category_info(category_id: str) -> dict | None:
    return next((c for c in CATEGORIES if c["id"] == category_id), None)
