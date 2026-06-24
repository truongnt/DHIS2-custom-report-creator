"""
Reusable JavaScript string constants shared across chart plugins.

Plugins import these constants and embed them into their build_js() output
rather than duplicating the same JS in every plugin file.

Usage example in a plugin:
    from charts.plugins.shared_js import PALETTE_JS, INIT_CHART_JS, SHARED_SCRIPT

    def build_js(cls, n, config):
        return f\"\"\"
        {PALETTE_JS}
        function renderChart{n}Sample(cvs) {{ ... }}
        function renderChart{n}Real(ou, pe) {{ ... }}
        {INIT_CHART_JS.format(n=n)}
        \"\"\"
"""

# ── Palette ───────────────────────────────────────────────────────────────────

PALETTE_JS: str = (
    "const PALETTE=['#e74c3c','#3498db','#f39c12','#27ae60','#9b59b6',"
    "'#1abc9c','#e67e22','#2980b9','#8e44ad','#16a085'];"
)

# ── Demo / sample data blobs ──────────────────────────────────────────────────
# These are used by renderChart{n}Sample() functions so plugins can show
# realistic-looking charts in PREVIEW mode (file:// / localhost) without
# hitting a real DHIS2 server.

SAMPLE_DATA: dict[str, str] = {
    # 12 months of a single numeric series
    "bar_monthly": (
        "{"
        "labels:['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],"
        "datasets:[{label:'Cases',"
        "data:[120,145,98,167,203,189,212,176,143,198,221,185],"
        "backgroundColor:PALETTE[1]}]"
        "}"
    ),

    # Multi-category stacked bar (3 categories x 12 months)
    "bar_stacked": (
        "{"
        "labels:['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],"
        "datasets:["
        "{label:'Category A',data:[40,55,30,60,80,70,85,65,50,75,90,70],backgroundColor:PALETTE[0]},"
        "{label:'Category B',data:[50,60,40,70,90,80,90,75,60,85,95,80],backgroundColor:PALETTE[1]},"
        "{label:'Category C',data:[30,30,28,37,33,39,37,36,33,38,36,35],backgroundColor:PALETTE[2]}]"
        "}"
    ),

    # 5-category pie
    "pie": (
        "{"
        "labels:['Alpha','Beta','Gamma','Delta','Epsilon'],"
        "datasets:[{data:[35,25,20,12,8],"
        "backgroundColor:[PALETTE[0],PALETTE[1],PALETTE[2],PALETTE[3],PALETTE[4]]}]"
        "}"
    ),

    # 6 org units horizontal bar
    "bar_ou": (
        "{"
        "labels:['District A','District B','District C','District D','District E','District F'],"
        "datasets:[{label:'Value',"
        "data:[320,275,410,190,355,280],"
        "backgroundColor:PALETTE[1]}]"
        "}"
    ),

    # Single KPI number (scorecard uses this as a plain object, not a Chart.js dataset)
    "scorecard": (
        "{"
        "value:1842,"
        "label:'Total cases',"
        "period:'Last 12 months'"
        "}"
    ),

    # 12-month single line
    "line": (
        "{"
        "labels:['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],"
        "datasets:[{label:'Trend',"
        "data:[95,110,88,130,155,142,168,145,120,158,174,162],"
        "borderColor:PALETTE[1],backgroundColor:'rgba(52,152,219,0.1)',tension:0.3,fill:true}]"
        "}"
    ),

    # 2-series line (compare two sources)
    "line_multi": (
        "{"
        "labels:['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],"
        "datasets:["
        "{label:'Series A',data:[95,110,88,130,155,142,168,145,120,158,174,162],"
        "borderColor:PALETTE[0],backgroundColor:'transparent',tension:0.3},"
        "{label:'Series B',data:[60,75,55,90,105,98,115,100,82,110,128,118],"
        "borderColor:PALETTE[1],backgroundColor:'transparent',tension:0.3}]"
        "}"
    ),

    # 3 groups x 3 bars (grouped bar)
    "bar_grouped": (
        "{"
        "labels:['Jan','Feb','Mar','Apr','May','Jun'],"
        "datasets:["
        "{label:'Group A',data:[80,95,70,110,130,115],backgroundColor:PALETTE[0]},"
        "{label:'Group B',data:[60,72,55,88,100,92],backgroundColor:PALETTE[1]},"
        "{label:'Group C',data:[45,58,40,65,78,70],backgroundColor:PALETTE[2]}]"
        "}"
    ),

    # Combined bar + line (first DE bars, second DE line overlay)
    "combined": (
        "{"
        "labels:['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],"
        "datasets:["
        "{type:'bar',label:'Cases',"
        "data:[120,145,98,167,203,189,212,176,143,198,221,185],"
        "backgroundColor:PALETTE[1],yAxisID:'y'},"
        "{type:'line',label:'Rate',"
        "data:[2.4,2.9,1.96,3.34,4.06,3.78,4.24,3.52,2.86,3.96,4.42,3.7],"
        "borderColor:PALETTE[0],backgroundColor:'transparent',tension:0.3,yAxisID:'y1'}]"
        "}"
    ),
}

# ── initChart{n} function template ───────────────────────────────────────────
# Use as: INIT_CHART_JS.format(n=n)
#
# Responsibilities:
#   1. Hides the loading spinner for card n.
#   2. Shows the chart canvas for card n.
#   3. In PREVIEW mode: shows the demo banner and calls the sample renderer,
#      then returns early so no real API call is made.
#   4. Otherwise: reads ou/pe from the page controls and calls the real fetch.

INIT_CHART_JS: str = """\
  async function initChart{n}() {{
    document.getElementById('loading{n}').style.display = 'none';
    const cvs = document.getElementById('chart{n}');
    cvs.style.display = 'block';
    if (PREVIEW) {{
      const banner = document.getElementById('demoBanner{n}');
      if (banner) banner.style.display = 'block';
      renderChart{n}Sample(cvs);
      return;
    }}
    const ou = document.getElementById('ouSelect').value;
    const pe = resolveRelativePeriod(document.getElementById('peSelect').value);
    await renderChart{n}Real(ou, pe);
  }}"""

# ── Full shared page-level script ─────────────────────────────────────────────
# Copied verbatim from fixed_templates._SHARED_SCRIPT.
# Inserted once at the bottom of the generated HTML page (not per-card).
# Contains: PREVIEW flag, showValues plugin, dhis2Get, resolveRelativePeriod,
# formatPeriodLabel, loadOrgUnits, generatePeriods, loadData,
# and the DOMContentLoaded bootstrap handler.
#
# The placeholder __INIT_CALLS__ inside loadData() is replaced at page-build
# time with a comma-separated list of initChart0(), initChart1(), … calls.

SHARED_SCRIPT: str = """\
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
