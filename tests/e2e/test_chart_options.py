"""
E2E per-option render tests for the Chart.js charts (bar, line, pie, combined) and the
canvas-drawn scorecard. Each option is verified by its REAL effect on the live chart —
read back from Chart.getChart('chart1') (v4 registry) or by sampling canvas pixels —
not by string-matching the HTML. Screenshots saved as evidence.

Run: pip install -r requirements-dev.txt ; pytest tests/e2e/test_chart_options.py -m e2e -s
"""
import pytest

from charts.fixed_templates import generate_preview_page

# Read the live Chart.js config back from the registry (cross-scope safe).
_CHART_PROBE = r"""
const c = Chart.getChart('chart1');
if (!c) return null;
const s = c.options.scales || {};
const ds0 = c.data.datasets[0] || {};
const bg = Array.isArray(ds0.backgroundColor) ? ds0.backgroundColor[0] : ds0.backgroundColor;
return {
  type: c.config.type,
  indexAxis: c.options.indexAxis || 'x',
  xStacked: !!(s.x && s.x.stacked),
  yStacked: !!(s.y && s.y.stacked),
  yType: (s.y && s.y.type) || 'linear',
  hasY2: !!s.y2,
  legendDisplay: c.options.plugins?.legend?.display,
  legendPos: c.options.plugins?.legend?.position,
  cutout: c.options.cutout,
  tension: ds0.tension,
  fill: ds0.fill,
  bg: bg,
  nDatasets: c.data.datasets.length,
};
"""

_M = lambda name, uid: {"uid": uid, "name": name, "type": "aggregate", "agg": "SUM"}


def _probe(render_preview, name, plugin_id, metrics, **opts):
    cfg = {"plugin_id": plugin_id, "title": f"E2E {name}",
           "metrics": metrics, "plugin_options": opts}
    if plugin_id == "pie_cat":
        cfg["dimension"] = {"uid": "deDim000001", "name": "Species"}
    ev = render_preview(generate_preview_page(cfg), f"opt_{name}")
    severe = [e for e in ev["severe"] if "favicon" not in (e.get("message") or "").lower()]
    assert not severe, f"{name}: JS errors:\n" + "\n".join(e.get("message", "") for e in severe)
    return ev, ev["driver"].execute_script(_CHART_PROBE)


# ── Bar ───────────────────────────────────────────────────────────────────────

@pytest.mark.e2e
def test_bar_orientation(render_preview):
    """REQ-BAR-ORIENT-01: Horizontal orientation flips the Chart.js index axis to 'y'."""
    _, v = _probe(render_preview, "bar_vert", "bar", [_M("Cases", "deBar000001")], orientation="Vertical")
    assert v["indexAxis"] == "x"
    _, h = _probe(render_preview, "bar_horz", "bar", [_M("Cases", "deBar000001")], orientation="Horizontal")
    assert h["indexAxis"] == "y"


@pytest.mark.e2e
def test_bar_stack_mode(render_preview):
    """REQ-BAR-STACK-01: Stack mode marks the axes stacked; None does not."""
    _, none = _probe(render_preview, "bar_nostack", "bar", [_M("Cases", "deBar000001")], stack_mode="None")
    _, stk = _probe(render_preview, "bar_stack", "bar", [_M("Cases", "deBar000001")], stack_mode="Stack")
    assert (stk["xStacked"] or stk["yStacked"])
    assert not (none["xStacked"] or none["yStacked"])


@pytest.mark.e2e
def test_bar_color_scheme(render_preview):
    """REQ-BAR-COLOR-01: changing color_scheme changes the dataset colours."""
    _, a = _probe(render_preview, "bar_default", "bar", [_M("Cases", "deBar000001")], color_scheme="Default")
    _, b = _probe(render_preview, "bar_dhis2", "bar", [_M("Cases", "deBar000001")], color_scheme="DHIS2")
    assert a["bg"] and b["bg"] and a["bg"] != b["bg"]


# ── Line ──────────────────────────────────────────────────────────────────────

@pytest.mark.e2e
def test_line_tension(render_preview):
    """REQ-LINE-TENSION-01: Straight = tension 0, Smooth = curved (>0)."""
    _, sm = _probe(render_preview, "line_smooth", "line_trend", [_M("Trend", "deLine00001")], line_tension="Smooth")
    _, st = _probe(render_preview, "line_straight", "line_trend", [_M("Trend", "deLine00001")], line_tension="Straight")
    assert sm["tension"] and sm["tension"] > 0
    assert not st["tension"]


@pytest.mark.e2e
def test_line_fill_area(render_preview):
    """REQ-LINE-FILL-01: Fill enables area fill; None disables it."""
    _, f = _probe(render_preview, "line_fill", "line_trend", [_M("Trend", "deLine00001")], fill_area="Fill")
    _, n = _probe(render_preview, "line_nofill", "line_trend", [_M("Trend", "deLine00001")], fill_area="None")
    assert f["fill"] and not n["fill"]


@pytest.mark.e2e
def test_line_log_scale(render_preview):
    """REQ-LINE-LOG-01: Log scale switches the Y axis to logarithmic."""
    _, on = _probe(render_preview, "line_log", "line_trend", [_M("Trend", "deLine00001")], log_scale="On")
    _, off = _probe(render_preview, "line_linear", "line_trend", [_M("Trend", "deLine00001")], log_scale="Off")
    assert on["yType"] == "logarithmic" and off["yType"] == "linear"


@pytest.mark.e2e
def test_line_legend(render_preview):
    """REQ-LINE-LEGEND-01: legend Off hides it; Top positions it at the top."""
    _, off = _probe(render_preview, "line_legoff", "line_trend", [_M("Trend", "deLine00001")], show_legend="Off")
    _, top = _probe(render_preview, "line_legtop", "line_trend", [_M("Trend", "deLine00001")], show_legend="Top")
    assert off["legendDisplay"] is False
    assert top["legendDisplay"] is not False and top["legendPos"] == "top"


# ── Pie ───────────────────────────────────────────────────────────────────────

@pytest.mark.e2e
def test_pie_chart_type(render_preview):
    """REQ-PIE-TYPE-01: Donut renders a doughnut (cutout > 0); Pie has no cutout."""
    _, pie = _probe(render_preview, "pie_pie", "pie_cat", [_M("Cases", "dePie000001")], chart_type="Pie")
    _, dn = _probe(render_preview, "pie_donut", "pie_cat", [_M("Cases", "dePie000001")], chart_type="Donut")
    assert dn["type"] == "doughnut" or (dn["cutout"] and dn["cutout"] != "0%")
    assert pie["type"] == "pie"


# ── Combined ──────────────────────────────────────────────────────────────────

@pytest.mark.e2e
def test_combined_dual_y(render_preview):
    """REQ-COMBINED-DUALY-01: Dual Y axis adds a second (right-hand 'y2') scale."""
    metrics = [_M("Bars", "deCmb000001"), _M("Line", "deCmb000002")]
    _, yes = _probe(render_preview, "comb_dual", "combined_bar_line", metrics, dual_y_axis="Yes")
    _, no = _probe(render_preview, "comb_single", "combined_bar_line", metrics, dual_y_axis="No")
    assert yes["hasY2"] and not no["hasY2"]


# ── Scorecard (canvas-drawn → sample pixels) ──────────────────────────────────

_PIXEL_PROBE = r"""
const cv = document.getElementById('chart1');
const ctx = cv.getContext('2d');
const d = ctx.getImageData(0, 0, cv.width, cv.height).data;
const [tr,tg,tb] = arguments[0];
let hits = 0;
for (let i = 0; i < d.length; i += 4) {
  if (d[i+3] > 40 && Math.abs(d[i]-tr)<40 && Math.abs(d[i+1]-tg)<40 && Math.abs(d[i+2]-tb)<40) hits++;
}
return hits;
"""


@pytest.mark.e2e
def test_scorecard_value_color(render_preview):
    """REQ-SCORECARD-COLOR-01: value_color paints the number in the chosen colour."""
    ev, _ = _probe(render_preview, "score_red", "scorecard", [_M("KPI", "deScr000001")], value_color="Red")
    red_hits = ev["driver"].execute_script(_PIXEL_PROBE, [231, 76, 60])   # #e74c3c
    assert red_hits > 50, f"expected red pixels for the value, got {red_hits}; see {ev['screenshot']}"


@pytest.mark.e2e
def test_pie_value_labels_render(render_preview):
    """REQ-PIE-VALUES-01: pie value labels draw via the registered `showValues` plugin
    (datalabels is intentionally NOT registered — it duplicated bar totals). Labels must
    be painted on the canvas (white text inside slices), not hover-only."""
    cfg = {"plugin_id": "pie_cat", "title": "E2E pie labels",
           "metrics": [_M("Cases", "dePie000001")],
           "dimension": {"uid": "deDim000001", "name": "Species"},
           "plugin_options": {"show_values": "Value", "label_pos": "Inside"}}
    ev = render_preview(generate_preview_page(cfg), "pie_labels")
    severe = [e for e in ev["severe"] if "favicon" not in (e.get("message") or "").lower()]
    assert not severe, "JS errors:\n" + "\n".join(e.get("message", "") for e in severe)
    sv_on = ev["driver"].execute_script(
        "const c=Chart.getChart('chart1'); return !!(c && c.options.plugins.showValues && c.options.plugins.showValues.display);")
    assert sv_on, "pie showValues.display not true"
    # White label text painted inside the slices (count near-white opaque pixels over the pie).
    white = ev["driver"].execute_script(r"""
      const cv=document.getElementById('chart1'); const ctx=cv.getContext('2d');
      const d=ctx.getImageData(0,0,cv.width,cv.height).data; let hits=0;
      for(let i=0;i<d.length;i+=4){ if(d[i+3]>200 && d[i]>240 && d[i+1]>240 && d[i+2]>240) hits++; }
      return hits;
    """)
    assert white > 30, f"no white value labels painted on pie (got {white} px)"
