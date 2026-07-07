"""
BarPlugin — Unified bar chart (replaces bar_monthly + stacked_cat + grouped_bar).

Modes (plugin_options.stack_mode):
  None   — simple bars or grouped side-by-side
  Stack  — stacked bars (stack: 'total')
  Expand — 100 % stacked bars

X Axis (plugin_options.x_axis):
  Period   — bars per time period (existing behaviour)
  Org Unit — bars per child org unit (uses USER_ORGUNIT_CHILDREN)

Data cases (Period x-axis):
  A. 1 tracker_numeric, no dim     → simple bar per period
  B. 1+ metrics, tracker_option dim → N series per option value
  C. 1+ aggregate/indicator         → 1 series per dx
  D. Mixed                          → parallel fetch, merge by period

Series limit (plugin_options.series_limit):
  All / 5 / 10 / 20 — limits the number of series shown (dim case only)

Color scheme (plugin_options.color_scheme):
  Default / DHIS2 / Warm / Cool / Earth / Pastel
"""
from __future__ import annotations

import json as _json
import re as _re
from pathlib import Path as _Path

from charts.plugins.base import (
    ChartPlugin,
    DimensionControl,
    MetricControl,
    SelectControl,
    TimeGrainControl,
)

# ── Colour palettes ────────────────────────────────────────────────────────────

# Distinct-adjacent categorical palettes, shared across all chart plugins.
from charts.plugins.shared_js import PALETTES as _PALETTES


def _palette_js(color_scheme: str) -> str:
    colors = _PALETTES.get(color_scheme, _PALETTES["Default"])
    return f"const PALETTE={_json.dumps(colors)};"


# ── Plugin class ───────────────────────────────────────────────────────────────

class BarPlugin(ChartPlugin):
    id          = "bar"
    label       = "Bar chart"
    icon        = "📊"
    description = (
        "Versatile bar chart: simple, grouped, stacked, or 100 % expanded. "
        "Supports tracker and aggregate sources."
    )
    preview_id  = "bar_monthly"

    metrics = [
        MetricControl(
            id="metrics",
            label="Metrics (1–3)",
            max_count=3,
            allowed_types=("tracker_numeric", "aggregate", "indicator"),
            default_agg="SUM",
            show_agg_picker=True,
            required=True,
        )
    ]
    dimensions = [
        DimensionControl(
            id="dimension",
            label="Split by (optional)",
            allowed_types=("tracker_option", "tracker_numeric", "aggregate", "indicator"),
            required=False,
            hint="Option-set DE → one series per option value",
        )
    ]
    options = [
        SelectControl("x_axis",       "X Axis",       ("Period", "Org Unit"),                                    "Period"),
        SelectControl("stack_mode",   "Stack mode",   ("None", "Stack", "Expand"),                              "None"),
        SelectControl("orientation",  "Orientation",  ("Vertical", "Horizontal"),                               "Vertical"),
        SelectControl("series_limit", "Series limit", ("All", "5", "10", "20"),                                 "All"),
        SelectControl("color_scheme", "Color scheme", ("Default", "DHIS2", "Warm", "Cool", "Earth", "Pastel"), "Default"),
    ]
    time_grain = TimeGrainControl(default="Monthly")

    # ── JS builder ─────────────────────────────────────────────────────────────

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        po      = config.get("plugin_options") or {}
        dims    = config.get("dimensions") or {}
        metrics = config.get("metrics") or []
        dim_de  = dims.get("dimension") or {}

        x_axis       = _po(po, "x_axis",       "Period")
        color_scheme = _po(po, "color_scheme",  "Default")
        has_dim      = bool(dim_de.get("uid"))
        dim_is_opt   = dim_de.get("type") == "tracker_option"
        all_agg      = all(m.get("type") in ("aggregate", "indicator") for m in metrics)
        metric_labels = [m.get("name") for m in metrics if m.get("name")]

        # ── Load fixture sample data (replaces hardcoded demo arrays) ────────
        fx = _load_fixture_sample(config)

        # ── Org Unit X Axis ──────────────────────────────────────────────────
        if x_axis == "Org Unit":
            sample_js = _sample_js_ou(n, po, color_scheme, metric_labels=metric_labels)
            real_js   = _real_js_ou(n, config, metrics, po, color_scheme)
            return sample_js + "\n" + real_js

        # ── Period X Axis (default) ──────────────────────────────────────────
        # Pass full fx to all sample functions; each decides based on stack_mode
        if has_dim and dim_is_opt:
            sample_js = _sample_js_dim(n, po, color_scheme, **fx)
            real_js   = _real_js_dim(n, config, metrics, dim_de, po, color_scheme)
        elif all_agg and metrics:
            sample_js = _sample_js(n, po, color_scheme, metric_labels=metric_labels, **fx)
            real_js   = _real_js_agg(n, config, metrics, po, color_scheme)
        elif len(metrics) == 1:
            m = metrics[0]
            sample_js = _sample_js(n, po, color_scheme, metric_labels=metric_labels, **fx)
            if m.get("type") == "tracker_numeric":
                real_js = _real_js_single_tracker(n, config, m, po, color_scheme)
            elif m.get("type") == "tracker_option":
                real_js = _real_js_count(n, config, m, po, color_scheme)
            else:
                real_js = _real_js_agg(n, config, [m], po, color_scheme)
        else:
            sample_js = _sample_js(n, po, color_scheme, metric_labels=metric_labels, **fx)
            real_js   = _real_js_mixed(n, config, metrics, po, color_scheme)

        return sample_js + "\n" + real_js


# ── Helpers ────────────────────────────────────────────────────────────────────

def _po(po: dict, key: str, default):
    return po.get(key, default) if po else default


def _bar_width(po: dict) -> str:
    """Bar thickness in px ('null' = auto). Accepts presets OR a custom number."""
    raw = str(_po(po, "bar_width", "Auto")).strip()
    preset = {"Auto": "null", "Thin": "12", "Normal": "22", "Wide": "36"}
    if raw in preset:
        return preset[raw]
    return raw if raw.isdigit() else "null"


def _jsbool(v) -> str:
    return "true" if v else "false"


def _slimit_val(po: dict) -> int:
    """Return series_limit as int (0 = All)."""
    raw = _po(po, "series_limit", "All")
    try:
        return 0 if raw == "All" else int(raw)
    except (ValueError, TypeError):
        return 0


def _slimit_js(po: dict) -> str:
    """Return JS snippet to apply series_limit to `datasets` array."""
    n = _slimit_val(po)
    if n == 0:
        return ""
    return f"""
        if (datasets.length > {n}) {{
          datasets.sort((a, b) =>
            b.data.reduce((s,v)=>s+(v||0),0) - a.data.reduce((s,v)=>s+(v||0),0));
          datasets = datasets.slice(0, {n});
        }}"""


def _dataset_opts(bar_width_js: str, stack_mode: str) -> str:
    stack = ", stack: 'total'" if stack_mode in ("Stack", "Expand") else ""
    bw    = f", barThickness: {bar_width_js}" if bar_width_js != "null" else ""
    return stack + bw


def _expand_normalize_js(stack_mode: str, datasets_var: str, labels_var: str) -> str:
    if stack_mode != "Expand":
        return ""
    return f"""
        const _totals = {labels_var}.map((_, i) =>
          {datasets_var}.reduce((s, ds) => s + (ds.data[i] || 0), 0));
        {datasets_var}.forEach(ds => {{
          ds.data = ds.data.map((v, i) => _totals[i] ? +(v / _totals[i] * 100).toFixed(1) : 0);
        }});"""


def _chartjs_options(n: int, po: dict) -> str:
    stack_mode   = _po(po, "stack_mode",   "None")
    orientation  = _po(po, "orientation",  "Vertical")
    show_values  = _po(po, "show_values",  False)
    only_total   = _po(po, "only_total",   True)
    show_legend  = _po(po, "show_legend",  True)
    legend_pos   = _po(po, "legend_pos",   "Bottom").lower()
    x_title      = _po(po, "x_title",      "")
    y_title      = _po(po, "y_title",      "")
    x_rotation   = int(_po(po, "x_rotation",  "45"))
    x_interval   = _po(po, "x_interval",  "Auto")
    y_format     = _po(po, "y_format",    "Default")
    log_scale    = _po(po, "log_scale",   False)
    rich_tooltip = _po(po, "rich_tooltip", True)
    tooltip_total= _po(po, "tooltip_total", True)
    bar_width    = _bar_width(po)

    is_stacked = stack_mode in ("Stack", "Expand")
    index_axis = "'y'" if orientation == "Horizontal" else "'x'"
    val_axis   = "x" if orientation == "Horizontal" else "y"
    cat_axis   = "y" if orientation == "Horizontal" else "x"

    # Y-axis format callback
    if y_format == "1,234":
        y_fmt_fn = "v => v.toLocaleString()"
    elif y_format == "1.2K":
        y_fmt_fn = "v => v >= 1000 ? (v/1000).toFixed(1)+'K' : v"
    elif y_format == "%":
        y_fmt_fn = "v => v+'%'"
    else:
        y_fmt_fn = "v => v"

    # Tooltip
    tooltip_mode   = "'index'" if rich_tooltip else "'point'"
    tooltip_footer = ""
    if rich_tooltip and tooltip_total and is_stacked:
        tooltip_footer = f"""
          footer: items => {{
            const total = items.reduce((s, i) => s + i.parsed.{val_axis}, 0);
            return 'Total: ' + ({y_fmt_fn})(total);
          }},"""

    # Datalabels
    dl_display = "true" if show_values else "false"
    dl_anchor  = "center" if is_stacked else "end"
    dl_align   = "center" if is_stacked else "end"
    if is_stacked and only_total and show_values:
        dl_display   = "ctx => ctx.datasetIndex === ctx.chart.data.datasets.length - 1"
        dl_formatter = f"""(v, ctx) => {{
              const ds = ctx.chart.data.datasets;
              const total = ds.reduce((s,d) => s + (d.data[ctx.dataIndex] || 0), 0);
              return ({y_fmt_fn})(total);
            }}"""
    else:
        dl_formatter = f"v => ({y_fmt_fn})(v)"

    scale_stacked = "true" if is_stacked else "false"
    interval_val  = "0" if x_interval == "All" else "'auto'"

    x_title_opt = f"""
          title: {{ display: {_jsbool(bool(x_title))}, text: {_json.dumps(x_title)} }},""" if x_title else ""
    y_title_opt = f"""
          title: {{ display: {_jsbool(bool(y_title))}, text: {_json.dumps(y_title)} }},""" if y_title else ""

    return f"""{{
        indexAxis: {index_axis},
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ display: {_jsbool(show_legend)}, position: '{legend_pos}' }},
          datalabels: {{
            display: {dl_display},
            anchor: '{dl_anchor}',
            align: '{dl_align}',
            formatter: {dl_formatter},
            font: {{ size: 10 }},
            color: '#333',
          }},
          tooltip: {{
            mode: {tooltip_mode},
            intersect: false,{tooltip_footer}
            callbacks: {{
              label: ctx => ctx.dataset.label + ': ' + ({y_fmt_fn})(ctx.parsed.{val_axis}),
            }},
          }},
        }},
        scales: {{
          {cat_axis}: {{
            stacked: {scale_stacked},
            ticks: {{ minRotation: {x_rotation}, maxRotation: {x_rotation},
                     autoSkip: true, autoSkipPadding: 8,
                     maxTicksLimit: {interval_val} === 0 ? 999 : undefined }},{x_title_opt}
          }},
          {val_axis}: {{
            stacked: {scale_stacked},
            beginAtZero: true,
            type: {'\"logarithmic\"' if log_scale else "'linear'"},
            ticks: {{ callback: {y_fmt_fn} }},{y_title_opt}
          }},
        }},
      }}"""


# ── Fixture sample loader ──────────────────────────────────────────────────────

def _load_fixture_sample(config: dict) -> dict:
    """Read test_fixture_{prog_uid}.json and return sample data for preview.

    Supports two fixture formats:
      raw_events_v1  — one row per event, all DE columns (new format)
      aggregate      — DHIS2 analytics/events/aggregate response (legacy)

    Returns a dict with either:
      {'fixture_labels': [...], 'fixture_datasets': [{'label':..,'data':[..]},...]}
    or:
      {'fixture_labels': [...], 'fixture_values': [...]}
    or {} if no fixture is found/parseable.
    """
    prog_uid = None
    for m in (config.get("metrics") or []):
        prog_uid = m.get("prog_uid")
        if prog_uid:
            break
    if not prog_uid:
        for dim in ((config.get("dimensions") or {}).values()):
            if isinstance(dim, dict):
                prog_uid = dim.get("prog_uid")
                if prog_uid:
                    break
    if not prog_uid:
        src = config.get("source") or {}
        prog_uid = src.get("prog_uid") or src.get("program_uid")
    if not prog_uid:
        return {}

    # Resolve stage_uid for per-stage fixture lookup
    stage_uid = (config.get("source") or {}).get("stage_uid", "")
    if not stage_uid:
        for m in (config.get("metrics") or []):
            stage_uid = m.get("stage_uid", "")
            if stage_uid:
                break
    if not stage_uid:
        dim_de_tmp = (config.get("dimensions") or {}).get("dimension") or {}
        stage_uid = dim_de_tmp.get("stage_uid", "")

    from dhis2.fixture_fetcher import load_raw_events as _load_raw
    raw = _load_raw(prog_uid, stage_uid)
    if raw:
        # Already validated as raw_events_v1 by load_raw_events
        fd = raw
    else:
        # Fall back to legacy aggregate file
        fp = _Path(f"C:/Temp/test_fixture_{prog_uid}.json")
        if not fp.exists():
            return {}
        try:
            fd = _json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            return {}

    try:
        # ── New format: raw_events_v1 ─────────────────────────────────────────
        if fd.get("_format") == "raw_events_v1":
            from dhis2.fixture_fetcher import aggregate_for_dim
            dim_de    = (config.get("dimensions") or {}).get("dimension") or {}
            dim_uid   = dim_de.get("uid", "")
            stg_uid   = dim_de.get("stage_uid", "") or fd.get("_stage_uid", "")
            if not dim_uid:
                return {}
            agg = aggregate_for_dim(fd, stg_uid, dim_uid)
            if not agg:
                return {}
            opt_names = {o["code"]: o["name"] for o in (dim_de.get("options") or [])}
            datasets  = [
                {"label": opt_names.get(ds["label"], ds["label"]), "data": ds["data"]}
                for ds in agg["datasets"]
            ]
            return {
                "fixture_labels":   agg["labels"],
                "fixture_datasets": datasets,
                "fixture_values":   agg["totals"],
            }

        # ── Legacy format: aggregate (value column) ───────────────────────────
        headers = [h["name"] for h in fd.get("headers", [])]
        rows    = fd.get("rows", [])
        if not rows or "pe" not in headers or "value" not in headers:
            return {}

        pe_idx  = headers.index("pe")
        val_idx = headers.index("value")
        cat_idx = next((i for i, h in enumerate(headers)
                        if h not in ("pe", "ou", "value")), None)

        all_periods = sorted(set(r[pe_idx] for r in rows))
        _MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]

        def _fmt(pe):
            m = _re.match(r'^(\d{4})(\d{2})$', pe)
            return (_MONTHS[int(m.group(2)) - 1] + " " + m.group(1)) if m else pe
        labels = [_fmt(p) for p in all_periods]

        if cat_idx is not None:
            dim_de   = (config.get("dimensions") or {}).get("dimension") or {}
            dim_uid  = dim_de.get("uid", "")
            stg_uid  = dim_de.get("stage_uid", "")
            cat_hdr  = headers[cat_idx]
            expected = f"{stg_uid}.{dim_uid}" if stg_uid and dim_uid else dim_uid
            if dim_uid and cat_hdr not in (expected, dim_uid):
                cat_idx = None
        if cat_idx is not None:
            cats = sorted(c for c in set(r[cat_idx] for r in rows) if c)
            opt_names = {o["code"]: o["name"] for o in (dim_de.get("options") or [])}
            datasets = []
            for cat in cats:
                vals = [
                    sum(float(r[val_idx]) for r in rows
                        if r[cat_idx] == cat and r[pe_idx] == pe)
                    for pe in all_periods
                ]
                if any(v > 0 for v in vals):
                    datasets.append({"label": opt_names.get(cat, cat), "data": vals})
            if datasets:
                totals = [sum(ds["data"][i] for ds in datasets)
                          for i in range(len(labels))]
                return {
                    "fixture_labels":   labels,
                    "fixture_datasets": datasets,
                    "fixture_values":   totals,
                }
        else:
            vals = [
                sum(float(r[val_idx]) for r in rows if r[pe_idx] == pe)
                for pe in all_periods
            ]
            return {"fixture_labels": labels, "fixture_values": vals}
    except Exception:
        pass
    return {}


# ── Sample (preview) JS ────────────────────────────────────────────────────────

def _sample_js(n: int, po: dict, color_scheme: str = "Default",
               fixture_labels=None, fixture_values=None,
               fixture_datasets=None, metric_labels=None) -> str:
    """Standard preview: 2 series × 12 months (or fixture data if available).
    Supports demo_y_scale (int multiplier, default 1) for large-value Y-format tests.
    Applies expand normalization and barThickness so all options are visible in preview.
    `metric_labels` (the selected metric names) label the demo series instead of 'Series A/B'.
    """
    _mlabels   = [s for s in (metric_labels or []) if s]
    stack_mode = _po(po, "stack_mode", "None")
    is_stacked = stack_mode in ("Stack", "Expand")
    bar_width  = _bar_width(po)
    bw_opt     = f", barThickness: {bar_width}" if bar_width != "null" else ""
    ds_opts    = (", stack: 'total'" if is_stacked else "") + bw_opt
    chart_opts = _chartjs_options(n, po)
    pal        = _palette_js(color_scheme)
    expand_js  = _expand_normalize_js(stack_mode, "datasets", "labels")

    if fixture_labels and fixture_datasets and is_stacked:
        # Stack/Expand mode + categorical fixture → show stacked species (most realistic)
        labels_js = _json.dumps(fixture_labels)
        datasets_js = ",\n            ".join(
            f"{{label:{_json.dumps(ds['label'])},data:{ds['data']},backgroundColor:PALETTE[{i}]{ds_opts}}}"
            for i, ds in enumerate(fixture_datasets)
        )
        return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const labels = {labels_js};
          let datasets = [
            {datasets_js}
          ];{expand_js}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{ labels, datasets }},
            options: {chart_opts}
          }});
        }}"""

    # Non-stacked or no categorical data → single series (totals or fixture_values)
    _vals = fixture_values  # totals pre-computed by _load_fixture_sample
    if fixture_labels and _vals:
        labels_js = _json.dumps(fixture_labels)
        vals_js   = _json.dumps(_vals)
        return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const labels = {labels_js};
          let datasets = [
            {{label:{_json.dumps(_mlabels[0] if _mlabels else 'Cases')},data:{vals_js},backgroundColor:PALETTE[0]{ds_opts}}}
          ];{expand_js}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{ labels, datasets }},
            options: {chart_opts}
          }});
        }}"""

    # ── Fallback: hardcoded demo arrays ──────────────────────────────────────
    scale = max(1, int(_po(po, "demo_y_scale", 1)))
    _demos = [[v * scale for v in row] for row in (
        [40,55,30,60,80,70,85,65,50,75,90,70],
        [30,40,20,50,60,55,65,50,40,60,70,55],
        [22,28,16,34,44,40,48,38,30,42,52,38],
    )]
    da = _demos[0]
    # Label demo series with the selected metric names — ONE series per metric (up to 3) so
    # the preview matches the real data's series count; default to two generic series.
    if _mlabels:
        _fb = [(_mlabels[i], _demos[i % 3]) for i in range(min(len(_mlabels), 3))]
    else:
        _fb = [("Series A", _demos[0]), ("Series B", _demos[1])]
    fallback_datasets_js = ",\n            ".join(
        f"{{label:{_json.dumps(lbl)},data:{data},backgroundColor:PALETTE[{i}]{ds_opts}}}"
        for i, (lbl, data) in enumerate(_fb)
    )
    x_rotation = int(_po(po, "x_rotation", "45"))
    if x_rotation > 0:
        month_labels = "['January','February','March','April','May','June','July','August','September','October','November','December']"
    else:
        month_labels = "['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']"
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const labels = {month_labels};
          let datasets = [
            {fallback_datasets_js}
          ];{expand_js}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{ labels, datasets }},
            options: {chart_opts}
          }});
        }}"""


def _sample_js_dim(n: int, po: dict, color_scheme: str = "Default",
                   fixture_labels=None, fixture_datasets=None,
                   fixture_values=None) -> str:  # fixture_values accepted but unused (totals)
    """Preview with fixture data (if available) or 6 hardcoded categories."""
    stack_mode   = _po(po, "stack_mode", "None")
    is_stacked   = stack_mode in ("Stack", "Expand")
    ds_opts      = ", stack: 'total'" if is_stacked else ""
    chart_opts   = _chartjs_options(n, po)
    pal          = _palette_js(color_scheme)
    slimit       = _slimit_val(po)
    expand_js    = _expand_normalize_js(stack_mode, "datasets", "labels")

    if fixture_labels and fixture_datasets:
        labels_js = _json.dumps(fixture_labels)
        datasets_js = ",\n            ".join(
            f"{{label:{_json.dumps(ds['label'])},data:{ds['data']},backgroundColor:PALETTE[{i}]{ds_opts}}}"
            for i, ds in enumerate(fixture_datasets)
        )
        return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const labels = {labels_js};
          let datasets = [
            {datasets_js}
          ];
          if ({slimit} > 0 && datasets.length > {slimit}) {{
            datasets.sort((a,b)=>b.data.reduce((s,v)=>s+(v||0),0)-a.data.reduce((s,v)=>s+(v||0),0));
            datasets = datasets.slice(0, {slimit});
          }}{expand_js}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{ labels, datasets }},
            options: {chart_opts}
          }});
        }}"""

    # ── Fallback: hardcoded demo arrays ──────────────────────────────────────
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
          let datasets = [
            {{label:'Cat A',data:[40,55,30,60,80,70,85,65,50,75,90,70],backgroundColor:PALETTE[0]{ds_opts}}},
            {{label:'Cat B',data:[30,40,20,50,60,55,65,50,40,60,70,55],backgroundColor:PALETTE[1]{ds_opts}}},
            {{label:'Cat C',data:[20,25,15,30,40,35,45,30,20,35,50,40],backgroundColor:PALETTE[2]{ds_opts}}},
            {{label:'Cat D',data:[15,20,10,20,30,25,35,20,15,25,35,30],backgroundColor:PALETTE[3]{ds_opts}}},
            {{label:'Cat E',data:[10,15,8,15,20,18,25,15,10,18,25,20],backgroundColor:PALETTE[4]{ds_opts}}},
            {{label:'Cat F',data:[8,10,5,10,15,12,18,10,8,12,18,15],backgroundColor:PALETTE[5]{ds_opts}}}
          ];
          if ({slimit} > 0 && datasets.length > {slimit}) {{
            datasets.sort((a,b)=>b.data.reduce((s,v)=>s+(v||0),0)-a.data.reduce((s,v)=>s+(v||0),0));
            datasets = datasets.slice(0, {slimit});
          }}{expand_js}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{ labels, datasets }},
            options: {chart_opts}
          }});
        }}"""


def _sample_js_ou(n: int, po: dict, color_scheme: str = "Default",
                  metric_labels=None) -> str:
    """Preview for Org Unit X Axis: 6 org units, one series per selected metric.

    Multiple metrics render as distinct-coloured series (stacked when stack_mode is on)
    so the preview matches the real multi-metric render.
    """
    _mlabels   = [s for s in (metric_labels or []) if s] or ["Value"]
    _mlabels   = _mlabels[:8]
    stack_mode = _po(po, "stack_mode", "None")
    ds_opts    = _dataset_opts(stack_mode == "None" and "null" or _bar_width(po), stack_mode)
    chart_opts = _chartjs_options(n, po)
    pal        = _palette_js(color_scheme)
    slimit     = _slimit_val(po)
    # One demo profile per metric so each series differs.
    _demos = [[320,275,410,190,355,280],
              [210,180,300,120,240,190],
              [140,120,205,80,160,130],
              [90,80,140,50,110,85]]
    datasets_js = ",\n                ".join(
        f"{{label:{_json.dumps(lbl)},data:{_demos[i % len(_demos)]},"
        f"backgroundColor:PALETTE[{i}]{ds_opts}}}"
        for i, lbl in enumerate(_mlabels)
    )
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const _labels = ['District A','District B','District C','District D','District E','District F'];
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{
              labels: _labels,
              datasets: [
                {datasets_js}
              ]
            }},
            options: {chart_opts}
          }});
        }}"""


# ── initChart wrapper (shared) ─────────────────────────────────────────────────

def _init_js(n: int) -> str:
    return f"""\
        async function initChart{n}(ou, pe) {{
          document.getElementById('loading{n}').style.display = 'none';
          const cvs = document.getElementById('chart{n}');
          cvs.style.display = 'block';
          if (PREVIEW) {{
            const b = document.getElementById('demoBanner{n}');
            if (b) b.style.display = 'block';
            renderChart{n}Sample(cvs); return;
          }}
          document.getElementById('demoBanner{n}').style.display = 'none';
          const errEl = document.getElementById('error{n}');
          errEl.style.display = 'none';"""


# ── Case A: single tracker_numeric, no dimension ───────────────────────────────

def _real_js_single_tracker(n: int, config: dict, m: dict, po: dict,
                             color_scheme: str = "Default") -> str:
    de_uid   = m.get("uid", "")
    agg      = m.get("agg", "SUM")
    prog_uid = m.get("prog_uid", "") or (config.get("source") or {}).get("prog_uid", "")
    stg_uid  = m.get("stage_uid", "") or (config.get("source") or {}).get("stage_uid", "")
    color    = config.get("chart_color", "#3498db")
    extra    = ChartPlugin._extra_params(config)
    stack_mode = _po(po, "stack_mode", "None")
    bar_width  = _bar_width(po)
    chart_opts = _chartjs_options(n, po)
    ds_opts    = _dataset_opts(bar_width, stack_mode)
    pal        = _palette_js(color_scheme)

    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const peIdx  = d.headers.findIndex(h => h.name === 'pe');
          const valIdx = d.headers.findIndex(h => h.name === 'value');
          const periods = [...new Set(d.rows.map(r => r[peIdx]))].sort();
          // Sum across all rows for each period (e.g. an OU-level filter returns one row
          // per org unit) so the bar shows the TOTAL, not just the first row's value.
          const vals = periods.map(p =>
            d.rows.filter(r => r[peIdx] === p)
                  .reduce((s, r) => s + (parseFloat(r[valIdx]) || 0), 0));
          const labels = periods.map(formatPeriodLabel);
          const datasets = [{{label:'',data:vals,backgroundColor:'{color}'{ds_opts}}}];
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar', data: {{ labels, datasets }}, options: {chart_opts}
          }});
        }}
        {_init_js(n)}
          try {{
            const rpe = resolveRelativePeriod(pe);
            const d = await dhis2Get(
              'api/analytics/events/aggregate/{prog_uid}'
              +'?stage={stg_uid}&value={de_uid}&aggregationType={agg}'
              +'&dimension=pe:'+encodeURIComponent(rpe)
              +'&dimension=ou:'+encodeURIComponent(ou)+'{extra}'
            );
            if (!d.rows||!d.rows.length){{errEl.textContent='No data.';errEl.style.display='block';return;}}
            renderChart{n}Real(cvs, d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);errEl.textContent='Failed: '+e.message;errEl.style.display='block';
          }}
        }}"""


# ── Case A2: single tracker_option metric (no dim) → count events per period ───
# A categorical (option) DE has no numeric value to sum, so we COUNT events per
# period, bucketed by the event date (DHIS2 timeField, default EVENT_DATE).

_TIME_FIELDS = {            # date_field option label → DHIS2 events analytics timeField
    "Event date":      "",                 # default → omit param
    "Enrollment date": "ENROLLMENT_DATE",
    "Incident date":   "INCIDENT_DATE",
    "Last updated":    "LAST_UPDATED",
}


def _time_field_param(po: dict) -> str:
    """Return '&timeField=...' for the chosen date_field, or '' (default = event date).
    A DATE data-element UID (11 chars) is passed through as the timeField value."""
    df = _po(po, "date_field", "Event date")
    tf = _TIME_FIELDS.get(df)
    if tf is None:                          # not a standard label → treat as a DE uid
        tf = df if df else ""
    return f"&timeField={tf}" if tf else ""


def _real_js_count(n: int, config: dict, m: dict, po: dict,
                   color_scheme: str = "Default") -> str:
    prog_uid = m.get("prog_uid", "") or (config.get("source") or {}).get("prog_uid", "")
    stg_uid  = m.get("stage_uid", "") or (config.get("source") or {}).get("stage_uid", "")
    name     = m.get("name", "")
    color    = config.get("chart_color", "#3498db")
    extra    = ChartPlugin._extra_params(config)
    tf       = _time_field_param(po)
    stack_mode = _po(po, "stack_mode", "None")
    bar_width  = _bar_width(po)
    chart_opts = _chartjs_options(n, po)
    ds_opts    = _dataset_opts(bar_width, stack_mode)
    pal        = _palette_js(color_scheme)

    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const peIdx  = d.headers.findIndex(h => h.name === 'pe');
          const valIdx = d.headers.findIndex(h => h.name === 'value');
          const periods = [...new Set(d.rows.map(r => r[peIdx]))].sort();
          // Sum across all rows for each period (e.g. an OU-level filter returns one row
          // per org unit) so the bar shows the TOTAL, not just the first row's value.
          const vals = periods.map(p =>
            d.rows.filter(r => r[peIdx] === p)
                  .reduce((s, r) => s + (parseFloat(r[valIdx]) || 0), 0));
          const labels = periods.map(formatPeriodLabel);
          const datasets = [{{label:{_json.dumps(name + ' (events)')},data:vals,backgroundColor:'{color}'{ds_opts}}}];
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type:'bar', data:{{labels,datasets}}, options:{chart_opts}
          }});
        }}
        {_init_js(n)}
          try {{
            const rpe = resolveRelativePeriod(pe);
            const d = await dhis2Get(
              'api/analytics/events/aggregate/{prog_uid}'
              +'?stage={stg_uid}'
              +'&dimension=pe:'+encodeURIComponent(rpe)
              +'&dimension=ou:'+encodeURIComponent(ou)+'{tf}{extra}'
            );
            if (!d.rows||!d.rows.length){{errEl.textContent='No data.';errEl.style.display='block';return;}}
            renderChart{n}Real(cvs, d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);errEl.textContent='Failed: '+e.message;errEl.style.display='block';
          }}
        }}"""


# ── Case B: tracker_option dimension ──────────────────────────────────────────

def _real_js_dim(n: int, config: dict, metrics: list, dim_de: dict, po: dict,
                 color_scheme: str = "Default") -> str:
    de_uid   = dim_de.get("uid", "")
    prog_uid = dim_de.get("prog_uid", "") or (config.get("source") or {}).get("prog_uid", "")
    is_tea   = bool(dim_de.get("is_tea"))
    # A program attribute (TEA) has no stage; the events query still needs a stage,
    # so borrow it from the first metric / source. The DE dimension is the bare uid
    # for a TEA, but "{stage}.{de}" for a stage data element.
    metric_stg = next((m.get("stage_uid", "") for m in metrics if m.get("stage_uid")), "")
    stg_uid  = dim_de.get("stage_uid", "") or metric_stg or (config.get("source") or {}).get("stage_uid", "")
    dim_token = de_uid if is_tea else f"{stg_uid}.{de_uid}"
    options  = dim_de.get("options", [])
    opt_js   = _json.dumps(options)
    extra    = ChartPlugin._extra_params(config)
    stack_mode  = _po(po, "stack_mode", "None")
    bar_width   = _bar_width(po)
    expand_js   = _expand_normalize_js(stack_mode, "datasets", "periods")
    chart_opts  = _chartjs_options(n, po)
    ds_opts     = _dataset_opts(bar_width, stack_mode)
    slimit_js   = _slimit_js(po)
    pal         = _palette_js(color_scheme)

    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const DIM_OPTIONS = {opt_js};
          const peIdx  = d.headers.findIndex(h => h.name === 'pe');
          // DHIS2 event analytics returns dimension header as "stageUid.deUid"
          const catIdx = d.headers.findIndex(h =>
            h.name === '{stg_uid}.{de_uid}' || h.name === '{de_uid}');
          const valIdx = d.headers.findIndex(h => h.name === 'value');
          const periods = [...new Set(d.rows.map(r => r[peIdx]))].sort();
          if (catIdx < 0) {{
            // The error element belongs to initChart{n}'s scope, not this renderer —
            // throw so the caller's try/catch surfaces it (referencing it here would be
            // an out-of-scope ReferenceError).
            throw new Error('Dimension column not found in API response. Check stage/DE uid.');
          }}
          const catCodesFromData = [...new Set(d.rows.map(r => r[catIdx]))];
          // Use DIM_OPTIONS ordering only when its codes actually appear in the data
          // (guards against stale options from a previously-selected dimension DE)
          const catCodes = (DIM_OPTIONS.length &&
            DIM_OPTIONS.some(o => catCodesFromData.includes(o.code)))
            ? DIM_OPTIONS.map(o => o.code).filter(c => catCodesFromData.includes(c))
            : catCodesFromData;
          const nameOf = code => {{
            const opt = DIM_OPTIONS.find(o => o.code === code);
            if (opt) return opt.name;
            // metaData may key by full uid or by option code
            return d.metaData?.items?.[code]?.name || code;
          }};
          const grouped = {{}};
          d.rows.forEach(r => {{
            const cat=r[catIdx],p=r[peIdx],v=parseFloat(r[valIdx])||0;
            if(!grouped[cat]) grouped[cat]={{}};
            grouped[cat][p]=(grouped[cat][p]||0)+v;
          }});
          let datasets = catCodes.map((cat,i) => ({{
            label:nameOf(cat),
            data:periods.map(p=>grouped[cat]?.[p]||0),
            backgroundColor:PALETTE[i%PALETTE.length]{ds_opts}
          }}));{slimit_js}{expand_js}
          const labels = periods.map(formatPeriodLabel);
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type:'bar', data:{{labels,datasets}}, options:{chart_opts}
          }});
        }}
        {_init_js(n)}
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


# ── Case C: aggregate/indicator ────────────────────────────────────────────────

def _real_js_agg(n: int, config: dict, metrics: list, po: dict,
                 color_scheme: str = "Default") -> str:
    de_ids      = ";".join(m["uid"] for m in metrics)
    de_names    = {m["uid"]: m.get("name","") for m in metrics}
    de_names_js = _json.dumps(de_names)
    extra       = ChartPlugin._extra_params(config)
    stack_mode  = _po(po, "stack_mode", "None")
    bar_width   = _bar_width(po)
    expand_js   = _expand_normalize_js(stack_mode, "datasets", "periods")
    chart_opts  = _chartjs_options(n, po)
    ds_opts     = _dataset_opts(bar_width, stack_mode)
    pal         = _palette_js(color_scheme)

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
          let datasets = dxIds.map((dx,i) => {{
            const lbl=(d.metaData?.items?.[dx]?.name)||DE_NAMES[dx]||dx;
            const vals=periods.map(p=>
              d.rows.filter(r=>r[dxIdx]===dx&&r[peIdx]===p)
                    .reduce((s,r)=>s+(parseFloat(r[valIdx])||0),0));
            return {{label:lbl,data:vals,backgroundColor:PALETTE[i%PALETTE.length]{ds_opts}}};
          }});{expand_js}
          const labels = periods.map(formatPeriodLabel);
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type:'bar', data:{{labels,datasets}}, options:{chart_opts}
          }});
        }}
        {_init_js(n)}
          try {{
            const d = await dhis2Get(
              'api/analytics.json?dimension=dx:{de_ids}'
              +'&dimension=pe:'+encodeURIComponent(resolveRelativePeriod(pe))
              +'&dimension=ou:'+encodeURIComponent(ou)
              +'&displayProperty=NAME{extra}'
            );
            if (!d.rows||!d.rows.length){{errEl.textContent='No data.';errEl.style.display='block';return;}}
            renderChart{n}Real(cvs, d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);errEl.textContent='Failed: '+e.message;errEl.style.display='block';
          }}
        }}"""


# ── Case D: mixed sources ──────────────────────────────────────────────────────

def _real_js_mixed(n: int, config: dict, metrics: list, po: dict,
                   color_scheme: str = "Default") -> str:
    extra      = ChartPlugin._extra_params(config)
    stack_mode = _po(po, "stack_mode", "None")
    bar_width  = _bar_width(po)
    chart_opts = _chartjs_options(n, po)
    ds_opts    = _dataset_opts(bar_width, stack_mode)
    expand_js  = _expand_normalize_js(stack_mode, "datasets", "allPeriods")
    pal        = _palette_js(color_scheme)

    fetch_calls = []
    for m in metrics:
        if m.get("type") == "tracker_numeric":
            pu,su,de,agg = m.get("prog_uid",""),m.get("stage_uid",""),m.get("uid",""),m.get("agg","SUM")
            fetch_calls.append(
                f"dhis2Get('api/analytics/events/aggregate/{pu}"
                f"?stage={su}&value={de}&aggregationType={agg}"
                f"&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou)"
                + (f"+'{extra}'" if extra else "") + ")"
            )
        else:
            de = m.get("uid","")
            fetch_calls.append(
                f"dhis2Get('api/analytics.json?dimension=dx:{de}"
                f"&dimension=pe:'+encodeURIComponent(resolveRelativePeriod(pe))+'&dimension=ou:'+encodeURIComponent(ou)"
                f"+'&displayProperty=NAME{extra}')"
            )
    fetch_array  = ",\n              ".join(fetch_calls)
    de_names_js  = _json.dumps([m.get("name","") for m in metrics])

    return f"""\
        function renderChart{n}Real(cvs, results) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const DE_NAMES = {de_names_js};
          const allPeriods = [...new Set(
            results.flatMap(d => {{
              const idx=d.headers.findIndex(h=>h.name==='pe');
              return d.rows.map(r=>r[idx]);
            }})
          )].sort();
          let datasets = results.map((d,i) => {{
            const peIdx=d.headers.findIndex(h=>h.name==='pe');
            const valIdx=d.headers.findIndex(h=>h.name==='value');
            const vals=allPeriods.map(p=>
              d.rows.filter(r=>r[peIdx]===p)
                    .reduce((s,r)=>s+(parseFloat(r[valIdx])||0),0));
            return {{label:DE_NAMES[i],data:vals,backgroundColor:PALETTE[i%PALETTE.length]{ds_opts}}};
          }});{expand_js}
          const labels = allPeriods.map(formatPeriodLabel);
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type:'bar', data:{{labels,datasets}}, options:{chart_opts}
          }});
        }}
        {_init_js(n)}
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


# ── Org Unit X Axis ────────────────────────────────────────────────────────────

def _real_js_ou(n: int, config: dict, metrics: list, po: dict,
                color_scheme: str = "Default") -> str:
    """
    Uses USER_ORGUNIT_CHILDREN as the org unit dimension.
    Each child OU becomes one bar on the x-axis.
    Supports tracker_numeric and aggregate/indicator (first metric used as single series).
    """
    if not metrics:
        return f"async function initChart{n}(ou,pe){{document.getElementById('loading{n}').style.display='none';}}"

    # Multiple aggregate/indicator metrics → one distinct-coloured series per metric
    # (stackable), grouped by org unit on the x-axis.
    all_agg = all(mm.get("type") in ("aggregate", "indicator") for mm in metrics)
    if len(metrics) > 1 and all_agg:
        return _real_js_ou_multi(n, config, metrics, po, color_scheme)

    m        = metrics[0]
    de_type  = m.get("type", "aggregate")
    de_uid   = m.get("uid", "")
    agg      = m.get("agg", "SUM")
    prog_uid = m.get("prog_uid", "") or (config.get("source") or {}).get("prog_uid", "")
    stg_uid  = m.get("stage_uid", "") or (config.get("source") or {}).get("stage_uid", "")
    name     = m.get("name", "Value")
    extra    = ChartPlugin._extra_params(config)
    chart_opts = _chartjs_options(n, po)
    pal        = _palette_js(color_scheme)
    slimit     = _slimit_val(po)
    slimit_js_snip = f"""
          if ({slimit} > 0 && combined.length > {slimit}) {{
            combined.sort((a,b)=>b.v-a.v);
            combined = combined.slice(0, {slimit});
          }}""" if slimit > 0 else ""

    render_body = f"""\
          const ouIdx  = d.headers.findIndex(h => h.name === 'ou');
          const valIdx = d.headers.findIndex(h => h.name === 'value');
          const getName = id => d.metaData?.items?.[id]?.name || id;
          const ouMap = {{}};
          d.rows.forEach(r => {{
            const id = r[ouIdx];
            ouMap[id] = (ouMap[id] || 0) + (parseFloat(r[valIdx]) || 0);
          }});
          let combined = Object.entries(ouMap).map(([id,v]) => ({{id,v,label:getName(id)}}));{slimit_js_snip}
          const labels   = combined.map(x => x.label);
          const datasets = [{{
            label: '{_json.dumps(name)[1:-1]}',
            data:  combined.map(x => x.v),
            backgroundColor: PALETTE[0]
          }}];
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type:'bar', data:{{labels,datasets}}, options:{chart_opts}
          }});"""

    if de_type == "tracker_numeric":
        fetch_snippet = f"""\
            const rpe = resolveRelativePeriod(pe);
            const d = await dhis2Get(
              'api/analytics/events/aggregate/{prog_uid}'
              +'?stage={stg_uid}&value={de_uid}&aggregationType={agg}'
              +'&dimension=pe:'+encodeURIComponent(rpe)
              +'&dimension=ou:USER_ORGUNIT_CHILDREN'+'{extra}'
            );"""
    else:
        fetch_snippet = f"""\
            const d = await dhis2Get(
              'api/analytics.json?dimension=dx:{de_uid}'
              +'&dimension=pe:'+encodeURIComponent(pe)
              +'&dimension=ou:USER_ORGUNIT_CHILDREN'
              +'&displayProperty=NAME{extra}'
            );"""

    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          {render_body}
        }}
        {_init_js(n)}
          try {{
            {fetch_snippet}
            if (!d.rows||!d.rows.length){{errEl.textContent='No data.';errEl.style.display='block';return;}}
            renderChart{n}Real(cvs, d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);errEl.textContent='Failed: '+e.message;errEl.style.display='block';
          }}
        }}"""


def _real_js_ou_multi(n: int, config: dict, metrics: list, po: dict,
                      color_scheme: str = "Default") -> str:
    """Org Unit x-axis with several aggregate/indicator metrics: one distinct-coloured
    (and stackable) series per metric, grouped by child org unit."""
    de_ids      = ";".join(m["uid"] for m in metrics)
    de_names    = {m["uid"]: m.get("name", "") for m in metrics}
    de_names_js = _json.dumps(de_names)
    extra       = ChartPlugin._extra_params(config)
    stack_mode  = _po(po, "stack_mode", "None")
    chart_opts  = _chartjs_options(n, po)
    ds_opts     = _dataset_opts(_bar_width(po), stack_mode)
    expand_js   = _expand_normalize_js(stack_mode, "datasets", "ouIds")
    pal         = _palette_js(color_scheme)

    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {pal}
          const DE_NAMES = {de_names_js};
          const dxIdx  = d.headers.findIndex(h => h.name === 'dx');
          const ouIdx  = d.headers.findIndex(h => h.name === 'ou');
          const valIdx = d.headers.findIndex(h => h.name === 'value');
          const getName = id => d.metaData?.items?.[id]?.name || id;
          const dxIds = [...new Set(d.rows.map(r => r[dxIdx]))];
          const ouIds = [...new Set(d.rows.map(r => r[ouIdx]))];
          let datasets = dxIds.map((dx,i) => {{
            const lbl = (d.metaData?.items?.[dx]?.name) || DE_NAMES[dx] || dx;
            const vals = ouIds.map(o =>
              d.rows.filter(r => r[dxIdx]===dx && r[ouIdx]===o)
                    .reduce((s,r)=>s+(parseFloat(r[valIdx])||0),0));
            return {{label:lbl,data:vals,backgroundColor:PALETTE[i%PALETTE.length]{ds_opts}}};
          }});{expand_js}
          const labels = ouIds.map(getName);
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type:'bar', data:{{labels,datasets}}, options:{chart_opts}
          }});
        }}
        {_init_js(n)}
          try {{
            const d = await dhis2Get(
              'api/analytics.json?dimension=dx:{de_ids}'
              +'&dimension=pe:'+encodeURIComponent(resolveRelativePeriod(pe))
              +'&dimension=ou:USER_ORGUNIT_CHILDREN'
              +'&displayProperty=NAME{extra}'
            );
            if (!d.rows||!d.rows.length){{errEl.textContent='No data.';errEl.style.display='block';return;}}
            renderChart{n}Real(cvs, d);
          }} catch(e) {{
            console.error('[Chart{n}]',e);errEl.textContent='Failed: '+e.message;errEl.style.display='block';
          }}
        }}"""
