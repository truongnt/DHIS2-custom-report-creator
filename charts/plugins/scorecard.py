"""
ScorecardPlugin — renders a single KPI value using Canvas 2D (no Chart.js).

Supported DE types: aggregate, indicator, tracker_numeric.

plugin_options keys
-------------------
y_format     : Default | 1,234 | 1.2K | %
value_color  : Green | Blue | Red | Orange
font_size    : Large | Medium | Small
"""
from __future__ import annotations

import json as _json

from charts.plugins.base import ChartPlugin, MetricControl, SelectControl, TimeGrainControl


def _po(po: dict, key: str, default):
    return po.get(key, default) if po else default


# ── Plugin class ───────────────────────────────────────────────────────────────

class ScorecardPlugin(ChartPlugin):
    id          = "scorecard"
    label       = "Scorecard"
    icon        = "🎯"
    description = "Single KPI value with period label"
    preview_id  = "scorecard"

    metrics = [
        MetricControl(
            id="metric",
            label="KPI value",
            max_count=1,
            allowed_types=("aggregate", "indicator", "tracker_numeric"),
            default_agg="SUM",
        )
    ]
    dimensions = []
    options = [
        SelectControl("y_format",    "Format",     ("Default", "1,234", "1.2K", "%"), "Default"),
        SelectControl("value_color", "Value color", ("Green", "Blue", "Red", "Orange"), "Green"),
        SelectControl("font_size",   "Font size",   ("Large", "Medium", "Small"),      "Large"),
    ]
    time_grain: TimeGrainControl | None = None

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        po        = config.get("plugin_options") or {}
        metrics   = config.get("metrics", [])
        m         = metrics[0] if metrics else {}
        uid       = m.get("uid", "")
        de_type   = m.get("type", "aggregate")
        agg       = m.get("agg", "SUM")
        prog_uid  = m.get("prog_uid", "")
        stage_uid = m.get("stage_uid", "")
        title     = config.get("title", "KPI").replace("'", "\\'")
        extra     = cls._extra_params(config)

        y_format    = _po(po, "y_format",    "Default")
        value_color = _po(po, "value_color", "Green")
        font_size   = _po(po, "font_size",   "Large")

        _COLORS = {"Green": "#27ae60", "Blue": "#3498db", "Red": "#e74c3c", "Orange": "#f39c12"}
        color_hex = _COLORS.get(value_color, "#27ae60")

        _SIZES = {"Large": "52", "Medium": "38", "Small": "28"}
        size_px = _SIZES.get(font_size, "52")

        # JS format function (inlined as a string literal in the generated JS)
        if y_format == "1,234":
            fmt_js = "v => Number(v).toLocaleString()"
        elif y_format == "1.2K":
            fmt_js = "v => Math.abs(v) >= 1000 ? (v/1000).toFixed(1)+'K' : String(v)"
        elif y_format == "%":
            fmt_js = "v => v+'%'"
        else:  # Default — no transformation
            fmt_js = "v => String(v)"

        sample_value = {"1,234": "1,234", "1.2K": "1.2K", "%": "57%"}.get(y_format, "1234")

        sample_js = f"""\
        let chart{n}Inst = null;
        function renderChart{n}Sample(cvs) {{
          chart{n}Inst = null;
          const ctx = cvs.getContext('2d');
          const w = cvs.parentElement.clientWidth || 260;
          const h = 200;
          cvs.width  = w;
          cvs.height = h;
          ctx.clearRect(0, 0, w, h);

          ctx.font = 'bold {size_px}px sans-serif';
          ctx.fillStyle = '{color_hex}';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText('{sample_value}', w / 2, h / 2 - 14);

          ctx.font = '14px sans-serif';
          ctx.fillStyle = '#555';
          ctx.fillText('{title}', w / 2, h / 2 + 34);

          ctx.font = '11px sans-serif';
          ctx.fillStyle = '#999';
          ctx.fillText('Last 12 months', w / 2, h / 2 + 56);
        }}"""

        render_real_js = f"""\
        function renderChart{n}Real(cvs, value, periodLabel) {{
          chart{n}Inst = null;
          const ctx = cvs.getContext('2d');
          const w = cvs.parentElement.clientWidth || 260;
          const h = 200;
          cvs.width  = w;
          cvs.height = h;
          ctx.clearRect(0, 0, w, h);
          const _fmt = {fmt_js};
          const display = (value !== null && value !== undefined) ? _fmt(value) : '—';

          ctx.font = 'bold {size_px}px sans-serif';
          ctx.fillStyle = '{color_hex}';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(display, w / 2, h / 2 - 14);

          ctx.font = '14px sans-serif';
          ctx.fillStyle = '#555';
          ctx.fillText('{title}', w / 2, h / 2 + 34);

          ctx.font = '11px sans-serif';
          ctx.fillStyle = '#999';
          ctx.fillText(periodLabel || '', w / 2, h / 2 + 56);
        }}"""

        if de_type == "tracker_numeric":
            fetch_block = f"""\
            const rpe = resolveRelativePeriod(pe);
            const d = await dhis2Get(
              'api/analytics/events/aggregate/{prog_uid}?stage={stage_uid}'
              +'&value={uid}&aggregationType={agg}'
              +'&dimension=pe:'+encodeURIComponent(rpe)
              +'&dimension=ou:'+encodeURIComponent(ou)+'{extra}'
            );
            const valIdx = d.headers.findIndex(h => h.name === 'value');
            const val = (d.rows && d.rows.length) ? parseFloat(d.rows[0][valIdx]) : null;
            renderChart{n}Real(cvs, val, rpe);"""
        else:
            fetch_block = f"""\
            const d = await dhis2Get(
              'api/analytics.json?dimension=dx:{uid}'
              +'&dimension=pe:'+encodeURIComponent(pe)
              +'&dimension=ou:'+encodeURIComponent(ou)
              +'&displayProperty=NAME{extra}'
            );
            const valIdx = d.headers.findIndex(h => h.name === 'value');
            const val = (d.rows && d.rows.length) ? parseFloat(d.rows[0][valIdx]) : null;
            renderChart{n}Real(cvs, val, pe);"""

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
          const errEl=document.getElementById('error{n}');
          errEl.style.display='none';
          try {{
            {fetch_block}
          }} catch(e) {{
            console.error('[Chart{n}]',e);errEl.textContent='Failed: '+e.message;errEl.style.display='block';
          }}
        }}"""

        return sample_js + "\n" + render_real_js + "\n" + init_js
