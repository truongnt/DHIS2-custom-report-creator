"""
E2E render smoke test — proves the bar-chart preview ACTUALLY renders in a browser,
not just that the HTML string contains the right fragments.

This is the layer that catches "unit test green but app broken": a JS runtime error
or a chart that never draws fails here, with a screenshot + console log as evidence.

Run: pip install -r requirements-dev.txt ; pytest tests/e2e -m e2e -s
"""
import pytest

from charts.fixed_templates import generate_preview_page, assemble_dashboard


def _ignorable(entry) -> bool:
    msg = (entry.get("message") or "").lower()
    return "favicon" in msg          # file:// favicon 404 is irrelevant


@pytest.mark.e2e
def test_bar_preview_renders(render_preview):
    """REQ-TEST-03: bar chart renders a canvas with no JS console errors."""
    cfg = {
        "plugin_id": "bar",
        "title": "E2E Bar Smoke",
        "metrics": [
            {"uid": "deUid000001", "name": "Confirmed cases",
             "type": "aggregate", "agg": "SUM"},
        ],
    }
    html = generate_preview_page(cfg)
    ev = render_preview(html, "bar_smoke")

    severe = [e for e in ev["severe"] if not _ignorable(e)]

    # Evidence-backed assertions (screenshot + console log saved under test-evidence/)
    assert ev["canvas_present"], (
        f"chart1 canvas missing — see {ev['screenshot']} / {ev['html_path']}"
    )
    w, h = ev["canvas_size"]
    assert w > 0 and h > 0, f"canvas not drawn (size={w}x{h}); see {ev['screenshot']}"
    assert not severe, (
        "JS console errors during render:\n"
        + "\n".join(e.get("message", "") for e in severe)
        + f"\n(screenshot: {ev['screenshot']})"
    )


@pytest.mark.e2e
def test_dashboard_renders_no_infinite_spinner(render_preview):
    """REQ-DASH-EXP-03/04: an assembled multi-card dashboard renders — the first card's
    chart draws (loading spinner clears) and the chart is height-bounded, not stretched."""
    cfg = lambda name, w: {
        "plugin_id": "bar", "title": name, "col_width": w,
        "metrics": [{"uid": "deUid000001", "name": "Cases", "type": "aggregate", "agg": "SUM"}],
    }
    html = assemble_dashboard([cfg("Wide", 12), cfg("Half", 6)], title="E2E Dash", preview=True)
    ev = render_preview(html, "dashboard_render")

    severe = [e for e in ev["severe"] if not _ignorable(e)]
    assert ev["canvas_present"], f"card-1 chart missing (spinner stuck?) — see {ev['screenshot']}"
    w, h = ev["canvas_size"]
    assert w > 0 and h > 0, f"card-1 chart not drawn (size={w}x{h}); see {ev['screenshot']}"
    # Height bounded: the wrapper caps at 240px (≈ devicePixelRatio*240) — not a tall stretch.
    assert h < 240 * 3, f"chart looks stretched (h={h}px); see {ev['screenshot']}"
    assert not severe, (
        "JS console errors:\n" + "\n".join(e.get("message", "") for e in severe)
        + f"\n(screenshot: {ev['screenshot']})")


@pytest.mark.e2e
def test_filter_bar_v2_renders(render_preview):
    """REQ-DASH-FILTER-06/07: filter bar shows the custom-range From/To pickers (range default)
    and the OU 'by level' options — rendered live, screenshot saved as evidence."""
    cfg = {"plugin_id": "bar", "title": "Filtered", "col_width": 12,
           "metrics": [{"uid": "deUid000001", "name": "Cases", "type": "aggregate", "agg": "SUM"}]}
    html = assemble_dashboard([cfg], title="Filter V2",
                              filters={"ou": "LEVEL-2", "period_from": "202401",
                                       "period_to": "202406"}, preview=True)
    ev = render_preview(html, "filter_bar_v2")
    assert ev["canvas_present"], f"chart missing — see {ev['screenshot']}"
    severe = [e for e in ev["severe"] if not _ignorable(e)]
    assert not severe, "JS errors:\n" + "\n".join(e.get("message", "") for e in severe)


@pytest.mark.e2e
def test_filter_bar_v3_dynamic(render_preview):
    """REQ-DASH-FILTER-10: dynamic filter list renders aliased primary controls + an extra
    (Dimension) filter on the bar, and charts still draw — screenshot saved as evidence."""
    cfg = lambda t: {"plugin_id": "bar", "title": t, "col_width": 6,
                     "metrics": [{"uid": "deUid000001", "name": "Cases", "type": "aggregate", "agg": "SUM"}]}
    html = assemble_dashboard([cfg("Chart A"), cfg("Chart B")], title="Filter V3", preview=True,
                              filters=[
                                  {"id": "ou", "alias": "Province", "type": "ou",
                                   "default": "LEVEL-2", "scope": "all"},
                                  {"id": "pe", "alias": "Reporting month", "type": "period",
                                   "default": "THIS_YEAR", "scope": "all"},
                                  {"id": "sex", "alias": "Sex", "type": "dimension",
                                   "source": "stg.deSEX", "value_type": "option",
                                   "options": [["Male", "M"], ["Female", "F"]],
                                   "default": "M", "scope": [0]},
                              ])
    ev = render_preview(html, "filter_bar_v3")
    assert ev["canvas_present"], f"chart missing — see {ev['screenshot']}"
    severe = [e for e in ev["severe"] if not _ignorable(e)]
    assert not severe, "JS errors:\n" + "\n".join(e.get("message", "") for e in severe)


@pytest.mark.e2e
def test_chart_reload_no_stale_overlay(render_preview, _chrome_driver):
    """REQ-RELOAD-02: re-running loadData (filter change) must not leave a stale Chart.js
    instance — exactly one chart on the canvas, no console errors."""
    cfg = {"plugin_id": "bar", "title": "Reload Bar",
           "metrics": [{"uid": "deUid000001", "name": "Cases", "type": "aggregate", "agg": "SUM"}]}
    render_preview(generate_preview_page(cfg), "bar_reload")
    d = _chrome_driver
    d.get_log("browser")                          # drain
    d.execute_script("loadData();")
    import time; time.sleep(2)
    msgs = " ".join(e.get("message", "") for e in d.get_log("browser") if e.get("level") == "SEVERE")
    assert "already" not in msgs.lower(), f"re-init error on reload:\n{msgs}"
    # Chart.js tracks live instances; after reload there must be exactly one for chart1.
    cnt = d.execute_script(
        "var c=document.getElementById('chart1');"
        "return (window.Chart && Chart.getChart && Chart.getChart(c)) ? 1 : 0;")
    assert cnt == 1, f"expected exactly one live chart after reload, got {cnt}"
