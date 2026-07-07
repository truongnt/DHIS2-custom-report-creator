"""
Integration tests — dashboard-level shared filters (PART K of DASHBOARD_REQUIREMENTS.md).

DHIS2 adaptation of Superset native filters: a shared Period (time) + Org-Unit (value)
filter scoped to all charts, with configurable DEFAULT values that the generated
dashboard's filter bar starts on.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _cfg(title, w=6):
    return {"title": title, "col_width": w, "template_id": "bar_monthly"}


# ── Assembly injects filter defaults ────────────────────────────────────────────

def test_assemble_injects_filter_defaults():
    """REQ-DASH-FILTER-03: assemble_dashboard injects the chosen period/ou as defaults."""
    from charts.fixed_templates import assemble_dashboard
    html = assemble_dashboard([_cfg("A")], title="T",
                              filters={"period": "THIS_YEAR", "ou": "USER_ORGUNIT_CHILDREN"})
    assert "DEFAULT_PE = 'THIS_YEAR'" in html
    assert "DEFAULT_OU = 'USER_ORGUNIT_CHILDREN'" in html
    assert "__DEFAULT_PE__" not in html and "__DEFAULT_OU__" not in html


def test_assemble_default_filters_fallback():
    """REQ-DASH-FILTER-03: with no filters, sensible defaults are used."""
    from charts.fixed_templates import assemble_dashboard
    html = assemble_dashboard([_cfg("A")], title="T")
    assert "DEFAULT_PE = 'LAST_12_MONTHS'" in html
    assert "DEFAULT_OU = 'USER_ORGUNIT'" in html


def test_preview_page_honours_config_filters():
    """REQ-DASH-FILTER-03: single-chart preview also fills the filter placeholders."""
    from charts.fixed_templates import generate_preview_page
    html = generate_preview_page({**_cfg("A"), "filters": {"period": "LAST_QUARTER"}})
    assert "DEFAULT_PE = 'LAST_QUARTER'" in html
    assert "__DEFAULT_PE__" not in html


# ── Filter dialog ────────────────────────────────────────────────────────────────

def test_filter_dialog_returns_selection(qtbot):
    """REQ-DASH-FILTER-01/02: the dialog exposes period + ou choices and returns them."""
    from ui.dashboard_filter_dialog import DashboardFilterDialog
    dlg = DashboardFilterDialog(None, {"period": "THIS_YEAR", "ou": "USER_ORGUNIT"})
    qtbot.addWidget(dlg)
    assert dlg._pe.currentData() == "THIS_YEAR"        # pre-selects existing default
    dlg._pe.setCurrentIndex(dlg._pe.findData("LAST_6_MONTHS"))
    dlg._ou.setCurrentIndex(dlg._ou.findData("USER_ORGUNIT_CHILDREN"))
    dlg._on_ok()
    assert dlg.result_filters == {"period": "LAST_6_MONTHS", "ou": "USER_ORGUNIT_CHILDREN"}


def test_panel_default_filters(qtbot):
    """REQ-DASH-FILTER-01: a new dashboard has sensible default filters."""
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    assert p._dash_filters == {"period": "LAST_12_MONTHS", "ou": "USER_ORGUNIT"}


# ── Filters flow through preview / export / save-load ────────────────────────────

def test_preview_uses_filters(qtbot, monkeypatch):
    """REQ-DASH-FILTER-04: Preview assembles with the dashboard's filters."""
    served = {}
    import ui.preview_window  # ensure the module exists before patching its attr
    monkeypatch.setattr("ui.preview_window.update_preview",
                        lambda html, title="": served.update(html=html))
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p._manual_btn.click()
    p._dash_filters = {"period": "THIS_QUARTER", "ou": "USER_ORGUNIT"}
    p.add_card(_cfg("A"))
    p._on_preview()
    assert "DEFAULT_PE = 'THIS_QUARTER'" in served["html"]


def test_export_passes_filters(qtbot):
    """REQ-DASH-FILTER-04: the export callback receives the dashboard filters."""
    captured = {}
    p_cb = {"on_export": lambda cards, filters=None, **kw: captured.update(f=filters)}
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, p_cb)
    qtbot.addWidget(p)
    p._manual_btn.click()
    p._dash_filters = {"period": "LAST_YEAR", "ou": "USER_ORGUNIT"}
    p.add_card(_cfg("A"))
    p._on_export()
    assert captured["f"] == {"period": "LAST_YEAR", "ou": "USER_ORGUNIT"}


# ── Filter V2: OU level (hierarchical) + custom date range ───────────────────────

def test_ou_level_filter_injected():
    """REQ-DASH-FILTER-06: an OU-level filter yields ou:LEVEL-N + by-level options in the bar."""
    from charts.fixed_templates import assemble_dashboard
    html = assemble_dashboard([_cfg("A")], filters={"ou": "LEVEL-2", "period": "THIS_YEAR"})
    assert "DEFAULT_OU = 'LEVEL-2'" in html
    assert "_appendOuLevels" in html and "By level" in html       # selectable in the bar


def test_custom_range_filter_injected():
    """REQ-DASH-FILTER-07: a custom period range injects __RANGE__ + From/To defaults + pickers."""
    from charts.fixed_templates import assemble_dashboard
    html = assemble_dashboard([_cfg("A")], filters={"ou": "USER_ORGUNIT",
                              "period_from": "202401", "period_to": "202406"})
    assert "DEFAULT_PE = '__RANGE__'" in html
    assert "202401" in html and "202406" in html
    assert 'id="peFrom"' in html and 'id="peTo"' in html and "expandMonths" in html


def test_filter_bar_has_range_and_levels_single_preview():
    """REQ-DASH-FILTER-06/07: the shared filter bar (single preview too) offers range + levels."""
    from charts.fixed_templates import generate_preview_page
    html = generate_preview_page(_cfg("A"))
    assert "Custom range" in html and 'id="peFrom"' in html
    assert "OU_LEVELS" in html


def test_no_leftover_filter_placeholders():
    """REQ-DASH-FILTER-08/09: all 4 filter placeholders are replaced (longest-first order)."""
    import re
    from charts.fixed_templates import assemble_dashboard
    html = assemble_dashboard([_cfg("A")], filters={"ou": "LEVEL-3",
                              "period_from": "202301", "period_to": "202312"})
    assert not re.findall(r"__DEFAULT_PE[A-Z_]*__|__DEFAULT_OU__", html)


def test_dialog_returns_ou_level(qtbot):
    """REQ-DASH-FILTER-06: the dialog can pick an OU level and returns it."""
    from ui.dashboard_filter_dialog import DashboardFilterDialog
    dlg = DashboardFilterDialog(None, {"period": "THIS_YEAR", "ou": "USER_ORGUNIT"})
    qtbot.addWidget(dlg)
    dlg._ou.setCurrentIndex(dlg._ou.findData("LEVEL-2"))
    dlg._on_ok()
    assert dlg.result_filters["ou"] == "LEVEL-2"


def test_dialog_returns_custom_range(qtbot):
    """REQ-DASH-FILTER-07: selecting Custom range returns period_from/period_to."""
    from ui.dashboard_filter_dialog import DashboardFilterDialog
    dlg = DashboardFilterDialog(None, {"period": "THIS_YEAR", "ou": "USER_ORGUNIT"})
    qtbot.addWidget(dlg)
    dlg._pe.setCurrentIndex(dlg._pe.findData("__RANGE__"))
    assert dlg._range_row.isVisibleTo(dlg)             # range pickers revealed
    dlg._from.setCurrentIndex(dlg._from.findData(dlg._from.itemData(2)))
    dlg._to.setCurrentIndex(0)
    dlg._on_ok()
    assert "period_from" in dlg.result_filters and "period_to" in dlg.result_filters
    assert "period" not in dlg.result_filters


def test_dialog_preselects_existing_range(qtbot):
    """REQ-DASH-FILTER-09: reopening a range-filtered dashboard preselects Custom range."""
    from ui.dashboard_filter_dialog import DashboardFilterDialog
    dlg = DashboardFilterDialog(None, {"ou": "USER_ORGUNIT",
                                       "period_from": "202401", "period_to": "202406"})
    qtbot.addWidget(dlg)
    assert dlg._pe.currentData() == "__RANGE__"
    assert dlg._from.currentData() == "202401" and dlg._to.currentData() == "202406"


def test_save_load_persists_range_filter(qtbot, tmp_path, monkeypatch):
    """REQ-DASH-FILTER-05/09: a custom-range filter round-trips through save/load."""
    import config.dashboard_library as lib
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "d.json")
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *a, **k: None)
    monkeypatch.setattr("ui.save_entity_dialog.SaveEntityDialog.prompt",
                        staticmethod(lambda *a, **k: ("RangeDash", "")))
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p._manual_btn.click()
    p._dash_filters = {"ou": "LEVEL-2", "period_from": "202401", "period_to": "202406"}
    p.add_card(_cfg("A"))
    p._on_save_dashboard()
    saved = lib.load_dashboards()[0]
    assert saved["filters"]["period_from"] == "202401"
    p2 = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p2)
    p2.load_dashboard_entry(saved)
    assert p2._dash_filters["ou"] == "LEVEL-2"


# ── Filter V3: dynamic list, alias, type, scope ──────────────────────────────────

def test_v3_dash_filters_json_has_alias_type_scope():
    """REQ-DASH-FILTER-10: a V3 filter list injects DASH_FILTERS with alias/type/scope."""
    from charts.fixed_templates import assemble_dashboard
    html = assemble_dashboard([_cfg("A"), _cfg("B")], filters=[
        {"id": "ou", "alias": "Province", "type": "ou", "default": "LEVEL-2", "scope": "all"},
        {"id": "pe", "alias": "Period", "type": "period", "default": "THIS_YEAR", "scope": "all"},
        {"id": "sex", "alias": "Sex", "type": "dimension", "default": "M", "scope": [0]},
    ])
    assert '"alias": "Province"' in html and '"alias": "Sex"' in html
    assert '"scope": [0]' in html                       # scoped to chart 1 only
    assert "ouForChart" in html and "peForChart" in html and "applyFilterMeta" in html
    assert "CHART_COUNT  = 2" in html


def test_v3_backcompat_flat_dict_still_works():
    """REQ-DASH-FILTER-09: old flat {ou,period} normalises to the V3 list (no break)."""
    from charts.fixed_templates import assemble_dashboard
    html = assemble_dashboard([_cfg("A")], filters={"ou": "USER_ORGUNIT", "period": "LAST_YEAR"})
    assert "DEFAULT_PE = 'LAST_YEAR'" in html
    assert '"type": "ou"' in html and '"type": "period"' in html   # built the 2 base filters


def test_normalize_filters_ensures_ou_and_period():
    """REQ-DASH-FILTER-09: normalisation guarantees an OU + Period filter exist."""
    from charts.fixed_templates import _normalize_filters
    out = _normalize_filters([{"id": "x", "alias": "Sex", "type": "dimension", "default": "M"}])
    types = [f["type"] for f in out]
    assert "ou" in types and "period" in types and "dimension" in types


def test_dimension_filter_applies_to_query():
    """REQ-DASH-FILTER-13: a dimension filter carries its source + appends &filter= at runtime."""
    from charts.fixed_templates import assemble_dashboard
    html = assemble_dashboard([_cfg("A")], filters=[
        {"id": "sex", "alias": "Sex", "type": "dimension",
         "source": "dimUID123", "default": "OPT1", "scope": "all"}])
    assert '"source": "dimUID123"' in html             # source survives normalisation
    assert "dimExtra" in html and "initChartScoped" in html
    assert "'&filter='+encodeURIComponent(f.source)+':'+op+':'" in html   # item:OP:value
    assert "'IN'" in html and "indexOf('/events')" in html   # operator + event-only gating


_META = {
    "program_stage_data_elements": [
        {"id": "deSEX01", "displayName": "Sex",
         "program": {"id": "pMAL", "displayName": "Malaria"},
         "stage": {"id": "stg1", "displayName": "Case"},
         "optionSet": {"options": [{"id": "o1", "code": "M", "displayName": "Male"},
                                    {"id": "o2", "code": "F", "displayName": "Female"}]}},
    ],
    "tracked_entity_attributes": [
        {"id": "paAGE01", "displayName": "Age group",
         "program": {"id": "pMAL", "displayName": "Malaria"}, "optionSet": None},
    ],
}


def test_manager_dimension_picker_program_de_pa(qtbot):
    """REQ-DASH-FILTER-14: dimension filter picks Program → DE/PA from metadata, value from optionSet."""
    from ui.dashboard_filters_manager import FiltersManagerDialog, _build_dim_sources
    srcs = _build_dim_sources(_META)
    assert {s["kind"] for s in srcs} == {"DE", "PA"}
    de = [s for s in srcs if s["kind"] == "DE"][0]
    assert de["source"] == "stg1.deSEX01"               # tracker DE → stage.uid
    assert ("Male", "M") in de["options"]               # value options from optionSet

    base = [{"id": "ou", "alias": "Org unit", "type": "ou", "default": "USER_ORGUNIT", "scope": "all"},
            {"id": "pe", "alias": "Period", "type": "period", "default": "LAST_12_MONTHS", "scope": "all"}]
    dlg = FiltersManagerDialog(None, base, ["Chart A"], metadata=_META)
    qtbot.addWidget(dlg)
    assert dlg._has_dim_meta
    dlg._on_add()                                        # new dimension filter selected
    dlg._dim_src.setCurrentIndex(0)                      # pick first DE/PA
    dlg._dim_val.setCurrentIndex(dlg._dim_val.findData("M"))
    dlg._on_ok()
    dim = [f for f in dlg.result_filters if f["type"] == "dimension"][0]
    assert dim["source"] in ("stg1.deSEX01", "paAGE01")  # a real metadata UID, not free text
    assert dim["default"] in ("M", "")                   # value from optionSet


def test_manager_combos_have_popup_styling(qtbot):
    """Regression: every combo in the manager styles its popup view (no black dropdown)."""
    from ui.dashboard_filters_manager import FiltersManagerDialog
    from PySide6.QtWidgets import QComboBox
    dlg = FiltersManagerDialog(None, None, ["Chart A"])
    qtbot.addWidget(dlg)
    combos = dlg._editor.findChildren(QComboBox)
    assert combos and all("QAbstractItemView" in c.styleSheet() for c in combos)


def test_option_dimension_renders_viewer_dropdown():
    """REQ-DASH-FILTER-15: an option-type dimension filter renders a viewer SELECT (not a fixed value)."""
    from charts.fixed_templates import assemble_dashboard
    html = assemble_dashboard([_cfg("A")], filters=[
        {"id": "sex", "alias": "Sex", "type": "dimension", "source": "stg.deSEX",
         "value_type": "option", "options": [["Male", "M"], ["Female", "F"]],
         "default": "", "scope": "all"}])
    assert '"value_type": "option"' in html
    assert '["Male", "M"]' in html and '["Female", "F"]' in html
    assert "(all) " in html                              # blank option = viewer can clear it


def test_control_type_mapping():
    """REQ-DASH-FILTER-15: DHIS2 valueType / optionSet maps to the right control type."""
    from ui.dashboard_filters_manager import _control_type
    assert _control_type({"optionSet": {"options": [{"id": "o"}]}}) == "option"
    assert _control_type({"valueType": "INTEGER"}) == "number"
    assert _control_type({"valueType": "DATE"}) == "date"
    assert _control_type({"valueType": "TEXT"}) == "text"


def test_dimension_filter_program_scoped_to_matching_charts():
    """REQ-DASH-FILTER-16: a dimension filter only applies to charts of its program (Superset:
    a filter applies only where the dimension/column exists)."""
    from charts.fixed_templates import assemble_dashboard
    c1 = {"template_id": "point_map", "title": "Map",
          "metrics": [{"uid": "qf5", "label": "x", "type": "tracker_numeric",
                       "prog_uid": "pMAL", "stage_uid": "stg1"}]}
    c2 = {"template_id": "bar_monthly", "title": "Agg",
          "metrics": [{"uid": "IND1", "label": "y", "type": "aggregate"}]}
    html = assemble_dashboard([c1, c2], filters=[
        {"id": "tr", "alias": "Test result", "type": "dimension", "source": "stg1.qf5",
         "program": "pMAL", "value_type": "option", "options": [["Pos", "PF"]],
         "default": "PF", "scope": "all"}])
    import re, json
    cp = json.loads(re.search(r"CHART_PROG\s*=\s*(\{.*?\});", html).group(1))
    assert cp == {"1": "pMAL", "2": ""}                  # chart1 tracker, chart2 aggregate
    assert '"program": "pMAL"' in html                   # filter restricted to that program
    assert "f.program !== cp" in html                    # JS guard skips non-matching charts


def test_dimension_filter_normalize_keeps_source():
    """REQ-DASH-FILTER-13: _normalize_filters preserves a dimension filter's source."""
    from charts.fixed_templates import _normalize_filters
    out = _normalize_filters([{"id": "d", "type": "dimension", "source": "abc", "default": "x"}])
    dim = [f for f in out if f["type"] == "dimension"][0]
    assert dim["source"] == "abc" and dim["default"] == "x"


def test_manager_add_edit_returns_v3_list(qtbot):
    """REQ-DASH-FILTER-10: the manager adds a filter and returns alias/type/value/scope."""
    from ui.dashboard_filters_manager import FiltersManagerDialog
    from PySide6.QtCore import Qt
    base = [{"id": "ou", "alias": "Org unit", "type": "ou", "default": "USER_ORGUNIT", "scope": "all"},
            {"id": "pe", "alias": "Period", "type": "period", "default": "LAST_12_MONTHS", "scope": "all"}]
    dlg = FiltersManagerDialog(None, base, ["Chart A", "Chart B"])
    qtbot.addWidget(dlg)
    dlg._on_add()                                       # adds a dimension filter, selects it
    assert dlg._cur == 2
    dlg._alias.setText("Sex")
    dlg._src.setText("dimUID123")
    dlg._dimval.setText("Male")
    dlg._scope_sel.setChecked(True)                     # scope = selected
    dlg._charts.item(0).setCheckState(Qt.CheckState.Checked)
    dlg._on_ok()

    res = dlg.result_filters
    assert len(res) == 3
    sex = [f for f in res if f["type"] == "dimension"][0]
    assert sex["alias"] == "Sex" and sex["source"] == "dimUID123" and sex["default"] == "Male"
    assert sex["scope"] == [0]                          # applies to Chart A only


def test_manager_change_ou_level_and_period_range(qtbot):
    """REQ-DASH-FILTER-06/07 via manager: OU level + custom period range editable per filter."""
    from ui.dashboard_filters_manager import FiltersManagerDialog
    base = [{"id": "ou", "alias": "Org unit", "type": "ou", "default": "USER_ORGUNIT", "scope": "all"},
            {"id": "pe", "alias": "Period", "type": "period", "default": "LAST_12_MONTHS", "scope": "all"}]
    dlg = FiltersManagerDialog(None, base, ["Chart A"])
    qtbot.addWidget(dlg)
    dlg._list.setCurrentRow(0)                          # OU filter
    dlg._ou.setCurrentIndex(dlg._ou.findData("LEVEL-2"))
    dlg._list.setCurrentRow(1)                          # Period filter
    dlg._pe.setCurrentIndex(dlg._pe.findData("__RANGE__"))
    assert dlg._range_row.isVisibleTo(dlg)
    dlg._on_ok()
    ou = [f for f in dlg.result_filters if f["type"] == "ou"][0]
    pe = [f for f in dlg.result_filters if f["type"] == "period"][0]
    assert ou["default"] == "LEVEL-2"
    assert pe["default"] == "__RANGE__" and pe["from"] and pe["to"]


def test_v3_filters_save_load_roundtrip(qtbot, tmp_path, monkeypatch):
    """REQ-DASH-FILTER-05/10: a V3 filter list round-trips through save/load."""
    import config.dashboard_library as lib
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "d.json")
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *a, **k: None)
    monkeypatch.setattr("ui.save_entity_dialog.SaveEntityDialog.prompt",
                        staticmethod(lambda *a, **k: ("V3Dash", "")))
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p._manual_btn.click()
    p._dash_filters = [
        {"id": "ou", "alias": "Province", "type": "ou", "default": "LEVEL-2", "scope": "all"},
        {"id": "pe", "alias": "Period", "type": "period", "default": "THIS_YEAR", "scope": "all"},
        {"id": "sex", "alias": "Sex", "type": "dimension", "default": "M", "scope": [0]},
    ]
    p.add_card(_cfg("A"))
    p._on_save_dashboard()
    saved = lib.load_dashboards()[0]
    assert isinstance(saved["filters"], list) and len(saved["filters"]) == 3
    p2 = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p2)
    p2.load_dashboard_entry(saved)
    assert [f["alias"] for f in p2._dash_filters] == ["Province", "Period", "Sex"]


def test_save_load_persists_filters(qtbot, tmp_path, monkeypatch):
    """REQ-DASH-FILTER-05: filters are saved with the dashboard and restored on load."""
    import config.dashboard_library as lib
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "d.json")
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *a, **k: None)
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p._manual_btn.click()
    p._dash_filters = {"period": "THIS_YEAR", "ou": "USER_ORGUNIT_CHILDREN"}
    p.add_card(_cfg("A"))
    monkeypatch.setattr("ui.save_entity_dialog.SaveEntityDialog.prompt",
                        staticmethod(lambda *a, **k: ("WithFilters", "")))
    p._on_save_dashboard()

    saved = lib.load_dashboards()[0]
    assert saved["filters"] == {"period": "THIS_YEAR", "ou": "USER_ORGUNIT_CHILDREN"}

    p2 = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p2)
    p2.load_dashboard_entry(saved)
    assert p2._dash_filters == {"period": "THIS_YEAR", "ou": "USER_ORGUNIT_CHILDREN"}
