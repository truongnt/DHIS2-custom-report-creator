"""
BarMonthlyPlugin — "Bar — monthly trend"

Single-DE bar chart grouped by period (monthly, quarterly, or yearly).
Supports tracker_numeric, aggregate, and indicator data element types.

Config shape expected by build_js():
    {
        "plugin_id": "bar_monthly",
        "title": str,
        "col_width": int,          # Bootstrap column width (default 6)
        "chart_color": str,        # CSS hex color, e.g. "#3498db"
        "metrics": [
            {
                "uid":       str,  # DE / indicator UID
                "name":      str,  # Display name
                "type":      str,  # "tracker_numeric" | "aggregate" | "indicator"
                "agg":       str,  # Aggregation type, e.g. "SUM"
            }
        ],
        "source": {
            "prog_uid":  str,      # Program UID  (tracker_numeric only)
            "stage_uid": str,      # Stage UID    (tracker_numeric only)
        },
        "dimensions": {
            "filters":   list,     # Optional filter list for _extra_params
            "group_by":  list,     # Optional group_by list for _extra_params
            "sort_by":   str,      # "None" | "Value" | "Label"
            "sort_dir":  str,      # "Asc" | "Desc"
            "row_limit": int,      # 0 = no limit
        },
        "custom_options": dict,    # Optional Chart.js option overrides
    }
"""
from __future__ import annotations

from charts.plugins.base import (
    ChartPlugin,
    DimensionControl,
    MetricControl,
    TimeGrainControl,
)


class BarMonthlyPlugin(ChartPlugin):
    """Bar chart — monthly trend (single metric, all DE types except option-set)."""

    id: str          = "bar_monthly"
    label: str       = "Bar — monthly trend"
    hidden: bool     = True  # superseded by unified BarPlugin
    icon: str        = "📊"
    description: str = (
        "Monthly bar chart — one bar per period. "
        "Works with tracker numeric DEs (SUM aggregation) and aggregate / indicator sources."
    )
    preview_id: str  = "bar_monthly"

    metrics: list[MetricControl] = [
        MetricControl(
            id="metric",
            label="Metric",
            max_count=1,
            allowed_types=("tracker_numeric", "aggregate", "indicator"),
            default_agg="SUM",
        )
    ]
    dimensions: list[DimensionControl] = []
    time_grain: TimeGrainControl | None = TimeGrainControl(default="Monthly")

    # ── JS generation ─────────────────────────────────────────────────────────

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        """
        Return the per-card JavaScript string for card index n.

        Generates three JS functions:
          - renderChart{n}Sample(cvs)     — sample / preview data renderer
          - renderChart{n}Real(cvs, d)    — real DHIS2 data renderer
          - initChart{n}(ou, pe)          — fetches data and calls the appropriate renderer
        """
        metrics = config.get("metrics", [])
        metric  = metrics[0] if metrics else {}

        de_uid    = metric.get("uid", "")
        de_type   = metric.get("type", "aggregate")
        agg_type  = metric.get("agg", "SUM")

        source    = config.get("source", {})
        prog_uid  = source.get("prog_uid", "")
        stage_uid = source.get("stage_uid", "")

        color     = config.get("chart_color", "#3498db")

        sample = cls._sample_js(n, color)
        real   = cls._real_js(n, de_uid, de_type, agg_type, prog_uid, stage_uid, color, config)
        init   = cls._init_js(n, de_type, de_uid, agg_type, prog_uid, stage_uid, config)

        return sample + "\n" + real + "\n" + init

    # ── Private JS builder helpers ─────────────────────────────────────────────

    @classmethod
    def _sample_js(cls, n: int, color: str) -> str:
        """renderChart{n}Sample — renders hardcoded 12-month bar chart."""
        return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{
              labels: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
              datasets: [{{
                label: 'Cases',
                data: [120, 145, 98, 167, 203, 189, 212, 176, 143, 198, 221, 185],
                backgroundColor: '{color}'
              }}]
            }},
            options: {{
              responsive: true,
              plugins: {{ legend: {{ display: false }} }},
              scales: {{ y: {{ beginAtZero: true }} }}
            }}
          }});
        }}"""

    @classmethod
    def _real_js(cls, n: int, de_uid: str, de_type: str,
                 agg_type: str, prog_uid: str, stage_uid: str,
                 color: str, config: dict) -> str:
        """
        renderChart{n}Real(cvs, d) — renders real DHIS2 API response.

        The response shape differs between tracker_numeric and aggregate/indicator:
          - tracker_numeric: headers include "pe", "ou", "value"
          - aggregate/indicator: headers include "dx", "pe", "ou", "value"
        Both are handled identically in this renderer (pe + value columns).

        Periods are sorted chronologically (natural API order) then optionally
        re-sorted/limited by _sort_limit_js.
        """
        sort_limit = cls._sort_limit_js(config, "combined")
        return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const peIdx  = d.headers.findIndex(h => h.name === 'pe');
          const valIdx = d.headers.findIndex(h => h.name === 'value');
          const periods = [...new Set(d.rows.map(r => r[peIdx]))].sort();
          const vals = periods.map(p => {{
            const row = d.rows.find(r => r[peIdx] === p);
            return row ? parseFloat(row[valIdx]) || 0 : 0;
          }});
          let labels = periods.map(formatPeriodLabel);
          let combined = labels.map((l, i) => ({{l, v: vals[i]}}));
          {sort_limit}
          const sortedLabels = combined.map(x => x.l);
          const sortedVals = combined.map(x => x.v);
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{
              labels: sortedLabels,
              datasets: [{{
                label: 'Value',
                data: sortedVals,
                backgroundColor: '{color}',
                borderColor: '{color}',
                borderWidth: 1
              }}]
            }},
            options: {{
              responsive: true,
              plugins: {{ legend: {{ display: false }} }},
              scales: {{
                x: {{ ticks: {{ maxRotation: 45 }} }},
                y: {{ beginAtZero: true }}
              }}
            }}
          }});
        }}"""

    @classmethod
    def _init_js(cls, n: int, de_type: str, de_uid: str,
                 agg_type: str, prog_uid: str, stage_uid: str,
                 config: dict) -> str:
        """
        initChart{n}(ou, pe) — standard init pattern:
          1. Hide loading spinner, show canvas.
          2. In PREVIEW mode: show demo banner, render sample, return.
          3. Otherwise: fetch real data and render.

        API endpoints:
          tracker_numeric -> /api/analytics/events/aggregate/{prog}
                             ?stage={stg}&value={de}&aggregationType={agg}
                             &dimension=pe:{rpe}&dimension=ou:{ou}{extra}
          aggregate/indicator -> /api/analytics.json
                             ?dimension=dx:{de}&dimension=pe:{pe}&dimension=ou:{ou}
                             &displayProperty=NAME{extra}
        """
        extra = cls._extra_params(config)

        if de_type == "tracker_numeric":
            fetch_expr = (
                f"dhis2Get('api/analytics/events/aggregate/{prog_uid}"
                f"?stage={stage_uid}&value={de_uid}&aggregationType={agg_type}"
                f"&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou)"
                + f"'{extra}')"
            )
            period_resolve = f"const rpe = resolveRelativePeriod(pe);"
        else:
            # aggregate or indicator — /api/analytics.json, pass period verbatim
            # (the shared loadData() passes the raw select value; analytics.json
            #  accepts both relative strings and fixed period IDs directly)
            fetch_expr = (
                f"dhis2Get('api/analytics.json"
                f"?dimension=dx:{de_uid}&dimension=pe:'+encodeURIComponent(pe)"
                f"+'&dimension=ou:'+encodeURIComponent(ou)+'&displayProperty=NAME"
                + extra
                + "')"
            )
            period_resolve = ""  # pe is used as-is

        return f"""\
        async function initChart{n}(ou, pe) {{
          document.getElementById('loading{n}').style.display = 'none';
          const cvs = document.getElementById('chart{n}');
          cvs.style.display = 'block';
          if (PREVIEW) {{
            const banner = document.getElementById('demoBanner{n}');
            if (banner) banner.style.display = 'block';
            renderChart{n}Sample(cvs);
            return;
          }}
          document.getElementById('demoBanner{n}').style.display = 'none';
          const errEl = document.getElementById('error{n}');
          errEl.style.display = 'none';
          try {{
            {period_resolve}
            const d = await {fetch_expr};
            if (!d.rows || !d.rows.length) {{
              errEl.textContent = 'No data for the selected period / org unit.';
              errEl.style.display = 'block';
              return;
            }}
            renderChart{n}Real(cvs, d);
          }} catch (e) {{
            console.error('[Chart{n}]', e);
            errEl.textContent = 'Failed to load: ' + e.message;
            errEl.style.display = 'block';
          }}
        }}"""
