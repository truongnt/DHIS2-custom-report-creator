"""
CustomHtmlPlugin — render a user-supplied HTML/CSS/JS template inside a sandboxed
iframe, bound to the chart's data. Inspired by the Superset "ECDS HTML Widget"
(github.com/truongnt/Superset → ecds-html-widget).

Data contract (mirrors the Data Table: metrics = columns, dimensions = rows, plus a
Raw mode). The same fetch pipeline as `table_view` is reused — this plugin simply
**overrides `_tMount{n}`** so the computed `{cols, rows}` are rendered as an HTML widget
instead of a table.

Inside the iframe the template can use:
  window.__chartData     — Array<Object>, one object per row keyed by column name
  window.DATA            — alias of __chartData
  window.FIRST           — __chartData[0] || {}
  window.__columnNames   — Array<String> of column headers
  window.__metricLabels  — Array<String> of the selected metric names
  {{Column name}}        — replaced (before render) with FIRST row's value
                           (numbers get thousands separators / 2 decimals)

plugin_options keys
-------------------
mode       : Aggregated | Raw   (same as table_view)
html       : the HTML/CSS/JS template (TextAreaControl)
min_height : iframe minimum height in px (preset or custom number)
"""
from __future__ import annotations

import json as _json
import re as _re

from charts.plugins.base import (
    ChartPlugin, DimensionControl, MetricControl, SelectControl,
    TextAreaControl, TimeGrainControl,
)
from charts.plugins.table_view import TablePlugin


def _po(po: dict, key: str, default):
    return po.get(key, default) if po else default


def _metric_name(m: dict) -> str:
    """Display/key name for a metric: the user's alias if set, else the real name/uid.
    This is what {{<name> @ period}} and the matrix/columns are keyed by."""
    return (m.get("alias") or "").strip() or m.get("name") or m.get("uid", "")


DEFAULT_HTML = """\
<div style="padding:16px;font-family:system-ui,Segoe UI,sans-serif;color:#1e2d3d">
  <h3 style="margin:0 0 10px;color:#1a6fa8">Custom HTML widget</h3>
  <p style="margin:0 0 12px;color:#5a7a9a">
    Edit the HTML/JS in the chart options. Data is available as
    <code>window.DATA</code> / <code>window.FIRST</code> and via <code>{{Column}}</code>.
  </p>
  <div id="hw-table"></div>
  <script>
    var cols = window.__columnNames || [];
    var rows = window.DATA || [];
    var th = cols.map(function(c){ return '<th style="text-align:left;padding:4px 8px;border-bottom:2px solid #1a6fa8">'+c+'</th>'; }).join('');
    var tr = rows.map(function(r){
      return '<tr>'+cols.map(function(c){ return '<td style="padding:4px 8px;border-bottom:1px solid #e3e9ef">'+(r[c]==null?'':r[c])+'</td>'; }).join('')+'</tr>';
    }).join('');
    document.getElementById('hw-table').innerHTML =
      '<table style="border-collapse:collapse;font-size:13px;width:100%">'
      + '<thead><tr>'+th+'</tr></thead><tbody>'+tr+'</tbody></table>'
      + '<p style="margin-top:10px;color:#8aa0b4;font-size:12px">'+rows.length+' row(s)</p>';
  </script>
</div>"""


# Rendered with str.replace (NOT an f-string / .format) so the JS braces, regex and
# escapes stay literal. Placeholders: __N__ __HTML__ __LABELS__ __MINH__.
_RENDER_TMPL = r"""
    // Override the table's mount: render {cols, rows} as an HTML widget in an iframe.
    function _tMount__N__(cvs, cols, rows, meta) {
      cvs.style.display = 'none';
      // Collapse the fixed-height chart-wrapper so the widget iframe sits flush (no gap).
      var _w = cvs.closest('.chart-wrapper');
      if (_w) { _w.style.height = '0'; _w.style.minHeight = '0'; _w.style.margin = '0'; _w.style.padding = '0'; }
      var par = cvs.closest('.card-body') || cvs.parentElement;
      var data = (rows || []).map(function (r) {
        var o = {}; (cols || []).forEach(function (c, i) { o[c] = r[i]; }); return o;
      });
      var first = data[0] || {};
      // Period matrix (supplied by the period-matrix init): periods + metric→period values.
      var __periods = (meta && meta.periods) || [];
      var __matrix  = (meta && meta.matrix)  || {};
      var tpl = __HTML__;
      function _fmt(v) {
        if (v == null) return '';
        var num = (typeof v === 'number') ? v
                 : (/^-?\d+(\.\d+)?$/.test(String(v).trim()) ? parseFloat(v) : NaN);
        if (!isNaN(num)) return Number.isInteger(num) ? num.toLocaleString('en-US') : num.toFixed(2);
        return String(v);
      }
      // {{Column}} → first row; {{Metric @ 202601}} or {{Metric @ Jan 2026}} → matrix cell.
      function _lookup(key) {
        var at = key.indexOf('@');
        if (at >= 0) {
          var mname = key.slice(0, at).trim();
          var pid   = key.slice(at + 1).trim();
          var col   = __matrix[mname] || {};
          if (col[pid] != null) return col[pid];
          var f = __periods.filter(function (x) { return x.label === pid; })[0];
          return f ? col[f.id] : null;
        }
        return first[key];
      }
      var filled = tpl.replace(/\{\{([^}]+)\}\}/g, function (_m, k) { return _fmt(_lookup(k.trim())); });
      // Build the iframe document. Every "<" is written as \x3c so this parent inline
      // script contains NO literal HTML script/body end-tags in its source — otherwise the
      // host page HTML tokenizer would act on them and merge/truncate scripts so that
      // initChart never gets defined. Runtime string values are unchanged.
      var head = '\x3c!doctype html>\x3chtml>\x3chead>\x3cmeta charset="utf-8">'
        + '\x3cstyle>html,body{margin:0;padding:0;font-family:system-ui,Segoe UI,Arial,sans-serif;}\x3c/style>\x3c/head>\x3cbody>';
      var dataScript = '\x3cscript>'
        + 'window.__chartData=' + JSON.stringify(data) + ';'
        + 'window.__columnNames=' + JSON.stringify(cols || []) + ';'
        + 'window.__metricLabels=' + JSON.stringify(__LABELS__) + ';'
        + 'window.__periods=' + JSON.stringify(__periods) + ';'
        + 'window.__matrix=' + JSON.stringify(__matrix) + ';'
        + 'window.DATA=window.__chartData;window.FIRST=window.__chartData[0]||{};'
        + 'window.val=function(m,p){var c=(window.__matrix[m]||{});if(c[p]!=null)return c[p];'
        + 'var f=window.__periods.filter(function(x){return x.label===p;})[0];'
        + 'return f?(c[f.id]!=null?c[f.id]:""):"";};'
        + '\x3c/script>';
      var resize = '\x3cscript>(function(){function r(){try{parent.postMessage('
        + '{__hwH:document.documentElement.scrollHeight,__hwId:__N__},"*");}catch(e){}}'
        + 'window.addEventListener("load",r);setTimeout(r,150);setTimeout(r,600);'
        + 'try{new ResizeObserver(r).observe(document.body);}catch(e){}})();\x3c/script>';
      var srcdoc = head + dataScript + filled + resize + '\x3c/body>\x3c/html>';
      var f = par.querySelector('[data-hw="__N__"]');
      if (!f) {
        f = document.createElement('iframe');
        f.setAttribute('data-hw', '__N__');
        // allow-same-origin so PNG/PDF export can read + snapshot the widget's rendered
        // content (a cross-origin sandbox comes out blank in the export).
        f.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox');
        f.style.cssText = 'width:100%;border:0;display:block;background:#fff;min-height:__MINH__px;';
        par.appendChild(f);
      }
      f.srcdoc = srcdoc;
      var ld = document.getElementById('loading__N__'); if (ld) ld.style.display = 'none';
      var er = document.getElementById('error__N__'); if (er) er.style.display = 'none';
    }
    // Auto-resize the iframe to its content height.
    window.addEventListener('message', function (e) {
      if (e.data && e.data.__hwId === __N__ && e.data.__hwH) {
        var f = document.querySelector('[data-hw="__N__"]');
        if (f) f.style.height = Math.max(__MINH__, e.data.__hwH) + 'px';
      }
    });
"""


# Period-matrix init: fetch each metric BY PERIOD (pe as a dimension at the selected grain)
# and hand _tMount{n} one row per period + a {periods, matrix} meta so the template can
# address a single cell, e.g. {{Total tests @ 202601}} → Jan 2026's value. Rendered with
# str.replace so JS braces stay literal. Placeholders: __N__ __METRICS__ __FILT__.
_MATRIX_INIT_TMPL = r"""
    // Override the table's initChart: build a metric × period matrix (dx domain).
    function initChart__N__(ou, pe) {
      var ld = document.getElementById('loading__N__'); if (ld) ld.style.display = 'none';
      var cvs = document.getElementById('chart__N__'); cvs.style.display = 'block';
      if (PREVIEW) { renderChart__N__Sample(cvs); return; }
      var er0 = document.getElementById('error__N__'); if (er0) er0.style.display = 'none';
      (async function () {
        try {
          var METRICS = __METRICS__;
          var dxUids = METRICS.map(function (m) { return m.uid; }).join(';');
          // Period ids are driven by the TIME GRAIN (not the period dropdown): a fixed
          // window at the chosen grain — Monthly→last 12 months, Quarterly→last 8 quarters,
          // Yearly→last 5 years. Template addresses a cell by its exact id, e.g. @ 2025Q4.
          var GRAIN = "__GRAIN__";
          function _grainPeriods(g) {
            var now = new Date(), y = now.getFullYear(), m = now.getMonth() + 1, out = [];
            function pad(n) { return String(n).padStart(2, '0'); }
            if (g === 'Quarterly') {
              var q = Math.ceil(m / 3), yr = y;
              for (var i = 0; i < 8; i++) { out.unshift(yr + 'Q' + q); q--; if (q <= 0) { q = 4; yr--; } }
              return out.join(';');
            }
            if (g === 'Yearly') {
              for (var j = 0; j < 5; j++) out.unshift(String(y - j));
              return out.join(';');
            }
            var mo = m, yr2 = y;            // Monthly (default): last 12 months
            for (var k = 0; k < 12; k++) { out.unshift(yr2 + pad(mo)); mo--; if (mo <= 0) { mo = 12; yr2--; } }
            return out.join(';');
          }
          var rpe = (GRAIN === 'Monthly' || GRAIN === 'Quarterly' || GRAIN === 'Yearly')
                  ? _grainPeriods(GRAIN) : resolveRelativePeriod(pe);
          var d = await dhis2Get('api/analytics.json?dimension=dx:' + encodeURIComponent(dxUids)
            + '&dimension=pe:' + encodeURIComponent(rpe)
            + '&filter=ou:' + encodeURIComponent(ou)
            + '&displayProperty=NAME__FILT__');
          var H = d.headers || [];
          var dxI = H.findIndex(function (h) { return h.name === 'dx'; });
          var peI = H.findIndex(function (h) { return h.name === 'pe'; });
          var vI  = H.findIndex(function (h) { return h.name === 'value'; });
          var matrix = {};                       // matrix[uid][peId] = value
          (d.rows || []).forEach(function (r) {
            var dx = r[dxI], p = r[peI], v = r[vI];
            (matrix[dx] = matrix[dx] || {})[p] = (v != null && v !== '' && !isNaN(+v)) ? +v : v;
          });
          var peOrder = (d.metaData && d.metaData.dimensions && d.metaData.dimensions.pe)
                      || rpe.split(';');
          var periods = peOrder.map(function (id) { return { id: id, label: formatPeriodLabel(id) }; });
          var matrixByName = {};
          METRICS.forEach(function (m) { matrixByName[m.name] = matrix[m.uid] || {}; });
          var cols = ['Period'].concat(METRICS.map(function (m) { return m.name; }));
          var rows = periods.map(function (pr) {
            return [pr.label].concat(METRICS.map(function (m) {
              var v = (matrix[m.uid] || {})[pr.id]; return v != null ? v : '';
            }));
          });
          _tMount__N__(cvs, cols, rows, { periods: periods, matrix: matrixByName });
        } catch (e) {
          console.error('[Chart__N__]', e);
          var er = document.getElementById('error__N__');
          if (er) { er.textContent = 'Failed: ' + e.message; er.style.display = 'block'; }
        }
      })();
    }
"""


def _period_matrix_init_js(n: int, config: dict) -> str:
    metrics = [m for m in (config.get("metrics") or []) if m.get("uid")]
    metrics_js = _json.dumps([{"uid": m["uid"], "name": _metric_name(m)} for m in metrics])
    filt = ChartPlugin._filter_params(config)
    filt = ("&" + filt) if filt else ""
    grain = (config.get("dimensions") or {}).get("time_grain") or "Monthly"
    return (_MATRIX_INIT_TMPL
            .replace("__N__", str(n))
            .replace("__METRICS__", metrics_js)
            .replace("__GRAIN__", grain)
            .replace("__FILT__", filt))


def _html_render_js(n: int, po: dict, config: dict) -> str:
    html = (_po(po, "html", "") or "").strip() or DEFAULT_HTML
    min_raw = str(_po(po, "min_height", "300")).strip()
    min_h = int(min_raw) if min_raw.isdigit() else 300
    # Embed as JS string literals. Escape every "<" to its < unicode form so the
    # template's literal <script>/</script>/<!-- tokens can't drive the host page's HTML
    # "script data" parser (which truncates the inline <script> mid-statement → the whole
    # plugin script fails to define initChart{n}). The runtime string value is unchanged.
    def _embed(s: str) -> str:
        return _json.dumps(s).replace("<", "\\u003c")
    html_js = _embed(html)
    labels = [_metric_name(m) for m in (config.get("metrics") or [])]
    labels_js = _json.dumps(labels).replace("<", "\\u003c")
    return (_RENDER_TMPL
            .replace("__N__", str(n))
            .replace("__HTML__", html_js)
            .replace("__LABELS__", labels_js)
            .replace("__MINH__", str(min_h)))


class CustomHtmlPlugin(ChartPlugin):
    id          = "custom_html"
    label       = "Custom HTML"
    icon        = "🧩"
    description = "Render your own HTML/CSS/JS bound to the chart data (sandboxed iframe)."
    preview_id  = "custom_html"

    metrics = [
        MetricControl(
            id="metric",
            label="Data element(s) / indicators",
            max_count=50,   # effectively unlimited — a custom report can bind many metrics
            allowed_types=("aggregate", "indicator", "tracker_numeric", "tracker_option"),
            default_agg="SUM",
        )
    ]
    dimensions = [
        DimensionControl(
            id="dimension",
            label="Disaggregate by (rows)",
            allowed_types=("tracker_option", "tracker_numeric"),
            required=False,
            max_count=4,
            show_alias=True,
            hint="Optional DE/PA(s) to split rows by; data is exposed as window.DATA",
        )
    ]
    options = [
        SelectControl("mode",       "Data",       ("Aggregated", "Raw"), "Aggregated"),
        SelectControl("min_height", "Min height", ("200", "300", "400", "600"), "300"),
        TextAreaControl("html", "HTML / JS template", default=DEFAULT_HTML, height=260,
                        placeholder="Write HTML/CSS/JS. Use window.DATA / FIRST or {{Column}}."),
    ]
    time_grain = TimeGrainControl(default="Monthly")

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        po = config.get("plugin_options") or {}
        metrics = [m for m in (config.get("metrics") or []) if m.get("uid")]
        mode = _po(po, "mode", "Aggregated")
        # dx-domain metrics (aggregate / indicator) can be split BY PERIOD so the template
        # can address a single month, e.g. {{Total tests @ 202601}}. Tracker metrics keep
        # the table pipeline (event-domain period split is a follow-up).
        dx_domain = bool(metrics) and all(
            m.get("type") in ("aggregate", "indicator") for m in metrics)
        # Reuse the table's pipeline for scaffolding (sample render, _tMount base, helpers),
        # then override _tMount{n} (HTML widget) — and, for the period matrix, initChart{n}.
        # Function-declaration hoisting makes the later (our) definitions win.
        table_js = TablePlugin.build_js(n, config)
        out = table_js + "\n" + _html_render_js(n, po, config)
        # A template that addresses per-period cells — {{Metric @ 2025Q3}} — NEEDS the
        # period matrix (one fetch per period), regardless of the Aggregated/Raw toggle.
        html_tmpl = _po(po, "html", "") or ""
        needs_period = bool(_re.search(r"\{\{[^{}]*@[^{}]*\}\}", html_tmpl))
        if dx_domain and (mode == "Aggregated" or needs_period):
            out += "\n" + _period_matrix_init_js(n, config)
        return out
