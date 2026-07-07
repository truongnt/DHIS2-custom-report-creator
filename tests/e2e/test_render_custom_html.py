"""
E2E render test for the Custom HTML widget (`custom_html`).

Verifies the user's template renders inside a sandboxed iframe bound to the chart data:
the iframe exists, `window.DATA` is populated, and `{{Column}}` substitution worked.
"""
import pytest

from charts.fixed_templates import generate_preview_page

pytestmark = pytest.mark.e2e


def _cfg(html, **po):
    opts = {"mode": "Aggregated", "min_height": "200"}
    opts.update(po)
    opts["html"] = html
    return {"plugin_id": "custom_html", "title": "E2E HTML",
            "metrics": [{"uid": "deTbl000001", "name": "Cases", "type": "aggregate", "agg": "SUM"}],
            "plugin_options": opts}


@pytest.mark.e2e
def test_custom_html_renders_in_iframe(render_preview):
    """REQ-HTML-RENDER-01: template renders in a sandboxed iframe; window.DATA is bound;
    {{Column}} is substituted from the first row."""
    html = ('<div id="kpi">{{Cases}}</div>'
            '<div id="n"></div>'
            '<script>document.getElementById("n").textContent = "rows:" + (window.DATA||[]).length;'
            'document.title = "READY";</script>')
    ev = render_preview(generate_preview_page(_cfg(html)), "custom_html")
    severe = [e for e in ev["severe"] if "favicon" not in (e.get("message") or "").lower()]
    assert not severe, "JS errors:\n" + "\n".join(e.get("message", "") for e in severe)
    driver = ev["driver"]
    # The widget iframe exists and is sandboxed.
    info = driver.execute_script("""
      const f = document.querySelector('iframe[data-hw="1"]');
      return f ? {sandbox: f.getAttribute('sandbox'), has: true} : {has:false};
    """)
    assert info["has"], "no custom-html iframe rendered"
    assert "allow-scripts" in (info["sandbox"] or "")
    # Inspect inside the iframe: DATA bound + {{Cases}} replaced with a number.
    driver.switch_to.frame(driver.find_element("css selector", 'iframe[data-hw="1"]'))
    inner = driver.execute_script("""
      return {
        title: document.title,
        dataIsArray: Array.isArray(window.DATA),
        cols: window.__columnNames || [],
        kpi: (document.getElementById('kpi')||{}).textContent || '',
        n: (document.getElementById('n')||{}).textContent || '',
      };
    """)
    driver.switch_to.default_content()
    assert inner["dataIsArray"], "window.DATA not bound inside iframe"
    assert inner["cols"] == ["Cases"], inner["cols"]
    assert inner["n"].startswith("rows:"), inner["n"]
    assert inner["kpi"] and inner["kpi"] != "{{Cases}}", f"placeholder not substituted: {inner['kpi']!r}"
