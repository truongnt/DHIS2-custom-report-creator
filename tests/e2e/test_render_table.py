"""
E2E per-option render tests for the Data Table (table_view) — for BOTH modes (Aggregated /
Raw) and EVERY style option (theme, heatmap, stripe, border, font_size). Each option is
verified by its real rendered effect (getComputedStyle on the table), with a screenshot.

Run: pip install -r requirements-dev.txt ; pytest tests/e2e/test_render_table.py -m e2e -s
"""
import pytest

from charts.fixed_templates import generate_preview_page

_PROBE = r"""
const ths=[...document.querySelectorAll('table thead th')];
const tds=[...document.querySelectorAll('table tbody td')];
const trs=[...document.querySelectorAll('table tbody tr')];
const cs=el=>getComputedStyle(el);
const td0=tds[0];
return {
  headers: ths.map(t=>t.textContent.replace(/[▲▼]/g,'').trim()),
  rowCount: trs.length,
  thBg: ths[0]?cs(ths[0]).backgroundColor:'',
  tdFontSize: td0?cs(td0).fontSize:'',
  tdBorder: td0?(cs(td0).borderTopWidth+' '+cs(td0).borderTopStyle):'',
  row2Bg: trs[1]?cs(trs[1]).backgroundColor:'',
  heatCount: tds.filter(td=>/rgb\(/.test(td.style.background||'')).length,
};
"""


def _rgb(hexv):
    h = hexv.lstrip("#")
    return f"rgb({int(h[0:2],16)}, {int(h[2:4],16)}, {int(h[4:6],16)})"


_SAMPLE_DIM = {"uid": "deDimSex001", "name": "Sex", "type": "tracker_option",
               "stage_uid": "SSSSSSSSSSS",
               "options": [{"code": "M", "name": "Male"}, {"code": "F", "name": "Female"}]}


def _render(render_preview, name, dims=None, **opts):
    cfg = {"plugin_id": "table_view", "title": f"E2E table {name}",
           "metrics": [{"uid": "deTbl000001", "name": "Cases", "type": "aggregate", "agg": "SUM"}],
           "plugin_options": opts}
    if dims:
        cfg["dimensions"] = {"group_by": dims, "dimension": dims[0]}
    ev = render_preview(generate_preview_page(cfg), f"table_{name}")
    assert ev["has_table"], f"no <table> rendered; see {ev['screenshot']}"
    severe = [e for e in ev["severe"] if "favicon" not in (e.get("message") or "").lower()]
    assert not severe, "JS errors:\n" + "\n".join(e.get("message", "") for e in severe)
    return ev, ev["driver"].execute_script(_PROBE)


# ── Modes ────────────────────────────────────────────────────────────────────

@pytest.mark.e2e
def test_table_mode_aggregated(render_preview):
    """REQ-TABLE-MODE-01: Aggregated mode columns = selected metrics; no auto org/time
    split → a single total row by default."""
    ev, p = _render(render_preview, "mode_agg", mode="Aggregated")
    assert p["headers"] == ["Cases"], p["headers"]   # only the selected metric
    assert p["rowCount"] == 1                          # single total, not disaggregated


@pytest.mark.e2e
def test_table_aggregated_disaggregate_by_dimension(render_preview):
    """REQ-TABLE-DISAGG-01: a selected dimension (DE/PA, e.g. Sex) becomes a row column
    (its alias/name as header); metrics stay as columns."""
    ev, p = _render(render_preview, "agg_dim", dims=[_SAMPLE_DIM], mode="Aggregated")
    assert p["headers"] == ["Sex", "Cases"], p["headers"]
    assert p["rowCount"] > 1


@pytest.mark.e2e
def test_table_aggregated_two_dimensions(render_preview):
    """REQ-TABLE-DISAGG-02: multiple dimensions each add a row column, in order."""
    d2 = {"uid": "deDimSpc001", "name": "Species", "type": "tracker_option",
          "stage_uid": "SSSSSSSSSSS", "options": [{"code": "PF", "name": "Pf"}]}
    ev, p = _render(render_preview, "agg_dim2", dims=[_SAMPLE_DIM, d2], mode="Aggregated")
    assert p["headers"] == ["Sex", "Species", "Cases"], p["headers"]


@pytest.mark.e2e
def test_table_mode_raw(render_preview):
    """REQ-TABLE-MODE-02: Raw mode shows flat event rows (one column per field)."""
    ev, p = _render(render_preview, "mode_raw", mode="Raw")
    assert "Facility" in p["headers"] and "Cases" in p["headers"]
    assert "Org Unit" not in p["headers"]
    assert p["rowCount"] == 8


# ── Theme (header background per theme) ───────────────────────────────────────

@pytest.mark.e2e
@pytest.mark.parametrize("theme,hexbg", [
    ("Default", "#2c3e50"), ("Blue", "#1a5276"), ("Green", "#1e8449"),
    ("Light", "#dfe6e9"), ("Dark", "#17202a"),
], ids=["default", "blue", "green", "light", "dark"])
def test_table_theme(render_preview, theme, hexbg):
    """REQ-TABLE-THEME-01: theme sets the header background colour."""
    ev, p = _render(render_preview, f"theme_{theme.lower()}", theme=theme)
    assert p["thBg"] == _rgb(hexbg), f"{theme}: header bg {p['thBg']} != {_rgb(hexbg)}"


# ── Heatmap ───────────────────────────────────────────────────────────────────

@pytest.mark.e2e
def test_table_heatmap_on(render_preview):
    """REQ-TABLE-HEATMAP-01: heatmap On shades numeric cells by value."""
    ev, p = _render(render_preview, "heatmap_on", dims=[_SAMPLE_DIM], mode="Aggregated", heatmap="On")
    assert p["heatCount"] > 0


@pytest.mark.e2e
def test_table_heatmap_off(render_preview):
    """REQ-TABLE-HEATMAP-01: heatmap Off leaves cells unshaded."""
    ev, p = _render(render_preview, "heatmap_off", mode="Aggregated", heatmap="Off")
    assert p["heatCount"] == 0


# ── Stripe ────────────────────────────────────────────────────────────────────

@pytest.mark.e2e
def test_table_stripe_on(render_preview):
    """REQ-TABLE-STRIPE-01: stripe On gives alternating row background."""
    ev, p = _render(render_preview, "stripe_on", dims=[_SAMPLE_DIM], stripe="On", heatmap="Off")
    assert p["row2Bg"] == _rgb("#f8f9fa")


@pytest.mark.e2e
def test_table_stripe_off(render_preview):
    """REQ-TABLE-STRIPE-01: stripe Off leaves rows transparent."""
    ev, p = _render(render_preview, "stripe_off", dims=[_SAMPLE_DIM], stripe="Off", heatmap="Off")
    assert p["row2Bg"] == "rgba(0, 0, 0, 0)"


# ── Border ────────────────────────────────────────────────────────────────────

@pytest.mark.e2e
@pytest.mark.parametrize("border,expected", [
    ("Light", "1px solid"), ("None", "0px none"), ("Dark", "2px solid"),
], ids=["light", "none", "dark"])
def test_table_border(render_preview, border, expected):
    """REQ-TABLE-BORDER-01: border option sets cell border width/style."""
    ev, p = _render(render_preview, f"border_{border.lower()}", border=border)
    assert p["tdBorder"] == expected, f"{border}: border {p['tdBorder']!r} != {expected!r}"


# ── Font size ─────────────────────────────────────────────────────────────────

@pytest.mark.e2e
@pytest.mark.parametrize("size,px", [("Small", "11px"), ("Medium", "13px"), ("Large", "15px")],
                         ids=["small", "medium", "large"])
def test_table_font_size(render_preview, size, px):
    """REQ-TABLE-FONT-01: font_size option sets the cell font size."""
    ev, p = _render(render_preview, f"font_{size.lower()}", font_size=size)
    assert p["tdFontSize"] == px, f"{size}: font-size {p['tdFontSize']} != {px}"


# ── Interactive: dropdown filters + row highlight ─────────────────────────────

@pytest.mark.e2e
def test_table_filter_dropdown_for_categorical(render_preview):
    """REQ-TABLE-FILTER-DD-01: low-cardinality (option-set/org-unit) columns get a
    <select> dropdown filter that actually narrows the rows."""
    ev, _ = _render(render_preview, "filt_dropdown", mode="Raw")
    nsel = ev["driver"].execute_script(
        "return document.querySelectorAll('table thead tr:nth-child(2) select').length;")
    assert nsel >= 1, "no dropdown filter rendered for categorical columns"
    rows_after = ev["driver"].execute_script("""
      const sels=[...document.querySelectorAll('table thead tr:nth-child(2) select')];
      const s=sels.find(x=>[...x.options].some(o=>o.value==='Male'));
      if(!s) return -1;
      s.value='Male'; s.dispatchEvent(new Event('change'));
      return document.querySelectorAll('table tbody tr').length;
    """)
    assert rows_after == 4, f"Sex=Male should leave 4 sample rows, got {rows_after}"


@pytest.mark.e2e
def test_table_row_click_highlights(render_preview):
    """REQ-TABLE-ROWSEL-01: clicking a row highlights it (amber background)."""
    ev, _ = _render(render_preview, "rowclick", mode="Raw")
    bg = ev["driver"].execute_script("""
      const tr=document.querySelector('table tbody tr'); tr.click();
      return getComputedStyle(tr).backgroundColor;
    """)
    assert bg == "rgb(253, 230, 138)", f"clicked row not highlighted, bg={bg}"
