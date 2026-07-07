"""
LineTrendPlugin — monthly/quarterly/yearly line chart for a single metric.

Supported DE types: tracker_numeric, tracker_option (event count per period),
aggregate, indicator.

plugin_options keys
-------------------
color_scheme : Default | DHIS2 | Warm | Cool | Earth | Pastel
line_tension : Smooth | Straight
fill_area    : None | Fill
show_legend  : Off | Bottom | Top | Right
show_values  : Off | On
y_format     : Default | 1,234 | 1.2K | %
x_rotation   : 0 | 45 | 90
log_scale    : Off | On
x_title      : str  (optional axis title)
y_title      : str  (optional axis title)
"""
from __future__ import annotations

import json as _json

from charts.plugins.base import (
    ChartPlugin,
    MetricControl,
    DimensionControl,
    SelectControl,
    TimeGrainControl,
)

# ── Palettes (identical to bar.py) ────────────────────────────────────────────

# Distinct-adjacent categorical palettes, shared across all chart plugins.
from charts.plugins.shared_js import PALETTES as _PALETTES


def _po(po: dict, key: str, default):
    return po.get(key, default) if po else default


def _jsbool(v) -> str:
    return "true" if v else "false"


def _palette_js(color_scheme: str) -> str:
    colors = _PALETTES.get(color_scheme, _PALETTES["Default"])
    return f"const PALETTE={_json.dumps(colors)};"


def _chartjs_options(po: dict) -> str:
    legend_raw  = _po(po, "show_legend", "Bottom")
    show_legend = legend_raw != "Off"
    legend_pos  = legend_raw.lower() if show_legend else "bottom"
    show_values = _po(po, "show_values", "Off") == "On"
    y_format    = _po(po, "y_format",    "Default")
    x_rotation  = int(_po(po, "x_rotation", "0"))
    log_scale   = _po(po, "log_scale",   "Off") == "On"
    x_title     = _po(po, "x_title",    "")
    y_title     = _po(po, "y_title",    "")

    if y_format == "1,234":
        y_fmt_fn = "v => v.toLocaleString()"
    elif y_format == "1.2K":
        y_fmt_fn = "v => v >= 1000 ? (v/1000).toFixed(1)+'K' : v"
    elif y_format == "%":
        y_fmt_fn = "v => v+'%'"
    else:
        y_fmt_fn = "v => v"

    x_title_opt = (
        f"\n          title: {{ display: true, text: {_json.dumps(x_title)} }},"
        if x_title else ""
    )
    y_title_opt = (
        f"\n          title: {{ display: true, text: {_json.dumps(y_title)} }},"
        if y_title else ""
    )

    return f"""{{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ display: {_jsbool(show_legend)}, position: '{legend_pos}' }},
          // Value labels use the registered `showValues` plugin (datalabels isn't registered).
          showValues: {{ display: {_jsbool(show_values)}, fontSize: 10 }},
          tooltip: {{
            mode: 'index',
            intersect: false,
            callbacks: {{
              label: ctx => ctx.dataset.label + ': ' + ({y_fmt_fn})(ctx.parsed.y),
            }},
          }},
        }},
        scales: {{
          x: {{
            ticks: {{ minRotation: {x_rotation}, maxRotation: {x_rotation},
                     autoSkip: true, autoSkipPadding: 8 }},{x_title_opt}
          }},
          y: {{
            beginAtZero: true,
            type: {'\"logarithmic\"' if log_scale else "'linear'"},
            ticks: {{ callback: {y_fmt_fn} }},{y_title_opt}
          }},
        }},
      }}"""


def _sample_js(n: int, po: dict, color_scheme: str = "Default",
               metric_label: str = "Series A") -> str:
    tension_raw = _po(po, "line_tension", "Smooth")
    tension     = "0.3" if tension_raw == "Smooth" else "0"
    fill        = _po(po, "fill_area", "None") == "Fill"
    fill_js     = "PALETTE[0]+'30'" if fill else "'transparent'"
    chart_opts  = _chartjs_options(po)
    pal         = _palette_js(color_scheme)
    scale       = max(1, int(_po(po, "demo_y_scale", 1)))
    raw         = [95,110,88,130,155,142,168,145,120,158,174,162]
    da          = [v * scale for v in raw]
    label_js    = _json.dumps(metric_label or "Series A")
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'line',
            data: {{
              labels: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
              datasets: [{{
                label: {label_js},
                data: {da},
                borderColor: PALETTE[0],
                backgroundColor: {fill_js},
                fill: {_jsbool(fill)},
                tension: {tension},
                pointRadius: 4,
                pointHoverRadius: 6,
              }}]
            }},
            options: {chart_opts}
          }});
        }}"""


def _real_js(n: int, config: dict, m: dict, po: dict, color_scheme: str) -> str:
    de_type   = m.get("type", "aggregate")
    de_uid    = m.get("uid", "")
    agg       = m.get("agg", "SUM")
    metric_label_js = _json.dumps(m.get("name") or "Value")   # uses the alias when set
    prog_uid  = m.get("prog_uid", "") or (config.get("source") or {}).get("prog_uid", "")
    stg_uid   = m.get("stage_uid", "") or (config.get("source") or {}).get("stage_uid", "")
    extra     = ChartPlugin._extra_params(config)
    chart_opts = _chartjs_options(po)
    pal        = _palette_js(color_scheme)
    tension_raw = _po(po, "line_tension", "Smooth")
    tension     = "0.3" if tension_raw == "Smooth" else "0"
    fill        = _po(po, "fill_area", "None") == "Fill"
    fill_js     = "PALETTE[0]+'30'" if fill else "'transparent'"

    render_fn = f"""\
        function renderChart{n}Real_draw(cvs, sortedLabels, sortedVals) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'line',
            data: {{
              labels: sortedLabels.map(formatPeriodLabel),
              datasets: [{{
                label: {metric_label_js},
                data: sortedVals,
                borderColor: PALETTE[0],
                backgroundColor: {fill_js},
                fill: {_jsbool(fill)},
                tension: {tension},
                pointRadius: 4,
                pointHoverRadius: 6,
              }}]
            }},
            options: {chart_opts}
          }});
        }}"""

    if de_type == "tracker_numeric":
        fetch_block = f"""\
            const rpe = resolveRelativePeriod(pe);
            const d = await dhis2Get(
              'api/analytics/events/aggregate/{prog_uid}?stage={stg_uid}'
              +'&value={de_uid}&aggregationType={agg}'
              +'&dimension=pe:'+encodeURIComponent(rpe)
              +'&dimension=ou:'+encodeURIComponent(ou)+'{extra}'
            );
            if (!d.rows||!d.rows.length){{errEl.textContent='No data.';errEl.style.display='block';return;}}
            const peIdx=d.headers.findIndex(h=>h.name==='pe');
            const valIdx=d.headers.findIndex(h=>h.name==='value');
            const labels=[...new Set(d.rows.map(r=>r[peIdx]))].sort();
            const vals=labels.map(p=>d.rows.filter(r=>r[peIdx]===p).reduce((s,r)=>s+(parseFloat(r[valIdx])||0),0));
            renderChart{n}Real_draw(cvs,labels,vals);"""
    elif de_type == "tracker_option":
        # Option-set tracker DE used as a metric → trend of EVENT COUNT per period
        # (events of this DE's stage). Same shape as the bar count renderer.
        fetch_block = f"""\
            const rpe = resolveRelativePeriod(pe);
            const d = await dhis2Get(
              'api/analytics/events/aggregate/{prog_uid}?stage={stg_uid}'
              +'&dimension=pe:'+encodeURIComponent(rpe)
              +'&dimension=ou:'+encodeURIComponent(ou)+'{extra}'
            );
            if (!d.rows||!d.rows.length){{errEl.textContent='No data.';errEl.style.display='block';return;}}
            const peIdx=d.headers.findIndex(h=>h.name==='pe');
            const valIdx=d.headers.findIndex(h=>h.name==='value');
            const labels=[...new Set(d.rows.map(r=>r[peIdx]))].sort();
            const vals=labels.map(p=>d.rows.filter(r=>r[peIdx]===p).reduce((s,r)=>s+(parseFloat(r[valIdx])||0),0));
            renderChart{n}Real_draw(cvs,labels,vals);"""
    else:
        fetch_block = f"""\
            const d = await dhis2Get(
              'api/analytics.json?dimension=dx:{de_uid}'
              +'&dimension=pe:'+encodeURIComponent(pe)
              +'&dimension=ou:'+encodeURIComponent(ou)
              +'&displayProperty=NAME{extra}'
            );
            if (!d.rows||!d.rows.length){{errEl.textContent='No data.';errEl.style.display='block';return;}}
            const peIdx=d.headers.findIndex(h=>h.name==='pe');
            const valIdx=d.headers.findIndex(h=>h.name==='value');
            const labels=[...new Set(d.rows.map(r=>r[peIdx]))].sort();
            const vals=labels.map(p=>d.rows.filter(r=>r[peIdx]===p).reduce((s,r)=>s+(parseFloat(r[valIdx])||0),0));
            renderChart{n}Real_draw(cvs,labels,vals);"""

    init_js = f"""\
        async function initChart{n}(ou, pe) {{
          document.getElementById('loading{n}').style.display='none';
          const cvs=document.getElementById('chart{n}');
          cvs.style.display='block';
          if (PREVIEW) {{
            const b=document.getElementById('demoBanner{n}');
            if(b) b.style.display='block';
            renderChart{n}Sample(cvs); return;
          }}
          document.getElementById('demoBanner{n}').style.display='none';
          const errEl=document.getElementById('error{n}');
          errEl.style.display='none';
          try {{
            {fetch_block}
          }} catch(e) {{
            console.error('[Chart{n}]',e);
            errEl.textContent='Failed: '+e.message;errEl.style.display='block';
          }}
        }}"""

    return render_fn + "\n" + init_js


def _real_js_dim(n: int, config: dict, m: dict, dim_de: dict, po: dict,
                 color_scheme: str) -> str:
    """One line per option value of the split-by dimension (period on the X axis)."""
    src       = config.get("source") or {}
    de_uid    = dim_de.get("uid", "")
    prog_uid  = dim_de.get("prog_uid", "") or m.get("prog_uid", "") or src.get("prog_uid", "")
    is_tea    = bool(dim_de.get("is_tea"))
    metric_stg = m.get("stage_uid", "") or src.get("stage_uid", "")
    stg_uid   = dim_de.get("stage_uid", "") or metric_stg
    dim_token = de_uid if is_tea else f"{stg_uid}.{de_uid}"
    opt_js    = _json.dumps(dim_de.get("options", []))
    extra     = ChartPlugin._extra_params(config)
    chart_opts = _chartjs_options(po)
    pal        = _palette_js(color_scheme)
    tension    = "0.3" if _po(po, "line_tension", "Smooth") == "Smooth" else "0"
    fill       = _po(po, "fill_area", "None") == "Fill"

    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const DIM_OPTIONS = {opt_js};
          const peIdx  = d.headers.findIndex(h => h.name === 'pe');
          const catIdx = d.headers.findIndex(h =>
            h.name === '{stg_uid}.{de_uid}' || h.name === '{de_uid}');
          const valIdx = d.headers.findIndex(h => h.name === 'value');
          const periods = [...new Set(d.rows.map(r => r[peIdx]))].sort();
          if (catIdx < 0) {{
            throw new Error('Dimension column not found in API response. Check stage/DE uid.');
          }}
          const catCodesFromData = [...new Set(d.rows.map(r => r[catIdx]))];
          const catCodes = (DIM_OPTIONS.length &&
            DIM_OPTIONS.some(o => catCodesFromData.includes(o.code)))
            ? DIM_OPTIONS.map(o => o.code).filter(c => catCodesFromData.includes(c))
            : catCodesFromData;
          const nameOf = code => {{
            const opt = DIM_OPTIONS.find(o => o.code === code);
            if (opt) return opt.name;
            return d.metaData?.items?.[code]?.name || code;
          }};
          const grouped = {{}};
          d.rows.forEach(r => {{
            const cat=r[catIdx],p=r[peIdx],v=parseFloat(r[valIdx])||0;
            if(!grouped[cat]) grouped[cat]={{}};
            grouped[cat][p]=(grouped[cat][p]||0)+v;
          }});
          const datasets = catCodes.map((cat,i) => ({{
            label:nameOf(cat),
            data:periods.map(p=>grouped[cat]?.[p]||0),
            borderColor:PALETTE[i%PALETTE.length],
            backgroundColor:{'PALETTE[i%PALETTE.length]+"30"' if fill else "'transparent'"},
            fill:{_jsbool(fill)}, tension:{tension}, pointRadius:4, pointHoverRadius:6,
          }}));
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type:'line', data:{{labels:periods.map(formatPeriodLabel),datasets}}, options:{chart_opts}
          }});
        }}
        async function initChart{n}(ou, pe) {{
          document.getElementById('loading{n}').style.display='none';
          const cvs=document.getElementById('chart{n}');
          cvs.style.display='block';
          if (PREVIEW) {{
            const b=document.getElementById('demoBanner{n}');
            if(b) b.style.display='block';
            renderChart{n}Sample(cvs); return;
          }}
          document.getElementById('demoBanner{n}').style.display='none';
          const errEl=document.getElementById('error{n}');
          errEl.style.display='none';
          try {{
            const rpe = resolveRelativePeriod(pe);
            const d = await dhis2Get(
              'api/analytics/events/aggregate/{prog_uid}'
              +'?stage={stg_uid}'
              +'&dimension={dim_token}'
              +'&dimension=pe:'+encodeURIComponent(rpe)
              +'&dimension=ou:'+encodeURIComponent(ou)+'{extra}'
            );
            if (!d.rows||!d.rows.length){{errEl.textContent='No data.';errEl.style.display='block';return;}}
            renderChart{n}Real(cvs, d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);errEl.textContent='Failed: '+e.message;errEl.style.display='block';
          }}
        }}"""


# ── Plugin class ───────────────────────────────────────────────────────────────

class LineTrendPlugin(ChartPlugin):
    id          = "line_trend"
    label       = "Line — trend over time"
    icon        = "📈"
    description = "Line chart tracking values over time with full formatting options"
    preview_id  = "line_single"

    metrics = [
        MetricControl(
            id="metric",
            label="Metric",
            max_count=1,
            allowed_types=("tracker_numeric", "tracker_option", "aggregate", "indicator"),
            default_agg="SUM",
        )
    ]
    dimensions = [
        DimensionControl(
            id="dimension",
            label="Split by (one line per value)",
            allowed_types=("tracker_option", "tracker_numeric", "aggregate", "indicator"),
            required=False,
            hint="Option-set DE/PA: each option value becomes its own line",
        )
    ]
    options = [
        SelectControl("color_scheme", "Color scheme", ("Default", "DHIS2", "Warm", "Cool", "Earth", "Pastel"), "Default"),
        SelectControl("line_tension", "Line curve",   ("Smooth", "Straight"),                                   "Smooth"),
        SelectControl("fill_area",    "Fill area",    ("None", "Fill"),                                         "None"),
        SelectControl("show_legend",  "Legend",       ("Off", "Bottom", "Top", "Right"),                        "Bottom"),
        SelectControl("show_values",  "Data labels",  ("Off", "On"),                                             "Off"),
        SelectControl("y_format",     "Y format",     ("Default", "1,234", "1.2K", "%"),                        "Default"),
        SelectControl("x_rotation",   "X rotation",   ("0", "45", "90"),                                         "0"),
        SelectControl("log_scale",    "Log scale",    ("Off", "On"),                                             "Off"),
    ]
    time_grain = TimeGrainControl(default="Monthly")

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        po           = config.get("plugin_options") or {}
        metrics      = config.get("metrics", [])
        m            = metrics[0] if metrics else {}
        color_scheme = _po(po, "color_scheme", "Default")
        dim_de       = (config.get("dimensions") or {}).get("dimension") or {}

        sample = _sample_js(n, po, color_scheme, metric_label=m.get("name") or "Series A")
        if dim_de.get("uid"):
            real = _real_js_dim(n, config, m, dim_de, po, color_scheme)
        else:
            real = _real_js(n, config, m, po, color_scheme)
        return sample + "\n" + real
