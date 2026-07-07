"""
CombinedBarLinePlugin — Mixed bar + line chart with two data sources.

First metric renders as bars, second metric as a line overlay.
Supports tracker_numeric, aggregate, and indicator source types.

plugin_options keys
-------------------
color_scheme : Default | DHIS2 | Warm | Cool | Earth | Pastel
show_legend  : Off | Bottom | Top | Right
show_values  : Off | On
y_format     : Default | 1,234 | 1.2K | %
x_rotation   : 0 | 45 | 90
dual_y_axis  : No | Yes  (separate left/right Y axes for bar vs line)
x_title      : str
y_title      : str
"""
from __future__ import annotations

import json as _json

from charts.plugins.base import (
    ChartPlugin,
    MetricControl,
    SelectControl,
    TimeGrainControl,
)

# ── Palettes ──────────────────────────────────────────────────────────────────

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
    dual_y      = _po(po, "dual_y_axis", "No") == "Yes"
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

    if dual_y:
        scales_block = f"""{{
          x: {{
            ticks: {{ minRotation: {x_rotation}, maxRotation: {x_rotation},
                     autoSkip: true, autoSkipPadding: 8 }},{x_title_opt}
          }},
          y: {{
            type: 'linear',
            position: 'left',
            beginAtZero: true,
            ticks: {{ callback: {y_fmt_fn} }},{y_title_opt}
          }},
          y2: {{
            type: 'linear',
            position: 'right',
            beginAtZero: true,
            grid: {{ drawOnChartArea: false }},
          }},
        }}"""
    else:
        scales_block = f"""{{
          x: {{
            ticks: {{ minRotation: {x_rotation}, maxRotation: {x_rotation},
                     autoSkip: true, autoSkipPadding: 8 }},{x_title_opt}
          }},
          y: {{
            beginAtZero: true,
            ticks: {{ callback: {y_fmt_fn} }},{y_title_opt}
          }},
        }}"""

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
          }},
          tooltip: {{
            mode: 'index',
            intersect: false,
            callbacks: {{
              label: ctx => ctx.dataset.label + ': ' + ({y_fmt_fn})(ctx.parsed.y),
            }},
          }},
        }},
        scales: {scales_block},
      }}"""


def _sample_js(n: int, po: dict, color_scheme: str = "Default",
               metric_labels=None) -> str:
    chart_opts  = _chartjs_options(po)
    pal         = _palette_js(color_scheme)
    dual_y      = _po(po, "dual_y_axis", "No") == "Yes"
    y2_opt      = ", yAxisID: 'y2'" if dual_y else ""
    demo_y      = _po(po, "demo_y_scale", 1)
    _CASES_BASE = [120, 145, 98, 167, 203, 189, 212, 176, 143, 198, 221, 185]
    _RATE_BASE  = [2.4, 2.9, 1.96, 3.34, 4.06, 3.78, 4.24, 3.52, 2.86, 3.96, 4.42, 3.7]
    import json as _j
    _ml         = [s for s in (metric_labels or []) if s]
    label_bar   = _j.dumps(_ml[0] if len(_ml) >= 1 else "Cases")
    label_line  = _j.dumps(_ml[1] if len(_ml) >= 2 else "Rate")
    cases_data = _j.dumps([int(v * demo_y) for v in _CASES_BASE])
    rate_data  = _j.dumps([round(v * demo_y, 2) for v in _RATE_BASE])
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{
              labels: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
              datasets: [
                {{type:'bar',  label:{label_bar},
                  data:{cases_data},
                  backgroundColor:PALETTE[1], order:2}},
                {{type:'line', label:{label_line},
                  data:{rate_data},
                  borderColor:PALETTE[0], backgroundColor:'transparent',
                  tension:0.3, order:1{y2_opt}}}
              ]
            }},
            options: {chart_opts}
          }});
        }}"""


def _fetch_call(s: dict, config: dict) -> str:
    extra = ChartPlugin._extra_params(config)
    t = s.get("type")
    if t == "tracker_numeric":
        return (
            f"dhis2Get('api/analytics/events/aggregate/{s['prog_uid']}?"
            f"stage={s['stage_uid']}&value={s['uid']}&aggregationType=SUM"
            f"&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou)+'{extra}')"
        )
    elif t == "tracker_option":
        # Option-set tracker DE → EVENT COUNT per period for its stage.
        return (
            f"dhis2Get('api/analytics/events/aggregate/{s['prog_uid']}?"
            f"stage={s['stage_uid']}"
            f"&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou)+'{extra}')"
        )
    else:
        return (
            f"dhis2Get('api/analytics.json?dimension=dx:{s['uid']}"
            f"&dimension=pe:'+encodeURIComponent(pe)+'&dimension=ou:'+encodeURIComponent(ou)+'&displayProperty=NAME{extra}')"
        )


def _real_js(n: int, s0: dict, s1: dict, config: dict, po: dict, color_scheme: str) -> str:
    fetch0      = _fetch_call(s0, config)
    fetch1      = _fetch_call(s1, config)
    name0       = s0.get("name", "Bar").replace('"', "'")
    name1       = s1.get("name", "Line").replace('"', "'")
    chart_opts  = _chartjs_options(po)
    pal         = _palette_js(color_scheme)
    dual_y      = _po(po, "dual_y_axis", "No") == "Yes"
    y2_opt      = ", yAxisID: 'y2'" if dual_y else ""

    return f"""\
        function renderChart{n}Real(cvs, results) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          function getVals(d, periods) {{
            const peIdx  = d.headers.findIndex(h => h.name === 'pe');
            const valIdx = d.headers.findIndex(h => h.name === 'value');
            return periods.map(p => {{
              return d.rows.filter(r => r[peIdx] === p)
                           .reduce((s, r) => s + (parseFloat(r[valIdx]) || 0), 0);
            }});
          }}
          const allPeriods = [...new Set(
            results.flatMap(d => {{
              const idx = d.headers.findIndex(h => h.name === 'pe');
              return d.rows.map(r => r[idx]);
            }})
          )].sort();
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{
              labels: allPeriods.map(formatPeriodLabel),
              datasets: [
                {{type:'bar',  label:'{name0}', data:getVals(results[0], allPeriods),
                  backgroundColor:PALETTE[1], order:2}},
                {{type:'line', label:'{name1}', data:getVals(results[1], allPeriods),
                  borderColor:PALETTE[0], backgroundColor:'transparent',
                  tension:0.3, order:1{y2_opt}}}
              ]
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
            const results = await Promise.all([
              {fetch0},
              {fetch1}
            ]);
            if (results.every(d=>!d.rows||!d.rows.length)){{errEl.textContent='No data.';errEl.style.display='block';return;}}
            renderChart{n}Real(cvs, results);
          }} catch(e) {{
            console.error('[Chart{n}]',e);errEl.textContent='Failed: '+e.message;errEl.style.display='block';
          }}
        }}"""


# ── Plugin class ───────────────────────────────────────────────────────────────

class CombinedBarLinePlugin(ChartPlugin):
    id          = "combined_bar_line"
    label       = "Combined bar + line"
    icon        = "🔀"
    description = "First metric as bars, second metric as a line overlay — two sources required"
    preview_id  = "combined_bar_line"

    metrics = [
        MetricControl(
            id="metric_bar",
            label="Bar metric",
            max_count=1,
            allowed_types=("tracker_numeric", "tracker_option", "aggregate", "indicator"),
            default_agg="SUM",
            required=True,
        ),
        MetricControl(
            id="metric_line",
            label="Line metric",
            max_count=1,
            allowed_types=("tracker_numeric", "tracker_option", "aggregate", "indicator"),
            default_agg="SUM",
            required=True,
        ),
    ]
    dimensions = []
    options = [
        SelectControl("color_scheme", "Color scheme", ("Default", "DHIS2", "Warm", "Cool", "Earth", "Pastel"), "Default"),
        SelectControl("show_legend",  "Legend",       ("Off", "Bottom", "Top", "Right"),                       "Bottom"),
        SelectControl("show_values",  "Data labels",  ("Off", "On"),                                            "Off"),
        SelectControl("y_format",     "Y format",     ("Default", "1,234", "1.2K", "%"),                       "Default"),
        SelectControl("x_rotation",   "X rotation",   ("0", "45", "90"),                                        "0"),
        SelectControl("dual_y_axis",  "Dual Y axis",  ("No", "Yes"),                                            "No"),
    ]
    time_grain = TimeGrainControl(default="Monthly")

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        po      = config.get("plugin_options") or {}
        sources = config.get("metrics", [])
        color_scheme = _po(po, "color_scheme", "Default")

        if len(sources) < 2:
            raise ValueError(
                f"CombinedBarLinePlugin requires exactly 2 metrics, got {len(sources)}"
            )

        s0, s1 = sources[0], sources[1]
        sample = _sample_js(n, po, color_scheme,
                            metric_labels=[s0.get("name"), s1.get("name")])
        real   = _real_js(n, s0, s1, config, po, color_scheme)
        return sample + "\n" + real
