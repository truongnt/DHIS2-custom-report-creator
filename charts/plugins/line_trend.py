"""
LineTrendPlugin — monthly/quarterly/yearly line chart for a single metric.

Supported DE types: tracker_numeric, aggregate, indicator.

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
    SelectControl,
    TimeGrainControl,
)

# ── Palettes (identical to bar.py) ────────────────────────────────────────────

_PALETTES: dict[str, list[str]] = {
    "Default": ["#e74c3c","#3498db","#f39c12","#27ae60","#9b59b6","#1abc9c","#e67e22","#2980b9"],
    "DHIS2":   ["#147cd7","#00b5ae","#ff5722","#8bc34a","#e91e63","#ff9800","#9c27b0","#2196f3"],
    "Warm":    ["#f39c12","#e74c3c","#e67e22","#d35400","#c0392b","#a04000","#f1c40f","#ca6f1e"],
    "Cool":    ["#2980b9","#3498db","#1abc9c","#16a085","#5dade2","#48c9b0","#76d7c4","#85c1e9"],
    "Earth":   ["#6e2f21","#935116","#7d6608","#1e8449","#4a235a","#117a65","#b9770e","#17202a"],
    "Pastel":  ["#f1948a","#7fb3d3","#f8c471","#82e0aa","#c39bd3","#73c6b6","#f0b27a","#abebc6"],
}


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
          datalabels: {{
            display: {_jsbool(show_values)},
            formatter: v => ({y_fmt_fn})(v),
            font: {{ size: 10 }},
            color: '#333',
            backgroundColor: 'rgba(255,255,255,0.7)',
            borderRadius: 3,
            padding: 2,
          }},
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


def _sample_js(n: int, po: dict, color_scheme: str = "Default") -> str:
    tension_raw = _po(po, "line_tension", "Smooth")
    tension     = "0.3" if tension_raw == "Smooth" else "0"
    fill        = _po(po, "fill_area", "None") == "Fill"
    fill_js     = "PALETTE[0]+'30'" if fill else "'transparent'"
    chart_opts  = _chartjs_options(po)
    pal         = _palette_js(color_scheme)
    scale       = max(1, int(_po(po, "demo_y_scale", 1)))
    raw         = [95,110,88,130,155,142,168,145,120,158,174,162]
    da          = [v * scale for v in raw]
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
                label: 'Series A',
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
                label: 'Value',
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
            const vals=labels.map(p=>{{const row=d.rows.find(r=>r[peIdx]===p);return row?parseFloat(row[valIdx])||0:0;}});
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
            const vals=labels.map(p=>{{const row=d.rows.find(r=>r[peIdx]===p);return row?parseFloat(row[valIdx])||0:0;}});
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
            allowed_types=("tracker_numeric", "aggregate", "indicator"),
            default_agg="SUM",
        )
    ]
    dimensions = []
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

        sample = _sample_js(n, po, color_scheme)
        real   = _real_js(n, config, m, po, color_scheme)
        return sample + "\n" + real
