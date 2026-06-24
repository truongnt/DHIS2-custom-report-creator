"""
PieCatPlugin — Pie / Donut chart broken down by option-set category.

Sums all values per category across the selected period and renders a pie.
Only compatible with tracker_option DEs (those that have an option set).

plugin_options keys
-------------------
color_scheme : Default | DHIS2 | Warm | Cool | Earth | Pastel
chart_type   : Pie | Donut
show_legend  : Off | Bottom | Top | Right
show_values  : Off | Percent | Value
"""
from __future__ import annotations

import json as _json

from charts.plugins.base import (
    ChartPlugin,
    DimensionControl,
    MetricControl,
    SelectControl,
)

# ── Palettes ──────────────────────────────────────────────────────────────────

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
    show_values = _po(po, "show_values", "Off")   # "Off" | "Percent" | "Value"
    chart_type  = _po(po, "chart_type",  "Pie")   # "Pie" | "Donut"
    cutout      = "50%" if chart_type == "Donut" else "0%"

    if show_values == "Percent":
        dl_display   = "true"
        dl_formatter = "(v, ctx) => { const total = ctx.chart.data.datasets[0].data.reduce((s,x)=>s+x,0); return total ? (v/total*100).toFixed(1)+'%' : '0%'; }"
    elif show_values == "Value":
        dl_display   = "true"
        dl_formatter = "v => v.toLocaleString()"
    else:
        dl_display   = "false"
        dl_formatter = "v => v"

    return f"""{{
        responsive: true,
        maintainAspectRatio: false,
        cutout: '{cutout}',
        plugins: {{
          legend: {{ display: {_jsbool(show_legend)}, position: '{legend_pos}' }},
          datalabels: {{
            display: {dl_display},
            formatter: {dl_formatter},
            font: {{ size: 11, weight: 'bold' }},
            color: '#fff',
          }},
          tooltip: {{
            callbacks: {{
              label: ctx => {{
                const total = ctx.chart.data.datasets[0].data.reduce((s,x)=>s+x,0);
                const pct = total ? (ctx.parsed/total*100).toFixed(1)+'%' : '0%';
                return ctx.label + ': ' + ctx.parsed.toLocaleString() + ' (' + pct + ')';
              }},
            }},
          }},
        }},
      }}"""


def _sample_js(n: int, po: dict, color_scheme: str = "Default") -> str:
    chart_opts = _chartjs_options(po)
    pal        = _palette_js(color_scheme)
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'pie',
            data: {{
              labels: ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon'],
              datasets: [{{
                data: [35, 25, 20, 12, 8],
                backgroundColor: [PALETTE[0],PALETTE[1],PALETTE[2],PALETTE[3],PALETTE[4]]
              }}]
            }},
            options: {chart_opts}
          }});
        }}"""


def _real_js(n: int, de_uid: str, prog_uid: str, stg_uid: str,
             config: dict, options: list, po: dict, color_scheme: str) -> str:
    options_js  = _json.dumps(options)
    extra       = ChartPlugin._extra_params(config)
    sort_limit  = ChartPlugin._sort_limit_js(config, "combined")
    chart_opts  = _chartjs_options(po)
    pal         = _palette_js(color_scheme)

    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const DIM_OPTIONS = {options_js};
          const catIdx = d.headers.findIndex(h => h.name === '{de_uid}');
          const valIdx = d.headers.findIndex(h => h.name === 'value');

          const totals = {{}};
          d.rows.forEach(r => {{
            const cat = r[catIdx];
            totals[cat] = (totals[cat] || 0) + (parseFloat(r[valIdx]) || 0);
          }});

          const catCodes = DIM_OPTIONS.length
            ? DIM_OPTIONS.map(o => o.code)
            : Object.keys(totals);
          const nameOf = code => {{
            const opt = DIM_OPTIONS.find(o => o.code === code);
            return opt ? opt.name : (d.metaData?.items?.[code]?.name || code);
          }};

          const labels = catCodes.map(nameOf);
          const vals   = catCodes.map(c => totals[c] || 0);
          let combined = labels.map((l, i) => ({{l, v: vals[i]}}));
          {sort_limit}
          const sortedLabels = combined.map(x => x.l);
          const sortedVals   = combined.map(x => x.v);
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'pie',
            data: {{
              labels: sortedLabels,
              datasets: [{{
                data: sortedVals,
                backgroundColor: PALETTE.slice(0, sortedLabels.length)
              }}]
            }},
            options: {chart_opts}
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
              +'&dimension={stg_uid}.{de_uid}'
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

class PieCatPlugin(ChartPlugin):
    id          = "pie_cat"
    label       = "Pie — by category"
    icon        = "🥧"
    description = "Pie or donut chart: breakdown by option-set category for the selected period"
    preview_id  = "pie"

    metrics = [
        MetricControl(
            id="metric",
            label="Value (optional — leave empty for event count)",
            max_count=1,
            allowed_types=("tracker_numeric", "aggregate", "indicator"),
            default_agg="SUM",
            show_agg_picker=True,
            required=False,
        )
    ]
    dimensions = [
        DimensionControl(
            id="dimension",
            label="Split by (pie slices)",
            allowed_types=("tracker_option", "tracker_numeric", "aggregate", "indicator"),
            required=True,
            hint="Option-set DE: each option value becomes one pie slice",
        )
    ]
    options = [
        SelectControl("color_scheme", "Color scheme", ("Default", "DHIS2", "Warm", "Cool", "Earth", "Pastel"), "Default"),
        SelectControl("chart_type",   "Chart type",   ("Pie", "Donut"),                                        "Pie"),
        SelectControl("show_legend",  "Legend",       ("Off", "Bottom", "Top", "Right"),                       "Bottom"),
        SelectControl("show_values",  "Labels",       ("Off", "Percent", "Value"),                             "Off"),
    ]
    time_grain = None

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        po   = config.get("plugin_options") or {}
        dims = config.get("dimensions") or {}
        dim_de  = dims.get("dimension")
        source  = config.get("source") or {}
        color_scheme = _po(po, "color_scheme", "Default")

        if dim_de and dim_de.get("uid"):
            de_uid   = dim_de["uid"]
            prog_uid = dim_de.get("prog_uid", "") or source.get("prog_uid", "")
            stg_uid  = dim_de.get("stage_uid", "") or source.get("stage_uid", "")
        else:
            metrics = config.get("metrics") or []
            m        = metrics[0] if metrics else {}
            de_uid   = m.get("uid", "") or config.get("de_uid", "")
            prog_uid = m.get("prog_uid", "") or source.get("prog_uid", "") or config.get("prog_uid", "")
            stg_uid  = m.get("stage_uid", "") or source.get("stage_uid", "") or config.get("stage_uid", "")

        options = dim_de.get("options", []) if dim_de else []

        sample = _sample_js(n, po, color_scheme)
        real   = _real_js(n, de_uid, prog_uid, stg_uid, config, options, po, color_scheme)
        return sample + "\n" + real
