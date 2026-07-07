"""
GroupedBarPlugin — Grouped (side-by-side) bar chart comparing multiple data sources.

Supports 2-3 metrics of types: tracker_numeric, aggregate, indicator.
Pure aggregate/indicator sources are batched into a single analytics.json call.
Mixed or tracker_numeric sources each get their own API call fetched in parallel.
Bars are NOT stacked — each period shows one group of side-by-side bars.
"""
from __future__ import annotations

from charts.plugins.base import (
    ChartPlugin,
    MetricControl,
    TimeGrainControl,
)
from charts.plugins.shared_js import PALETTE_JS


class GroupedBarPlugin(ChartPlugin):
    id          = "grouped_bar"
    label       = "Grouped bar — compare sources"
    hidden      = True  # superseded by unified BarPlugin
    icon        = "📊"
    description = "Side-by-side bars per period, one group per data element (up to 3 sources)"
    preview_id  = "bar_grouped"

    metrics = [
        MetricControl(
            id="metrics",
            label="Metrics to compare",
            max_count=3,
            allowed_types=("tracker_numeric", "aggregate", "indicator"),
            default_agg="SUM",
            required=True,
        )
    ]
    dimensions = []
    time_grain = TimeGrainControl(default="Monthly")

    # ── JS generators ─────────────────────────────────────────────────────────

    @classmethod
    def _sample_js(cls, n: int, metric_labels=None) -> str:
        import json as _json
        _ml = [s for s in (metric_labels or []) if s]
        _defaults = ["Group A", "Group B", "Group C"]
        _demo = [[80,95,70,110,130,115], [60,72,55,88,100,92], [45,58,40,65,78,70]]
        # One group per selected metric (so the legend shows real names), default to 3 demo groups.
        _names = _ml if _ml else _defaults
        _names = _names[:3]
        datasets_js = ",\n                ".join(
            f"{{label:{_json.dumps(_names[i])}, data:{_demo[i]}, backgroundColor:PALETTE[{i}]}}"
            for i in range(len(_names))
        )
        return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          {PALETTE_JS}
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{
              labels: ['Jan','Feb','Mar','Apr','May','Jun'],
              datasets: [
                {datasets_js}
              ]
            }},
            options: {{
              responsive: true,
              plugins: {{ legend: {{ position: 'bottom' }} }},
              scales: {{
                x: {{ ticks: {{ maxRotation: 45 }} }},
                y: {{ beginAtZero: true }}
              }}
            }}
          }});
        }}"""

    @classmethod
    def _real_js_all_aggregate(cls, n: int, sources: list[dict], config: dict) -> str:
        """Single analytics.json call when all sources are aggregate/indicator."""
        extra = cls._extra_params(config)
        de_ids = ";".join(s["uid"] for s in sources)
        de_names_js = (
            "{"
            + ",".join(
                f'"{s["uid"]}":"{s["name"].replace(chr(34), chr(39))}"'
                for s in sources
            )
            + "}"
        )
        return f"""\
        function renderChart{n}Real(cvs, d) {{
          {PALETTE_JS}
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          const dxIdx  = d.headers.findIndex(h => h.name === 'dx');
          const peIdx  = d.headers.findIndex(h => h.name === 'pe');
          const valIdx = d.headers.findIndex(h => h.name === 'value');
          const dxIds  = [...new Set(d.rows.map(r => r[dxIdx]))];
          const periods = [...new Set(d.rows.map(r => r[peIdx]))].sort();
          const DE_NAMES = {de_names_js};
          const datasets = dxIds.map((dx, i) => {{
            const label = (d.metaData && d.metaData.items && d.metaData.items[dx])
              ? d.metaData.items[dx].name : (DE_NAMES[dx] || dx);
            const vals = periods.map(p => {{
              const row = d.rows.find(r => r[dxIdx] === dx && r[peIdx] === p);
              return row ? parseFloat(row[valIdx]) || 0 : 0;
            }});
            return {{
              label, data: vals,
              backgroundColor: PALETTE[i % PALETTE.length]
            }};
          }});
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{ labels: periods.map(formatPeriodLabel), datasets }},
            options: {{
              responsive: true,
              plugins: {{ legend: {{ position: 'bottom' }} }},
              scales: {{
                x: {{ ticks: {{ maxRotation: 45 }} }},
                y: {{ beginAtZero: true }}
              }}
            }}
          }});
        }}
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
          try {{
            const d = await dhis2Get(
              'api/analytics.json?dimension=dx:{de_ids}'
              + '&dimension=pe:' + encodeURIComponent(pe)
              + '&dimension=ou:' + encodeURIComponent(ou)
              + '&displayProperty=NAME{extra}'
            );
            if (!d.rows || !d.rows.length) {{
              document.getElementById('error{n}').textContent = 'No data for the selected period / org unit.';
              document.getElementById('error{n}').style.display = 'block';
              return;
            }}
            renderChart{n}Real(cvs, d);
          }} catch(e) {{
            console.error('[Chart{n}]', e);
            document.getElementById('error{n}').textContent = 'Failed to load: ' + e.message;
            document.getElementById('error{n}').style.display = 'block';
          }}
        }}"""

    @classmethod
    def _real_js_mixed(cls, n: int, sources: list[dict], config: dict) -> str:
        """One parallel fetch per source when any source is tracker_numeric."""
        extra = cls._extra_params(config)
        fetch_calls = []
        for s in sources:
            if s["type"] == "tracker_numeric":
                fetch_calls.append(
                    f"dhis2Get('api/analytics/events/aggregate/{s['prog_uid']}?"
                    f"stage={s['stage_uid']}&value={s['uid']}&aggregationType=SUM"
                    f"&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou)" + (f"+'{extra}'" if extra else "") + ")"
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
        return f"""\
        function renderChart{n}Real(cvs, results) {{
          {PALETTE_JS}
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
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
              label: DE_NAMES[i],
              data: vals,
              backgroundColor: PALETTE[i % PALETTE.length]
            }};
          }});
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{ labels: allPeriods.map(formatPeriodLabel), datasets }},
            options: {{
              responsive: true,
              plugins: {{ legend: {{ position: 'bottom' }} }},
              scales: {{
                x: {{ ticks: {{ maxRotation: 45 }} }},
                y: {{ beginAtZero: true }}
              }}
            }}
          }});
        }}
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
          try {{
            const rpe = resolveRelativePeriod(pe);
            const results = await Promise.all([
              {fetch_array}
            ]);
            if (results.every(d => !d.rows || !d.rows.length)) {{
              document.getElementById('error{n}').textContent = 'No data for the selected period / org unit.';
              document.getElementById('error{n}').style.display = 'block';
              return;
            }}
            renderChart{n}Real(cvs, results);
          }} catch(e) {{
            console.error('[Chart{n}]', e);
            document.getElementById('error{n}').textContent = 'Failed to load: ' + e.message;
            document.getElementById('error{n}').style.display = 'block';
          }}
        }}"""

    # ── Public API ─────────────────────────────────────────────────────────────

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        sources: list[dict] = config.get("metrics", [])

        if len(sources) < 2:
            raise ValueError(
                f"GroupedBarPlugin requires at least 2 metrics, got {len(sources)}"
            )
        if len(sources) > 3:
            sources = sources[:3]

        sample = cls._sample_js(n, metric_labels=[s.get("name") for s in sources if s.get("name")])

        all_agg = all(s.get("type", "aggregate") in ("aggregate", "indicator") for s in sources)
        if all_agg:
            real = cls._real_js_all_aggregate(n, sources, config)
        else:
            real = cls._real_js_mixed(n, sources, config)

        return sample + "\n" + real
