"""
E2E render tests for the chart plugins — prove each chart type ACTUALLY renders in a
browser (canvas / table / scorecard) with no JS console errors. Screenshot + console
log saved as evidence. Upgrades the per-chart string-checks to real-render proof.

Run: pip install -r requirements-dev.txt ; pytest tests/e2e/test_render_charts.py -m e2e -s
"""
import pytest

from charts.fixed_templates import generate_preview_page


def _m(name, uid):
    return {"uid": uid, "name": name, "type": "aggregate", "agg": "SUM"}


# (plugin_id, kind, config) — kind drives the "rendered" assertion.
CHARTS = [
    ("bar", "canvas", {"metrics": [_m("Cases", "deBar000001")]}),
    ("line_trend", "canvas", {"metrics": [_m("Trend", "deLine00001")]}),
    ("line_multi", "canvas", {"metrics": [_m("A", "deMul000001"), _m("B", "deMul000002")]}),
    ("pie_cat", "canvas", {"metrics": [_m("Cases", "dePie000001")],
                           "dimension": {"uid": "deDim000001", "name": "Species"}}),
    ("combined_bar_line", "canvas", {"metrics": [_m("Bars", "deCmb000001"),
                                                 _m("Line", "deCmb000002")]}),
    ("table_view", "table", {"metrics": [_m("Cases", "deTbl000001")]}),
    ("scorecard", "text", {"metrics": [_m("KPI", "deScr000001")]}),
]


def _ignorable(e):
    return "favicon" in (e.get("message") or "").lower()


@pytest.mark.e2e
@pytest.mark.parametrize("plugin_id,kind,extra", CHARTS, ids=[c[0] for c in CHARTS])
def test_chart_renders(plugin_id, kind, extra, render_preview):
    """REQ-CHART-RENDER-01: each chart type draws without JS console errors (sample mode)."""
    cfg = {"plugin_id": plugin_id, "title": f"E2E {plugin_id}", **extra}
    html = generate_preview_page(cfg)
    ev = render_preview(html, f"chart_{plugin_id}")

    severe = [e for e in ev["severe"] if not _ignorable(e)]
    assert not severe, (
        f"{plugin_id}: JS console errors:\n"
        + "\n".join(e.get("message", "") for e in severe)
        + f"\n(screenshot: {ev['screenshot']})"
    )
    assert not ev["err_shown"], f"{plugin_id}: error banner {ev['err_text']!r} ({ev['screenshot']})"

    if kind == "canvas":
        w, h = ev["canvas_size"]
        assert ev["canvas_present"] and w > 0 and h > 0, \
            f"{plugin_id}: canvas not drawn (size={w}x{h}); see {ev['screenshot']}"
    elif kind == "table":
        assert ev["has_table"], f"{plugin_id}: no <table> rendered; see {ev['screenshot']}"
    else:  # text (scorecard)
        assert ev["text_len"] > 0, f"{plugin_id}: empty card; see {ev['screenshot']}"
