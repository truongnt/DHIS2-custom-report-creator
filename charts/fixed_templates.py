"""
Fixed chart templates for the new viz-builder flow.
Generates JS-based HTML cards that call DHIS2 API at runtime.

de_type values:
  tracker_option  — tracker DE with option set (Case B)
  tracker_numeric — tracker DE without option set (Case C: aggregationType=SUM)
  aggregate       — aggregate data element (/api/analytics.json)
  indicator       — indicator (/api/analytics.json, same as aggregate)
"""
from __future__ import annotations
import html as _html
from pathlib import Path

# ── Plugin imports (optional — falls back gracefully if plugins not yet available) ─

try:
    from charts.plugins import get_plugin, all_plugins, PLUGIN_REGISTRY
    from charts.plugins.base import migrate_old_config, ChartPlugin
    _PLUGINS_AVAILABLE = True
except Exception:
    _PLUGINS_AVAILABLE = False
    get_plugin = None
    all_plugins = None
    PLUGIN_REGISTRY = {}
    migrate_old_config = None
    ChartPlugin = None

# ── Template catalog ──────────────────────────────────────────────────────────

_FIXED_TEMPLATES_HARDCODED = [
    # ── Single-DE templates ────────────────────────────────────────────────────
    {
        "id": "ft_bar_monthly",
        "label": "Bar — monthly trend",
        "preview_id": "bar_monthly",   # maps to preview_canvas drawer
        "icon": "📊",
        "for_types": {"tracker_option", "tracker_numeric", "aggregate", "indicator"},
        "description": "Monthly bar chart — stacked by category for option-set DEs, simple bars for numeric/aggregate",
    },
    {
        "id": "ft_line_trend",
        "label": "Line — trend over time",
        "preview_id": "line_single",
        "icon": "📈",
        "for_types": {"tracker_numeric", "aggregate", "indicator"},
        "description": "Line chart tracking values month by month",
    },
    {
        "id": "ft_stacked_cat",
        "label": "Stacked bar — by category",
        "preview_id": "bar_stacked",
        "icon": "📋",
        "for_types": {"tracker_option"},
        "description": "Monthly stacked bars — each category is a color segment",
    },
    {
        "id": "ft_pie_cat",
        "label": "Pie — by category",
        "preview_id": "pie",
        "icon": "🥧",
        "for_types": {"tracker_option"},
        "description": "Pie chart: breakdown by option-set category for the selected period",
    },
    {
        "id": "ft_bar_ou",
        "label": "Bar — by org unit",
        "preview_id": "bar_horizontal_ou",
        "icon": "🏥",
        "for_types": {"tracker_option", "tracker_numeric", "aggregate", "indicator"},
        "description": "Horizontal bar comparing values across org units",
    },
    {
        "id": "ft_scorecard",
        "label": "Scorecard",
        "preview_id": "scorecard",
        "icon": "🎯",
        "for_types": {"aggregate", "indicator", "tracker_numeric"},
        "description": "Single KPI value with period label",
        "multi": False,
    },
    # ── Multi-DE templates (2–3 sources) ──────────────────────────────────────
    {
        "id": "ft_line_multi",
        "label": "Line — compare multiple sources",
        "preview_id": "line_multi",
        "icon": "📈",
        "for_types": {"tracker_numeric", "aggregate", "indicator"},
        "description": "Line chart with one series per selected data element",
        "multi": True,
        "min_sources": 2,
    },
    {
        "id": "ft_grouped_bar",
        "label": "Grouped bar — compare sources",
        "preview_id": "bar_grouped",
        "icon": "📊",
        "for_types": {"tracker_numeric", "aggregate", "indicator"},
        "description": "Side-by-side bars per period, one group per data element",
        "multi": True,
        "min_sources": 2,
    },
    {
        "id": "ft_combined_bar_line",
        "label": "Combined bar + line",
        "preview_id": "combined_bar_line",
        "icon": "🔀",
        "for_types": {"tracker_numeric", "aggregate", "indicator"},
        "description": "First DE as bars, second DE as line overlay",
        "multi": True,
        "min_sources": 2,
        "max_sources": 2,
    },
]

try:
    FIXED_TEMPLATES = [p.as_template_dict() for p in all_plugins()]
except Exception:
    FIXED_TEMPLATES = _FIXED_TEMPLATES_HARDCODED


def get_compatible(de_type: str) -> list[dict]:
    """Single-DE templates compatible with the given DE type."""
    return [t for t in FIXED_TEMPLATES
            if de_type in t["for_types"] and not t.get("multi")]


def get_compatible_multi(de_types: list[str], count: int) -> list[dict]:
    """Multi-DE templates where ALL selected DE types are supported."""
    result = []
    for t in FIXED_TEMPLATES:
        if not t.get("multi"):
            continue
        if count < t.get("min_sources", 2):
            continue
        if count > t.get("max_sources", 3):
            continue
        if all(dt in t["for_types"] for dt in de_types):
            result.append(t)
    return result


# ── Shared script (inserted once at bottom of full page) ─────────────────────

_SHARED_SCRIPT = """\
  const PREVIEW = window.location.protocol === 'file:' || window.location.hostname === 'localhost';

  // Disable datalabels plugin globally by default
  if (window.ChartDataLabels) {
    Chart.defaults.plugins.datalabels = { display: false };
  }

  // Built-in value-label plugin — works with inst.update() after custom_options injection
  Chart.register({
    id: 'showValues',
    afterDatasetsDraw: function(chart) {
      var opts = chart.options && chart.options.plugins && chart.options.plugins.showValues;
      if (!opts || !opts.display) return;
      var ctx = chart.ctx;
      var fontSize = opts.fontSize || 11;
      var color = opts.color || '#333';
      var type = chart.config.type;
      if (type === 'pie' || type === 'doughnut') return;
      chart.data.datasets.forEach(function(dataset, i) {
        var meta = chart.getDatasetMeta(i);
        if (!meta.visible) return;
        meta.data.forEach(function(element, idx) {
          var value = dataset.data[idx];
          if (value === null || value === undefined || value === 0) return;
          ctx.save();
          ctx.font = 'bold ' + fontSize + 'px sans-serif';
          ctx.fillStyle = color;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'bottom';
          var label = (typeof value === 'number') ? value.toLocaleString() : String(value);
          ctx.fillText(label, element.x, element.y - 3);
          ctx.restore();
        });
      });
    }
  });

  async function dhis2Get(path) {
    const r = await fetch('../' + path, {credentials:'include'});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  function resolveRelativePeriod(pe) {
    const now = new Date(), y = now.getFullYear(), m = now.getMonth()+1;
    const pad = n => String(n).padStart(2,'0');
    const pm = i => { let mo=m-i,yr=y; while(mo<=0){mo+=12;yr--;} return yr+pad(mo); };
    const q = Math.ceil(m/3);
    switch(pe) {
      case 'LAST_MONTH':     return pm(1);
      case 'LAST_3_MONTHS':  return [1,2,3].map(pm).join(';');
      case 'LAST_6_MONTHS':  return [1,2,3,4,5,6].map(pm).join(';');
      case 'LAST_12_MONTHS': return [1,2,3,4,5,6,7,8,9,10,11,12].map(pm).join(';');
      case 'THIS_QUARTER':   return y+'Q'+q;
      case 'LAST_QUARTER':   { let lq=q-1,yr=y; if(lq<=0){lq=4;yr--;} return yr+'Q'+lq; }
      case 'THIS_YEAR':      return String(y);
      case 'LAST_YEAR':      return String(y-1);
      default: return pe;
    }
  }

  async function loadOrgUnits() {
    const sel = document.getElementById('ouSelect');
    sel.innerHTML = '';
    const sg = document.createElement('optgroup'); sg.label='User organisation unit';
    [['User organisation unit','USER_ORGUNIT'],['User sub-units','USER_ORGUNIT_CHILDREN'],
     ['User sub-x2-units','USER_ORGUNIT_GRANDCHILDREN']].forEach(([l,v])=>sg.appendChild(new Option(l,v)));
    sel.appendChild(sg); sel.value='USER_ORGUNIT';
    try {
      const me = await dhis2Get('api/me.json?fields=organisationUnits[id,displayName,level]');
      const ous = (me.organisationUnits||[]).sort((a,b)=>a.displayName.localeCompare(b.displayName));
      if (ous.length) {
        const mg=document.createElement('optgroup'); mg.label='Org units';
        ous.forEach(o=>mg.appendChild(new Option(o.displayName,o.id)));
        sel.appendChild(mg);
      }
    } catch(e) { console.error('[OU]',e); }
  }

  function generatePeriods() {
    const sel = document.getElementById('peSelect');
    sel.innerHTML='';
    const rel=document.createElement('optgroup'); rel.label='Relative';
    [['Last month','LAST_MONTH'],['Last 3 months','LAST_3_MONTHS'],['Last 6 months','LAST_6_MONTHS'],
     ['Last 12 months','LAST_12_MONTHS'],['This quarter','THIS_QUARTER'],['Last quarter','LAST_QUARTER'],
     ['This year','THIS_YEAR'],['Last year','LAST_YEAR']].forEach(([l,v])=>rel.appendChild(new Option(l,v)));
    sel.appendChild(rel);
    const now=new Date(),y=now.getFullYear(),m=now.getMonth()+1;
    const mf=document.createElement('optgroup'); mf.label='Monthly';
    for(let i=0;i<12;i++){let mo=m-i,yr=y;if(mo<=0){mo+=12;yr--;}mf.appendChild(new Option('Month '+mo+'/'+yr,yr+String(mo).padStart(2,'0')));}
    sel.appendChild(mf);
    const qf=document.createElement('optgroup'); qf.label='Quarterly';
    for(let i=0;i<8;i++){let q=Math.ceil(m/3)-i,yr=y;if(q<=0){q+=4;yr--;}qf.appendChild(new Option('Q'+q+' '+yr,yr+'Q'+q));}
    sel.appendChild(qf);
    const yf=document.createElement('optgroup'); yf.label='Yearly';
    for(let yr=y;yr>=y-4;yr--)yf.appendChild(new Option(String(yr),String(yr)));
    sel.appendChild(yf);
    sel.value='LAST_12_MONTHS';
  }

  function formatPeriodLabel(pe) {
    const mm=pe.match(/^(\\d{4})(\\d{2})$/);
    if(mm){const M=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];return M[parseInt(mm[2],10)-1]+' '+mm[1];}
    const qm=pe.match(/^(\\d{4})Q(\\d)$/);
    if(qm) return 'Q'+qm[2]+' '+qm[1];
    return pe;
  }

  const PALETTE=['#e74c3c','#3498db','#f39c12','#27ae60','#9b59b6','#1abc9c','#e67e22','#2980b9','#8e44ad','#16a085'];

  async function loadData() {
    const ou=document.getElementById('ouSelect').value;
    const pe=document.getElementById('peSelect').value;
    const btn=document.getElementById('loadBtn');
    btn.disabled=true; btn.textContent='⏳ Loading...';
    try {
      await Promise.all([__INIT_CALLS__]);
      document.getElementById('lastUpdated').textContent='Updated: '+new Date().toLocaleTimeString();
    } finally { btn.disabled=false; btn.textContent='↻ Load data'; }
  }

  document.addEventListener('DOMContentLoaded', async ()=>{
    generatePeriods();
    if (PREVIEW) {
      const sel=document.getElementById('ouSelect');
      [['User organisation unit','USER_ORGUNIT'],['User sub-units','USER_ORGUNIT_CHILDREN'],
       ['User sub-x2-units','USER_ORGUNIT_GRANDCHILDREN']].forEach(([l,v])=>sel.appendChild(new Option(l,v)));
      sel.value='USER_ORGUNIT';
      await loadData();
      return;
    }
    try { await loadOrgUnits(); await loadData(); } catch(e) { console.error('Init error:',e); }
  });
"""

_PAGE_SHELL = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
  <style>
    body{{background:#f0f4f8;}}
    .demo-banner{{background:#fff3cd;color:#856404;border:1px solid #ffc107;border-radius:4px;
      padding:3px 10px;font-size:11px;margin-bottom:6px;text-align:center;display:none;}}
    .card-header{{background:{header_color};color:#fff;padding:8px 14px;}}
    .card-header h6{{margin:0;font-size:13px;font-weight:600;}}
  </style>
</head>
<body>
  <div id="controls" style="background:#f0f4f8;border-bottom:1px solid #d0dde8;padding:10px 20px;
    display:flex;gap:12px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:100;">
    <label style="font-weight:600;margin:0;font-size:13px">Org unit:</label>
    <select id="ouSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
    <label style="font-weight:600;margin:0;font-size:13px">Period:</label>
    <select id="peSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
    <button id="loadBtn" onclick="loadData()" style="padding:5px 16px;background:#1a6fa8;color:#fff;
      border:none;border-radius:4px;cursor:pointer;font-size:13px">↻ Load data</button>
    <span id="lastUpdated" style="font-size:11px;color:#6c757d;margin-left:8px"></span>
  </div>
  <div class="container-fluid px-3 py-3">
    <div class="row">
{cards}
    </div>
  </div>
  <script>
{shared}
  </script>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

_CARD_SHELL = """\
      <!-- CARD-START:{card_id} -->
      <div class="col-md-{col_width} mb-4">
        <div class="card h-100 shadow-sm">
          <div class="card-header"><h6>{title}</h6></div>
          <div class="card-body" style="position:relative;min-height:260px;padding:12px;">
            <div id="demoBanner{n}" class="demo-banner">⚠ Sample data — preview mode</div>
            <div id="loading{n}" class="d-flex align-items-center justify-content-center" style="min-height:220px;">
              <div class="spinner-border text-primary" role="status"></div>
            </div>
            <div id="error{n}" style="display:none;background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;
              border-radius:4px;padding:10px;font-size:13px;margin-top:8px;"></div>
            <canvas id="chart{n}" style="display:none;"></canvas>
          </div>
        </div>
      </div>
      <script>
{per_card_js}
      </script>
      <!-- CARD-END:{card_id} -->
"""

# ── JS generators per (template_id, de_type) ─────────────────────────────────

def _sample_js_bar_monthly(n: int) -> str:
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{
              labels: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
              datasets: [{{label:'Cases', data:[120,145,98,167,134,189,210,156,143,178,192,165], backgroundColor:'#3498db'}}]
            }},
            options: {{ responsive:true, plugins:{{legend:{{display:false}}}}, scales:{{y:{{beginAtZero:true}}}} }}
          }});
        }}"""

def _sample_js_stacked(n: int) -> str:
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{
              labels: ['Jan','Feb','Mar','Apr','May','Jun'],
              datasets: [
                {{label:'Positive', data:[40,52,38,61,49,70], backgroundColor:'#e74c3c'}},
                {{label:'Negative', data:[35,42,31,54,43,62], backgroundColor:'#3498db'}},
                {{label:'Pending',  data:[25,31,19,32,22,37], backgroundColor:'#f39c12'}}
              ]
            }},
            options: {{ responsive:true, plugins:{{legend:{{position:'bottom'}}}},
              scales:{{x:{{stacked:true}},y:{{stacked:true,beginAtZero:true}}}} }}
          }});
        }}"""

def _sample_js_line(n: int) -> str:
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'line',
            data: {{
              labels: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
              datasets: [{{label:'Value', data:[120,145,98,167,134,189,210,156,143,178,192,165],
                borderColor:'#e74c3c', backgroundColor:'rgba(231,76,60,0.1)', fill:true, tension:0.3}}]
            }},
            options: {{ responsive:true, plugins:{{legend:{{display:false}}}}, scales:{{y:{{beginAtZero:true}}}} }}
          }});
        }}"""

def _sample_js_bar_ou(n: int) -> str:
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{
              labels: ['Province A','Province B','Province C','Province D','Province E'],
              datasets: [{{label:'Value', data:[85,102,67,143,91], backgroundColor:'#27ae60'}}]
            }},
            options: {{ indexAxis:'y', responsive:true, plugins:{{legend:{{display:false}}}},
              scales:{{x:{{beginAtZero:true}}}} }}
          }});
        }}"""

def _sample_js_pie(n: int) -> str:
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'pie',
            data: {{
              labels: ['Positive','Negative','Pending','Other'],
              datasets: [{{data:[45,30,15,10], backgroundColor:['#e74c3c','#3498db','#f39c12','#27ae60']}}]
            }},
            options: {{ responsive:true, plugins:{{legend:{{position:'bottom'}}}} }}
          }});
        }}"""

def _sample_js_scorecard(n: int, title: str) -> str:
    safe_title = title.replace("'", "\\'")
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'doughnut',
            data: {{ labels:['Value','Remaining'], datasets:[{{data:[78,22], backgroundColor:['#27ae60','#ecf0f1'], borderWidth:0}}] }},
            options: {{ cutout:'75%', responsive:true, plugins:{{legend:{{display:false}},
              tooltip:{{enabled:false}},
              datalabels:{{display:false}}}} }}
          }});
          const ctx=cvs.getContext('2d');
          // center text drawn after chart
          setTimeout(()=>{{
            const cx=cvs.width/2,cy=cvs.height/2;
            ctx.font='bold 28px sans-serif'; ctx.fillStyle='#27ae60'; ctx.textAlign='center';
            ctx.fillText('1,234',cx,cy+10);
          }},100);
        }}"""


# ── Real-data JS per (template_id, de_type) ───────────────────────────────────

def _real_js_tracker_option_bar(n: int, c: dict, stacked: bool = False) -> str:
    prog, stg, de = c["prog_uid"], c["stage_uid"], c["de_uid"]
    stack_opt = "stacked:true," if stacked else ""
    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const PALETTE=['#e74c3c','#3498db','#f39c12','#27ae60','#9b59b6','#1abc9c','#e67e22','#2980b9'];
          const peIdx=d.headers.findIndex(h=>h.name==='pe');
          const catIdx=d.headers.findIndex(h=>h.name==='{de}');
          const valIdx=d.headers.findIndex(h=>h.name==='value');
          const periods=[...new Set(d.rows.map(r=>r[peIdx]))].sort();
          const categories=[...new Set(d.rows.map(r=>r[catIdx]))];
          const grouped={{}};
          d.rows.forEach(r=>{{
            const cat=r[catIdx],pe=r[peIdx],val=parseFloat(r[valIdx])||0;
            if(!grouped[cat])grouped[cat]={{}};
            grouped[cat][pe]=(grouped[cat][pe]||0)+val;
          }});
          const datasets=categories.map((cat,i)=>{{
            const label=d.metaData?.items?.[cat]?.name||cat;
            return {{label,data:periods.map(p=>grouped[cat]?.[p]||0),
              backgroundColor:PALETTE[i%PALETTE.length],borderWidth:1}};
          }});
          chart{n}Inst=new Chart(cvs.getContext('2d'),{{
            type:'bar',
            data:{{labels:periods.map(formatPeriodLabel),datasets}},
            options:{{responsive:true,plugins:{{legend:{{position:'bottom'}}}},
              scales:{{x:{{{stack_opt}ticks:{{maxRotation:45}}}},y:{{{stack_opt}beginAtZero:true}}}}}}
          }});
        }}
        async function initChart{n}(ou,pe) {{
          document.getElementById('loading{n}').style.display='none';
          const cvs=document.getElementById('chart{n}'); cvs.style.display='block';
          if(PREVIEW){{document.getElementById('demoBanner{n}').style.display='block';renderChart{n}Sample(cvs);return;}}
          document.getElementById('demoBanner{n}').style.display='none';
          try {{
            const rpe=resolveRelativePeriod(pe);
            const d=await dhis2Get('api/analytics/events/aggregate/{prog}?stage={stg}&dimension={stg}.{de}&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou));
            if(!d.rows||!d.rows.length){{document.getElementById('error{n}').textContent='No data for the selected period / org unit.';document.getElementById('error{n}').style.display='block';return;}}
            renderChart{n}Real(cvs,d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);
            document.getElementById('error{n}').textContent='Failed to load: '+e.message;
            document.getElementById('error{n}').style.display='block';
          }}
        }}"""

def _real_js_tracker_option_pie(n: int, c: dict) -> str:
    prog, stg, de = c["prog_uid"], c["stage_uid"], c["de_uid"]
    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const PALETTE=['#e74c3c','#3498db','#f39c12','#27ae60','#9b59b6','#1abc9c'];
          const catIdx=d.headers.findIndex(h=>h.name==='{de}');
          const valIdx=d.headers.findIndex(h=>h.name==='value');
          const totals={{}};
          d.rows.forEach(r=>{{totals[r[catIdx]]=(totals[r[catIdx]]||0)+(parseFloat(r[valIdx])||0);}});
          const cats=Object.keys(totals);
          chart{n}Inst=new Chart(cvs.getContext('2d'),{{
            type:'pie',
            data:{{
              labels:cats.map(c=>d.metaData?.items?.[c]?.name||c),
              datasets:[{{data:cats.map(c=>totals[c]),backgroundColor:PALETTE.slice(0,cats.length)}}]
            }},
            options:{{responsive:true,plugins:{{legend:{{position:'bottom'}}}}}}
          }});
        }}
        async function initChart{n}(ou,pe) {{
          document.getElementById('loading{n}').style.display='none';
          const cvs=document.getElementById('chart{n}'); cvs.style.display='block';
          if(PREVIEW){{document.getElementById('demoBanner{n}').style.display='block';renderChart{n}Sample(cvs);return;}}
          document.getElementById('demoBanner{n}').style.display='none';
          try {{
            const rpe=resolveRelativePeriod(pe);
            const d=await dhis2Get('api/analytics/events/aggregate/{prog}?stage={stg}&dimension={stg}.{de}&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou));
            if(!d.rows||!d.rows.length){{document.getElementById('error{n}').textContent='No data.';document.getElementById('error{n}').style.display='block';return;}}
            renderChart{n}Real(cvs,d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);
            document.getElementById('error{n}').textContent='Failed to load: '+e.message;
            document.getElementById('error{n}').style.display='block';
          }}
        }}"""

def _real_js_tracker_numeric(n: int, c: dict, chart_js_type: str, line_opts: str = "") -> str:
    prog, stg, de = c["prog_uid"], c["stage_uid"], c["de_uid"]
    bar_opts = "" if chart_js_type == "line" else "scales:{y:{beginAtZero:true}}"
    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const peIdx=d.headers.findIndex(h=>h.name==='pe');
          const valIdx=d.headers.findIndex(h=>h.name==='value');
          const periods=[...new Set(d.rows.map(r=>r[peIdx]))].sort();
          const vals=periods.map(p=>{{const row=d.rows.find(r=>r[peIdx]===p);return row?parseFloat(row[valIdx])||0:0;}});
          chart{n}Inst=new Chart(cvs.getContext('2d'),{{
            type:'{chart_js_type}',
            data:{{
              labels:periods.map(formatPeriodLabel),
              datasets:[{{label:'Value',data:vals,backgroundColor:'#3498db',borderColor:'#3498db',
                fill:{str(chart_js_type == "line").lower()},tension:0.3}}]
            }},
            options:{{responsive:true,plugins:{{legend:{{display:false}}}},{bar_opts}}}
          }});
        }}
        async function initChart{n}(ou,pe) {{
          document.getElementById('loading{n}').style.display='none';
          const cvs=document.getElementById('chart{n}'); cvs.style.display='block';
          if(PREVIEW){{document.getElementById('demoBanner{n}').style.display='block';renderChart{n}Sample(cvs);return;}}
          document.getElementById('demoBanner{n}').style.display='none';
          try {{
            const rpe=resolveRelativePeriod(pe);
            const d=await dhis2Get('api/analytics/events/aggregate/{prog}?stage={stg}&value={de}&aggregationType=SUM&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou));
            if(!d.rows||!d.rows.length){{document.getElementById('error{n}').textContent='No data.';document.getElementById('error{n}').style.display='block';return;}}
            renderChart{n}Real(cvs,d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);
            document.getElementById('error{n}').textContent='Failed to load: '+e.message;
            document.getElementById('error{n}').style.display='block';
          }}
        }}"""

def _real_js_aggregate(n: int, c: dict, chart_js_type: str, index_axis: str = "") -> str:
    de = c["de_uid"]
    ia = f"indexAxis:'y'," if index_axis == "y" else ""
    scale_opts = "x:{beginAtZero:true}" if index_axis == "y" else "y:{beginAtZero:true}"
    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const peIdx=d.headers.findIndex(h=>h.name==='pe');
          const ouIdx=d.headers.findIndex(h=>h.name==='ou');
          const valIdx=d.headers.findIndex(h=>h.name==='value');
          let labels,vals;
          if ('{index_axis}'==='y') {{
            const ouMap={{}};
            d.rows.forEach(r=>{{const name=d.metaData?.items?.[r[ouIdx]]?.name||r[ouIdx];ouMap[name]=(ouMap[name]||0)+(parseFloat(r[valIdx])||0);}});
            labels=Object.keys(ouMap); vals=Object.values(ouMap);
          }} else {{
            const periods=[...new Set(d.rows.map(r=>r[peIdx]))].sort();
            labels=periods.map(formatPeriodLabel);
            vals=periods.map(p=>{{const row=d.rows.find(r=>r[peIdx]===p);return row?parseFloat(row[valIdx])||0:0;}});
          }}
          chart{n}Inst=new Chart(cvs.getContext('2d'),{{
            type:'{chart_js_type}',
            data:{{labels,datasets:[{{label:'Value',data:vals,backgroundColor:'#3498db',borderColor:'#3498db',
              fill:{str(chart_js_type=="line").lower()},tension:0.3}}]}},
            options:{{responsive:true,{ia}plugins:{{legend:{{display:false}}}},scales:{{{scale_opts}}}}}
          }});
        }}
        async function initChart{n}(ou,pe) {{
          document.getElementById('loading{n}').style.display='none';
          const cvs=document.getElementById('chart{n}'); cvs.style.display='block';
          if(PREVIEW){{document.getElementById('demoBanner{n}').style.display='block';renderChart{n}Sample(cvs);return;}}
          document.getElementById('demoBanner{n}').style.display='none';
          try {{
            const d=await dhis2Get('api/analytics.json?dimension=dx:{de}&dimension=pe:'+encodeURIComponent(pe)+'&dimension=ou:'+encodeURIComponent(ou)+'&displayProperty=NAME');
            if(!d.rows||!d.rows.length){{document.getElementById('error{n}').textContent='No data.';document.getElementById('error{n}').style.display='block';return;}}
            renderChart{n}Real(cvs,d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);
            document.getElementById('error{n}').textContent='Failed to load: '+e.message;
            document.getElementById('error{n}').style.display='block';
          }}
        }}"""

def _real_js_scorecard_aggregate(n: int, c: dict) -> str:
    de = c["de_uid"]
    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const valIdx=d.headers.findIndex(h=>h.name==='value');
          const val=d.rows.length?parseFloat(d.rows[0][valIdx]):null;
          const ctx=cvs.getContext('2d');
          cvs.width=cvs.parentElement.clientWidth||200;
          cvs.height=180;
          ctx.clearRect(0,0,cvs.width,cvs.height);
          ctx.font='bold 36px sans-serif'; ctx.fillStyle='#27ae60'; ctx.textAlign='center';
          ctx.fillText(val!==null?val.toLocaleString():'—',cvs.width/2,90);
          ctx.font='13px sans-serif'; ctx.fillStyle='#555';
          ctx.fillText('Value',cvs.width/2,120);
        }}
        async function initChart{n}(ou,pe) {{
          document.getElementById('loading{n}').style.display='none';
          const cvs=document.getElementById('chart{n}'); cvs.style.display='block';
          if(PREVIEW){{document.getElementById('demoBanner{n}').style.display='block';renderChart{n}Sample(cvs);return;}}
          document.getElementById('demoBanner{n}').style.display='none';
          try {{
            const d=await dhis2Get('api/analytics.json?dimension=dx:{de}&dimension=pe:'+encodeURIComponent(pe)+'&dimension=ou:'+encodeURIComponent(ou));
            if(!d.rows||!d.rows.length){{document.getElementById('error{n}').textContent='No data.';document.getElementById('error{n}').style.display='block';return;}}
            renderChart{n}Real(cvs,d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);
            document.getElementById('error{n}').textContent='Failed to load: '+e.message;
            document.getElementById('error{n}').style.display='block';
          }}
        }}"""


def _real_js_tracker_numeric_ou(n: int, c: dict) -> str:
    prog, stg, de = c["prog_uid"], c["stage_uid"], c["de_uid"]
    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const ouIdx=d.headers.findIndex(h=>h.name==='ou');
          const valIdx=d.headers.findIndex(h=>h.name==='value');
          const ouMap={{}};
          d.rows.forEach(r=>{{const name=d.metaData?.items?.[r[ouIdx]]?.name||r[ouIdx];ouMap[name]=(ouMap[name]||0)+(parseFloat(r[valIdx])||0);}});
          const labels=Object.keys(ouMap); const vals=Object.values(ouMap);
          chart{n}Inst=new Chart(cvs.getContext('2d'),{{
            type:'bar',
            data:{{labels,datasets:[{{label:'Value',data:vals,backgroundColor:'#27ae60'}}]}},
            options:{{indexAxis:'y',responsive:true,plugins:{{legend:{{display:false}}}},scales:{{x:{{beginAtZero:true}}}}}}
          }});
        }}
        async function initChart{n}(ou,pe) {{
          document.getElementById('loading{n}').style.display='none';
          const cvs=document.getElementById('chart{n}'); cvs.style.display='block';
          if(PREVIEW){{document.getElementById('demoBanner{n}').style.display='block';renderChart{n}Sample(cvs);return;}}
          document.getElementById('demoBanner{n}').style.display='none';
          try {{
            const rpe=resolveRelativePeriod(pe);
            const d=await dhis2Get('api/analytics/events/aggregate/{prog}?stage={stg}&value={de}&aggregationType=SUM&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:USER_ORGUNIT_CHILDREN');
            if(!d.rows||!d.rows.length){{document.getElementById('error{n}').textContent='No data.';document.getElementById('error{n}').style.display='block';return;}}
            renderChart{n}Real(cvs,d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);
            document.getElementById('error{n}').textContent='Failed to load: '+e.message;
            document.getElementById('error{n}').style.display='block';
          }}
        }}"""

def _real_js_tracker_option_ou(n: int, c: dict) -> str:
    prog, stg, de = c["prog_uid"], c["stage_uid"], c["de_uid"]
    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const PALETTE=['#e74c3c','#3498db','#f39c12','#27ae60','#9b59b6','#1abc9c'];
          const ouIdx=d.headers.findIndex(h=>h.name==='ou');
          const catIdx=d.headers.findIndex(h=>h.name==='{de}');
          const valIdx=d.headers.findIndex(h=>h.name==='value');
          const ous=[...new Set(d.rows.map(r=>d.metaData?.items?.[r[ouIdx]]?.name||r[ouIdx]))];
          const cats=[...new Set(d.rows.map(r=>r[catIdx]))];
          const grouped={{}};
          d.rows.forEach(r=>{{
            const ou=d.metaData?.items?.[r[ouIdx]]?.name||r[ouIdx];
            const cat=r[catIdx];
            if(!grouped[cat])grouped[cat]={{}};
            grouped[cat][ou]=(grouped[cat][ou]||0)+(parseFloat(r[valIdx])||0);
          }});
          const datasets=cats.map((cat,i)=>{{
            return {{label:d.metaData?.items?.[cat]?.name||cat,
              data:ous.map(o=>grouped[cat]?.[o]||0),
              backgroundColor:PALETTE[i%PALETTE.length]}};
          }});
          chart{n}Inst=new Chart(cvs.getContext('2d'),{{
            type:'bar',
            data:{{labels:ous,datasets}},
            options:{{indexAxis:'y',responsive:true,plugins:{{legend:{{position:'bottom'}}}},
              scales:{{x:{{stacked:true,beginAtZero:true}},y:{{stacked:true}}}}}}
          }});
        }}
        async function initChart{n}(ou,pe) {{
          document.getElementById('loading{n}').style.display='none';
          const cvs=document.getElementById('chart{n}'); cvs.style.display='block';
          if(PREVIEW){{document.getElementById('demoBanner{n}').style.display='block';renderChart{n}Sample(cvs);return;}}
          document.getElementById('demoBanner{n}').style.display='none';
          try {{
            const rpe=resolveRelativePeriod(pe);
            const d=await dhis2Get('api/analytics/events/aggregate/{prog}?stage={stg}&dimension={stg}.{de}&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:USER_ORGUNIT_CHILDREN');
            if(!d.rows||!d.rows.length){{document.getElementById('error{n}').textContent='No data.';document.getElementById('error{n}').style.display='block';return;}}
            renderChart{n}Real(cvs,d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);
            document.getElementById('error{n}').textContent='Failed to load: '+e.message;
            document.getElementById('error{n}').style.display='block';
          }}
        }}"""


# ── Build per-card JS (sample + real) ─────────────────────────────────────────

# ── Multi-DE JS generators ────────────────────────────────────────────────────

def _multi_fetch_js(n: int, sources: list[dict], chart_js_type: str,
                    stacked: bool = False) -> str:
    """
    Generates initChartN for 2-3 DE sources.
    Supports: tracker_numeric (Case C), aggregate/indicator (/analytics.json).
    Mixed types: each source fetched with its own API call.
    Pure aggregate/indicator: single /analytics.json call with dx:de1;de2;...
    """
    all_agg = all(s["type"] in ("aggregate", "indicator") for s in sources)

    if all_agg:
        de_ids = ";".join(s["uid"] for s in sources)
        de_labels_js = "{" + ",".join(f'"{s["uid"]}":"{s["name"].replace(chr(34), chr(39))}"' for s in sources) + "}"
        stack_x = "stacked:true," if stacked else ""
        stack_y = "stacked:true," if stacked else ""
        chart_opts = f"scales:{{x:{{{stack_x}ticks:{{maxRotation:45}}}},y:{{{stack_y}beginAtZero:true}}}}" if chart_js_type == "bar" else "scales:{y:{beginAtZero:true}}"
        fill_prop = "true" if chart_js_type == "line" else "false"

        real = f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const PALETTE=['#e74c3c','#3498db','#f39c12','#27ae60','#9b59b6','#1abc9c'];
          const dxIdx=d.headers.findIndex(h=>h.name==='dx');
          const peIdx=d.headers.findIndex(h=>h.name==='pe');
          const valIdx=d.headers.findIndex(h=>h.name==='value');
          const dxIds=[...new Set(d.rows.map(r=>r[dxIdx]))];
          const periods=[...new Set(d.rows.map(r=>r[peIdx]))].sort();
          const DE_NAMES={de_labels_js};
          const datasets=dxIds.map((dx,i)=>{{
            const label=d.metaData?.items?.[dx]?.name||DE_NAMES[dx]||dx;
            const vals=periods.map(p=>{{const row=d.rows.find(r=>r[dxIdx]===dx&&r[peIdx]===p);return row?parseFloat(row[valIdx])||0:0;}});
            return {{label,data:vals,backgroundColor:PALETTE[i%PALETTE.length],borderColor:PALETTE[i%PALETTE.length],fill:{fill_prop},tension:0.3}};
          }});
          chart{n}Inst=new Chart(cvs.getContext('2d'),{{
            type:'{chart_js_type}',
            data:{{labels:periods.map(formatPeriodLabel),datasets}},
            options:{{responsive:true,plugins:{{legend:{{position:'bottom'}}}},{chart_opts}}}
          }});
        }}
        async function initChart{n}(ou,pe) {{
          document.getElementById('loading{n}').style.display='none';
          const cvs=document.getElementById('chart{n}'); cvs.style.display='block';
          if(PREVIEW){{document.getElementById('demoBanner{n}').style.display='block';renderChart{n}Sample(cvs);return;}}
          document.getElementById('demoBanner{n}').style.display='none';
          try {{
            const d=await dhis2Get('api/analytics.json?dimension=dx:{de_ids}&dimension=pe:'+encodeURIComponent(pe)+'&dimension=ou:'+encodeURIComponent(ou)+'&displayProperty=NAME');
            if(!d.rows||!d.rows.length){{document.getElementById('error{n}').textContent='No data.';document.getElementById('error{n}').style.display='block';return;}}
            renderChart{n}Real(cvs,d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);
            document.getElementById('error{n}').textContent='Failed: '+e.message;
            document.getElementById('error{n}').style.display='block';
          }}
        }}"""
    else:
        # One API call per source (tracker numeric or mixed)
        fetch_lines = []
        for s in sources:
            if s["type"] == "tracker_numeric":
                fetch_lines.append(
                    f"dhis2Get('api/analytics/events/aggregate/{s['prog_uid']}?"
                    f"stage={s['stage_uid']}&value={s['uid']}&aggregationType=SUM"
                    f"&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou))")
            else:
                fetch_lines.append(
                    f"dhis2Get('api/analytics.json?dimension=dx:{s['uid']}"
                    f"&dimension=pe:'+encodeURIComponent(pe)+'&dimension=ou:'+encodeURIComponent(ou)+'&displayProperty=NAME')")

        de_names_js = "[" + ",".join(f'"{s["name"].replace(chr(34), chr(39))}"' for s in sources) + "]"
        fetch_array = ",\n          ".join(fetch_lines)
        fill_prop = "true" if chart_js_type == "line" else "false"
        chart_opts = "scales:{y:{beginAtZero:true}}"

        real = f"""\
        function renderChart{n}Real(cvs, results) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const PALETTE=['#e74c3c','#3498db','#f39c12','#27ae60','#9b59b6','#1abc9c'];
          const DE_NAMES={de_names_js};
          const allPeriods=[...new Set(results.flatMap(d=>{{
            const idx=d.headers.findIndex(h=>h.name==='pe');
            return d.rows.map(r=>r[idx]);
          }}))].sort();
          const datasets=results.map((d,i)=>{{
            const peIdx=d.headers.findIndex(h=>h.name==='pe');
            const valIdx=d.headers.findIndex(h=>h.name==='value');
            const vals=allPeriods.map(p=>{{const row=d.rows.find(r=>r[peIdx]===p);return row?parseFloat(row[valIdx])||0:0;}});
            return {{label:DE_NAMES[i],data:vals,backgroundColor:PALETTE[i%PALETTE.length],
              borderColor:PALETTE[i%PALETTE.length],fill:{fill_prop},tension:0.3}};
          }});
          chart{n}Inst=new Chart(cvs.getContext('2d'),{{
            type:'{chart_js_type}',
            data:{{labels:allPeriods.map(formatPeriodLabel),datasets}},
            options:{{responsive:true,plugins:{{legend:{{position:'bottom'}}}},{chart_opts}}}
          }});
        }}
        async function initChart{n}(ou,pe) {{
          document.getElementById('loading{n}').style.display='none';
          const cvs=document.getElementById('chart{n}'); cvs.style.display='block';
          if(PREVIEW){{document.getElementById('demoBanner{n}').style.display='block';renderChart{n}Sample(cvs);return;}}
          document.getElementById('demoBanner{n}').style.display='none';
          try {{
            const rpe=resolveRelativePeriod(pe);
            const results=await Promise.all([
              {fetch_array}
            ]);
            if(results.every(d=>!d.rows||!d.rows.length)){{document.getElementById('error{n}').textContent='No data.';document.getElementById('error{n}').style.display='block';return;}}
            renderChart{n}Real(cvs,results);
          }} catch(e) {{
            console.error('[Chart{n}]',e);
            document.getElementById('error{n}').textContent='Failed: '+e.message;
            document.getElementById('error{n}').style.display='block';
          }}
        }}"""

    return real


def _combined_bar_line_js(n: int, sources: list[dict]) -> str:
    """Two sources: first=bars, second=line overlay."""
    s0, s1 = sources[0], sources[1]
    fetches = []
    for s in [s0, s1]:
        if s["type"] == "tracker_numeric":
            fetches.append(
                f"dhis2Get('api/analytics/events/aggregate/{s['prog_uid']}?"
                f"stage={s['stage_uid']}&value={s['uid']}&aggregationType=SUM"
                f"&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou))")
        else:
            fetches.append(
                f"dhis2Get('api/analytics.json?dimension=dx:{s['uid']}"
                f"&dimension=pe:'+encodeURIComponent(pe)+'&dimension=ou:'+encodeURIComponent(ou)+'&displayProperty=NAME')")

    name0 = s0["name"].replace('"', "'")
    name1 = s1["name"].replace('"', "'")

    return f"""\
        function renderChart{n}Real(cvs, results) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const getVals=(d,pds)=>{{const peIdx=d.headers.findIndex(h=>h.name==='pe');const valIdx=d.headers.findIndex(h=>h.name==='value');return pds.map(p=>{{const row=d.rows.find(r=>r[peIdx]===p);return row?parseFloat(row[valIdx])||0:0;}});}};
          const allPeriods=[...new Set(results.flatMap(d=>{{const idx=d.headers.findIndex(h=>h.name==='pe');return d.rows.map(r=>r[idx]);}}))] .sort();
          chart{n}Inst=new Chart(cvs.getContext('2d'),{{
            type:'bar',
            data:{{
              labels:allPeriods.map(formatPeriodLabel),
              datasets:[
                {{type:'bar',label:'{name0}',data:getVals(results[0],allPeriods),backgroundColor:'#3498db',order:2}},
                {{type:'line',label:'{name1}',data:getVals(results[1],allPeriods),borderColor:'#e74c3c',backgroundColor:'transparent',tension:0.3,order:1}}
              ]
            }},
            options:{{responsive:true,plugins:{{legend:{{position:'bottom'}}}},scales:{{y:{{beginAtZero:true}}}}}}
          }});
        }}
        async function initChart{n}(ou,pe) {{
          document.getElementById('loading{n}').style.display='none';
          const cvs=document.getElementById('chart{n}'); cvs.style.display='block';
          if(PREVIEW){{document.getElementById('demoBanner{n}').style.display='block';renderChart{n}Sample(cvs);return;}}
          document.getElementById('demoBanner{n}').style.display='none';
          try {{
            const rpe=resolveRelativePeriod(pe);
            const results=await Promise.all([{fetches[0]},{fetches[1]}]);
            renderChart{n}Real(cvs,results);
          }} catch(e) {{
            console.error('[Chart{n}]',e);
            document.getElementById('error{n}').textContent='Failed: '+e.message;
            document.getElementById('error{n}').style.display='block';
          }}
        }}"""


def _build_per_card_js(n: int, config: dict) -> str:
    tid = config["template_id"]
    dtype = config.get("de_type", "aggregate")
    sources = config.get("de_sources", [config])  # list of DE dicts

    # ── Multi-DE templates ────────────────────────────────────────────────────
    if tid == "ft_line_multi":
        sample = _sample_js_line(n)   # line with 2 series
        real   = _multi_fetch_js(n, sources, "line")
        return sample + "\n" + real

    if tid == "ft_grouped_bar":
        sample = _sample_js_stacked(n)
        real   = _multi_fetch_js(n, sources, "bar")
        return sample + "\n" + real

    if tid == "ft_combined_bar_line":
        sample = _sample_js_stacked(n)
        real   = _combined_bar_line_js(n, sources)
        return sample + "\n" + real

    # ── Single-DE templates ───────────────────────────────────────────────────
    # sample JS block
    if tid in ("ft_bar_monthly",):
        if dtype == "tracker_option":
            sample = _sample_js_stacked(n)
        else:
            sample = _sample_js_bar_monthly(n)
    elif tid == "ft_stacked_cat":
        sample = _sample_js_stacked(n)
    elif tid == "ft_line_trend":
        sample = _sample_js_line(n)
    elif tid == "ft_bar_ou":
        sample = _sample_js_bar_ou(n)
    elif tid == "ft_pie_cat":
        sample = _sample_js_pie(n)
    elif tid == "ft_scorecard":
        sample = _sample_js_scorecard(n, config.get("title", "KPI"))
    else:
        sample = _sample_js_bar_monthly(n)

    # real JS block
    if tid == "ft_bar_monthly":
        if dtype == "tracker_option":
            real = _real_js_tracker_option_bar(n, config, stacked=True)
        elif dtype == "tracker_numeric":
            real = _real_js_tracker_numeric(n, config, "bar")
        else:
            real = _real_js_aggregate(n, config, "bar")
    elif tid == "ft_stacked_cat":
        real = _real_js_tracker_option_bar(n, config, stacked=True)
    elif tid == "ft_line_trend":
        if dtype == "tracker_numeric":
            real = _real_js_tracker_numeric(n, config, "line")
        else:
            real = _real_js_aggregate(n, config, "line")
    elif tid == "ft_bar_ou":
        if dtype == "tracker_option":
            real = _real_js_tracker_option_ou(n, config)
        elif dtype == "tracker_numeric":
            real = _real_js_tracker_numeric_ou(n, config)
        else:
            real = _real_js_aggregate(n, config, "bar", index_axis="y")
    elif tid == "ft_pie_cat":
        real = _real_js_tracker_option_pie(n, config)
    elif tid == "ft_scorecard":
        if dtype == "tracker_numeric":
            real = _real_js_tracker_numeric(n, config, "bar")
        else:
            real = _real_js_scorecard_aggregate(n, config)
    else:
        real = _real_js_aggregate(n, config, "bar")

    return sample + "\n" + real


# ── Public API ────────────────────────────────────────────────────────────────

def _custom_options_js(n: int, custom_options: dict) -> str:
    """
    Returns a JS snippet that wraps initChartN to apply custom Chart.js
    options after the chart is created. Supports dataset-level and
    top-level options merging, including data-labels display.
    """
    import json as _json
    if not custom_options:
        return ""

    opts_json = _json.dumps(custom_options)

    return f"""\
        (function() {{
          const _customOpts{n} = {opts_json};
          const _origInit{n} = initChart{n};
          initChart{n} = async function(ou, pe) {{
            await _origInit{n}(ou, pe);
            const inst = chart{n}Inst;
            if (!inst || !Object.keys(_customOpts{n}).length) return;
            const merge = (t, s) => {{
              Object.keys(s).forEach(k => {{
                if (k === 'datasets' && Array.isArray(s[k])) {{
                  (inst.data.datasets || []).forEach((ds, i) => {{
                    const p = s[k][0] || {{}};
                    Object.assign(ds, p);
                  }});
                }} else if (s[k] && typeof s[k] === 'object' && !Array.isArray(s[k]) && t[k]) {{
                  merge(t[k], s[k]);
                }} else {{
                  t[k] = s[k];
                }}
              }});
            }};
            merge(inst.options, _customOpts{n});
            inst.update();
          }};
        }})();"""


def generate_card_fragment(n: int, config: dict) -> str:
    """Return card HTML + per-card script (no shared script, no page shell).

    Routing priority:
      1. "plugin_id" in config  -> use plugin.build_js(n, config) directly
      2. "template_id" in config and plugins available -> try migrate_old_config()
         then plugin.build_js(n, config); fall back to _build_per_card_js on error
      3. "template_id" in config, no plugins -> _build_per_card_js (original path)
    """
    card_id = config.get("card_id", f"card_{n}")
    title   = _html.escape(config.get("title", f"Chart {n}"))
    col_w   = config.get("col_width", 6)

    js = None

    # ── Route 1: explicit plugin_id ───────────────────────────────────────────
    if "plugin_id" in config and _PLUGINS_AVAILABLE:
        try:
            plugin = get_plugin(config["plugin_id"])
            if plugin is not None:
                js = plugin.build_js(n, config)
        except Exception:
            js = None  # fall through to legacy path

    # ── Route 2: template_id via migration ────────────────────────────────────
    if js is None and "template_id" in config and _PLUGINS_AVAILABLE:
        try:
            migrated = migrate_old_config(config)
            plugin_id = migrated.get("plugin_id")
            if plugin_id:
                plugin = get_plugin(plugin_id)
                if plugin is not None:
                    js = plugin.build_js(n, migrated)
        except Exception:
            js = None  # fall through to legacy path

    # ── Route 3: legacy fallback (always works) ───────────────────────────────
    if js is None:
        js = _build_per_card_js(n, config)

    custom = _custom_options_js(n, config.get("custom_options", {}))
    if custom:
        js = js + "\n" + custom

    return _CARD_SHELL.format(
        card_id=card_id, n=n, title=title, col_width=col_w,
        per_card_js=js,
    )


def assemble_dashboard(configs: list[dict], title: str = "Dashboard",
                       extra_html_cards: list[str] | None = None) -> str:
    """
    Build a complete HTML page from a list of configs (for fixed templates)
    plus optional pre-built card HTML strings (for AI-generated cards).
    """
    card_fragments: list[str] = []
    init_calls: list[str] = []

    for n, cfg in enumerate(configs, 1):
        card_fragments.append(generate_card_fragment(n, cfg))
        init_calls.append(f"initChart{n}(ou,pe)")

    if extra_html_cards:
        # Extra cards already contain their own initChartN at higher indices
        start = len(configs) + 1
        for i, html in enumerate(extra_html_cards):
            card_fragments.append(html)
            init_calls.append(f"initChart{start+i}(ou,pe)")

    shared = _SHARED_SCRIPT.replace("__INIT_CALLS__", ", ".join(init_calls) or "Promise.resolve()")

    return _PAGE_SHELL.format(
        title=_html.escape(title),
        header_color="#1a6fa8",
        cards="\n".join(card_fragments),
        shared=shared,
    )


def _extract_prog_uid(config: dict) -> str | None:
    """Extract program UID from chart config (metrics, dimensions, or source)."""
    for m in (config.get("metrics") or []):
        p = m.get("prog_uid")
        if p:
            return p
    for dim in ((config.get("dimensions") or {}).values()):
        if isinstance(dim, dict):
            p = dim.get("prog_uid")
            if p:
                return p
    src = config.get("source") or {}
    return src.get("prog_uid") or src.get("program_uid") or None


def generate_preview_page(config: dict, title: str | None = None) -> str:
    """Generate a centered single-chart preview page with fixed canvas height."""
    import html as _h
    import json as _j
    t = _h.escape(title or config.get("title", "Preview"))
    n = 1
    # Same routing as generate_card_fragment: plugin_id → template migration → legacy
    js = None
    if "plugin_id" in config and _PLUGINS_AVAILABLE:
        try:
            plugin = get_plugin(config["plugin_id"])
            if plugin is not None:
                js = plugin.build_js(n, config)
        except Exception:
            js = None
    if js is None and "template_id" in config and _PLUGINS_AVAILABLE:
        try:
            migrated = migrate_old_config(config)
            plugin_id = migrated.get("plugin_id")
            if plugin_id:
                plugin = get_plugin(plugin_id)
                if plugin is not None:
                    js = plugin.build_js(n, migrated)
        except Exception:
            js = None
    if js is None:
        js = _build_per_card_js(n, config)
    custom = _custom_options_js(n, config.get("custom_options", {}))
    if custom:
        js = js + "\n" + custom

    shared = _SHARED_SCRIPT.replace("__INIT_CALLS__", f"initChart{n}(ou,pe)")

    # ── Badge: green when fixture sample data is baked into renderChartNSample ──
    badge_text = "&#9888; Sample data — click &#8635; Load data to fetch real DHIS2 data"
    fixture_script = ""  # no longer used for injection; kept so template line renders empty
    _badge_fixture = False
    prog_uid = _extract_prog_uid(config)
    if prog_uid:
        fp = Path(f"C:/Temp/test_fixture_{prog_uid}.json")
        if fp.exists():
            try:
                n_rows = len(_j.loads(fp.read_text(encoding="utf-8")).get("rows", []))
                badge_text = (
                    f"&#128202; Fixture sample ({n_rows} rows from DHIS2) — "
                    f"program {prog_uid}"
                )
                _badge_fixture = True
            except Exception:
                pass
    # ─────────────────────────────────────────────────────────────────────────

    return f"""\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{t} — Preview</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
  <style>
    body {{ background:#f0f4f8; margin:0; }}
    .preview-badge {{ background:#fff3cd; color:#856404; border:1px solid #ffc107;
      border-radius:4px; padding:3px 10px; font-size:11px; text-align:center; margin-bottom:8px; }}
    .preview-badge.fixture {{ background:#d4edda; color:#155724; border-color:#c3e6cb; }}
    .card-header {{ background:#1a6fa8; color:#fff; padding:8px 14px; }}
    .card-header h6 {{ margin:0; font-size:13px; font-weight:600; }}
    /* chart fills exactly this wrapper — Chart.js respects parent height when maintainAspectRatio=false */
    .chart-wrapper {{ position:relative; height:calc(100vh - 160px); min-height:260px; max-height:480px; }}
  </style>
</head>
<body>
  <div id="controls" style="background:#fff;border-bottom:1px solid #d0dde8;padding:8px 16px;
    display:flex;gap:10px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:100;
    box-shadow:0 1px 4px rgba(0,0,0,.08);">
    <span style="font-weight:700;font-size:13px;color:#1a6fa8">&#128202; Preview</span>
    <label style="font-weight:600;margin:0;font-size:12px;color:#555">Org unit:</label>
    <select id="ouSelect" style="padding:3px 7px;border:1px solid #ced4da;border-radius:4px;font-size:12px"></select>
    <label style="font-weight:600;margin:0;font-size:12px;color:#555">Period:</label>
    <select id="peSelect" style="padding:3px 7px;border:1px solid #ced4da;border-radius:4px;font-size:12px"></select>
    <button id="loadBtn" onclick="loadData()" style="padding:4px 14px;background:#1a6fa8;color:#fff;
      border:none;border-radius:4px;cursor:pointer;font-size:12px">&#8635; Load data</button>
    <span id="lastUpdated" style="font-size:11px;color:#6c757d;"></span>
  </div>

  <div style="max-width:800px;margin:12px auto;padding:0 12px;">
    <div class="preview-badge{' fixture' if _badge_fixture else ''}">{badge_text}</div>
    <div class="card shadow-sm">
      <div class="card-header"><h6>{t}</h6></div>
      <div id="demoBanner{n}" style="background:#fff3cd;color:#856404;font-size:11px;
        padding:2px 12px;text-align:center;display:none;">&#9888; Sample data — preview mode</div>
      <div class="card-body" style="padding:12px;position:relative;">
        <div id="loading{n}" style="position:absolute;inset:0;display:flex;align-items:center;
          justify-content:center;background:rgba(255,255,255,.9);z-index:2;border-radius:0 0 4px 4px;">
          <div class="spinner-border text-primary" role="status"></div>
        </div>
        <div id="error{n}" style="display:none;background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;
          border-radius:4px;padding:8px;font-size:12px;margin-bottom:8px;"></div>
        <div class="chart-wrapper">
          <canvas id="chart{n}" style="display:none;"></canvas>
        </div>
      </div>
    </div>
  </div>

  <script>
{js}
  </script>
  <script>
  // Patch: disable maintainAspectRatio so Chart.js fills the fixed-height wrapper exactly
  (function() {{
    var _orig = initChart{n};
    initChart{n} = async function(ou, pe) {{
      await _orig(ou, pe);
      var inst = chart{n}Inst;
      if (inst) {{
        inst.options.maintainAspectRatio = false;
        inst.resize();
      }}
    }};
  }})();
  </script>
  <script>
{shared}
  </script>
{fixture_script}
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
