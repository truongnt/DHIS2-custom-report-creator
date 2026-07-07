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

try:
    # Primary: raw tracker events + org units under data/<active instance>/ (new export flow).
    from dhis2.event_adapter import build_fixture as _build_fixture_new
    try:
        # Legacy fallback: committed fixtures/ (raw_events_v1) — keeps existing data/tests working.
        from dhis2.fixture_fetcher import load_raw_events as _legacy_load_raw_events
    except Exception:
        _legacy_load_raw_events = None

    def load_raw_events(prog_uid, stage_uid=""):
        fx = _build_fixture_new(prog_uid, stage_uid)
        if fx is not None:
            return fx
        if _legacy_load_raw_events is not None:
            return _legacy_load_raw_events(prog_uid, stage_uid)
        return None

    _FIXTURE_LOADER_AVAILABLE = True
except Exception:
    _FIXTURE_LOADER_AVAILABLE = False
    load_raw_events = None

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
  let PREVIEW = window.location.protocol === 'file:' || window.location.hostname === 'localhost';

  // Dashboard-level filter defaults (REQ-DASH-FILTER) — injected at assemble time.
  const DEFAULT_PE = '__DEFAULT_PE__';
  const DEFAULT_OU = '__DEFAULT_OU__';
  const DEFAULT_PE_FROM = '__DEFAULT_PE_FROM__';   // custom-range default (YYYYMM) or ''
  const DEFAULT_PE_TO   = '__DEFAULT_PE_TO__';

  // OU "By level" options — Superset hierarchical Value filter mapped to DHIS2 ou:LEVEL-N
  const OU_LEVELS = [['All — Level 1 (national)','LEVEL-1'],['All — Level 2 (province)','LEVEL-2'],
                     ['All — Level 3 (district)','LEVEL-3'],['All — Level 4 (facility)','LEVEL-4']];
  function _appendOuLevels(sel){
    const g=document.createElement('optgroup'); g.label='By level';
    OU_LEVELS.forEach(([l,v])=>g.appendChild(new Option(l,v)));
    sel.appendChild(g);
  }
  // Expand a from→to month range (YYYYMM) into a ';'-joined DHIS2 pe list (inclusive).
  function expandMonths(from, to){
    if(!from || !to) return from || to || '';
    let a=parseInt(from.slice(0,4))*12+parseInt(from.slice(4,6))-1;
    let b=parseInt(to.slice(0,4))*12+parseInt(to.slice(4,6))-1;
    if(a>b){const t=a;a=b;b=t;}
    const out=[];
    for(let k=a;k<=b && out.length<60;k++){out.push(Math.floor(k/12)+String(k%12+1).padStart(2,'0'));}
    return out.join(';');
  }

  // ── Dynamic dashboard filters (V3) — Superset-style list, injected at assemble time ──
  // Each: {id, alias, type:'ou'|'period'|'dimension', default, from, to, scope:'all'|[chartIdx0…]}
  const DASH_FILTERS = __DASH_FILTERS__;
  const CHART_COUNT  = __CHART_COUNT__;
  const CHART_PROG   = __CHART_PROG__;   // {chartIndex(1-based): programUid} — '' if not program-based

  function _inScope(f, n){            // n is 1-based chart index
    return f.scope === 'all' || (Array.isArray(f.scope) && f.scope.indexOf(n-1) >= 0);
  }
  function _filterValue(f){
    if(f.type === 'period' && f._cid === 'peSelect') return currentPeriod();
    const el = document.getElementById(f._cid);
    if(!el) return f['default'] || '';
    if(f.type === 'period' && el.value === '__RANGE__')
      return expandMonths(f.from || DEFAULT_PE_FROM, f.to || DEFAULT_PE_TO);
    return el.value || f['default'] || '';
  }
  // Effective ou / pe for chart n: the last in-scope filter of that type wins (Superset OVERRIDE).
  function ouForChart(n){
    let v = DEFAULT_OU;
    DASH_FILTERS.forEach(function(f){ if(f.type==='ou' && _inScope(f,n)) v = _filterValue(f); });
    return v;
  }
  function peForChart(n){
    let v = currentPeriod();
    DASH_FILTERS.forEach(function(f){ if(f.type==='period' && _inScope(f,n)) v = _filterValue(f); });
    return v;
  }

  // Build the dynamic part of the filter bar (extra filters beyond the primary OU+Period)
  // and relabel the primary controls with their filter alias.
  function applyFilterMeta(){
    let firstOu=true, firstPe=true;
    const extra=document.getElementById('filterBarExtra');
    DASH_FILTERS.forEach(function(f){
      if(f.type==='ou' && firstOu){ firstOu=false; f._cid='ouSelect'; _relabel('ouLabel', f.alias); }
      else if(f.type==='period' && firstPe){ firstPe=false; f._cid='peSelect'; _relabel('peLabel', f.alias); }
      else { f._cid=f.id; if(extra) extra.appendChild(_mkExtraFilter(f)); }
    });
  }
  function _relabel(id, alias){ const l=document.getElementById(id); if(l && alias) l.textContent=alias+':'; }
  function _mkExtraFilter(f){
    const span=document.createElement('span');
    span.style.cssText='display:inline-flex;gap:6px;align-items:center;';
    const lbl=document.createElement('label'); lbl.textContent=(f.alias||f.type)+':';
    lbl.style.cssText='font-weight:600;margin:0;font-size:12px;color:#555'; span.appendChild(lbl);
    let ctrl;
    if(f.type==='dimension'){
      // Viewer-facing control depends on the DE/PA data type (REQ-DASH-FILTER-15).
      const vt=f.value_type||'text';
      if(vt==='option'){
        ctrl=document.createElement('select');
        ctrl.appendChild(new Option('(all) '+(f.alias||''), ''));   // blank = no filter
        (f.options||[]).forEach(function(o){ ctrl.appendChild(new Option(o[0], o[1])); });
        if(f['default']) _selectOrInsert(ctrl, f['default']);
      } else {
        ctrl=document.createElement('input');
        ctrl.type = (vt==='number') ? 'number' : (vt==='date') ? 'date' : 'text';
        ctrl.value=f['default']||''; ctrl.placeholder=(vt==='date')?'':'value';
      }
      ctrl.id=f.id;
      ctrl.style.cssText='padding:3px 7px;border:1px solid #ced4da;border-radius:4px;font-size:12px'
        + (ctrl.tagName==='INPUT'?';width:120px':'');
      ctrl.title='Filters charts on '+(f.source||'this dimension');
    } else {
      ctrl=document.createElement('select'); ctrl.id=f.id;
      ctrl.style.cssText='padding:3px 7px;border:1px solid #ced4da;border-radius:4px;font-size:12px';
      if(f.type==='ou'){
        [['User org unit','USER_ORGUNIT'],['User sub-units','USER_ORGUNIT_CHILDREN']].forEach(([l,v])=>ctrl.appendChild(new Option(l,v)));
        OU_LEVELS.forEach(([l,v])=>ctrl.appendChild(new Option(l,v)));
      } else {
        [['Last 3 months','LAST_3_MONTHS'],['Last 6 months','LAST_6_MONTHS'],['Last 12 months','LAST_12_MONTHS'],
         ['This year','THIS_YEAR'],['Last year','LAST_YEAR']].forEach(([l,v])=>ctrl.appendChild(new Option(l,v)));
      }
      if(f['default']) _selectOrInsert(ctrl, f['default']);
    }
    span.appendChild(ctrl);
    return span;
  }

  // Extra &filter= params for chart n from in-scope dimension filters (REQ-DASH-FILTER-13).
  // In-scope dimension filters for chart n that actually have a value AND belong to the
  // chart's program (a tracker DE/PA can only filter charts querying that program — like
  // Superset only applies a filter to charts whose dataset has that column).
  function dimFiltersFor(n){
    const cp = (CHART_PROG && CHART_PROG[n]) || '';
    const out=[];
    DASH_FILTERS.forEach(function(f){
      if(f.type!=='dimension' || !_inScope(f,n)) return;
      // Skip only when we KNOW the chart belongs to a different program. If the chart's
      // program is unknown (cp=''), don't skip — endpoint-gating in dimExtra() keeps it safe.
      if(f.program && cp && f.program !== cp) return;
      const el=document.getElementById(f._cid);
      const val = el ? el.value : (f['default']||'');
      if(f.source && val) out.push({source:f.source, value:val, vt:f.value_type||'text'});
    });
    return out;
  }
  // Build the &filter= fragment for one analytics URL. Our dimension filters come from
  // tracker DE / program attributes, which are only valid on EVENT analytics — so we only
  // append to .../analytics/events/... calls (aggregate analytics.json is left untouched,
  // avoiding 409). Event item filters need an operator: item:IN:value (EQ for number/date).
  function dimExtra(path, n){
    if (path.indexOf('/events') < 0) return '';      // not an event query → don't filter
    let s='';
    dimFiltersFor(n).forEach(function(f){
      const op = (f.vt==='number' || f.vt==='date') ? 'EQ' : 'IN';
      s += '&filter='+encodeURIComponent(f.source)+':'+op+':'+encodeURIComponent(f.value);
    });
    return s;
  }
  // Run one chart's init with dimension filters appended to its analytics calls.
  async function initChartScoped(n){
    const fn=window['initChart'+n];
    if(typeof fn!=='function') return;
    if(!dimFiltersFor(n).length) return fn(ouForChart(n), peForChart(n));
    const _og=dhis2Get;
    dhis2Get=function(path){
      if(typeof path==='string' && path.indexOf('analytics')>=0) path=path+dimExtra(path, n);
      return _og(path);
    };
    try { await fn(ouForChart(n), peForChart(n)); }
    finally { dhis2Get=_og; }
  }

  // Debug logger — POST errors/logs back to preview server for session log
  (function() {
    function _dbgPost(level, msg) {
      // Only POST when a preview server is actually serving us (http/https). Under
      // file:// (offline tests) the fetch would reject async to file:///.../log and
      // surface as a SEVERE network error that leaks across tests — so skip it.
      if (location.protocol !== 'http:' && location.protocol !== 'https:') return;
      try { fetch('/log', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({level: level, msg: String(msg).slice(0, 2000)})}).catch(function(){}); } catch(_) {}
    }
    var _ce = console.error.bind(console);
    console.error = function() { _ce.apply(console, arguments); _dbgPost('error', Array.from(arguments).join(' ')); };
    window.addEventListener('unhandledrejection', function(e) { _dbgPost('unhandled', e.reason ? (e.reason.message||e.reason) : 'unhandled rejection'); });
    window.onerror = function(msg, src, line) { _dbgPost('error', msg + ' [' + (src||'') + ':' + line + ']'); };
    window._dbg = function(msg) { _dbgPost('debug', msg); };
  })();

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
      if (type === 'pie' || type === 'doughnut') {
        var ds0 = chart.data.datasets[0] || {data:[]};
        var meta0 = chart.getDatasetMeta(0);
        var total = (ds0.data||[]).reduce(function(s,x){return s+(parseFloat(x)||0);},0);
        var mode = opts.mode || 'value';          // 'value' | 'percent'
        var outside = opts.pos === 'outside';
        (meta0.data||[]).forEach(function(arc, idx){
          var v = ds0.data[idx];
          if (v === null || v === undefined || v === 0) return;
          var txt = (mode === 'percent') ? (total ? (v/total*100).toFixed(1)+'%' : '0%')
                    : ((typeof v === 'number') ? v.toLocaleString() : String(v));
          var ang = (arc.startAngle + arc.endAngle) / 2;
          var rr = outside ? (arc.outerRadius + 14)
                           : (arc.innerRadius + (arc.outerRadius - arc.innerRadius) * 0.6);
          ctx.save();
          ctx.font = 'bold ' + fontSize + 'px sans-serif';
          ctx.fillStyle = outside ? (opts.color || '#333') : (opts.color || '#fff');
          ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
          ctx.fillText(txt, arc.x + Math.cos(ang)*rr, arc.y + Math.sin(ang)*rr);
          ctx.restore();
        });
        return;
      }
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
    if (!r.ok) {
      // Surface the DHIS2 conflict message + the query so the cause is visible on-screen.
      let detail = '';
      try { const j = await r.json(); detail = j.message || j.error || ''; } catch(e) {}
      const q = path.indexOf('?') >= 0 ? path.slice(path.indexOf('?')) : path;
      throw new Error('HTTP ' + r.status + (detail ? ': ' + detail : '') + '  «' + q.slice(0, 200) + '»');
    }
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
    sel.appendChild(sg);
    _appendOuLevels(sel);                       // REQ-DASH-FILTER-06: by-level options
    sel.value='USER_ORGUNIT';
    try {
      const me = await dhis2Get('api/me.json?fields=organisationUnits[id,displayName,level]');
      const ous = (me.organisationUnits||[]).sort((a,b)=>a.displayName.localeCompare(b.displayName));
      if (ous.length) {
        const mg=document.createElement('optgroup'); mg.label='Org units';
        ous.forEach(o=>mg.appendChild(new Option(o.displayName,o.id)));
        sel.appendChild(mg);
      }
      _selectOrInsert(sel, DEFAULT_OU);
    } catch(e) { console.error('[OU]',e); }
  }

  // Set a select to value; if the option isn't present, insert it first so the default sticks.
  function _selectOrInsert(sel, value){
    if(!value) return;
    if(!Array.from(sel.options).some(o=>o.value===value)){
      sel.insertBefore(new Option(value.indexOf(';')>=0?'Selected range':value, value), sel.firstChild);
    }
    sel.value=value;
  }

  function generatePeriods() {
    const sel = document.getElementById('peSelect');
    sel.innerHTML='';
    sel.appendChild(new Option('Custom range…','__RANGE__'));   // REQ-DASH-FILTER-07
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

    // Populate From/To month pickers (last 36 months) for the custom-range mode
    const from=document.getElementById('peFrom'), to=document.getElementById('peTo');
    if(from && to){
      from.innerHTML=''; to.innerHTML='';
      for(let i=0;i<36;i++){let mo=m-i,yr=y;while(mo<=0){mo+=12;yr--;}
        const v=yr+String(mo).padStart(2,'0'), lbl='Month '+mo+'/'+yr;
        from.appendChild(new Option(lbl,v)); to.appendChild(new Option(lbl,v));}
      if(DEFAULT_PE_FROM) from.value=DEFAULT_PE_FROM;
      if(DEFAULT_PE_TO)   to.value=DEFAULT_PE_TO;
      sel.onchange=function(){togglePeRange();};
    }
    _selectOrInsert(sel, DEFAULT_PE);
    togglePeRange();
  }

  function togglePeRange(){
    const sel=document.getElementById('peSelect'), box=document.getElementById('peRange');
    if(box) box.style.display = (sel && sel.value==='__RANGE__') ? 'inline-flex' : 'none';
  }

  // Effective period: expand the custom range, else use the selected value (fallback DEFAULT_PE).
  function currentPeriod(){
    const sel=document.getElementById('peSelect');
    if(sel && sel.value==='__RANGE__'){
      return expandMonths(document.getElementById('peFrom').value,
                          document.getElementById('peTo').value);
    }
    return (sel && sel.value) || DEFAULT_PE;
  }

  function formatPeriodLabel(pe) {
    if (pe == null) return '';
    pe = String(pe);
    const mm=pe.match(/^(\\d{4})(\\d{2})$/);
    if(mm){const M=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];return M[parseInt(mm[2],10)-1]+' '+mm[1];}
    const qm=pe.match(/^(\\d{4})Q(\\d)$/);
    if(qm) return 'Q'+qm[2]+' '+qm[1];
    return pe;
  }

  const PALETTE=['#e74c3c','#3498db','#f39c12','#27ae60','#9b59b6','#1abc9c','#e67e22','#2980b9','#8e44ad','#16a085'];

  // Reset a card BEFORE its chart re-runs: clear the stale error box and make the canvas
  // visible again (a previous "no data" may have hidden it). No Chart.js destroy here —
  // the plugins destroy + recreate their own instance on success, so we don't interfere.
  function _resetCard(n){
    try {
      const er=document.getElementById('error'+n); if(er){ er.style.display='none'; er.textContent=''; }
      const cv=document.getElementById('chart'+n); if(cv) cv.style.display='block';
    } catch(e){}
  }
  // AFTER a chart runs: if it ended on "No data"/error, hide the canvas so the OLD chart
  // (still drawn on it) doesn't show underneath the message. Next successful load re-shows it.
  function _postCard(n){
    try {
      const er=document.getElementById('error'+n);
      const cv=document.getElementById('chart'+n);
      if(er && cv && er.style.display==='block') cv.style.display='none';
    } catch(e){}
  }

  async function loadData() {
    const btn=document.getElementById('loadBtn');
    btn.disabled=true; btn.textContent='⏳ Loading...';
    try {
      // Per-chart scope routing (REQ-DASH-FILTER-10/13): each chart gets the ou/pe of the
      // filters scoped to it, plus any in-scope dimension filters appended to its query.
      const hasDim = DASH_FILTERS.some(function(f){ return f.type==='dimension' && (f.source||''); });
      if(hasDim){
        // Sequential so the per-chart dhis2Get override can't race across charts.
        for(let n=1;n<=CHART_COUNT;n++){ _resetCard(n); await initChartScoped(n); _postCard(n); }
      } else {
        const tasks=[];
        for(let n=1;n<=CHART_COUNT;n++){
          _resetCard(n);
          const fn=window['initChart'+n];
          if(typeof fn==='function') tasks.push(Promise.resolve(fn(ouForChart(n), peForChart(n))).then(function(){_postCard(n);}).catch(function(){_postCard(n);}));
        }
        await Promise.all(tasks);
      }
      document.getElementById('lastUpdated').textContent='Updated: '+new Date().toLocaleTimeString();
    } finally { btn.disabled=false; btn.textContent='↻ Load data'; }
  }

  document.addEventListener('DOMContentLoaded', async ()=>{
    generatePeriods();
    if (PREVIEW) {
      const sel=document.getElementById('ouSelect');
      [['User organisation unit','USER_ORGUNIT'],['User sub-units','USER_ORGUNIT_CHILDREN'],
       ['User sub-x2-units','USER_ORGUNIT_GRANDCHILDREN']].forEach(([l,v])=>sel.appendChild(new Option(l,v)));
      _appendOuLevels(sel);                     // REQ-DASH-FILTER-06
      _selectOrInsert(sel, DEFAULT_OU);
      applyFilterMeta();                        // relabel + render extra filters (REQ-DASH-FILTER-10)
      await loadData();
      return;
    }
    try { await loadOrgUnits(); applyFilterMeta(); await loadData(); } catch(e) { console.error('Init error:',e); }
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
  <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
  <style>
    body{{background:#f0f4f8;}}
    .demo-banner{{background:#fff3cd;color:#856404;border:1px solid #ffc107;border-radius:4px;
      padding:3px 10px;font-size:11px;margin-bottom:6px;text-align:center;display:none;}}
    .card-header{{background:{header_color};color:#fff;padding:8px 14px;}}
    .card-header h6{{margin:0;font-size:13px;font-weight:600;}}
    /* bounded chart box — Chart.js (maintainAspectRatio=false) fills it exactly */
    .chart-wrapper{{position:relative;}}
    .chart-wrapper canvas{{max-height:100%;}}
  </style>
{custom_css}
</head>
<body>
  <div id="controls" style="background:#f0f4f8;border-bottom:1px solid #d0dde8;padding:10px 20px;
    display:flex;gap:12px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:100;">
    <label id="ouLabel" style="font-weight:600;margin:0;font-size:13px">Org unit:</label>
    <select id="ouSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
    <label id="peLabel" style="font-weight:600;margin:0;font-size:13px">Period:</label>
    <select id="peSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
    <span id="peRange" style="display:none;gap:6px;align-items:center;">
      <label style="margin:0;font-size:12px;color:#555">From:</label>
      <select id="peFrom" style="padding:3px 6px;border:1px solid #ced4da;border-radius:4px;font-size:12px"></select>
      <label style="margin:0;font-size:12px;color:#555">To:</label>
      <select id="peTo" style="padding:3px 6px;border:1px solid #ced4da;border-radius:4px;font-size:12px"></select>
    </span>
    <span id="filterBarExtra" style="display:inline-flex;gap:10px;align-items:center;"></span>
    <button id="loadBtn" onclick="loadData()" style="padding:5px 16px;background:#1a6fa8;color:#fff;
      border:none;border-radius:4px;cursor:pointer;font-size:13px">↻ Load data</button>
    <button id="exportDashBtn" onclick="exportDashboardPDF()" title="Export the whole dashboard to a multi-page PDF"
      style="padding:5px 16px;background:#fff;color:#1a6fa8;border:1px solid #1a6fa8;border-radius:4px;cursor:pointer;font-size:13px">⬇ Export PDF</button>
    <span id="lastUpdated" style="font-size:11px;color:#6c757d;margin-left:8px"></span>
  </div>
  <div class="container-fluid px-3 py-3" id="dashRoot">
    <div class="row">
{cards}
    </div>
  </div>
  <script>
{shared}
  </script>
{fixtures}
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

_CARD_SHELL = """\
      <!-- CARD-START:{card_id} -->
      <div class="col-md-{col_width} mb-4">
        <div class="card shadow-sm">
          <div class="card-header" style="display:flex;align-items:center;gap:4px;">
            <h6 style="flex:1;margin:0;font-size:13px;font-weight:600;">{title}</h6>
            <button onclick="exportChart('png',{n})" title="Export image (PNG)" style="background:rgba(255,255,255,.2);border:none;color:#fff;border-radius:3px;padding:2px 6px;cursor:pointer;font-size:9px;font-weight:600;">PNG</button>
            <button onclick="exportChart('pdf',{n})" title="Export PDF" style="background:rgba(255,255,255,.2);border:none;color:#fff;border-radius:3px;padding:2px 6px;cursor:pointer;font-size:9px;font-weight:600;">PDF</button>
            <button onclick="exportChart('xlsx',{n})" title="Export Excel / CSV" style="background:rgba(255,255,255,.2);border:none;color:#fff;border-radius:3px;padding:2px 6px;cursor:pointer;font-size:9px;font-weight:600;">XLS</button>
          </div>
          <div class="card-body" style="position:relative;padding:12px;">
            <div id="demoBanner{n}" class="demo-banner">⚠ Sample data — preview mode</div>
            <div id="loading{n}" style="position:absolute;inset:0;display:flex;align-items:center;
              justify-content:center;background:rgba(255,255,255,.85);z-index:2;border-radius:4px;">
              <div class="spinner-border text-primary" role="status"></div>
            </div>
            <div id="error{n}" style="display:none;background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;
              border-radius:4px;padding:10px;font-size:13px;margin-top:8px;"></div>
            <!-- chart-wrapper has a BOUNDED height so wide cards don't stretch the chart tall -->
            <div class="chart-wrapper" style="position:relative;height:{chart_h}px;">
              <canvas id="chart{n}" style="display:none;"></canvas>
            </div>
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

def _extract_stage_uid(config: dict) -> str | None:
    """Extract stage UID from chart config (first tracker metric, then source)."""
    for m in (config.get("metrics") or []):
        s = m.get("stage_uid")
        if s:
            return s
    src = config.get("source") or {}
    return src.get("stage_uid") or config.get("stage_uid") or None


# ── Fixture mock JS (plain string — no f-string, real curly braces OK) ───────
_FIXTURE_MOCK_JS = """\
function _mockDhis2Get(path, fx) {
  var hdrs=fx.headers.map(function(h){return h.name;});
  var rows=fx.rows||[];
  var stgUid=fx._stage_uid||'';
  var ouCol=hdrs.indexOf('ou');
  var ouNameCol=hdrs.indexOf('ouname');
  var peCol=hdrs.indexOf('pe');
  var edCol=hdrs.indexOf('eventdate');
  var peSource=peCol>=0?peCol:edCol;
  var useEd=peCol<0;
  var metaItems={};
  if(ouCol>=0&&ouNameCol>=0){
    rows.forEach(function(r){var uid=r[ouCol],nm=r[ouNameCol];if(uid&&nm)metaItems[uid]={name:nm};});
  }
  function toPe(v){
    if(!useEd)return v;
    var m=(v||'').match(/^(\\d{4})-(\\d{2})/);
    return m?m[1]+m[2]:(v||'');
  }
  function findCol(stg,de){var i=hdrs.indexOf(stg+'.'+de);return i>=0?i:hdrs.indexOf(de);}

  // analytics/events/query → filter to requested DE dimensions (table raw mode)
  if(path.indexOf('analytics/events/query')>=0){
    // Honor stage= — events/query?stage=X returns ONLY events of that stage. The fixture
    // holds every stage's events, so drop the others (else rows with empty DE values appear).
    var qStageM=path.match(/[?&]stage=([A-Za-z0-9]{11})/);
    var qPsCol=hdrs.indexOf('ps');
    if(qStageM&&qPsCol>=0){
      rows=rows.filter(function(r){return r[qPsCol]===qStageM[1];});
    }
    // Parse requested DE dimensions from URL: dimension={stg}.{de}
    var reqDims=[];
    var dimRe=/[?&]dimension=([A-Za-z0-9]{11})\\.([A-Za-z0-9]{11})/g;
    var dm;
    while((dm=dimRe.exec(path))!==null){reqDims.push(dm[1]+'.'+dm[2]);}
    var stdCols=['psi','ps','eventdate','lastupdated','storedby','ou','ouname',
                 'longitude','latitude','geometry','pe'];
    // Select headers: standard metadata cols + only the requested DE cols
    var selHdrs;
    if(reqDims.length>0){
      selHdrs=fx.headers.filter(function(h){
        return stdCols.indexOf(h.name)>=0||reqDims.indexOf(h.name)>=0;
      });
    } else {
      selHdrs=fx.headers;
    }
    // Enrich headers with display name from _names map (built from config metrics)
    var names=fx._names||{};
    selHdrs=selHdrs.map(function(h){
      return {name:h.name,column:names[h.name]||h.column||h.name};
    });
    // Build row slices matching selected header positions
    var colIdx=selHdrs.map(function(h){return hdrs.indexOf(h.name);});
    var filtRows=rows.map(function(r){return colIdx.map(function(i){return i>=0?r[i]:'';});});
    return {headers:selHdrs,rows:filtRows,metaData:{items:metaItems,dimensions:{}}};
  }

  // analytics/events/aggregate → aggregate fixture
  if(path.indexOf('analytics/events/aggregate')>=0){
    // Honor the stage= filter: events/aggregate?stage=X counts ONLY events of stage X.
    // The fixture holds events from every stage of the program, so filter by the 'ps'
    // column (else a tracker metric counts all stages and over-reports).
    var stageM=path.match(/[?&]stage=([A-Za-z0-9]{11})/);
    var psCol=hdrs.indexOf('ps');
    if(stageM&&psCol>=0){
      rows=rows.filter(function(r){return r[psCol]===stageM[1];});
    }
    // Group by OU only when an OU LEVEL is requested (maps). A plain dimension=ou:{uid}
    // is just a filter for period charts → group by PERIOD, not collapse to one OU bar.
    var ouMode=/LEVEL-\\d+/.test(path);
    // Detect target OU level from URL (e.g. LEVEL-3 in dimension=ou:ROOT;LEVEL-3)
    var lvlMa=path.match(/dimension=ou:[^&]*LEVEL-(\\d+)/);
    var targetLvl=lvlMa?parseInt(lvlMa[1]):0;
    var ouParents=fx._ou_parents||{};
    // Map raw event OU → ancestor at targetLvl (or self if already at/below target)
    function resolveOu(evOu){
      if(!targetLvl||!ouMode)return evOu;
      var chain=ouParents[evOu];
      if(!chain)return evOu;
      // chain keys are strings (JSON); try numeric targetLvl as string key
      return chain[targetLvl]||chain[String(targetLvl)]||evOu;
    }
    var dimM=path.match(/[?&]dimension=([A-Za-z0-9]{11})\\.([A-Za-z0-9]{11})/);
    // Program attribute (PA / TEA) dimension: bare uid, no "stage." prefix, no "pe:"/"ou:".
    var teaM=path.match(/[?&]dimension=([A-Za-z0-9]{11})(?=&|$)/);
    var valM=path.match(/[?&]value=([A-Za-z0-9]{11})/);
    if(dimM||teaM){
      // tracker_option / PA: group by (period|ou) × category
      var catIdx, deName;
      if(dimM){catIdx=findCol(dimM[1],dimM[2]);deName=dimM[2];}
      else    {catIdx=hdrs.indexOf(teaM[1]);deName=teaM[1];}
      var cnts={};
      rows.forEach(function(r){
        var rawOu=r[ouCol]||'';
        var grp=ouMode?resolveOu(rawOu):toPe(r[peSource]||'');
        var cat=catIdx>=0?r[catIdx]:'';
        if(!grp||!cat)return;
        var k=grp+'\\x00'+cat;cnts[k]=(cnts[k]||0)+1;
      });
      var hdr=ouMode?'ou':'pe';
      var oR=Object.keys(cnts).map(function(k){var p=k.split('\\x00');return[p[0],p[1],String(cnts[k])];});
      return {headers:[{name:hdr},{name:deName},{name:'value'}],rows:oR,
              metaData:{items:ouMode?metaItems:{},dimensions:{}}};
    }
    if(valM){
      // tracker_numeric: sum by period|ou
      var vIdx=findCol(stgUid,valM[1]);
      var s={};
      rows.forEach(function(r){
        var rawOu=r[ouCol]||'';
        var grp=ouMode?resolveOu(rawOu):toPe(r[peSource]||'');
        var v=parseFloat(vIdx>=0?r[vIdx]:0)||0;
        if(!grp)return;s[grp]=(s[grp]||0)+v;
      });
      var hdr=ouMode?'ou':'pe';
      var oR=Object.keys(s).map(function(k){return[k,String(s[k])];});
      return {headers:[{name:hdr},{name:'value'}],rows:oR,
              metaData:{items:ouMode?metaItems:{},dimensions:{}}};
    }
    // plain event COUNT per period|ou (no value=, no dimension={stg}.{de})
    var cntC={};
    rows.forEach(function(r){
      var rawOu=r[ouCol]||'';
      var grp=ouMode?resolveOu(rawOu):toPe(r[peSource]||'');
      if(!grp)return;cntC[grp]=(cntC[grp]||0)+1;
    });
    var hdrC=ouMode?'ou':'pe';
    var oRC=Object.keys(cntC).map(function(k){return[k,String(cntC[k])];});
    return {headers:[{name:hdrC},{name:'value'}],rows:oRC,
            metaData:{items:ouMode?metaItems:{},dimensions:{}}};
  }

  // analytics.json (aggregate/indicator) → deterministic synthetic sample
  if(path.indexOf('analytics.json')>=0){
    var dxM=path.match(/dimension=dx:([A-Za-z0-9;]+)/);
    var dxIds=dxM?dxM[1].split(';'):['sample'];
    var pds=['202501','202502','202503','202504','202505','202506',
             '202507','202508','202509','202510','202511','202512'];
    var MN=['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    var sm={items:{},dimensions:{pe:pds}};
    pds.forEach(function(p){sm.items[p]={name:MN[parseInt(p.substring(4,6))]+' '+p.substring(0,4)};});
    var base=[120,145,98,167,134,189,210,156,143,178,192,165],sr=[];
    dxIds.forEach(function(dx,di){
      pds.forEach(function(pe,pi){sr.push([dx,pe,'ORGUNIT',String(base[pi]*(di+1))]);});
    });
    return {headers:[{name:'dx'},{name:'pe'},{name:'ou'},{name:'value'}],rows:sr,metaData:sm};
  }

  // geoFeatures → return boundaries stored in fixture (fetched at download time)
  if(path.indexOf('geoFeatures')>=0){
    var lvlM=path.match(/LEVEL-(\\d+)/);
    var lvl=lvlM?lvlM[1]:'2';
    var geo=fx._geo||{};
    var feats=geo[lvl];
    return feats&&feats.length?feats:null;  // null → fall through to real dhis2Get via proxy
  }

  // Unknown path — null falls through to real dhis2Get
  return null;
}"""


def _build_fixture_script(n: int, fixture_json: str) -> str:
    """Return a <script> block that embeds fixture data and patches initChartN."""
    patch = (
        "(function(){\n"
        "  var _oi=initChart" + str(n) + ";\n"
        "  var _og=dhis2Get;\n"
        "  initChart" + str(n) + "=async function(ou,pe){\n"
        "    dhis2Get=function(path){var m=_mockDhis2Get(path,window.__DEMO_FX__);return m!==null?Promise.resolve(m):_og(path);};\n"
        "    PREVIEW=false;\n"
        "    try{await _oi(ou,pe);}\n"
        "    finally{PREVIEW=true;dhis2Get=_og;}\n"
        "  };\n"
        "})();"
    )
    return (
        "  <script>\n"
        "window.__DEMO_FX__ = " + fixture_json + ";\n\n"
        + _FIXTURE_MOCK_JS + "\n\n"
        + patch + "\n"
        "  </script>"
    )


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
            const inst = typeof chart{n}Inst !== 'undefined' ? chart{n}Inst : null;
            if (!inst || !Object.keys(_customOpts{n}).length) return;
            const merge = (t, s) => {{
              Object.keys(s).forEach(k => {{
                if (k === 'datasets' && Array.isArray(s[k])) {{
                  const _isPie = inst.config && (inst.config.type === 'pie' || inst.config.type === 'doughnut');
                  (inst.data.datasets || []).forEach((ds, i) => {{
                    const p = Object.assign({{}}, s[k][0] || {{}});
                    // A single colour is meaningless for a pie/doughnut: fills are per-slice
                    // (an array) and the border is just the white slice separator. Dropping a
                    // scalar backgroundColor/borderColor here stops one colour painting the
                    // whole pie (and its borders) the same.
                    ['backgroundColor','borderColor'].forEach(function(ck) {{
                      if (typeof p[ck] === 'string' && (_isPie || Array.isArray(ds[ck]))) delete p[ck];
                    }});
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


def _normalize_metric_keys(config: dict) -> dict:
    """Back-compat: older AI configs stored the metric UID under 'dx_uid'; plugins read 'uid'.
    Without this, dimension=dx: is empty → DHIS2 analytics returns 409 on deploy."""
    metrics = config.get("metrics")
    if not metrics:
        return config
    new, fixed = [], False
    for m in metrics:
        if isinstance(m, dict) and not m.get("uid") and m.get("dx_uid"):
            m = {**m, "uid": m["dx_uid"]}; fixed = True
        new.append(m)
    return {**config, "metrics": new} if fixed else config


_EXPORT_JS = r"""
  // ── Export: PNG / PDF / Excel per chart + whole-dashboard PDF ──────────────
  window.__charts = window.__charts || {};   // {n: Chart.js instance} — set after each init
  function _expCard(n){ var c=document.getElementById('chart'+n); return c ? c.closest('.card') : null; }
  function _expName(n){
    var card=_expCard(n), h=card && card.querySelector('.card-header h6');
    var t=(h ? h.textContent : ('chart'+n)).trim().replace(/[^0-9a-zA-Z _.-]+/g,'_').slice(0,60);
    return t || ('chart'+n);
  }
  function _dl(href,name){ var a=document.createElement('a'); a.href=href; a.download=name;
    document.body.appendChild(a); a.click(); a.remove(); }
  // html2canvas clones the DOM to render it, but <canvas> bitmaps are NOT copied into the
  // clone → charts come out blank. Copy each live canvas's pixels into its clone here.
  function _canvasCopyOnClone(clonedDoc){
    try{
      var origs=document.querySelectorAll('canvas');
      var clones=clonedDoc.querySelectorAll('canvas');
      for(var i=0;i<clones.length;i++){
        var o=(clones[i].id && document.getElementById(clones[i].id)) || origs[i];
        if(o && o.width && o.height){
          clones[i].width=o.width; clones[i].height=o.height;
          var cx=clones[i].getContext('2d');
          if(cx){ try{ cx.drawImage(o,0,0); }catch(e){} }
        }
      }
    }catch(e){}
  }
  var _H2C={backgroundColor:'#ffffff',useCORS:true,scale:2,logging:false,onclone:_canvasCopyOnClone};
  function _h2c(el,extra){ var o=Object.assign({},_H2C,extra||{}); return html2canvas(el,o); }
  // Custom-HTML widgets render inside a srcdoc <iframe> (allow-same-origin) which html2canvas
  // can't capture directly (comes out blank). Pre-render each iframe's own document.body to an
  // <img> swapped in place, capture, then restore. Returns Promise<restoreFn>.
  function _prepWidgets(scope){
    if(!window.html2canvas) return Promise.resolve(function(){});
    var ifrs=[].slice.call((scope||document).querySelectorAll('iframe[data-hw]'));
    var restores=[];
    return ifrs.reduce(function(p,ifr){ return p.then(function(){
      var doc; try{ doc=ifr.contentDocument||ifr.contentWindow.document; }catch(e){ return; }
      if(!doc || !doc.body) return;
      var bw=doc.body.scrollWidth||ifr.clientWidth, bh=doc.body.scrollHeight||ifr.clientHeight;
      return _h2c(doc.body,{width:bw,height:bh,windowWidth:bw,windowHeight:bh}).then(function(cv){
        var img=document.createElement('img'); img.src=cv.toDataURL('image/png');
        img.setAttribute('data-hw-shot','1');
        img.style.cssText='display:block;width:100%;height:'+(ifr.clientHeight||bh)+'px;';
        ifr.style.display='none'; ifr.parentNode.insertBefore(img,ifr);
        restores.push(function(){ try{img.remove();}catch(e){} ifr.style.display=''; });
      }).catch(function(){});
    }); }, Promise.resolve()).then(function(){ return function(){ restores.forEach(function(f){f&&f();}); }; });
  }
  function _cardCanvas(card){
    if(!window.html2canvas) return Promise.resolve(null);
    return _prepWidgets(card).then(function(restore){
      return _h2c(card).then(function(cv){ restore(); return cv; })
                       .catch(function(e){ restore(); throw e; });
    });
  }
  function exportChart(kind,n){
    var name=_expName(n);
    if(kind==='xlsx'){ return _exportRows(n,name); }
    var card=_expCard(n);
    if(!card){ alert('Chart not found.'); return; }
    _cardCanvas(card).then(function(cv){
      if(!cv){ alert('Export library still loading — try again in a moment.'); return; }
      if(kind==='png'){ _dl(cv.toDataURL('image/png'), name+'.png'); return; }
      if(kind==='pdf'){
        var J=window.jspdf && window.jspdf.jsPDF; if(!J){ alert('PDF library not loaded.'); return; }
        var orient = cv.width>=cv.height ? 'l' : 'p';
        var pdf=new J({orientation:orient, unit:'pt', format:'a4', compress:true});
        var pw=pdf.internal.pageSize.getWidth(), ph=pdf.internal.pageSize.getHeight();
        var r=Math.min((pw-40)/cv.width,(ph-40)/cv.height), w=cv.width*r, h=cv.height*r;
        // JPEG (not PNG) keeps the file small — PNG of gradient/photo-like charts is huge.
        pdf.addImage(cv.toDataURL('image/jpeg',0.9),'JPEG',(pw-w)/2,20,w,h);
        pdf.save(name+'.pdf');
      }
    });
  }
  // Rows for Excel/CSV: Chart.js data (labels + datasets), else a <table>, else custom-html iframe.
  function _rowsFor(n){
    var inst=window.__charts[n];
    if(inst && inst.data && inst.data.datasets && inst.data.datasets.length){
      var labels=inst.data.labels||[], ds=inst.data.datasets;
      var head=['Label'].concat(ds.map(function(d,i){return d.label||('Series '+(i+1));}));
      var body=labels.map(function(l,i){return [l].concat(ds.map(function(d){return d.data[i];}));});
      return [head].concat(body);
    }
    var card=_expCard(n);
    var tbl=card && card.querySelector('table');
    if(tbl){ return [].map.call(tbl.querySelectorAll('tr'),function(tr){
      return [].map.call(tr.querySelectorAll('th,td'),function(c){return c.textContent.trim();}); }); }
    var ifr=card && card.querySelector('iframe[data-hw]');
    try{ if(ifr && ifr.contentWindow && ifr.contentWindow.__chartData){
      var d=ifr.contentWindow.__chartData;
      var cols=ifr.contentWindow.__columnNames || Object.keys(d[0]||{});
      return [cols].concat(d.map(function(r){return cols.map(function(c){return r[c];});}));
    } }catch(e){}
    return null;
  }
  function _exportRows(n,name){
    var rows=_rowsFor(n);
    if(!rows || !rows.length){ alert('No tabular data to export for this chart.'); return; }
    if(window.XLSX){
      var ws=XLSX.utils.aoa_to_sheet(rows), wb=XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb,ws,'Data'); XLSX.writeFile(wb,name+'.xlsx');
    } else {
      var csv=rows.map(function(r){return r.map(function(c){var s=(c==null?'':String(c));
        return /[",\n]/.test(s) ? '"'+s.replace(/"/g,'""')+'"' : s; }).join(',');}).join('\n');
      _dl('data:text/csv;charset=utf-8,﻿'+encodeURIComponent(csv), name+'.csv');
    }
  }
  // Capture the WHOLE dashboard grid (preserving the on-screen card layout) as one tall
  // image, then slice it across A4 pages — so the PDF matches the browser layout instead
  // of one-card-per-page.
  function exportDashboardPDF(){
    var J=window.jspdf && window.jspdf.jsPDF;
    var root=document.getElementById('dashRoot');
    if(!J || !window.html2canvas){ alert('Export libraries not loaded yet — try again in a moment.'); return; }
    if(!root){ alert('Dashboard container not found.'); return; }
    var btn=document.getElementById('exportDashBtn'); if(btn){ btn.disabled=true; btn.textContent='⏳ Exporting…'; }
    _prepWidgets(root).then(function(restoreWidgets){
    var rootRect=root.getBoundingClientRect();
    // scale 1.6 (not 2) → far fewer pixels; still crisp enough for an A4 PDF.
    _h2c(root,{windowWidth:root.scrollWidth, width:root.scrollWidth, scale:1.6}).then(function(full){
      restoreWidgets();
      var pdf=new J({orientation:'p', unit:'pt', format:'a4', compress:true});
      var pw=pdf.internal.pageSize.getWidth(), ph=pdf.internal.pageSize.getHeight();
      var margin=18;
      var imgW=pw-2*margin;
      var ptPerPx=imgW/full.width;                      // canvas px → PDF pt
      var pageSrcH=Math.floor((ph-2*margin)/ptPerPx);   // canvas px that fit one page height
      // Card boundaries in canvas px, so page breaks land in the gaps between card rows
      // (never through a card) unless a single card is taller than a page.
      var cScale=full.width/rootRect.width;             // canvas px per CSS px
      var cards=[].slice.call(root.querySelectorAll('.card')).map(function(el){
        var r=el.getBoundingClientRect();
        return {top:(r.top-rootRect.top)*cScale, bottom:(r.bottom-rootRect.top)*cScale};
      });
      function straddles(Y){ return cards.some(function(c){ return c.top < Y-1 && c.bottom > Y+1; }); }
      // Safe break candidates = card bottoms where no card straddles (i.e. end of a row).
      var breaks=cards.map(function(c){return c.bottom;})
        .filter(function(Y){ return !straddles(Y); })
        .sort(function(a,b){return a-b;});
      var y=0, first=true, guard=0;
      while(y < full.height-1 && guard++ < 500){
        var remaining=full.height-y;
        var sliceBottom;
        if(remaining <= pageSrcH){ sliceBottom=full.height; }            // rest fits on one page
        else {
          var target=y+pageSrcH;
          var fit=breaks.filter(function(b){ return b > y+1 && b <= target+0.5; });
          if(fit.length){ sliceBottom=Math.max.apply(null, fit); }        // break at a row gap
          else { sliceBottom=target; }                                    // card taller than page → force cut
        }
        var sliceH=Math.max(1, Math.round(sliceBottom-y));
        var tmp=document.createElement('canvas'); tmp.width=full.width; tmp.height=sliceH;
        var ctx=tmp.getContext('2d'); ctx.fillStyle='#ffffff'; ctx.fillRect(0,0,tmp.width,sliceH);
        ctx.drawImage(full, 0, y, full.width, sliceH, 0, 0, full.width, sliceH);
        if(!first) pdf.addPage(); first=false;
        // JPEG (q=0.9) instead of PNG — cuts the PDF from tens of MB to ~1-2 MB.
        pdf.addImage(tmp.toDataURL('image/jpeg',0.9),'JPEG', margin, margin, imgW, sliceH*ptPerPx);
        y += sliceH;
      }
      pdf.save('dashboard.pdf');
      if(btn){ btn.disabled=false; btn.textContent='⬇ Export PDF'; }
    }).catch(function(e){
      restoreWidgets();
      if(btn){ btn.disabled=false; btn.textContent='⬇ Export PDF'; }
      alert('Export failed: '+(e && e.message ? e.message : e));
    });
    });
  }
"""


def generate_card_fragment(n: int, config: dict) -> str:
    """Return card HTML + per-card script (no shared script, no page shell).

    Routing priority:
      1. "plugin_id" in config  -> use plugin.build_js(n, config) directly
      2. "template_id" in config and plugins available -> try migrate_old_config()
         then plugin.build_js(n, config); fall back to _build_per_card_js on error
      3. "template_id" in config, no plugins -> _build_per_card_js (original path)
    """
    config  = _normalize_metric_keys(config)
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

    # Fill the bounded chart-wrapper exactly (no tall stretch on wide cards). No-op for maps.
    js = js + (
        f"\n(function(){{var _o=initChart{n};initChart{n}=async function(ou,pe){{"
        f"await _o(ou,pe);var i=(typeof chart{n}Inst!=='undefined')?chart{n}Inst:null;"
        f"if(i&&i.options){{i.options.maintainAspectRatio=false;i.resize();}}"
        f"(window.__charts=window.__charts||{{}})[{n}]=i;}};}})();"   # register for export
    )

    # Card height tracks the grid row-span (layout.h); default ~1 row.
    h = int((config.get("layout") or {}).get("h", 1) or 1)
    chart_h = max(220, h * 240)

    return _CARD_SHELL.format(
        card_id=card_id, n=n, title=title, col_width=col_w,
        per_card_js=js, chart_h=chart_h,
    )


def _normalize_filters(filters) -> list[dict]:
    """Coerce any saved filter shape into the V3 list of filter dicts.

    Accepts:
      - V3 list:  [{id, alias, type, default, from, to, scope}, …]  (returned as-is, defaulted)
      - V2/V1 flat dict: {"ou": ..., "period": ..., "period_from"/"period_to": ...}
        → a 2-filter list (Org unit + Period), scope "all".
    Always returns at least an Org-unit + Period filter so every chart has ou/pe.
    """
    if isinstance(filters, list):
        out = []
        for f in filters:
            out.append({
                "id": f.get("id") or f.get("type", "f"),
                "alias": f.get("alias") or {"ou": "Org unit", "period": "Period"}.get(f.get("type"), f.get("type", "Filter")),
                "type": f.get("type", "dimension"),
                "default": f.get("default", ""),
                "source": f.get("source", ""),          # dimension UID for &filter= (REQ-DASH-FILTER-13)
                "value_type": f.get("value_type", "text"),   # option/number/date/text → viewer control
                "options": f.get("options", []),        # [[label,value]…] for option-type filters
                "program": f.get("program", ""),        # restrict dimension filter to this program's charts
                "from": f.get("from", ""), "to": f.get("to", ""),
                "scope": f.get("scope", "all"),
            })
        if not any(f["type"] == "ou" for f in out):
            out.insert(0, {"id": "ou", "alias": "Org unit", "type": "ou",
                           "default": "USER_ORGUNIT", "from": "", "to": "", "scope": "all"})
        if not any(f["type"] == "period" for f in out):
            out.insert(1, {"id": "pe", "alias": "Period", "type": "period",
                           "default": "LAST_12_MONTHS", "from": "", "to": "", "scope": "all"})
        return out

    f = filters or {}
    pf, pt = f.get("period_from") or "", f.get("period_to") or ""
    return [
        {"id": "ou", "alias": "Org unit", "type": "ou",
         "default": f.get("ou") or "USER_ORGUNIT", "from": "", "to": "", "scope": "all"},
        {"id": "pe", "alias": "Period", "type": "period",
         "default": "__RANGE__" if (pf and pt) else (f.get("period") or "LAST_12_MONTHS"),
         "from": pf, "to": pt, "scope": "all"},
    ]


def _apply_filter_defaults(shared: str, filters) -> str:
    """Inject the V3 dynamic filter list + primary OU/Period defaults into the shared script.

    DHIS2 adaptation of Superset native filters: a configurable LIST of filters, each with
    an alias, type (ou/period/dimension), default value, and chart scope. The first OU and
    first Period filter drive the primary controls; extras render dynamically. See PART K.
    """
    import json as _json
    flist = _normalize_filters(filters)
    prim_ou = next((f for f in flist if f["type"] == "ou"), {"default": "USER_ORGUNIT"})
    prim_pe = next((f for f in flist if f["type"] == "period"),
                   {"default": "LAST_12_MONTHS", "from": "", "to": ""})
    pf, pt = prim_pe.get("from") or "", prim_pe.get("to") or ""
    pe = "__RANGE__" if (pf and pt) else (prim_pe.get("default") or "LAST_12_MONTHS")
    filters_json = _json.dumps(flist).replace("</", "<\\/")
    return (shared.replace("__DASH_FILTERS__", filters_json)
                  .replace("__DEFAULT_PE_FROM__", pf)
                  .replace("__DEFAULT_PE_TO__", pt)
                  .replace("__DEFAULT_PE__", pe)
                  .replace("__DEFAULT_OU__", prim_ou.get("default") or "USER_ORGUNIT"))


def assemble_dashboard(configs: list[dict], title: str = "Dashboard",
                       extra_html_cards: list[str] | None = None,
                       filters: dict | None = None, preview: bool = False,
                       custom_css: str | None = None) -> str:
    """
    Build a complete HTML page from a list of configs (for fixed templates)
    plus optional pre-built card HTML strings (for AI-generated cards).

    filters : optional {"period": <relative pe>, "ou": <ou mode/id>} defaults for the
              shared filter bar applied to every chart (REQ-DASH-FILTER).
    preview : when True, inject downloaded sample-data fixtures per card so the
              dashboard renders offline (no infinite spinner). Export/Deploy leave
              this False so the deployed page fetches real DHIS2 data.
    """
    card_fragments: list[str] = []
    fixture_scripts: list[str] = []

    for n, cfg in enumerate(configs, 1):
        card_fragments.append(generate_card_fragment(n, cfg))
        if preview:
            fx, _badge, _is_fx = _build_card_fixture(n, cfg)
            if fx:
                fixture_scripts.append(fx)

    if extra_html_cards:
        for html in extra_html_cards:
            card_fragments.append(html)

    chart_count = len(configs) + (len(extra_html_cards) if extra_html_cards else 0)
    # Per-chart program uid → dimension filters only apply to charts of the same program.
    import json as _json
    chart_prog = {n: (_extract_prog_uid(_normalize_metric_keys(cfg)) or "")
                  for n, cfg in enumerate(configs, 1)}
    shared = _SHARED_SCRIPT.replace("__CHART_COUNT__", str(chart_count))
    shared = shared.replace("__CHART_PROG__", _json.dumps(chart_prog))
    shared = _apply_filter_defaults(shared, filters)
    shared = shared + "\n" + _EXPORT_JS

    return _PAGE_SHELL.format(
        title=_html.escape(title),
        header_color="#1a6fa8",
        cards="\n".join(card_fragments),
        shared=shared,
        fixtures="\n".join(fixture_scripts),
        custom_css=_custom_css_block(custom_css),
    )


def _custom_css_block(custom_css: str | None) -> str:
    """A <style> block for the dashboard's user CSS, placed after the default style so
    it overrides it (REQ-DASH-CSS-03). Empty/blank CSS → no tag at all."""
    if not custom_css or not custom_css.strip():
        return ""
    return f'  <style id="dashboard-custom-css">\n{custom_css}\n  </style>'


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
    config = _normalize_metric_keys(config)
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

    import json as _jp
    shared = _SHARED_SCRIPT.replace("__CHART_COUNT__", "1")
    shared = shared.replace("__CHART_PROG__", _jp.dumps({1: _extract_prog_uid(config) or ""}))
    shared = _apply_filter_defaults(shared, config.get("filters"))
    shared = shared + "\n" + _EXPORT_JS

    # ── Fixture injection: use downloaded sample data for preview ────────────
    fixture_script, badge_text, _badge_fixture = _build_card_fixture(n, config)
    return _render_single_preview(n, t, js, shared, fixture_script, badge_text, _badge_fixture)


def _build_card_fixture(n: int, config: dict) -> tuple[str, str, bool]:
    """Build the fixture <script> for card `n` from downloaded sample events.

    Returns (fixture_script, badge_text, is_fixture). When no fixture is available the
    script is empty and the badge text falls back to the 'sample data' note.
    """
    import json as _j
    badge_text = "&#9888; Sample data — click &#8635; Load data to fetch real DHIS2 data"
    _badge_fixture = False
    fixture_script = ""

    prog_uid = _extract_prog_uid(config)
    stage_uid = _extract_stage_uid(config)

    if prog_uid and _FIXTURE_LOADER_AVAILABLE and load_raw_events is not None:
        try:
            raw = load_raw_events(prog_uid, stage_uid or "")
            if raw and raw.get("rows"):
                n_rows_total = len(raw["rows"])
                # Build display-name map: "{stageUid}.{deUid}" → metric name
                _stage = raw.get("_stage_uid", stage_uid or "")
                _names = {}
                for m in config.get("metrics") or []:
                    de_uid  = m.get("uid", "")
                    de_name = m.get("name", "")
                    stg     = m.get("stage_uid") or _stage
                    if de_uid and de_name and stg:
                        _names[f"{stg}.{de_uid}"] = de_name
                # Build OU hierarchy lookup so mock can aggregate events at any level.
                # Maps event OU uid → {level_int: ancestor_uid, ...}
                _geo = raw.get("_geo", {})
                _ou_parents: dict = {}
                if _geo:
                    hdrs_raw = [h["name"] for h in raw.get("headers", [])]
                    ou_col_idx = next((i for i, h in enumerate(hdrs_raw) if h == "ou"), -1)
                    if ou_col_idx >= 0:
                        # Build level→pi lookup from geoFeatures
                        _pi = {}  # uid → pi (direct parent uid)
                        _le = {}  # uid → level int
                        for lvl_str, feats in _geo.items():
                            for feat in feats:
                                uid = feat.get("id")
                                if uid:
                                    _pi[uid] = feat.get("pi", "")
                                    _le[uid] = int(feat.get("le", lvl_str))
                        for row in raw["rows"]:
                            ev_ou = row[ou_col_idx] if row else ""
                            if not ev_ou or ev_ou in _ou_parents:
                                continue
                            chain: dict[int, str] = {}
                            cur = ev_ou
                            # Walk up until root (pi is empty or uid=pi)
                            visited: set[str] = set()
                            while cur and cur not in visited:
                                visited.add(cur)
                                lvl = _le.get(cur)
                                if lvl is not None:
                                    chain[lvl] = cur
                                parent = _pi.get(cur, "")
                                if not parent or parent == cur:
                                    break
                                cur = parent
                            _ou_parents[ev_ou] = chain

                fixture_trimmed = {
                    "_format":    raw.get("_format", "raw_events_v1"),
                    "_prog_uid":  raw.get("_prog_uid", prog_uid),
                    "_stage_uid": _stage,
                    "_names":     _names,  # {stg.deUid → display name} for column headers
                    "_ou_parents": _ou_parents,  # event_ou → {level: ancestor_uid}
                    "headers":    raw.get("headers", []),
                    "rows":       raw["rows"][:500],  # cap at 500 rows
                }
                # Push geo boundaries to preview server (served at /api/geoFeatures)
                # so map charts work in fixture mode without embedding large coords in HTML
                try:
                    from ui.preview_server import set_geo_cache as _set_geo
                    _set_geo(_geo)
                except Exception:
                    pass
                fx_json = _j.dumps(fixture_trimmed, ensure_ascii=False)
                fx_json = fx_json.replace("</", "<\\/")  # prevent </script> in JSON
                badge_text = (
                    f"&#128202; Fixture data ({n_rows_total} events) — "
                    "preview uses downloaded DHIS2 data"
                )
                _badge_fixture = True
                fixture_script = _build_fixture_script(n, fx_json)
        except Exception:
            pass
    return fixture_script, badge_text, _badge_fixture


def _render_single_preview(n, t, js, shared, fixture_script, badge_text, _badge_fixture) -> str:
    """Render the single-chart preview page shell around an already-built card."""
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
  <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
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
    <label id="ouLabel" style="font-weight:600;margin:0;font-size:12px;color:#555">Org unit:</label>
    <select id="ouSelect" style="padding:3px 7px;border:1px solid #ced4da;border-radius:4px;font-size:12px"></select>
    <label id="peLabel" style="font-weight:600;margin:0;font-size:12px;color:#555">Period:</label>
    <select id="peSelect" style="padding:3px 7px;border:1px solid #ced4da;border-radius:4px;font-size:12px"></select>
    <span id="peRange" style="display:none;gap:6px;align-items:center;">
      <label style="margin:0;font-size:12px;color:#555">From:</label>
      <select id="peFrom" style="padding:3px 6px;border:1px solid #ced4da;border-radius:4px;font-size:12px"></select>
      <label style="margin:0;font-size:12px;color:#555">To:</label>
      <select id="peTo" style="padding:3px 6px;border:1px solid #ced4da;border-radius:4px;font-size:12px"></select>
    </span>
    <span id="filterBarExtra" style="display:inline-flex;gap:10px;align-items:center;"></span>
    <button id="loadBtn" onclick="loadData()" style="padding:4px 14px;background:#1a6fa8;color:#fff;
      border:none;border-radius:4px;cursor:pointer;font-size:12px">&#8635; Load data</button>
    <span id="lastUpdated" style="font-size:11px;color:#6c757d;"></span>
  </div>

  <div style="max-width:800px;margin:12px auto;padding:0 12px;">
    <div class="preview-badge{' fixture' if _badge_fixture else ''}">{badge_text}</div>
    <div class="card shadow-sm">
      <div class="card-header" style="display:flex;align-items:center;gap:4px;">
        <h6 style="flex:1;margin:0;font-size:13px;font-weight:600;">{t}</h6>
        <button onclick="exportChart('png',{n})" title="Export image (PNG)" style="background:rgba(255,255,255,.2);border:none;color:#fff;border-radius:3px;padding:2px 6px;cursor:pointer;font-size:9px;font-weight:600;">PNG</button>
        <button onclick="exportChart('pdf',{n})" title="Export PDF" style="background:rgba(255,255,255,.2);border:none;color:#fff;border-radius:3px;padding:2px 6px;cursor:pointer;font-size:9px;font-weight:600;">PDF</button>
        <button onclick="exportChart('xlsx',{n})" title="Export Excel / CSV" style="background:rgba(255,255,255,.2);border:none;color:#fff;border-radius:3px;padding:2px 6px;cursor:pointer;font-size:9px;font-weight:600;">XLS</button>
      </div>
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
      var inst = typeof chart{n}Inst !== 'undefined' ? chart{n}Inst : null;
      if (inst) {{
        inst.options.maintainAspectRatio = false;
        inst.resize();
      }}
      (window.__charts = window.__charts || {{}})[{n}] = inst;   // register for export
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
