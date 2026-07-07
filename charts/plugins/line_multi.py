"""
LineMultiPlugin — Line chart comparing multiple data sources over time.

Supports 2-3 metrics of types: tracker_numeric, aggregate, indicator.
Pure aggregate/indicator sources are batched into a single analytics.json call.
Mixed or tracker_numeric sources each get their own API call fetched in parallel.

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


def _sample_js(n: int, po: dict, color_scheme: str = "Default",
               metric_labels=None) -> str:
    _ml = [s for s in (metric_labels or []) if s]
    label_a = _json.dumps(_ml[0] if len(_ml) >= 1 else "Series A")
    label_b = _json.dumps(_ml[1] if len(_ml) >= 2 else "Series B")
    tension_raw = _po(po, "line_tension", "Smooth")
    tension     = "0.3" if tension_raw == "Smooth" else "0"
    fill        = _po(po, "fill_area", "None") == "Fill"
    fill_bg0    = "PALETTE[0]+'30'" if fill else "'transparent'"
    fill_bg1    = "PALETTE[1]+'30'" if fill else "'transparent'"
    chart_opts  = _chartjs_options(po)
    pal         = _palette_js(color_scheme)
    scale       = max(1, int(_po(po, "demo_y_scale", 1)))
    raw_a       = [95,110,88,130,155,142,168,145,120,158,174,162]
    raw_b       = [60,75,55,90,105,98,115,100,82,110,128,118]
    da          = [v * scale for v in raw_a]
    db          = [v * scale for v in raw_b]
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'line',
            data: {{
              labels: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
              datasets: [
                {{
                  label: {label_a},
                  data: {da},
                  borderColor: PALETTE[0], backgroundColor: {fill_bg0},
                  fill: {_jsbool(fill)}, tension: {tension}, pointRadius: 4, pointHoverRadius: 6,
                }},
                {{
                  label: {label_b},
                  data: {db},
                  borderColor: PALETTE[1], backgroundColor: {fill_bg1},
                  fill: {_jsbool(fill)}, tension: {tension}, pointRadius: 4, pointHoverRadius: 6,
                }}
              ]
            }},
            options: {chart_opts}
          }});
        }}"""


def _real_js_all_aggregate(n: int, sources: list[dict], config: dict, po: dict,
                            color_scheme: str) -> str:
    extra       = ChartPlugin._extra_params(config)
    de_ids      = ";".join(s["uid"] for s in sources)
    de_names_js = (
        "{"
        + ",".join(f'"{s["uid"]}":"{s["name"].replace(chr(34), chr(39))}"' for s in sources)
        + "}"
    )
    chart_opts  = _chartjs_options(po)
    pal         = _palette_js(color_scheme)
    tension_raw = _po(po, "line_tension", "Smooth")
    tension     = "0.3" if tension_raw == "Smooth" else "0"
    fill        = _po(po, "fill_area", "None") == "Fill"
    bg_expr     = "PALETTE[i%PALETTE.length]+'30'" if fill else "'transparent'"

    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const DE_NAMES = {de_names_js};
          const dxIdx  = d.headers.findIndex(h => h.name === 'dx');
          const peIdx  = d.headers.findIndex(h => h.name === 'pe');
          const valIdx = d.headers.findIndex(h => h.name === 'value');
          const dxIds  = [...new Set(d.rows.map(r => r[dxIdx]))];
          const periods = [...new Set(d.rows.map(r => r[peIdx]))].sort();
          const datasets = dxIds.map((dx, i) => {{
            const label = (d.metaData && d.metaData.items && d.metaData.items[dx])
              ? d.metaData.items[dx].name : (DE_NAMES[dx] || dx);
            const vals = periods.map(p => {{
              const row = d.rows.find(r => r[dxIdx] === dx && r[peIdx] === p);
              return row ? parseFloat(row[valIdx]) || 0 : 0;
            }});
            return {{
              label, data: vals,
              borderColor: PALETTE[i % PALETTE.length],
              backgroundColor: {bg_expr},
              fill: {_jsbool(fill)}, tension: {tension}, pointRadius: 4, pointHoverRadius: 6,
            }};
          }});
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'line',
            data: {{ labels: periods.map(formatPeriodLabel), datasets }},
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
            const d = await dhis2Get(
              'api/analytics.json?dimension=dx:{de_ids}'
              +'&dimension=pe:'+encodeURIComponent(pe)
              +'&dimension=ou:'+encodeURIComponent(ou)
              +'&displayProperty=NAME{extra}'
            );
            if (!d.rows||!d.rows.length){{errEl.textContent='No data.';errEl.style.display='block';return;}}
            renderChart{n}Real(cvs, d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);errEl.textContent='Failed: '+e.message;errEl.style.display='block';
          }}
        }}"""


def _real_js_mixed(n: int, sources: list[dict], config: dict, po: dict,
                   color_scheme: str) -> str:
    extra = ChartPlugin._extra_params(config)
    fetch_calls = []
    for s in sources:
        if s["type"] == "tracker_numeric":
            fetch_calls.append(
                f"dhis2Get('api/analytics/events/aggregate/{s['prog_uid']}?"
                f"stage={s['stage_uid']}&value={s['uid']}&aggregationType=SUM"
                f"&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou)+'{extra}')"
            )
        elif s["type"] == "tracker_option":
            # Option-set tracker DE → EVENT COUNT per period for its stage.
            fetch_calls.append(
                f"dhis2Get('api/analytics/events/aggregate/{s['prog_uid']}?"
                f"stage={s['stage_uid']}"
                f"&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou)+'{extra}')"
            )
        else:
            fetch_calls.append(
                f"dhis2Get('api/analytics.json?dimension=dx:{s['uid']}"
                f"&dimension=pe:'+encodeURIComponent(pe)+'&dimension=ou:'+encodeURIComponent(ou)+'&displayProperty=NAME{extra}')"
            )
    fetch_array = ",\n              ".join(fetch_calls)
    de_names_js = (
        "["
        + ", ".join(f'"{s["name"].replace(chr(34), chr(39))}"' for s in sources)
        + "]"
    )
    chart_opts  = _chartjs_options(po)
    pal         = _palette_js(color_scheme)
    tension_raw = _po(po, "line_tension", "Smooth")
    tension     = "0.3" if tension_raw == "Smooth" else "0"
    fill        = _po(po, "fill_area", "None") == "Fill"
    bg_expr     = "PALETTE[i%PALETTE.length]+'30'" if fill else "'transparent'"

    return f"""\
        function renderChart{n}Real(cvs, results) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const DE_NAMES = {de_names_js};
          const allPeriods = [...new Set(
            results.flatMap(d => {{
              const idx = d.headers.findIndex(h => h.name === 'pe');
              return d.rows.map(r => r[idx]);
            }})
          )].sort();
          const datasets = results.map((d, i) => {{
            const peIdx  = d.headers.findIndex(h => h.name === 'pe');
            const valIdx = d.headers.findIndex(h => h.name === 'value');
            const vals = allPeriods.map(p => {{
              return d.rows.filter(r => r[peIdx] === p)
                           .reduce((s, r) => s + (parseFloat(r[valIdx]) || 0), 0);
            }});
            return {{
              label: DE_NAMES[i], data: vals,
              borderColor: PALETTE[i % PALETTE.length],
              backgroundColor: {bg_expr},
              fill: {_jsbool(fill)}, tension: {tension}, pointRadius: 4, pointHoverRadius: 6,
            }};
          }});
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'line',
            data: {{ labels: allPeriods.map(formatPeriodLabel), datasets }},
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
              {fetch_array}
            ]);
            if (results.every(d=>!d.rows||!d.rows.length)){{errEl.textContent='No data.';errEl.style.display='block';return;}}
            renderChart{n}Real(cvs, results);
          }} catch(e) {{
            console.error('[Chart{n}]',e);errEl.textContent='Failed: '+e.message;errEl.style.display='block';
          }}
        }}"""


# ── Plugin class ───────────────────────────────────────────────────────────────

class LineMultiPlugin(ChartPlugin):
    id          = "line_multi"
    label       = "Line — compare multiple"
    icon        = "📈"
    description = "Line chart with one series per selected data element, up to 3 sources"
    preview_id  = "line_multi"

    metrics = [
        MetricControl(
            id="metrics",
            label="Metrics to compare",
            max_count=3,
            allowed_types=("tracker_numeric", "tracker_option", "aggregate", "indicator"),
            default_agg="SUM",
            required=True,
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
        po      = config.get("plugin_options") or {}
        sources = config.get("metrics", [])
        color_scheme = _po(po, "color_scheme", "Default")

        if len(sources) < 2:
            raise ValueError(
                f"LineMultiPlugin requires at least 2 metrics, got {len(sources)}"
            )
        if len(sources) > 3:
            sources = sources[:3]

        sample  = _sample_js(n, po, color_scheme,
                             metric_labels=[s.get("name") for s in sources if s.get("name")])
        all_agg = all(s.get("type", "aggregate") in ("aggregate", "indicator") for s in sources)
        if all_agg:
            real = _real_js_all_aggregate(n, sources, config, po, color_scheme)
        else:
            real = _real_js_mixed(n, sources, config, po, color_scheme)

        return sample + "\n" + real
