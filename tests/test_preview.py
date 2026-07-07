"""
Requirements tests for chart preview system.

  REQ-CORE    : generate_preview_page produces correct HTML structure
  REQ-PLUGIN  : Each plugin generates valid JS with required functions
  REQ-TYPE    : Data-type routing is correct per plugin
  REQ-FIXTURE : Fixture data is used when available; falls back to sample
  REQ-ARCH    : Core and plugin concerns stay separated
  REQ-MOCK    : JavaScript mock produces correct DHIS2-format responses

Run:  python -m pytest tests/test_preview.py -v
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from charts.fixed_templates import generate_preview_page
from charts.plugins import get_plugin, visible_plugins

# ── shared fixtures / helpers ─────────────────────────────────────────────────

MALARIA_PROG  = "yAKTrPUMAuU"
MALARIA_STAGE = "KqjOmlBpYtd"
MALARIA_DE_OPT = "LLhY5gyRTjq"   # values '0','1' — tracker_option

ALL_PLUGIN_IDS = ["bar", "line_trend", "pie_cat", "scorecard",
                  "combined_bar_line", "line_multi", "table_view", "custom_html"]


def _tracker_cfg(de_uid="AAAAAAAAAAA", de_type="tracker_numeric",
                 prog_uid="PPPPPPPPPPP", stage_uid="SSSSSSSSSSS",
                 options=None, plugin_id="bar", extra_metrics=None,
                 dim_uid=None, dim_type="tracker_option",
                 plugin_options=None):
    metrics = [{
        "uid": de_uid, "name": "Test DE", "type": de_type,
        "agg": "SUM", "prog_uid": prog_uid, "stage_uid": stage_uid,
        "options": options or [],
    }]
    if extra_metrics:
        metrics += extra_metrics
    dim = {}
    if dim_uid:
        dim = {"uid": dim_uid, "name": "Dim DE", "type": dim_type,
               "prog_uid": prog_uid, "stage_uid": stage_uid, "options": options or []}
    return {
        "plugin_id": plugin_id,
        "title": f"Test {plugin_id}",
        "metrics": metrics,
        "dimensions": {"dimension": dim},
        "plugin_options": plugin_options or {},
        "mode": "fixed",
        "source": {"prog_uid": prog_uid, "stage_uid": stage_uid},
    }


def _agg_cfg(de_uid="BBBBBBBBBBB", plugin_id="bar"):
    return {
        "plugin_id": plugin_id,
        "title": f"Test {plugin_id} agg",
        "metrics": [{"uid": de_uid, "name": "Cases", "type": "aggregate",
                      "agg": "SUM", "options": []}],
        "dimensions": {"dimension": {}},
        "plugin_options": {},
        "mode": "fixed",
    }


def _has_fn(js: str, fn_name: str) -> bool:
    """True if `fn_name` is defined (function or const arrow) in the JS snippet."""
    return fn_name in js


def _min_cfg(plugin_id: str):
    """Minimum valid config for any plugin (some require 2 metrics)."""
    base = _tracker_cfg(plugin_id=plugin_id)
    if plugin_id in ("combined_bar_line", "line_multi"):
        base["metrics"].append({
            "uid": "XXXXXXYYYYY", "name": "DE2",
            "type": "aggregate", "agg": "SUM", "options": [],
        })
    return base


# ─────────────────────────────────────────────────────────────────────────────
# REQ-CORE : Page structure
# ─────────────────────────────────────────────────────────────────────────────

class TestCorePageStructure:
    def test_returns_nonempty_string(self):
        """REQ-CORE-01 generate_preview_page returns a non-empty HTML string."""
        html = generate_preview_page(_tracker_cfg())
        assert isinstance(html, str) and len(html) > 500

    def test_has_doctype(self):
        """REQ-CORE-02 Output starts with <!doctype html>."""
        html = generate_preview_page(_tracker_cfg())
        assert html.lower().lstrip().startswith("<!doctype html>")

    def test_canvas_id(self):
        """REQ-CORE-03 HTML contains <canvas id="chart1">."""
        html = generate_preview_page(_tracker_cfg())
        assert 'id="chart1"' in html

    def test_loading_div(self):
        """REQ-CORE-04 HTML contains loading spinner div."""
        html = generate_preview_page(_tracker_cfg())
        assert 'id="loading1"' in html

    def test_error_div(self):
        """REQ-CORE-05 HTML contains error div for user-facing error messages."""
        html = generate_preview_page(_tracker_cfg())
        assert 'id="error1"' in html

    def test_preview_flag_present(self):
        """REQ-CORE-06 PREVIEW variable is defined in the page script."""
        html = generate_preview_page(_tracker_cfg())
        assert "let PREVIEW" in html or "const PREVIEW" in html

    def test_dhis2get_function(self):
        """REQ-CORE-07 dhis2Get function is defined in shared script."""
        html = generate_preview_page(_tracker_cfg())
        assert "function dhis2Get" in html or "dhis2Get" in html

    def test_load_data_function(self):
        """REQ-CORE-08 loadData() is defined and called on DOMContentLoaded."""
        html = generate_preview_page(_tracker_cfg())
        assert "loadData" in html

    def test_init_chart_called(self):
        """REQ-CORE-09 initChart1(ou,pe) is wired into loadData."""
        html = generate_preview_page(_tracker_cfg())
        assert "initChart1" in html

    def test_preview_badge_present(self):
        """REQ-CORE-10 Preview badge is always shown (yellow or green)."""
        html = generate_preview_page(_tracker_cfg())
        assert 'class="preview-badge' in html

    def test_ou_period_selects(self):
        """REQ-CORE-11 OU and Period dropdowns are in the page controls."""
        html = generate_preview_page(_tracker_cfg())
        assert 'id="ouSelect"' in html
        assert 'id="peSelect"' in html

    def test_chart_wrapper_css(self):
        """REQ-CORE-12 chart-wrapper div is present (for height constraint)."""
        html = generate_preview_page(_tracker_cfg())
        assert "chart-wrapper" in html


class TestPeriodAggregation:
    """REQ-CHART-SUM-01: a period-series chart SUMS all rows for each period, so an
    OU-level filter (many org-unit rows per period) shows the TOTAL, not the first row."""

    @pytest.mark.parametrize("plugin_id,cfg_fn", [
        ("bar", _tracker_cfg), ("bar_monthly", _tracker_cfg),
        ("line_trend", _tracker_cfg),
    ])
    def test_sums_rows_per_period(self, plugin_id, cfg_fn):
        js = get_plugin(plugin_id).build_js(1, cfg_fn(plugin_id=plugin_id))
        # Uses filter(...).reduce(sum) per period, not a single-row .find(pe===p).
        assert "peIdx] === p)" in js or "peIdx]===p)" in js
        assert ".reduce(" in js and ".filter(" in js
        # The old first-row-only pattern must be gone from the value aggregation.
        assert "const row = d.rows.find(r => r[peIdx] === p)" not in js
        assert "const row=d.rows.find(r=>r[peIdx]===p)" not in js


# ─────────────────────────────────────────────────────────────────────────────
# REQ-PLUGIN : JS generation per plugin
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("plugin_id", ALL_PLUGIN_IDS)
class TestPluginJsGeneration:
    def test_plugin_registered(self, plugin_id):
        """REQ-PLUGIN-01 Plugin is in the registry."""
        assert get_plugin(plugin_id) is not None

    def test_defines_render_sample(self, plugin_id):
        """REQ-PLUGIN-02 Plugin generates renderChart1Sample function."""
        plugin = get_plugin(plugin_id)
        js = plugin.build_js(1, _min_cfg(plugin_id))
        assert _has_fn(js, "renderChart1Sample"), \
            f"{plugin_id}: renderChart1Sample not found"

    def test_defines_render_real(self, plugin_id):
        """REQ-PLUGIN-03 Plugin generates renderChart1Real (or equivalent)."""
        plugin = get_plugin(plugin_id)
        js = plugin.build_js(1, _min_cfg(plugin_id))
        assert _has_fn(js, "renderChart1Real") or _has_fn(js, "_tMount1"), \
            f"{plugin_id}: renderChart1Real not found"

    def test_defines_init(self, plugin_id):
        """REQ-PLUGIN-04 Plugin generates initChart1 function."""
        plugin = get_plugin(plugin_id)
        js = plugin.build_js(1, _min_cfg(plugin_id))
        assert _has_fn(js, "initChart1"), \
            f"{plugin_id}: initChart1 not found"

    def test_init_checks_preview(self, plugin_id):
        """REQ-PLUGIN-05 initChart1 uses the PREVIEW flag."""
        plugin = get_plugin(plugin_id)
        js = plugin.build_js(1, _min_cfg(plugin_id))
        assert "PREVIEW" in js, f"{plugin_id}: PREVIEW not referenced"

    def test_calls_dhis2get_when_real(self, plugin_id):
        """REQ-PLUGIN-06 initChart1 calls dhis2Get in non-preview path."""
        plugin = get_plugin(plugin_id)
        js = plugin.build_js(1, _min_cfg(plugin_id))
        assert "dhis2Get" in js, f"{plugin_id}: dhis2Get not called"

    def test_no_python_fstring_artifacts(self, plugin_id):
        """REQ-PLUGIN-07 Generated JS has no unresolved Python f-string variable references."""
        plugin = get_plugin(plugin_id)
        js = plugin.build_js(1, _min_cfg(plugin_id))
        # Detect Python f-string placeholders that were never resolved, e.g. {prog_uid}, {stage_uid}
        # These always contain at least one underscore and are lowercase identifiers
        bad = re.findall(r'\{[a-z][a-z0-9]*_[a-z0-9_]+\}', js)
        assert not bad, f"{plugin_id}: unresolved f-string vars found: {bad[:3]}"

    def test_n_index_substitution(self, plugin_id):
        """REQ-PLUGIN-08 build_js(2, config) uses index 2, not 1."""
        plugin = get_plugin(plugin_id)
        js = plugin.build_js(2, _min_cfg(plugin_id))
        assert "initChart2" in js, f"{plugin_id}: index 2 not substituted"
        assert "initChart1" not in js, f"{plugin_id}: stale index 1 found"

    def test_aggregate_config_works(self, plugin_id):
        """REQ-PLUGIN-09 Aggregate config doesn't crash for any plugin."""
        if plugin_id == "pie_cat":
            pytest.skip("pie_cat requires tracker_option")
        plugin = get_plugin(plugin_id)
        cfg = _agg_cfg(plugin_id=plugin_id)
        if plugin_id in ("combined_bar_line", "line_multi"):
            cfg["metrics"].append({"uid": "CCCCCCCCCCC", "name": "DE2",
                                   "type": "aggregate", "agg": "SUM", "options": []})
        js = plugin.build_js(1, cfg)
        assert "initChart1" in js


# ─────────────────────────────────────────────────────────────────────────────
# REQ-TYPE : Data-type routing
# ─────────────────────────────────────────────────────────────────────────────

class TestDataTypeRouting:
    def test_bar_tracker_numeric_uses_events_aggregate(self):
        """REQ-TYPE-01 Bar + tracker_numeric → analytics/events/aggregate API."""
        js = get_plugin("bar").build_js(1, _tracker_cfg(de_type="tracker_numeric"))
        assert "analytics/events/aggregate" in js

    def test_bar_aggregate_uses_analytics_json(self):
        """REQ-TYPE-02 Bar + aggregate → analytics.json API."""
        js = get_plugin("bar").build_js(1, _agg_cfg())
        assert "analytics.json" in js

    def test_bar_tracker_option_dim_uses_events_aggregate(self):
        """REQ-TYPE-03 Bar + tracker_option dimension → analytics/events/aggregate."""
        cfg = _tracker_cfg(
            de_type="tracker_numeric",
            dim_uid="DDDDDDDDDDD", dim_type="tracker_option",
        )
        js = get_plugin("bar").build_js(1, cfg)
        assert "analytics/events/aggregate" in js

    def test_palettes_have_well_separated_adjacent_colours(self):
        """REQ-BAR-COLOR: every colour scheme keeps ADJACENT series far apart in RGB
        (regression: old schemes had near-identical neighbouring blues/oranges)."""
        from charts.plugins.shared_js import PALETTES

        def _rgb(h):
            h = h.lstrip("#")
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

        def _dist(a, b):
            return sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b))) ** 0.5

        for name, cols in PALETTES.items():
            assert len(cols) == len(set(cols)), f"{name} has duplicate colours"
            worst = min(_dist(cols[i], cols[i + 1]) for i in range(len(cols) - 1))
            assert worst >= 60, f"{name}: adjacent colours too close (min dist {worst:.0f})"

    def test_all_plugins_share_one_palette_source(self):
        """REQ-BAR-COLOR: bar / line / pie / combined all reference the same PALETTES dict
        (no drifting per-plugin copies)."""
        from charts.plugins.shared_js import PALETTES
        from charts.plugins import bar, line_multi, line_trend, pie_cat, combined_bar_line
        for mod in (bar, line_multi, line_trend, pie_cat, combined_bar_line):
            assert mod._PALETTES is PALETTES

    def test_bar_stacked_metrics_have_distinct_colours_period(self):
        """REQ-BAR-COLOR: 3 stacked metrics on the Period axis get distinct palette colours."""
        import re
        cfg = {"plugin_id": "bar",
               "plugin_options": {"stack_mode": "Stack", "color_scheme": "Default"},
               "metrics": [{"uid": "a1", "name": "M1", "type": "indicator"},
                           {"uid": "b2", "name": "M2", "type": "indicator"},
                           {"uid": "c3", "name": "M3", "type": "indicator"}]}
        js = get_plugin("bar").build_js(1, cfg)
        # renderChart1Real assigns one distinct palette index per metric series.
        assert "PALETTE[i%PALETTE.length]" in js
        # Sample preview also shows 3 distinct series (not all PALETTE[0]).
        assert {"PALETTE[0]", "PALETTE[1]", "PALETTE[2]"}.issubset(
            set(re.findall(r"PALETTE\[\d\]", js)))

    def test_bar_stacked_metrics_have_distinct_colours_org_unit(self):
        """REQ-BAR-COLOR: 3 stacked metrics on the Org Unit axis are one distinct-coloured
        series each (regression: previously collapsed to a single PALETTE[0] series)."""
        import re
        cfg = {"plugin_id": "bar",
               "plugin_options": {"stack_mode": "Stack", "x_axis": "Org Unit"},
               "metrics": [{"uid": "a1", "name": "M1", "type": "indicator"},
                           {"uid": "b2", "name": "M2", "type": "indicator"},
                           {"uid": "c3", "name": "M3", "type": "indicator"}]}
        js = get_plugin("bar").build_js(1, cfg)
        assert "USER_ORGUNIT_CHILDREN" in js
        assert "PALETTE[i%PALETTE.length]" in js                 # real: one series per dx
        assert {"PALETTE[0]", "PALETTE[1]", "PALETTE[2]"}.issubset(
            set(re.findall(r"PALETTE\[\d\]", js)))               # sample: 3 distinct series
        assert js.count("stack: 'total'") >= 3                   # all series stacked

    def test_table_raw_multiple_metrics(self):
        """REQ-TYPE-04 Table raw mode accepts multiple tracker DEs."""
        cfg = _tracker_cfg(
            plugin_id="table_view",
            de_type="tracker_option",
            plugin_options={"mode": "Raw"},  # plugin uses "Raw" (capital R)
            extra_metrics=[{"uid": "EEEEEEEEEEE", "name": "DE2",
                            "type": "tracker_numeric", "agg": "SUM",
                            "prog_uid": "PPPPPPPPPPP", "stage_uid": "SSSSSSSSSSS",
                            "options": []}],
        )
        js = get_plugin("table_view").build_js(1, cfg)
        assert "initChart1" in js
        assert "analytics/events/query" in js  # raw mode uses events/query

    def test_table_aggregate_mode(self):
        """REQ-TYPE-05 Table aggregate mode uses analytics.json."""
        cfg = _agg_cfg(plugin_id="table_view")
        cfg["plugin_options"] = {"mode": "aggregate"}
        js = get_plugin("table_view").build_js(1, cfg)
        assert "initChart1" in js

    def test_scorecard_numeric(self):
        """REQ-TYPE-06 Scorecard renders for tracker_numeric."""
        js = get_plugin("scorecard").build_js(1, _tracker_cfg(
            de_type="tracker_numeric", plugin_id="scorecard"))
        assert "renderChart1Sample" in js

    def test_line_multi_two_metrics(self):
        """REQ-TYPE-07 line_multi needs at least 2 metrics."""
        cfg = _tracker_cfg(
            plugin_id="line_multi",
            de_type="tracker_numeric",
            extra_metrics=[{"uid": "FFFFFFFFFFF", "name": "DE2",
                            "type": "aggregate", "agg": "SUM", "options": []}],
        )
        js = get_plugin("line_multi").build_js(1, cfg)
        assert "renderChart1Sample" in js

    def test_combined_bar_line_two_metrics(self):
        """REQ-TYPE-08 combined_bar_line requires exactly 2 metrics."""
        cfg = _tracker_cfg(
            plugin_id="combined_bar_line",
            de_type="tracker_numeric",
            extra_metrics=[{"uid": "GGGGGGGGGGG", "name": "DE2",
                            "type": "aggregate", "agg": "SUM", "options": []}],
        )
        js = get_plugin("combined_bar_line").build_js(1, cfg)
        assert "renderChart1Sample" in js


# ─────────────────────────────────────────────────────────────────────────────
# REQ-FIXTURE : Fixture injection
# ─────────────────────────────────────────────────────────────────────────────

class TestFixtureInjection:
    def _malaria_bar_cfg(self, de_uid=MALARIA_DE_OPT, de_type="tracker_option"):
        return _tracker_cfg(
            de_uid=de_uid, de_type=de_type,
            prog_uid=MALARIA_PROG, stage_uid=MALARIA_STAGE,
            plugin_id="bar",
        )

    def test_fixture_file_exists(self):
        """REQ-FIXTURE-01 Malaria stage fixture file is in fixtures/."""
        from dhis2.fixture_fetcher import fixture_path
        fp = fixture_path(MALARIA_PROG, MALARIA_STAGE)
        assert fp.exists(), f"Missing: {fp}"

    def test_fixture_loads(self):
        """REQ-FIXTURE-02 Fixture file loads and has > 0 rows."""
        from dhis2.fixture_fetcher import load_raw_events
        raw = load_raw_events(MALARIA_PROG, MALARIA_STAGE)
        assert raw is not None
        assert raw.get("_format") == "raw_events_v1"
        assert len(raw.get("rows", [])) > 0

    def test_badge_green_with_fixture(self):
        """REQ-FIXTURE-03 Badge is green (fixture class) when fixture exists."""
        html = generate_preview_page(self._malaria_bar_cfg())
        assert 'preview-badge fixture' in html

    def test_badge_yellow_without_fixture(self):
        """REQ-FIXTURE-04 Badge is yellow (no fixture class) for aggregate DEs."""
        html = generate_preview_page(_agg_cfg(de_uid="NONEXISTDE1"))
        assert 'preview-badge fixture' not in html
        assert 'preview-badge"' in html  # yellow badge still present

    def test_demo_fx_embedded(self):
        """REQ-FIXTURE-05 __DEMO_FX__ is embedded in page script."""
        html = generate_preview_page(self._malaria_bar_cfg())
        assert 'window.__DEMO_FX__' in html

    def test_mock_dhis2get_embedded(self):
        """REQ-FIXTURE-06 _mockDhis2Get function is embedded."""
        html = generate_preview_page(self._malaria_bar_cfg())
        assert '_mockDhis2Get' in html

    def test_preview_false_patch_embedded(self):
        """REQ-FIXTURE-07 initChart1 is patched to set PREVIEW=false."""
        html = generate_preview_page(self._malaria_bar_cfg())
        assert 'PREVIEW=false' in html

    def test_embedded_rows_capped(self):
        """REQ-FIXTURE-08 Embedded fixture rows ≤ 500."""
        html = generate_preview_page(self._malaria_bar_cfg())
        # Find the embedded JSON
        marker = 'window.__DEMO_FX__ = '
        start = html.find(marker)
        assert start >= 0
        # The JSON ends at the first semicolon on its own line
        chunk = html[start + len(marker):start + len(marker) + 600_000]
        # Find the closing }; of the JSON (should end with };\n)
        # Try to extract and parse (rows key should exist)
        rows_count = chunk.count('"psi"')  # psi appears once per row in raw fixtures
        # Rough check: at most 500 events
        assert rows_count <= 500, f"Fixture embeds too many rows: {rows_count}"

    def test_badge_text_mentions_event_count(self):
        """REQ-FIXTURE-09 Badge text mentions event count from fixture."""
        html = generate_preview_page(self._malaria_bar_cfg())
        assert "events" in html

    def test_no_fixture_no_demo_fx(self):
        """REQ-FIXTURE-10 No __DEMO_FX__ in page when fixture absent."""
        html = generate_preview_page(_agg_cfg(de_uid="NONEXISTDE1"))
        assert 'window.__DEMO_FX__' not in html


# ─────────────────────────────────────────────────────────────────────────────
# REQ-MOCK : JS mock response format
# ─────────────────────────────────────────────────────────────────────────────

class TestMockResponseFormat:
    """Validates the Python-side logic that the JS mock mirrors."""

    def _load_malaria(self):
        from dhis2.fixture_fetcher import load_raw_events
        return load_raw_events(MALARIA_PROG, MALARIA_STAGE)

    def test_aggregate_tracker_option_by_period(self):
        """REQ-MOCK-01 Aggregating tracker_option by period produces (pe,cat,count) rows."""
        import re
        raw = self._load_malaria()
        hdrs = [h["name"] for h in raw["headers"]]
        rows = raw["rows"]
        de = MALARIA_DE_OPT
        col_name = f"{MALARIA_STAGE}.{de}"
        assert col_name in hdrs, f"DE column {col_name} not in fixture"
        cat_idx = hdrs.index(col_name)
        ed_idx  = hdrs.index("eventdate") if "eventdate" in hdrs else -1
        assert ed_idx >= 0

        def to_pe(v):
            m = re.match(r'^(\d{4})-(\d{2})', v or "")
            return (m.group(1) + m.group(2)) if m else ""

        cnts = {}
        for row in rows:
            pe  = to_pe(row[ed_idx]) if ed_idx < len(row) else ""
            cat = row[cat_idx] if cat_idx < len(row) else ""
            if not pe or not cat: continue
            cnts[(pe, cat)] = cnts.get((pe, cat), 0) + 1

        assert len(cnts) > 0, "No aggregated data"
        out_rows = [[p, c, str(v)] for (p, c), v in cnts.items()]
        # Must have 3-element rows: [pe, category, count]
        assert all(len(r) == 3 for r in out_rows)

    def test_aggregate_tracker_numeric_by_period(self):
        """REQ-MOCK-02 Aggregating tracker_numeric by period sums to positive totals."""
        import re
        raw = self._load_malaria()
        hdrs = [h["name"] for h in raw["headers"]]
        rows = raw["rows"]
        # Find a numeric-ish DE (just use first DE column)
        de_cols = [h for h in hdrs if "." in h]
        assert de_cols, "No DE columns in fixture"
        de_col = de_cols[0]
        de_idx = hdrs.index(de_col)
        ed_idx = hdrs.index("eventdate") if "eventdate" in hdrs else -1
        assert ed_idx >= 0

        def to_pe(v):
            m = re.match(r'^(\d{4})-(\d{2})', v or "")
            return (m.group(1) + m.group(2)) if m else ""

        sums = {}
        for row in rows:
            pe  = to_pe(row[ed_idx]) if ed_idx < len(row) else ""
            val = float(row[de_idx] or 0) if de_idx < len(row) else 0.0
            if not pe: continue
            sums[pe] = sums.get(pe, 0.0) + val

        # Result has at least one period with a value
        assert len(sums) > 0

    def test_raw_query_returns_fixture_directly(self):
        """REQ-MOCK-03 analytics/events/query mock returns full fixture structure."""
        raw = self._load_malaria()
        # The mock would return raw fixture directly — verify fixture has headers+rows
        assert "headers" in raw and "rows" in raw
        assert len(raw["rows"]) > 0

    def test_ou_name_map_from_fixture(self):
        """REQ-MOCK-04 OU names can be extracted from fixture ouname column."""
        raw = self._load_malaria()
        hdrs = [h["name"] for h in raw["headers"]]
        has_ou     = "ou" in hdrs
        has_ouname = "ouname" in hdrs
        if has_ou and has_ouname:
            ou_idx  = hdrs.index("ou")
            nm_idx  = hdrs.index("ouname")
            meta = {}
            for row in raw["rows"]:
                uid = row[ou_idx] if ou_idx < len(row) else ""
                nm  = row[nm_idx] if nm_idx < len(row) else ""
                if uid and nm:
                    meta[uid] = nm
            assert len(meta) > 0, "No OU names extracted from fixture"

    def test_raw_query_filters_to_requested_des(self):
        """REQ-MOCK-05 events/query mock filters columns to only requested DEs."""
        import json
        de1, de2 = MALARIA_DE_OPT, "mVryEWCmdYd"
        cfg = _tracker_cfg(
            de_uid=de1, de_type="tracker_option",
            prog_uid=MALARIA_PROG, stage_uid=MALARIA_STAGE,
            plugin_id="table_view",
            plugin_options={"mode": "Raw"},
            extra_metrics=[{
                "uid": de2, "name": "Malaria Test Result", "type": "tracker_option",
                "agg": "SUM", "prog_uid": MALARIA_PROG, "stage_uid": MALARIA_STAGE,
                "options": [],
            }],
        )
        html = generate_preview_page(cfg)
        marker = "window.__DEMO_FX__ = "
        start = html.find(marker) + len(marker)
        end   = html.find(";", start)
        fx    = json.loads(html[start:end])

        # _names must contain entries for the 2 requested DEs
        names = fx.get("_names", {})
        assert f"{MALARIA_STAGE}.{de1}" in names, "_names missing de1"
        assert f"{MALARIA_STAGE}.{de2}" in names, "_names missing de2"

        # Simulate mock filter: standard + only the 2 requested DE cols
        std_cols = {"psi","ps","eventdate","lastupdated","storedby","ou","ouname",
                    "longitude","latitude","geometry","pe"}
        req_dims = {f"{MALARIA_STAGE}.{de1}", f"{MALARIA_STAGE}.{de2}"}
        all_hdrs = {h["name"] for h in fx["headers"]}
        # DE columns NOT in reqDims should not appear in filtered output
        de_cols_not_requested = [h["name"] for h in fx["headers"]
                                 if "." in h["name"] and h["name"] not in req_dims]
        sel_names = {h["name"] for h in fx["headers"]
                     if h["name"] in std_cols or h["name"] in req_dims}
        # At least one non-requested DE column exists in fixture
        assert len(de_cols_not_requested) > 0, "Fixture has no extra DE columns to filter"
        # After filtering, non-requested DE columns are excluded
        for extra_col in de_cols_not_requested[:3]:
            assert extra_col not in sel_names, f"Non-requested col leaked: {extra_col}"

    def test_raw_query_column_display_names(self):
        """REQ-MOCK-06 events/query mock uses metric names as column display names."""
        import json
        cfg = _tracker_cfg(
            de_uid=MALARIA_DE_OPT, de_type="tracker_option",
            prog_uid=MALARIA_PROG, stage_uid=MALARIA_STAGE,
            plugin_id="table_view",
            plugin_options={"mode": "Raw"},
        )
        # Override metric name to something recognisable
        cfg["metrics"][0]["name"] = "My Custom Metric Name"
        html = generate_preview_page(cfg)
        marker = "window.__DEMO_FX__ = "
        start = html.find(marker) + len(marker)
        end   = html.find(";", start)
        fx    = json.loads(html[start:end])
        names = fx.get("_names", {})
        key   = f"{MALARIA_STAGE}.{MALARIA_DE_OPT}"
        assert names.get(key) == "My Custom Metric Name", \
            f"Display name mismatch: {names.get(key)}"


# ─────────────────────────────────────────────────────────────────────────────
# REQ-ARCH : Architecture separation
# ─────────────────────────────────────────────────────────────────────────────

class TestArchitecture:
    def test_plugins_dont_import_fixed_templates(self):
        """REQ-ARCH-01 Plugin modules must not have Python import of fixed_templates."""
        plugin_dir = ROOT / "charts" / "plugins"
        for py_file in plugin_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            bad = re.findall(
                r'^\s*(?:import|from)\s+\S*fixed_templates',
                source, re.MULTILINE,
            )
            assert not bad, \
                f"{py_file.name} imports fixed_templates (circular dependency): {bad}"

    def test_all_visible_plugins_have_build_js(self):
        """REQ-ARCH-02 Every visible plugin implements build_js."""
        for plugin in visible_plugins():
            assert callable(getattr(plugin, "build_js", None)), \
                f"{plugin.id} missing callable build_js"

    def test_build_js_takes_n_and_config(self):
        """REQ-ARCH-03 build_js(n, config) has exactly (cls, n, config) signature."""
        import inspect
        for plugin in visible_plugins():
            sig   = inspect.signature(plugin.build_js)
            names = [p for p in sig.parameters if p not in ("cls", "self")]
            assert names == ["n", "config"], \
                f"{plugin.id}.build_js params: {names}"

    def test_core_defines_shared_js_functions(self):
        """REQ-ARCH-04 Core page always provides dhis2Get, formatPeriodLabel, PALETTE."""
        html = generate_preview_page(_tracker_cfg())
        assert "dhis2Get" in html
        assert "formatPeriodLabel" in html
        assert "PALETTE" in html

    def test_plugin_references_shared_globals(self):
        """REQ-ARCH-05 Plugins reference shared globals (dhis2Get, formatPeriodLabel)."""
        # Bar uses both; check that bar's JS references them (not defines them)
        js = get_plugin("bar").build_js(1, _tracker_cfg())
        assert "dhis2Get" in js          # references shared function
        assert "formatPeriodLabel" in js  # references shared function
        # Plugins must NOT define these — they come from the core
        assert "async function dhis2Get" not in js
        assert "function formatPeriodLabel" not in js


# ─────────────────────────────────────────────────────────────────────────────
# REQ-MAP : Area Map and Point Map plugin options
# Each test verifies that a changed option produces the expected JS/HTML output.
# Manual tests (log + browser screenshot) are also required — see CLAUDE.md.
# ─────────────────────────────────────────────────────────────────────────────

_MAP_PROG  = MALARIA_PROG
_MAP_STAGE = MALARIA_STAGE
_MAP_DE    = "LLhY5gyRTjq"   # tracker_option DE present in fixture


def _area_map_cfg(overrides: dict) -> dict:
    opts = {"ou_level": "Level 3", "base_map": "CartoDB Light",
            "overlay_levels": "", "color_scheme": "Blues", "show_labels": "Hide"}
    opts.update(overrides)
    return {
        "plugin_id": "area_map", "title": "Map",
        "metrics": [{"uid": _MAP_DE, "name": "Cases", "type": "tracker_option",
                     "agg": "SUM", "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}],
        "plugin_options": opts,
        "source": {"prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE},
    }


def _point_map_cfg(overrides: dict) -> dict:
    opts = {"ou_level": "Level 4", "base_map": "CartoDB Light", "overlay_levels": "",
            "point_scale": "Medium", "point_color": "Blue",
            "bubble_gradient": "None", "show_values": "Hide"}
    opts.update(overrides)
    return {
        "plugin_id": "point_map", "title": "Map",
        "metrics": [{"uid": _MAP_DE, "name": "Cases", "type": "tracker_option",
                     "agg": "SUM", "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}],
        "plugin_options": opts,
        "source": {"prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE},
    }


@pytest.mark.parametrize("cfg_fn", [_area_map_cfg, _point_map_cfg])
def test_map_tracker_option_no_bad_aggregationtype(cfg_fn):
    """REQ-REGR-MAP-409: a tracker_option map must NOT send aggregationType without a
    value= — DHIS2 rejects it (E7204 → HTTP 409, deployed AreaMap crash 2026-06-28)."""
    html = generate_preview_page(cfg_fn({}))
    assert "aggregationType" not in html, "aggregationType emitted without value= → DHIS2 409"
    # The events/aggregate count query (DE dimension) is still present.
    assert f"{_MAP_STAGE}.{_MAP_DE}" in html
    assert "analytics/events/aggregate" in html


def _scripts(html: str) -> list[str]:
    return re.findall(r'<script>(.*?)</script>', html, re.DOTALL)


def _brace_balanced(js: str) -> bool:
    return js.count("{") == js.count("}")


class TestAreaMapOptions:
    """REQ-MAP-AM : Area Map plugin option validation."""

    def test_ou_level_sets_correct_level_in_fetch(self):
        """REQ-MAP-AM-01 ou_level option controls LEVEL-N in geoFeatures URL and analytics."""
        for level_n, expected in [("Level 2", "LEVEL-2"), ("Level 4", "LEVEL-4")]:
            html = generate_preview_page(_area_map_cfg({"ou_level": level_n}))
            # Main geo fetch and analytics ou dimension must both use the selected level
            assert f"LEVEL-{level_n[-1]}" in html, f"Level {level_n[-1]} not in HTML"
            geo_lines = [l for l in html.splitlines() if "geoFeatures" in l and f"LEVEL-{level_n[-1]}" in l]
            assert len(geo_lines) >= 1, f"No geoFeatures URL with {expected}"

    def test_base_map_cartodb_light(self):
        """REQ-MAP-AM-02 CartoDB Light produces correct tileLayer URL."""
        html = generate_preview_page(_area_map_cfg({"base_map": "CartoDB Light"}))
        assert "cartocdn.com/light_all" in html

    def test_base_map_cartodb_dark(self):
        """REQ-MAP-AM-03 CartoDB Dark produces correct URL and DARK_MAP=true."""
        html = generate_preview_page(_area_map_cfg({"base_map": "CartoDB Dark"}))
        assert "cartocdn.com/dark_all" in html
        assert re.search(r'DARK_MAP1\s*=\s*true', html)

    def test_base_map_osm(self):
        """REQ-MAP-AM-04 OpenStreetMap produces OSM tileLayer URL."""
        html = generate_preview_page(_area_map_cfg({"base_map": "OpenStreetMap"}))
        assert "tile.openstreetmap.org" in html

    def test_base_map_satellite(self):
        """REQ-MAP-AM-05 Satellite produces ArcGIS imagery URL."""
        html = generate_preview_page(_area_map_cfg({"base_map": "Satellite"}))
        assert "arcgisonline.com" in html

    def test_base_map_none(self):
        """REQ-MAP-AM-06 None basemap produces no tileLayer call."""
        html = generate_preview_page(_area_map_cfg({"base_map": "None"}))
        assert "tileLayer" not in html

    def test_overlay_single_level(self):
        """REQ-MAP-AM-07 Single overlay level adds one extra geoFeatures fetch and OV_LEVELS entry."""
        html = generate_preview_page(_area_map_cfg({"overlay_levels": "Level 2"}))
        assert re.search(r'OV_LEVELS1\s*=\s*\[2\]', html)
        # Promise.all must have 3 calls: main geo + analytics + overlay
        pa = re.search(r'Promise\.all\(\[(.*?)\]\)', html, re.DOTALL)
        assert pa
        n_fetches = pa.group(1).count("dhis2Get")
        assert n_fetches == 3, f"Expected 3 fetches, got {n_fetches}"

    def test_overlay_multi_level(self):
        """REQ-MAP-AM-08 Two overlay levels adds 2 extra fetches and OV_LEVELS=[2,3]."""
        html = generate_preview_page(_area_map_cfg({"overlay_levels": "Level 2,Level 3"}))
        assert "[2, 3]" in html
        pa = re.search(r'Promise\.all\(\[(.*?)\]\)', html, re.DOTALL)
        assert pa
        assert pa.group(1).count("dhis2Get") == 4

    def test_overlay_none(self):
        """REQ-MAP-AM-09 No overlay levels produces empty OV_LEVELS and 2 fetches."""
        html = generate_preview_page(_area_map_cfg({"overlay_levels": ""}))
        assert re.search(r'OV_LEVELS1\s*=\s*\[\]', html)
        pa = re.search(r'Promise\.all\(\[(.*?)\]\)', html, re.DOTALL)
        assert pa
        assert pa.group(1).count("dhis2Get") == 2

    def test_show_labels(self):
        """REQ-MAP-AM-10 show_labels=Show sets SHOW_LABELS to true."""
        html_show = generate_preview_page(_area_map_cfg({"show_labels": "Show"}))
        html_hide = generate_preview_page(_area_map_cfg({"show_labels": "Hide"}))
        assert re.search(r'SHOW_LABELS1\s*=\s*true', html_show)
        assert re.search(r'SHOW_LABELS1\s*=\s*false', html_hide)

    def test_js_brace_balance_all_options(self):
        """REQ-MAP-AM-11 Generated JS is brace-balanced for various option combinations."""
        combos = [
            {"ou_level": "Level 2", "overlay_levels": "Level 3,Level 4", "base_map": "CartoDB Dark", "show_labels": "Show"},
            {"ou_level": "Level 4", "overlay_levels": "", "base_map": "None"},
            {"ou_level": "Level 3", "overlay_levels": "Level 2", "base_map": "Satellite"},
        ]
        for opts in combos:
            html = generate_preview_page(_area_map_cfg(opts))
            for i, s in enumerate(_scripts(html)):
                assert _brace_balanced(s), f"Unbalanced braces in script {i} with opts {opts}"

    def test_fixture_injects_ou_parents(self):
        """REQ-MAP-AM-12 When fixture available, _ou_parents is embedded in window.__DEMO_FX__."""
        html = generate_preview_page(_area_map_cfg({}))
        if "window.__DEMO_FX__" not in html:
            pytest.skip("No fixture available")
        marker = "window.__DEMO_FX__ = "
        start = html.find(marker) + len(marker)
        end   = html.find(";", start)
        fx    = json.loads(html[start:end])
        assert "_ou_parents" in fx, "_ou_parents missing from fixture data"
        assert len(fx["_ou_parents"]) > 0, "_ou_parents is empty"
        # Each entry must map at least one level
        sample = next(iter(fx["_ou_parents"].values()))
        assert isinstance(sample, dict) and len(sample) >= 1

    def test_fixture_no_geo_in_html(self):
        """REQ-MAP-AM-13 Geo coordinate data must NOT be embedded in HTML (served via preview server)."""
        html = generate_preview_page(_area_map_cfg({}))
        if "window.__DEMO_FX__" not in html:
            pytest.skip("No fixture available")
        # _geo key must not appear in the embedded fixture JSON
        marker = "window.__DEMO_FX__ = "
        start = html.find(marker) + len(marker)
        end   = html.find(";", start)
        fx    = json.loads(html[start:end])
        assert "_geo" not in fx, "_geo coordinates embedded in HTML (too large — must use preview server)"

    def test_border_color_auto(self):
        """REQ-MAP-AM-14 border_color=Auto sets BORDER_COLOR to null (auto from dark/light map)."""
        html = generate_preview_page(_area_map_cfg({"border_color": "Auto"}))
        assert re.search(r'BORDER_COLOR1\s*=\s*null', html)

    def test_border_color_black(self):
        """REQ-MAP-AM-15 border_color=Black sets BORDER_COLOR to #111111."""
        html = generate_preview_page(_area_map_cfg({"border_color": "Black"}))
        assert re.search(r'BORDER_COLOR1\s*=\s*"#111111"', html)

    def test_border_weight_thick(self):
        """REQ-MAP-AM-16 border_weight=Thick sets BORDER_WEIGHT to 2.5."""
        html = generate_preview_page(_area_map_cfg({"border_weight": "Thick"}))
        assert re.search(r'BORDER_WEIGHT1\s*=\s*2\.5', html)

    def test_border_weight_thin(self):
        """REQ-MAP-AM-17 border_weight=Thin sets BORDER_WEIGHT to 0.8."""
        html = generate_preview_page(_area_map_cfg({"border_weight": "Thin"}))
        assert re.search(r'BORDER_WEIGHT1\s*=\s*0\.8', html)


class TestPointMapOptions:
    """REQ-MAP-PM : Point Map plugin option validation."""

    def test_no_data_is_graceful_not_thrown(self):
        """REQ-MAP-NODATA-01: empty results show a 'No data' message (via _emptyMap), not a
        hard throw that surfaces as a red 'Map error' and leaves a stale map on reload."""
        html = generate_preview_page(_point_map_cfg({"ou_level": "Level 4"}))
        assert "_emptyMap1" in html                       # graceful no-data helper present
        # The no-data branches must NOT throw (which would show 'Map error:' + leak old map).
        assert "throw new Error('No event coordinates" not in html
        assert "throw new Error('No point coordinates" not in html
        assert "throw new Error('No coordinates to plot" not in html

    def test_ou_level_controls_geo_level(self):
        """REQ-MAP-PM-01 ou_level controls LEVEL-N in the geoFeatures and analytics URL."""
        for level_n in ["Level 3", "Level 4"]:
            html = generate_preview_page(_point_map_cfg({"ou_level": level_n}))
            assert f"LEVEL-{level_n[-1]}" in html

    def test_base_maps_all_options(self):
        """REQ-MAP-PM-02 Each base_map option produces the correct tileLayer (or none for None)."""
        cases = {
            "CartoDB Light": "cartocdn.com/light_all",
            "CartoDB Dark":  "cartocdn.com/dark_all",
            "OpenStreetMap": "tile.openstreetmap.org",
            "Satellite":     "arcgisonline.com",
            "None":          None,
        }
        for bm, expected_url in cases.items():
            html = generate_preview_page(_point_map_cfg({"base_map": bm}))
            if expected_url:
                assert expected_url in html, f"{bm}: expected URL fragment '{expected_url}'"
            else:
                assert "tileLayer" not in html, "None basemap should have no tileLayer"

    @staticmethod
    def _ou_promise_all(html: str) -> str:
        """The OU-mode Promise.all block (the one fetching geoFeatures); the bubble map
        now also has an Event-coords branch with its own Promise.all."""
        blocks = re.findall(r'Promise\.all\(\[(.*?)\]\)', html, re.DOTALL)
        ou = [b for b in blocks if "geoFeatures" in b and "events/query" not in b]
        return ou[0] if ou else ""

    def test_overlay_levels_multi(self):
        """REQ-MAP-PM-03 Multi-level overlay produces correct OV_LEVELS and fetch count."""
        html = generate_preview_page(_point_map_cfg({"overlay_levels": "Level 2,Level 3"}))
        assert "[2, 3]" in html
        assert self._ou_promise_all(html).count("dhis2Get") == 4

    def test_overlay_none(self):
        """REQ-MAP-PM-04 No overlay levels → 2 fetches only."""
        html = generate_preview_page(_point_map_cfg({"overlay_levels": ""}))
        assert self._ou_promise_all(html).count("dhis2Get") == 2

    def test_bubble_gradient_none(self):
        """REQ-MAP-PM-05 bubble_gradient=None uses flat color (no gradient interpolation)."""
        html = generate_preview_page(_point_map_cfg({"bubble_gradient": "None"}))
        assert re.search(r'USE_GRADIENT1\s*=\s*false', html)

    def test_bubble_gradient_enabled(self):
        """REQ-MAP-PM-06 bubble_gradient=Gradient embeds GRADIENT array and USE_GRADIENT=true."""
        html = generate_preview_page(_point_map_cfg({"bubble_gradient": "Gradient"}))
        assert re.search(r'USE_GRADIENT1\s*=\s*true', html)
        assert "GRADIENT1" in html

    def test_show_values(self):
        """REQ-MAP-PM-07 show_values=Show sets SHOW_VALUES constant and embeds divIcon."""
        html_show = generate_preview_page(_point_map_cfg({"show_values": "Show"}))
        html_hide = generate_preview_page(_point_map_cfg({"show_values": "Hide"}))
        assert "L.divIcon" in html_show, "Show mode must have L.divIcon label code"
        # Use regex to match regardless of whitespace between constant name and =
        assert re.search(r'SHOW_VALUES1\s*=\s*true', html_show), "Show mode must set SHOW_VALUES to true"
        assert re.search(r'SHOW_VALUES1\s*=\s*false', html_hide), "Hide mode must set SHOW_VALUES to false"

    def test_point_scale_options(self):
        """REQ-MAP-PM-08 point_scale controls MAX_R constant value."""
        small  = generate_preview_page(_point_map_cfg({"point_scale": "Small"}))
        medium = generate_preview_page(_point_map_cfg({"point_scale": "Medium"}))
        large  = generate_preview_page(_point_map_cfg({"point_scale": "Large"}))
        # Extract MAX_R values
        def get_max_r(html):
            m = re.search(r'MAX_R\d+\s*=\s*(\d+)', html)
            return int(m.group(1)) if m else None
        rs = get_max_r(small), get_max_r(medium), get_max_r(large)
        assert rs[0] is not None, "MAX_R not found in small HTML"
        assert rs[0] < rs[1] < rs[2], f"MAX_R must increase Small<Medium<Large, got {rs}"

    def test_point_color_blue(self):
        """REQ-MAP-PM-09 point_color=Blue embeds blue GRADIENT values."""
        html = generate_preview_page(_point_map_cfg({"point_color": "Blue", "bubble_gradient": "Gradient"}))
        assert "GRADIENT1" in html

    def test_js_brace_balance(self):
        """REQ-MAP-PM-10 Generated JS is brace-balanced for all option combinations."""
        combos = [
            {"ou_level": "Level 3", "overlay_levels": "Level 2", "bubble_gradient": "Gradient", "show_values": "Show"},
            {"ou_level": "Level 4", "overlay_levels": "", "base_map": "None", "show_values": "Hide"},
        ]
        for opts in combos:
            html = generate_preview_page(_point_map_cfg(opts))
            for i, s in enumerate(_scripts(html)):
                assert _brace_balanced(s), f"Unbalanced braces in script {i} with {opts}"

    def test_fixture_ou_parents_aggregation(self):
        """REQ-MAP-PM-11 _ou_parents contains OU→ancestor chains that include level info."""
        html = generate_preview_page(_point_map_cfg({"ou_level": "Level 4"}))
        if "window.__DEMO_FX__" not in html:
            pytest.skip("No fixture available")
        marker = "window.__DEMO_FX__ = "
        start = html.find(marker) + len(marker)
        end   = html.find(";", start)
        fx    = json.loads(html[start:end])
        assert "_ou_parents" in fx
        chains = fx["_ou_parents"]
        assert len(chains) > 0, "_ou_parents is empty"
        # OUs without geoFeatures data have empty chains (no coordinates) — that's ok
        non_empty = [c for c in chains.values() if c]
        assert len(non_empty) > 0, "All event OUs have empty chains (no geo data found)"
        # At least some events must resolve at level 3 or 4 (main use-case for maps)
        has_l3 = any("3" in chain for chain in non_empty)
        has_l4 = any("4" in chain for chain in non_empty)
        assert has_l3 or has_l4, "_ou_parents has no level-3 or level-4 entries in non-empty chains"

    def test_show_empty_hide(self):
        """REQ-MAP-PM-12 show_empty=Hide (default) sets HIDE_EMPTY to true."""
        html = generate_preview_page(_point_map_cfg({"show_empty": "Hide"}))
        assert re.search(r'HIDE_EMPTY1\s*=\s*true', html)

    def test_show_empty_show(self):
        """REQ-MAP-PM-13 show_empty=Show sets HIDE_EMPTY to false (all OUs render)."""
        html = generate_preview_page(_point_map_cfg({"show_empty": "Show"}))
        assert re.search(r'HIDE_EMPTY1\s*=\s*false', html)

    def test_border_color_auto(self):
        """REQ-MAP-PM-14 border_color=Auto sets BORDER_COLOR to null."""
        html = generate_preview_page(_point_map_cfg({"border_color": "Auto"}))
        assert re.search(r'BORDER_COLOR1\s*=\s*null', html)

    def test_border_color_black(self):
        """REQ-MAP-PM-15 border_color=Black sets BORDER_COLOR to #111111."""
        html = generate_preview_page(_point_map_cfg({"border_color": "Black"}))
        assert re.search(r'BORDER_COLOR1\s*=\s*"#111111"', html)

    def test_border_weight_thick(self):
        """REQ-MAP-PM-16 border_weight=Thick sets BORDER_WEIGHT to 2.5."""
        html = generate_preview_page(_point_map_cfg({"border_weight": "Thick"}))
        assert re.search(r'BORDER_WEIGHT1\s*=\s*2\.5', html)


# ─────────────────────────────────────────────────────────────────────────────
# REQ-DASH-EXP : assembled dashboard — bounded height + offline fixtures
# ─────────────────────────────────────────────────────────────────────────────

class TestAssembledDashboard:
    @staticmethod
    def _cfg(h=1):
        c = {"template_id": "bar_monthly", "title": "Chart", "col_width": 6,
             "metrics": [{"dx_uid": "AAAAAAAAAAA", "label": "X", "type": "aggregate"}]}
        if h != 1:
            c["layout"] = {"x": 0, "y": 0, "w": 6, "h": h}
        return c

    def test_cards_bounded_height_not_stretched(self):
        """REQ-DASH-EXP-03 cards use a bounded chart-wrapper + maintainAspectRatio=false (no stretch)."""
        from charts.fixed_templates import assemble_dashboard
        html = assemble_dashboard([self._cfg()], title="D")
        assert "chart-wrapper" in html
        assert "height:240px" in html                       # default 1-row height
        assert "maintainAspectRatio=false" in html
        assert "card h-100" not in html                     # the stretch cause is gone

    def test_height_scales_with_layout_h(self):
        """REQ-DASH-EXP-03 a card's height follows its grid row-span (layout.h)."""
        from charts.fixed_templates import assemble_dashboard
        html = assemble_dashboard([self._cfg(h=2)], title="D")
        assert "height:480px" in html                       # 2 rows → 2×240

    def test_preview_injects_fixture(self, monkeypatch):
        """REQ-DASH-EXP-04 preview=True embeds sample-data fixtures so charts render offline."""
        import charts.fixed_templates as ft
        raw = {"_format": "raw_events_v1", "_prog_uid": "PROG", "_stage_uid": "STG",
               "_geo": {}, "headers": [{"name": "ou"}, {"name": "STG.DE1"}],
               "rows": [["OU1", "5"], ["OU2", "9"]]}
        monkeypatch.setattr(ft, "_FIXTURE_LOADER_AVAILABLE", True)
        monkeypatch.setattr(ft, "load_raw_events", lambda p, s="": raw)
        cfg = {"template_id": "bar_monthly", "title": "T",
               "metrics": [{"prog_uid": "PROG", "uid": "DE1", "name": "Cases", "stage_uid": "STG"}]}
        with_fx = ft.assemble_dashboard([cfg], title="D", preview=True)
        without  = ft.assemble_dashboard([cfg], title="D", preview=False)
        assert "window.__DEMO_FX__" in with_fx               # offline data present
        assert "window.__DEMO_FX__" not in without           # real-data mode stays clean


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))


def test_raw_table_query_disables_paging():
    """REQ-TABLE-RAW-03: raw Data Table fetches ALL rows (paging=false), not the
    default 50-row page (user 2026-06-28: 'why only 50 rows')."""
    cfg = {
        "plugin_id": "table_view", "title": "T", "plugin_options": {"mode": "Raw"},
        "metrics": [{"uid": _MAP_DE, "name": "Dx", "type": "tracker_option",
                     "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}],
        "source": {"type": "tracker_option", "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE},
    }
    html = generate_preview_page(cfg)
    assert "analytics/events/query" in html
    assert "paging=false" in html, "raw table must request paging=false (else capped at 50 rows)"


def test_bubble_map_coordinate_source_option():
    """REQ-MAP-COORD-01: Bubble (point) map can plot by OU centroid or by EVENT coords."""
    def cfg(mode, de_type="tracker_numeric"):
        return {"plugin_id": "point_map", "title": "M",
                "plugin_options": {"coordinates": mode, "ou_level": "Level 4"},
                "metrics": [{"uid": _MAP_DE, "name": "V", "type": de_type, "agg": "SUM",
                             "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}],
                "source": {"type": de_type, "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}}
    ou = generate_preview_page(cfg("Org Unit"))
    ev = generate_preview_page(cfg("Event"))
    assert "EVENT_COORDS1  = false" in ou
    assert "EVENT_COORDS1  = true" in ev and "coordinatesOnly=true" in ev
    # Event coords only apply to tracker sources → aggregate forces OU.
    agg = generate_preview_page(cfg("Event", de_type="aggregate"))
    assert "EVENT_COORDS1  = false" in agg


def test_bubble_map_event_clusters_ou_does_not():
    """REQ-MAP-COORD-04: Event coords cluster + re-split on zoom; OU centroids never split."""
    def cfg(mode):
        return {"plugin_id": "point_map", "title": "M",
                "plugin_options": {"coordinates": mode, "ou_level": "Level 4"},
                "metrics": [{"uid": _MAP_DE, "name": "Cases", "type": "tracker_option",
                             "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}],
                "source": {"type": "tracker_option", "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}}
    ev = generate_preview_page(cfg("Event"))
    ou = generate_preview_page(cfg("Org Unit"))
    # zoom re-cluster machinery exists in the shared renderer
    assert "_clusterAt" in ev and "zoomend" in ev
    # Event path opts in cluster mode; OU path explicitly does not.
    assert "eventBased:true, cluster:true" in ev
    assert "ovGeos, {})" in ou   # OU centroids: static, no clustering


def test_bubble_map_event_spiderfies_coincident_points():
    """REQ-MAP-COORD-05: Event coords near max zoom fan coincident events into
    individual points (events geocoded to the same facility share one lat/lon and
    cannot be split by zoom alone). User params: Bubble Map, Coordinates=Event."""
    cfg = {"plugin_id": "point_map", "title": "M",
           "plugin_options": {"coordinates": "Event", "ou_level": "Level 4"},
           "metrics": [{"uid": _MAP_DE, "name": "Cases", "type": "tracker_option",
                        "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}],
           "source": {"type": "tracker_option", "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}}
    html = generate_preview_page(cfg)
    # spiderfy machinery: per-member fan-out kicks in at high zoom
    assert "_spiderfy" in html
    assert "SPIDER_ZOOM1" in html
    assert "grp.members" in html               # iterates individual events
    assert "maxZoom:19" in html                # bounded zoom so threshold is deterministic
    # clusters must retain their member events so they can be fanned out
    assert "members:[]" in html and "members.push(p)" in html


class TestPieOptions:
    """REQ-PIE label position + hide-empty options (user-reported: no value-position
    control; legend showed zero-value categories)."""

    @staticmethod
    def _cfg(**po):
        return {"plugin_id": "pie_cat", "title": "Pie",
                "metrics": [],
                "dimensions": {"dimension": {
                    "uid": "deDim000001", "name": "Species", "type": "tracker_option",
                    "prog_uid": "PPPPPPPPPPP", "stage_uid": "SSSSSSSSSSS",
                    "options": [{"code": "PF", "name": "Pf"}, {"code": "PV", "name": "Pv"}]}},
                "source": {"prog_uid": "PPPPPPPPPPP", "stage_uid": "SSSSSSSSSSS"},
                "plugin_options": po}

    def test_label_inside_default(self):
        """REQ-PIE-LABELPOS-01: Inside → showValues plugin, centred white labels, no padding."""
        html = generate_preview_page(self._cfg(show_values="Value", label_pos="Inside"))
        assert "showValues: { display: true, mode: 'value', pos: 'inside'" in html
        assert "color: '#fff'" in html
        assert "padding: 0" in html
        assert "datalabels: { display: false }" in html   # not via datalabels

    def test_label_outside(self):
        """REQ-PIE-LABELPOS-02: Outside → showValues pos:outside, dark labels, chart padding."""
        html = generate_preview_page(self._cfg(show_values="Percent", label_pos="Outside"))
        assert "pos: 'outside'" in html and "mode: 'percent'" in html
        assert "color: '#333'" in html
        assert "padding: 28" in html

    def test_label_off(self):
        """REQ-PIE-VALUES-01: show_values=Off → showValues disabled."""
        html = generate_preview_page(self._cfg(show_values="Off"))
        assert "showValues: { display: false" in html

    def test_hide_empty_default_filters_zero(self):
        """REQ-PIE-EMPTY-01: default (show_empty=Hide) filters zero-value slices in real data."""
        html = generate_preview_page(self._cfg())
        assert "combined.filter(x => x.v > 0)" in html
        assert "if (true) combined = combined.filter" in html

    def test_show_empty_keeps_zero(self):
        """REQ-PIE-EMPTY-02: show_empty=Show keeps zero-value categories (filter guarded off)."""
        html = generate_preview_page(self._cfg(show_empty="Show"))
        assert "if (false) combined = combined.filter" in html


class TestAreaMapLegendTooltip:
    """REQ-MAP-AM-LEGEND-01 / REQ-MAP-AM-TOOLTIP-01: choropleth gains a color-ramp
    legend and a richer hover tooltip (metric name, % of total, rank)."""

    @staticmethod
    def _cfg():
        return {"plugin_id": "area_map", "title": "A",
                "plugin_options": {"ou_level": "Level 2", "color_scheme": "Reds"},
                "metrics": [{"uid": _MAP_DE, "name": "Confirmed cases", "type": "tracker_option",
                             "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}],
                "source": {"prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}}

    def test_legend_present(self):
        """REQ-MAP-AM-LEGEND-01: a bottom-right gradient legend is added."""
        html = generate_preview_page(self._cfg())
        assert "legend.addTo(map)" in html
        assert "linear-gradient(to right," in html
        assert "METRIC_LABEL1" in html

    def test_tooltip_enriched(self):
        """REQ-MAP-AM-TOOLTIP-01: tooltip shows metric label, % of total and rank."""
        html = generate_preview_page(self._cfg())
        assert "METRIC_LABEL1 + ': ' + fmt" in html   # metric name in tooltip
        assert "/ totalV * 100" in html               # share-of-total %
        assert "Rank " in html                        # rank among OUs


class TestBubbleMapCaptureLink:
    """REQ-MAP-PM-CAPTURE-01: event-coordinate bubbles deep-link a single event into
    the DHIS2 Capture app via a click popup."""

    @staticmethod
    def _cfg(coords="Event"):
        return {"plugin_id": "point_map", "title": "B",
                "plugin_options": {"coordinates": coords, "ou_level": "Level 4"},
                "metrics": [{"uid": _MAP_DE, "name": "Cases", "type": "tracker_option",
                             "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}],
                "source": {"prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}}

    def test_capture_link_wired(self):
        """REQ-MAP-PM-CAPTURE-01: Tracker Capture deep-link (tei/program/ou) + popup + program uid."""
        html = generate_preview_page(self._cfg())
        assert "dhis-web-tracker-capture/index.html#/dashboard?" in html
        assert "'tei=' + ev.tei + '&program=' + PROGRAM_UID1" in html
        assert "_captureUrl1" in html and "CAPTURE_ROOT1" in html
        assert "Open in Tracker Capture" in html
        assert f'PROGRAM_UID1   = "{_MAP_PROG}"' in html

    def test_capture_link_opens_new_tab_via_top(self):
        """REQ-MAP-PM-CAPTURE-04: link opens a NEW tab via the top window (sandboxed
        srcdoc iframes block a bare target=_blank)."""
        html = generate_preview_page(self._cfg())
        assert 'target="_blank"' in html
        assert "(window.top || window).open(_url, '_blank', 'noopener')" in html

    def test_capture_root_srcdoc_safe(self):
        """REQ-MAP-PM-CAPTURE-03: deployed reports run in an about:srcdoc iframe where
        window.location.href is not a valid URL base. Resolve the root from document.baseURI
        inside try/catch so 'new URL' can't throw and abort initChart{n}."""
        html = generate_preview_page(self._cfg())
        assert "new URL('../', window.location.href)" not in html   # would throw in srcdoc
        assert "new URL('../', document.baseURI)" in html
        assert "catch(_e)" in html

    def test_event_identifiers_extracted(self):
        """REQ-MAP-PM-CAPTURE-01: per-event tei/pi/ou are carried into points."""
        html = generate_preview_page(self._cfg())
        assert "tei:(teiI" in html and "pi:(piI" in html and "ou:(ouI" in html

    def test_ou_mode_has_no_capture_link(self):
        """REQ-MAP-PM-CAPTURE-02: OU-centroid bubbles aren't single events → no tei carried."""
        html = generate_preview_page(self._cfg(coords="Org Unit"))
        # OU path builds points from geoFeatures (id/name/value) with no tei field
        assert "value: byOu[f.id]" in html


class TestTableNewFeatures:
    """REQ-TABLE: OU-hierarchy columns + Tracker Capture link (raw tracker), and the
    typed filter row (date range / dropdown / text)."""

    @staticmethod
    def _raw_tracker(**po):
        opts = {"mode": "Raw"}; opts.update(po)
        return {"plugin_id": "table_view", "title": "T", "plugin_options": opts,
                "metrics": [{"uid": _MAP_DE, "name": "Result", "type": "tracker_option",
                             "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE,
                             "options": [{"code": "1", "name": "Positive"}]}],
                "source": {"type": "tracker_option", "prog_uid": _MAP_PROG, "stage_uid": _MAP_STAGE}}

    def test_ou_hierarchy_query_and_columns(self):
        """REQ-TABLE-OUHIER-01: ou_hierarchy=On sets the flag + hierarchyMeta query + level fetch."""
        html = generate_preview_page(self._raw_tracker(ou_hierarchy="On"))
        assert "const OU_HIER1  = true;" in html
        assert "hierarchyMeta=true" in html
        assert "api/organisationUnitLevels.json" in html
        assert "ancLevels" in html and "ouH[ouUid]" in html

    def test_ou_hierarchy_off_by_default(self):
        """REQ-TABLE-OUHIER-02: default leaves the hierarchy flag false (no ancestor cols)."""
        html = generate_preview_page(self._raw_tracker())
        assert "const OU_HIER1  = false;" in html

    def test_tracker_link_column(self):
        """REQ-TABLE-TLINK-01: tracker_link=On sets the flag + Tracker Capture deep-link + new-tab open."""
        html = generate_preview_page(self._raw_tracker(tracker_link="On"))
        assert "const TRK_LINK1 = true;" in html
        assert "dhis-web-tracker-capture/index.html#/dashboard?tei=" in html
        assert "linkCol=cols.length-1" in html
        assert "(window.top||window).open(u,'_blank','noopener')" in html

    def test_tracker_link_off_by_default(self):
        """REQ-TABLE-TLINK-02: default leaves the link flag false (no link column)."""
        html = generate_preview_page(self._raw_tracker())
        assert "const TRK_LINK1 = false;" in html

    def test_typed_filters_present(self):
        """REQ-TABLE-FILTER-DD-01/REQ-TABLE-FILTER-DATE-01: classifier emits date/select/text filters."""
        html = generate_preview_page(self._raw_tracker())
        assert "_tClassify1" in html
        assert "ftypes.push('date')" in html and "ftypes.push('select')" in html
        assert 'type="date"' in html and "data-fd=" in html        # date range pickers
        assert "<select data-fi=" in html                          # dropdown filter


class TestCustomHtml:
    """REQ-HTML: Custom HTML widget — reuses the table data pipeline, overrides _tMount
    to render the user's HTML in a sandboxed iframe with the data globals + {{col}}."""

    @staticmethod
    def _cfg(html=None, **po):
        opts = {"mode": "Aggregated", "min_height": "300"}
        opts.update(po)
        if html is not None:
            opts["html"] = html
        return {"plugin_id": "custom_html", "title": "HW",
                "metrics": [{"uid": "dx1", "name": "Cases", "type": "aggregate", "agg": "SUM"}],
                "plugin_options": opts}

    def test_registered_and_visible(self):
        """REQ-HTML-REG-01: plugin is registered and shown in the picker."""
        from charts.plugins import get_plugin, visible_plugins
        assert get_plugin("custom_html") is not None
        assert any(p.id == "custom_html" for p in visible_plugins())

    def test_override_after_table_mount(self):
        """REQ-HTML-RENDER-01: our _tMount override is emitted AFTER the table's, so it
        wins (function-declaration hoisting) → rows render as HTML, not a table."""
        html = generate_preview_page(self._cfg("<b>{{Cases}}</b>"))
        i_tbl = html.find("function _tMount1(cvs,cols,rows,meta)")      # table's (no spaces)
        i_ovr = html.find("function _tMount1(cvs, cols, rows, meta)")   # override (spaces)
        assert 0 < i_tbl < i_ovr, (i_tbl, i_ovr)
        assert 'sandbox' in html and "data-hw=" in html
        assert "window.__chartData" in html and "window.FIRST" in html

    def test_template_embedded_and_script_safe(self):
        """REQ-HTML-SAFE-01: a template containing <script>/</script> is neutralised (every
        '<' → \\u003c) so the HTML tokenizer can't act on it and break the host page script."""
        html = generate_preview_page(self._cfg("<div></div><script>var x=1;</script>"))
        # No raw script tag from the template may leak into the page source.
        assert "<script>var x=1;" not in html
        assert "var x=1;</script>" not in html
        # Escaped form present instead (only '<' is escaped, not '>').
        assert "\\u003cscript>var x=1;" in html

    def test_default_template_when_empty(self):
        """REQ-HTML-DEFAULT-01: empty html falls back to the starter template."""
        html = generate_preview_page(self._cfg(""))
        assert "Custom HTML widget" in html       # from DEFAULT_HTML

    def test_min_height_applied(self):
        """REQ-HTML-HEIGHT-01: min_height drives the iframe min-height."""
        html = generate_preview_page(self._cfg("<i>x</i>", min_height="450"))
        assert "min-height:450px" in html

    def test_period_matrix_for_dx_metrics(self):
        """REQ-HTML-PERIOD-01: dx-domain metrics (aggregate/indicator) are fetched BY PERIOD
        (pe as a dimension) and an initChart override builds a metric×period matrix, so the
        template can address one month, e.g. {{Total tests @ 202601}}."""
        html = generate_preview_page(self._cfg("<b>{{Cases @ 202601}}</b>"))
        # pe becomes a DIMENSION (not a filter) → period columns
        assert "dimension=pe:" in html
        # the matrix init overrides initChart1 (emitted after the table's → wins by hoisting)
        assert html.count("function initChart1") >= 2
        # period-keyed contract is exposed inside the iframe
        assert "window.__periods" in html and "window.__matrix" in html and "window.val=" in html
        # {{metric @ period}} lookup helper present
        assert "_lookup" in html

    def test_period_matrix_when_template_has_at_cells_even_in_raw_mode(self):
        """REQ-HTML-PERIOD-04: a template that addresses per-period cells ({{Metric @ 2025Q3}})
        gets the period matrix even when mode != 'Aggregated' — else the @-cells stay blank."""
        html = generate_preview_page(self._cfg("<b>{{Cases @ 2025Q4}}</b>", mode="Raw"))
        assert "dimension=pe:" in html              # per-period fetch was emitted
        assert html.count("function initChart1") >= 2   # matrix init overrides the base

    def test_no_period_matrix_without_at_cells_in_raw_mode(self):
        """REQ-HTML-PERIOD-04: Raw mode with no @-cell template keeps the plain table pipeline
        (no extra matrix initChart override)."""
        html = generate_preview_page(self._cfg("<b>{{Cases}}</b>", mode="Raw"))
        assert html.count("function initChart1") == 1

    def test_period_grain_drives_period_ids(self):
        """REQ-HTML-PERIOD-03: time_grain (Monthly/Quarterly/Yearly) drives the period ids
        fetched — the matrix init builds a fixed window at that grain via _grainPeriods."""
        # Default grain is Monthly.
        h_m = generate_preview_page(self._cfg("<b>{{Cases @ 202601}}</b>"))
        assert 'var GRAIN = "Monthly"' in h_m and "_grainPeriods" in h_m
        # Quarterly grain is propagated from dimensions.time_grain.
        cfg = self._cfg("<b>{{Cases @ 2025Q4}}</b>")
        cfg["dimensions"] = {"time_grain": "Quarterly"}
        h_q = generate_preview_page(cfg)
        assert 'var GRAIN = "Quarterly"' in h_q
        assert "'Q'" in h_q          # quarter-id construction present

    def test_period_matrix_skipped_for_tracker(self):
        """REQ-HTML-PERIOD-02: tracker-domain metrics keep the table pipeline (event-domain
        period split is a follow-up) — no extra initChart override is added."""
        cfg = {"plugin_id": "custom_html", "title": "HW",
               "metrics": [{"uid": "de1", "name": "Temp", "type": "tracker_numeric",
                            "agg": "AVERAGE", "prog_uid": "PROG1", "stage_uid": "STG1"}],
               "plugin_options": {"mode": "Aggregated", "min_height": "300",
                                  "html": "<b>{{Temp}}</b>"},
               "source": {"type": "tracker_numeric", "prog_uid": "PROG1", "stage_uid": "STG1"}}
        html = generate_preview_page(cfg)
        assert html.count("function initChart1") == 1   # only the table's, no matrix override


def test_export_toolbar_present():
    """REQ-EXPORT-01: every chart gets PNG/PDF/Excel export buttons, the export JS +
    CDN libs are injected, and the dashboard gets a whole-dashboard PDF export button."""
    from charts.fixed_templates import assemble_dashboard
    prev = generate_preview_page({"plugin_id": "bar", "title": "T",
                                  "metrics": [{"uid": "d1", "name": "Cases",
                                               "type": "aggregate", "agg": "SUM"}]})
    for frag in ("exportChart('png',", "exportChart('pdf',", "exportChart('xlsx',",
                 "function exportChart(", "html2canvas@1.4.1", "jspdf@2.5.1", "xlsx@0.18.5"):
        assert frag in prev, frag
    dash = assemble_dashboard([
        {"plugin_id": "bar", "title": "A", "metrics": [{"uid": "d1", "name": "C",
                                                        "type": "aggregate", "agg": "SUM"}]},
        {"plugin_id": "line_trend", "title": "B", "metrics": [{"uid": "d2", "name": "D",
                                                              "type": "aggregate", "agg": "SUM"}]},
    ])
    assert dash.count("exportChart('png',") == 2          # one toolbar per card
    assert "function exportDashboardPDF" in dash
    assert "exportDashboardPDF()" in dash and "Export PDF" in dash
    assert "window.__charts" in dash


def test_custom_options_keeps_pie_slice_colors():
    """REQ-PIE-IND-02: a saved AI customization with a single backgroundColor must NOT
    overwrite a pie's per-slice color ARRAY (which would paint every slice one colour).
    The merge guards: scalar color is skipped when the dataset color is an array."""
    mets = [{"uid": "I1", "name": "P.v", "alias": "pv", "type": "indicator", "agg": "SUM"},
            {"uid": "I2", "name": "P.F", "alias": "pf", "type": "indicator", "agg": "SUM"}]
    cfg = {"plugin_id": "pie_cat", "title": "Pie", "metrics": mets, "dimensions": {},
           "plugin_options": {}, "source": {"type": "indicator"},
           "custom_options": {"datasets": [{"backgroundColor": "#3498db"}]}}
    html = generate_preview_page(cfg)
    # the guard that drops a scalar color when the dataset color is a per-slice array
    assert "Array.isArray(ds[ck])" in html
    assert "['backgroundColor','borderColor']" in html


def test_pie_multi_indicator_mode():
    """REQ-PIE-IND-01: selecting multiple indicators/aggregates (no option-set dimension)
    renders a pie with one slice per metric, queried as dx, legend = each metric's alias —
    not the 'Alpha/Beta' demo categories."""
    from charts.plugins.pie_cat import PieCatPlugin
    mets = [{"uid": "I1", "name": "MAL T: Cases tested", "alias": "cases tested",
             "type": "indicator", "agg": "SUM"},
            {"uid": "I2", "name": "MAL T: Positive", "alias": "positive",
             "type": "indicator", "agg": "SUM"}]
    js = PieCatPlugin.build_js(1, {"metrics": mets, "dimensions": {},
                                   "plugin_options": {}, "source": {"type": "indicator"}})
    assert "analytics.json?dimension=dx:I1;I2" in js     # dx, multiple items
    assert "analytics/events" not in js                  # not the tracker endpoint
    assert "cases tested" in js and "positive" in js     # alias legend (sample + real)
    assert "Alpha" not in js


def test_indicator_sample_labels_use_metric_name():
    """REQ-IND-LABEL-01: preview sample series are labelled with the selected metric name,
    not a generic 'Series A'/'Group A' — indicators have no fixture so they hit the sample
    renderer, which used to show 'Series A' (the user's "Serial" report)."""
    from charts.plugins.bar import BarPlugin
    from charts.plugins.line_trend import LineTrendPlugin
    from charts.plugins.line_multi import LineMultiPlugin
    from charts.plugins.combined_bar_line import CombinedBarLinePlugin
    from charts.plugins.grouped_bar import GroupedBarPlugin

    def m(u, nm):
        return {"uid": u, "name": nm, "type": "indicator", "agg": "SUM"}

    def base(mets):
        return {"metrics": mets, "dimensions": {}, "plugin_options": {},
                "source": {"type": "indicator"}}

    single = [m("I1", "Cases tested")]
    two = [m("I1", "Cases tested"), m("I2", "Positive")]

    for P in (BarPlugin, LineTrendPlugin):
        js = P.build_js(1, base(single))
        assert "Cases tested" in js, P.__name__
        assert "'Series A'" not in js, P.__name__
    for P in (LineMultiPlugin, CombinedBarLinePlugin, GroupedBarPlugin):
        js = P.build_js(1, base(two))
        assert "Cases tested" in js and "Positive" in js, P.__name__
        assert "'Series A'" not in js and "'Group A'" not in js, P.__name__


def test_program_indicator_metric_uses_dx():
    """REQ-CE-PI-01: a program-indicator metric (type 'indicator') renders via analytics
    dx — the same aggregate path as indicators (no per-plugin change needed)."""
    cfg = {"plugin_id": "bar", "title": "PI",
           "metrics": [{"uid": "pi00000001", "name": "Malaria incidence", "type": "indicator",
                        "agg": "SUM", "prog_uid": "PROG1", "stage_uid": ""}],
           "dimensions": {"dimension": {}}, "plugin_options": {}, "mode": "fixed",
           "source": {"type": "indicator", "prog_uid": "PROG1"}}
    html = generate_preview_page(cfg)
    assert "analytics.json?dimension=dx:pi00000001" in html
    # must NOT route to the tracker events endpoint for an indicator-typed metric
    assert "analytics/events/aggregate/PROG1" not in html
