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
label_pos    : Inside | Outside   (where value labels sit relative to the slice)
show_empty   : Hide | Show        (Hide drops zero-value categories from slices + legend)
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

# Distinct-adjacent categorical palettes, shared across all chart plugins.
from charts.plugins.shared_js import PALETTES as _PALETTES


def _po(po: dict, key: str, default):
    return po.get(key, default) if po else default


def _metric_name(m: dict) -> str:
    """Legend/slice label for a metric: the user's alias if set, else the real name/uid."""
    return (m.get("alias") or "").strip() or m.get("name") or m.get("uid", "")


def _jsbool(v) -> str:
    return "true" if v else "false"


def _palette_js(color_scheme: str) -> str:
    colors = _PALETTES.get(color_scheme, _PALETTES["Default"])
    return f"const PALETTE={_json.dumps(colors)};"


def _chartjs_options(po: dict) -> str:
    legend_raw  = _po(po, "show_legend", "Bottom")
    show_legend = legend_raw != "Off"
    legend_pos  = legend_raw.lower() if show_legend else "bottom"
    show_values = _po(po, "show_values", "Off")    # "Off" | "Percent" | "Value"
    label_pos   = _po(po, "label_pos",   "Inside") # "Inside" | "Outside"
    chart_type  = _po(po, "chart_type",  "Pie")    # "Pie" | "Donut"
    cutout      = "50%" if chart_type == "Donut" else "0%"

    # Value labels are drawn by the registered `showValues` plugin (datalabels is not
    # registered — see shared script). mode = percent|value; pos = inside|outside.
    sv_display = "true" if show_values in ("Percent", "Value") else "false"
    sv_mode    = "percent" if show_values == "Percent" else "value"
    outside    = label_pos == "Outside"
    sv_pos     = "outside" if outside else "inside"
    sv_color   = "#333" if outside else "#fff"
    layout_pad = "28" if outside else "0"   # room so outside labels aren't clipped

    return f"""{{
        responsive: true,
        maintainAspectRatio: false,
        cutout: '{cutout}',
        layout: {{ padding: {layout_pad} }},
        plugins: {{
          legend: {{ display: {_jsbool(show_legend)}, position: '{legend_pos}' }},
          datalabels: {{ display: false }},
          showValues: {{ display: {sv_display}, mode: '{sv_mode}', pos: '{sv_pos}',
                         color: '{sv_color}', fontSize: 12 }},
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


def _sample_js(n: int, po: dict, color_scheme: str = "Default", labels=None) -> str:
    chart_opts = _chartjs_options(po)
    pal        = _palette_js(color_scheme)
    # Label the demo slices with the selected metric/category names so the preview is
    # representative (indicators have no fixture, so this sample is what the user sees).
    _lbls = [s for s in (labels or []) if s] or ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
    _lbls = _lbls[:8]
    _demo = [35, 25, 20, 12, 8, 6, 4, 3][:len(_lbls)]
    labels_js = _json.dumps(_lbls)
    data_js   = _json.dumps(_demo)
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'pie',
            data: {{
              labels: {labels_js},
              datasets: [{{
                data: {data_js},
                backgroundColor: {labels_js}.map((_,i)=>PALETTE[i%PALETTE.length])
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
    # Hide categories with no value so empty slices don't clutter the pie or its legend.
    hide_empty_js = _jsbool(_po(po, "show_empty", "Hide") == "Hide")

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
          if ({hide_empty_js}) combined = combined.filter(x => x.v > 0);
          {sort_limit}
          if (!combined.length) {{
            const errEl = document.getElementById('error{n}');
            errEl.textContent = 'No non-zero values to plot.'; errEl.style.display = 'block';
            return;
          }}
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


def _real_js_metrics(n: int, metrics: list, config: dict, po: dict, color_scheme: str) -> str:
    """Pie of MULTIPLE dx metrics (indicators / aggregates): one slice per metric, labelled
    by the metric's alias/name. Queried as dx via analytics.json (period + OU as filters)."""
    uids   = [m["uid"] for m in metrics]
    labels = [_metric_name(m) for m in metrics]
    dx     = ";".join(uids)
    uids_js   = _json.dumps(uids)
    labels_js = _json.dumps(labels)
    chart_opts = _chartjs_options(po)
    pal        = _palette_js(color_scheme)
    hide_empty_js = _jsbool(_po(po, "show_empty", "Hide") == "Hide")
    filt = ChartPlugin._filter_params(config)
    filt = ("&" + filt) if filt else ""
    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const UIDS = {uids_js}, LABELS = {labels_js};
          const dxIdx  = d.headers.findIndex(h => h.name === 'dx');
          const valIdx = d.headers.findIndex(h => h.name === 'value');
          const byDx = {{}};
          (d.rows||[]).forEach(r => {{ byDx[r[dxIdx]] = (byDx[r[dxIdx]]||0) + (parseFloat(r[valIdx])||0); }});
          let combined = UIDS.map((u,i) => ({{l: LABELS[i], v: byDx[u]||0}}));
          if ({hide_empty_js}) combined = combined.filter(x => x.v > 0);
          if (!combined.length) {{
            const errEl = document.getElementById('error{n}');
            errEl.textContent = 'No non-zero values to plot.'; errEl.style.display = 'block'; return;
          }}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'pie',
            data: {{
              labels: combined.map(x => x.l),
              datasets: [{{ data: combined.map(x => x.v),
                            backgroundColor: combined.map((_,i)=>PALETTE[i%PALETTE.length]) }}]
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
            const d = await dhis2Get(
              'api/analytics.json?dimension=dx:{dx}'
              +'&filter=ou:'+encodeURIComponent(ou)
              +'&filter=pe:'+encodeURIComponent(pe)
              +'&displayProperty=NAME{filt}'
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
            label="Values (indicators → one slice each) or leave for event count",
            max_count=10,
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
            required=False,
            hint="Option-set DE: one slice per option value. (Or pick multiple indicators above.)",
        )
    ]
    options = [
        SelectControl("color_scheme", "Color scheme", ("Default", "DHIS2", "Warm", "Cool", "Earth", "Pastel"), "Default"),
        SelectControl("chart_type",   "Chart type",   ("Pie", "Donut"),                                        "Pie"),
        SelectControl("show_legend",  "Legend",       ("Off", "Bottom", "Top", "Right"),                       "Bottom"),
        SelectControl("show_values",  "Labels",       ("Off", "Percent", "Value"),                             "Off"),
        SelectControl("label_pos",    "Label position", ("Inside", "Outside"),                                 "Inside"),
        SelectControl("show_empty",   "Empty slices", ("Hide", "Show"),                                        "Hide"),
    ]
    time_grain = None

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        po   = config.get("plugin_options") or {}
        dims = config.get("dimensions") or {}
        dim_de  = dims.get("dimension")
        source  = config.get("source") or {}
        color_scheme = _po(po, "color_scheme", "Default")

        # Multi-metric pie: multiple dx metrics (indicators/aggregates) → one slice each,
        # legend = each metric's alias. Used when there's no option-set split dimension.
        dim_is_opt = bool(dim_de and dim_de.get("uid") and dim_de.get("type") == "tracker_option")
        dx_metrics = [m for m in (config.get("metrics") or [])
                      if m.get("uid") and m.get("type") in ("aggregate", "indicator")]
        if not dim_is_opt and dx_metrics:
            sample = _sample_js(n, po, color_scheme,
                                labels=[_metric_name(m) for m in dx_metrics])
            real   = _real_js_metrics(n, dx_metrics, config, po, color_scheme)
            return sample + "\n" + real

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

        sample = _sample_js(n, po, color_scheme,
                            labels=[o.get("name") for o in options if o.get("name")])
        real   = _real_js(n, de_uid, prog_uid, stg_uid, config, options, po, color_scheme)
        return sample + "\n" + real
