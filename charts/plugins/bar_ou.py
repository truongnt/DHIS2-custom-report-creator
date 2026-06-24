"""
BarOuPlugin — Horizontal bar chart comparing values across org units.

Uses the selected period (no time axis) and always queries USER_ORGUNIT_CHILDREN
as the org-unit dimension, so each child unit becomes one bar.

Supports all DE types:
  tracker_option  — stacked horizontal bars (one segment per category value)
  tracker_numeric — single horizontal bar per child OU, aggregated by agg type
  aggregate       — /api/analytics.json, single horizontal bar per child OU
  indicator       — /api/analytics.json, same as aggregate
"""
from __future__ import annotations

from charts.plugins.base import ChartPlugin, MetricControl, DimensionControl, TimeGrainControl
from charts.plugins.shared_js import PALETTE_JS


class BarOuPlugin(ChartPlugin):
    id          = "bar_ou"
    label       = "Bar — by org unit"
    hidden      = True  # org unit axis will be a SelectControl option in BarPlugin v2
    icon        = "🏥"
    description = "Horizontal bar comparing values across org units"
    preview_id  = "bar_horizontal_ou"

    metrics = [
        MetricControl(
            id="metric",
            label="Metric",
            max_count=1,
            allowed_types=("tracker_option", "tracker_numeric", "aggregate", "indicator"),
            default_agg="SUM",
            show_agg_picker=True,
        )
    ]
    dimensions: list[DimensionControl] = []
    time_grain = None   # fixed: uses selected period, no time axis

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        """
        Parameters
        ----------
        n      : card index
        config : card config dict.  Expected keys:
                   metrics[0] — {uid, type, agg, prog_uid, stage_uid}
                 OR legacy keys: de_uid, de_type, agg_type, prog_uid, stage_uid
        """
        # ── resolve metric ────────────────────────────────────────────────────
        metrics = config.get("metrics") or []
        if metrics:
            m        = metrics[0]
            de_uid   = m.get("uid", "")
            de_type  = m.get("type", "aggregate")
            agg      = m.get("agg", "SUM")
            prog_uid = m.get("prog_uid", "")
            stg_uid  = m.get("stage_uid", "")
        else:
            de_uid   = config.get("de_uid", "")
            de_type  = config.get("de_type", "aggregate")
            agg      = config.get("agg_type", "SUM")
            prog_uid = config.get("prog_uid", "")
            stg_uid  = config.get("stage_uid", "")

        sample = _sample_js(n)

        if de_type == "tracker_option":
            real = _real_js_tracker_option(n, de_uid, prog_uid, stg_uid, config)
        elif de_type == "tracker_numeric":
            real = _real_js_tracker_numeric(n, de_uid, prog_uid, stg_uid, agg, config)
        else:
            # aggregate or indicator
            real = _real_js_aggregate(n, de_uid, config)

        return sample + "\n" + real


# ── Sample (preview) renderer ─────────────────────────────────────────────────

def _sample_js(n: int) -> str:
    return f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {PALETTE_JS}
          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{
              labels: ['District A', 'District B', 'District C',
                       'District D', 'District E', 'District F'],
              datasets: [{{
                label: 'Value',
                data: [320, 275, 410, 190, 355, 280],
                backgroundColor: PALETTE[1]
              }}]
            }},
            options: {{
              indexAxis: 'y',
              responsive: true,
              plugins: {{ legend: {{ display: false }} }},
              scales: {{ x: {{ beginAtZero: true }} }}
            }}
          }});
        }}"""


# ── Real-data renderers ───────────────────────────────────────────────────────

def _real_js_tracker_option(
    n: int, de_uid: str, prog_uid: str, stg_uid: str, config: dict
) -> str:
    """
    tracker_option — stacked horizontal bars, one segment per category option.
    API: api/analytics/events/aggregate/{prog_uid}
           ?stage={stg_uid}
           &dimension={stg_uid}.{de_uid}
           &dimension=pe:{rpe}
           &dimension=ou:USER_ORGUNIT_CHILDREN
    Sort/limit is skipped for stacked multi-series (tracker_option).
    """
    extra = BarOuPlugin._extra_params(config)
    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {PALETTE_JS}
          const ouIdx  = d.headers.findIndex(h => h.name === 'ou');
          const catIdx = d.headers.findIndex(h => h.name === '{de_uid}');
          const valIdx = d.headers.findIndex(h => h.name === 'value');

          const getName = (id) => (d.metaData && d.metaData.items && d.metaData.items[id])
                                   ? d.metaData.items[id].name : id;

          const ous  = [...new Set(d.rows.map(r => r[ouIdx]))];
          const cats = [...new Set(d.rows.map(r => r[catIdx]))];

          // grouped[category][ou] = total value
          const grouped = {{}};
          d.rows.forEach(r => {{
            const ou  = r[ouIdx];
            const cat = r[catIdx];
            if (!grouped[cat]) grouped[cat] = {{}};
            grouped[cat][ou] = (grouped[cat][ou] || 0) + (parseFloat(r[valIdx]) || 0);
          }});

          const ouLabels = ous.map(getName);
          const datasets = cats.map((cat, i) => ({{
            label: getName(cat),
            data: ous.map(o => grouped[cat][o] || 0),
            backgroundColor: PALETTE[i % PALETTE.length],
          }}));

          chart{n}Inst = new Chart(cvs.getContext('2d'), {{
            type: 'bar',
            data: {{ labels: ouLabels, datasets }},
            options: {{
              indexAxis: 'y',
              responsive: true,
              plugins: {{ legend: {{ position: 'bottom' }} }},
              scales: {{
                x: {{ stacked: true, beginAtZero: true }},
                y: {{ stacked: true }}
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
            const d = await dhis2Get(
              'api/analytics/events/aggregate/{prog_uid}'
              + '?stage={stg_uid}'
              + '&dimension={stg_uid}.{de_uid}'
              + '&dimension=pe:' + encodeURIComponent(rpe)
              + '&dimension=ou:USER_ORGUNIT_CHILDREN'{extra}'
            );
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


def _real_js_tracker_numeric(
    n: int, de_uid: str, prog_uid: str, stg_uid: str, agg: str, config: dict
) -> str:
    """
    tracker_numeric — single horizontal bar per child OU.
    API: api/analytics/events/aggregate/{prog_uid}
           ?stage={stg_uid}
           &value={de_uid}
           &aggregationType={agg}
           &dimension=pe:{rpe}
           &dimension=ou:USER_ORGUNIT_CHILDREN
    Applies full sort/limit on labels=ou names, vals=values.
    """
    extra = BarOuPlugin._extra_params(config)
    sort_limit = BarOuPlugin._sort_limit_js(config, "combined")
    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {PALETTE_JS}
          const ouIdx  = d.headers.findIndex(h => h.name === 'ou');
          const valIdx = d.headers.findIndex(h => h.name === 'value');

          const getName = (id) => (d.metaData && d.metaData.items && d.metaData.items[id])
                                   ? d.metaData.items[id].name : id;

          // Sum values per OU (there may be multiple period rows per OU)
          const ouMap = {{}};
          d.rows.forEach(r => {{
            const name = getName(r[ouIdx]);
            ouMap[name] = (ouMap[name] || 0) + (parseFloat(r[valIdx]) || 0);
          }});

          const labels = Object.keys(ouMap);
          const vals   = Object.values(ouMap);

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
                backgroundColor: PALETTE[1]
              }}]
            }},
            options: {{
              indexAxis: 'y',
              responsive: true,
              plugins: {{ legend: {{ display: false }} }},
              scales: {{ x: {{ beginAtZero: true }} }}
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
            const d = await dhis2Get(
              'api/analytics/events/aggregate/{prog_uid}'
              + '?stage={stg_uid}'
              + '&value={de_uid}'
              + '&aggregationType={agg}'
              + '&dimension=pe:' + encodeURIComponent(rpe)
              + '&dimension=ou:USER_ORGUNIT_CHILDREN'{extra}'
            );
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


def _real_js_aggregate(n: int, de_uid: str, config: dict) -> str:
    """
    aggregate / indicator — single horizontal bar per child OU.
    API: api/analytics.json
           ?dimension=dx:{de_uid}
           &dimension=pe:{pe}
           &dimension=ou:USER_ORGUNIT_CHILDREN
           &displayProperty=NAME
    Note: aggregate/indicator use the raw pe value (not resolved) because
    /analytics.json handles relative periods natively. The caller passes the
    raw value from the period selector.
    Applies full sort/limit on labels=ou names, vals=values.
    """
    extra = BarOuPlugin._extra_params(config)
    sort_limit = BarOuPlugin._sort_limit_js(config, "combined")
    return f"""\
        function renderChart{n}Real(cvs, d) {{
          if (chart{n}Inst) {{ chart{n}Inst.destroy(); chart{n}Inst = null; }}
          {PALETTE_JS}
          const ouIdx  = d.headers.findIndex(h => h.name === 'ou');
          const valIdx = d.headers.findIndex(h => h.name === 'value');

          const getName = (id) => (d.metaData && d.metaData.items && d.metaData.items[id])
                                   ? d.metaData.items[id].name : id;

          // Sum values per OU across all period rows
          const ouMap = {{}};
          d.rows.forEach(r => {{
            const name = getName(r[ouIdx]);
            ouMap[name] = (ouMap[name] || 0) + (parseFloat(r[valIdx]) || 0);
          }});

          const labels = Object.keys(ouMap);
          const vals   = Object.values(ouMap);

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
                backgroundColor: PALETTE[1]
              }}]
            }},
            options: {{
              indexAxis: 'y',
              responsive: true,
              plugins: {{ legend: {{ display: false }} }},
              scales: {{ x: {{ beginAtZero: true }} }}
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
              'api/analytics.json'
              + '?dimension=dx:{de_uid}'
              + '&dimension=pe:' + encodeURIComponent(pe)
              + '&dimension=ou:USER_ORGUNIT_CHILDREN'
              + '&displayProperty=NAME'{extra}
            );
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
