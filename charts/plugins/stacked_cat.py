"""
StackedCatPlugin — Stacked bar by category (tracker option-set DE).

Template id : stacked_cat
Preview id  : bar_stacked

The selected DE must be a tracker_option DE (i.e. it has an option set).
Each option-set value becomes one coloured layer in the stacked bar chart,
with one bar per period on the x-axis.

API call (real data):
    /api/analytics/events/aggregate/{prog}
        ?stage={stg}
        &dimension={stg}.{de_uid}
        &dimension=pe:{rpe}
        &dimension=ou:{ou}

The response rows are grouped by (pe, category-option) to build Chart.js
stacked datasets.  Category names are resolved from d.metaData.items.
"""
from __future__ import annotations

from charts.plugins.base import (
    ChartPlugin,
    DimensionControl,
    MetricControl,
    TimeGrainControl,
)


class StackedCatPlugin(ChartPlugin):
    """Stacked bar chart — option-set categories become the stacked layers."""

    # ── Plugin identity ───────────────────────────────────────────────────────
    id          = "stacked_cat"
    label       = "Stacked bar — by category"
    hidden      = True  # superseded by unified BarPlugin
    icon        = "📋"
    preview_id  = "bar_stacked"
    description = (
        "Monthly stacked bars where each option-set value becomes one colour "
        "layer. Select an option-set DE — its options become the stacked layers."
    )

    # ── Controls ──────────────────────────────────────────────────────────────
    # Metric = what to count/sum (event count by default — no specific DE needed)
    # Dimension = the option-set DE whose values become the stack layers
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
            label="Split by (stack layers)",
            allowed_types=("tracker_option", "tracker_numeric", "aggregate", "indicator"),
            required=True,
            hint="Option-set DE: each option value becomes one stack layer",
        )
    ]
    time_grain = TimeGrainControl(default="Monthly")

    # ── JS builder ────────────────────────────────────────────────────────────

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        """
        Return the per-card JavaScript for card index *n*.

        config expected keys (new plugin format):
            metrics : list of metric dicts, first entry used
                      keys: uid, prog_uid, stage_uid, type, name
            title   : card title (optional, used for fallback)

        Also accepts legacy flat keys for backwards compatibility:
            de_uid, prog_uid, stage_uid, de_type
        """
        # ── Resolve dimension (option-set DE that defines the stack layers) ─────
        # New format: config["dimensions"]["dimension"] = {uid, name, type, ...}
        # Legacy format: metrics[0] with type="tracker_option"
        dims = config.get("dimensions") or {}
        dim_de = dims.get("dimension")  # new: single dimension field
        source = config.get("source") or {}

        if dim_de and dim_de.get("uid"):
            de_uid    = dim_de["uid"]
            prog_uid  = dim_de.get("prog_uid", "") or source.get("prog_uid", "")
            stage_uid = dim_de.get("stage_uid", "") or source.get("stage_uid", "")
        else:
            # Legacy: old format has option-set DE in metrics[0]
            metrics = config.get("metrics", [])
            m = metrics[0] if metrics else {}
            de_uid    = m.get("uid", "") or config.get("de_uid", "")
            prog_uid  = m.get("prog_uid", "") or source.get("prog_uid", "") or config.get("prog_uid", "")
            stage_uid = m.get("stage_uid", "") or source.get("stage_uid", "") or config.get("stage_uid", "")

        extra = cls._extra_params(config)

        # Options baked from pre-loaded metadata — no browser refetch needed
        dims = config.get("dimensions") or {}
        dim_de = dims.get("dimension") or {}
        options = dim_de.get("options", [])

        sample_js = _sample_js(n)
        real_js   = _real_js(n, de_uid=de_uid, prog_uid=prog_uid, stage_uid=stage_uid,
                              extra=extra, options=options)
        return sample_js + "\n" + real_js


# ── Sample (preview) JS ───────────────────────────────────────────────────────

def _sample_js(n: int) -> str:
    """Stacked bar with 3 demo categories × 12 months — no API call."""
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const PALETTE=['#e74c3c','#3498db','#f39c12','#27ae60','#9b59b6','#1abc9c','#e67e22','#2980b9'];
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{
              labels: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
              datasets: [
                {{
                  label: 'Category A',
                  data: [40,55,30,60,80,70,85,65,50,75,90,70],
                  backgroundColor: PALETTE[0]
                }},
                {{
                  label: 'Category B',
                  data: [50,60,40,70,90,80,90,75,60,85,95,80],
                  backgroundColor: PALETTE[1]
                }},
                {{
                  label: 'Category C',
                  data: [30,30,28,37,33,39,37,36,33,38,36,35],
                  backgroundColor: PALETTE[2]
                }}
              ]
            }},
            options: {{
              responsive: true,
              plugins: {{ legend: {{ position: 'bottom' }} }},
              scales: {{
                x: {{ stacked: true, ticks: {{ maxRotation: 45 }} }},
                y: {{ stacked: true, beginAtZero: true }}
              }}
            }}
          }});
        }}"""


# ── Real-data JS ──────────────────────────────────────────────────────────────

def _real_js(n: int, *, de_uid: str, prog_uid: str, stage_uid: str,
             extra: str, options: list) -> str:
    """
    Fetches real data from:
        /api/analytics/events/aggregate/{prog_uid}
            ?stage={stage_uid}
            &dimension={stage_uid}.{de_uid}
            &dimension=pe:{rpe}
            &dimension=ou:{ou}

    Options are baked in from pre-loaded metadata — no browser re-fetch needed.
    If options is empty, falls back to values found in the API response rows.
    """
    import json as _json
    options_js = _json.dumps(options)   # e.g. [{"code":"M","name":"Male"}, ...]

    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const PALETTE=['#e74c3c','#3498db','#f39c12','#27ae60','#9b59b6','#1abc9c','#e67e22','#2980b9'];
          const DIM_OPTIONS = {options_js};
          const peIdx  = d.headers.findIndex(h => h.name === 'pe');
          const catIdx = d.headers.findIndex(h => h.name === '{de_uid}');
          const valIdx = d.headers.findIndex(h => h.name === 'value');

          const periods = [...new Set(d.rows.map(r => r[peIdx]))].sort();
          // Use baked option order; fall back to values found in response
          const catCodes = DIM_OPTIONS.length
            ? DIM_OPTIONS.map(o => o.code)
            : [...new Set(d.rows.map(r => r[catIdx]))];

          const nameOf = code => {{
            const opt = DIM_OPTIONS.find(o => o.code === code);
            return opt ? opt.name : (d.metaData?.items?.[code]?.name || code);
          }};

          // group[catCode][period] = sum of values
          const grouped = {{}};
          d.rows.forEach(r => {{
            const cat = r[catIdx], pe = r[peIdx], val = parseFloat(r[valIdx]) || 0;
            if (!grouped[cat]) grouped[cat] = {{}};
            grouped[cat][pe] = (grouped[cat][pe] || 0) + val;
          }});

          const datasets = catCodes.map((cat, i) => ({{
            label: nameOf(cat),
            data: periods.map(p => grouped[cat]?.[p] || 0),
            backgroundColor: PALETTE[i % PALETTE.length],
            borderWidth: 1,
          }}));

          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{ labels: periods.map(formatPeriodLabel), datasets }},
            options: {{
              responsive: true,
              plugins: {{ legend: {{ position: 'bottom' }} }},
              scales: {{
                x: {{ stacked: true, ticks: {{ maxRotation: 45 }} }},
                y: {{ stacked: true, beginAtZero: true }}
              }}
            }}
          }});
        }}

        async function initChart{n}(ou, pe) {{
          document.getElementById('loading{n}').style.display = 'none';
          const cvs = document.getElementById('chart{n}');
          cvs.style.display = 'block';

          if (PREVIEW) {{
            document.getElementById('demoBanner{n}').style.display = 'block';
            renderChart{n}Sample(cvs);
            return;
          }}

          document.getElementById('demoBanner{n}').style.display = 'none';
          try {{
            const rpe = resolveRelativePeriod(pe);
            const url = 'api/analytics/events/aggregate/{prog_uid}'
              + '?stage={stage_uid}'
              + '&dimension={stage_uid}.{de_uid}'
              + '&dimension=pe:' + encodeURIComponent(rpe)
              + '&dimension=ou:' + encodeURIComponent(ou){extra};
            const d = await dhis2Get(url);
            if (!d.rows || !d.rows.length) {{
              document.getElementById('error{n}').textContent =
                'No data for the selected period / org unit.';
              document.getElementById('error{n}').style.display = 'block';
              return;
            }}
            renderChart{n}Real(cvs, d);
          }} catch (e) {{
            console.error('[Chart{n}]', e);
            document.getElementById('error{n}').textContent = 'Failed to load: ' + e.message;
            document.getElementById('error{n}').style.display = 'block';
          }}
        }}"""
