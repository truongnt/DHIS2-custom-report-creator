"""Integration tests — Save / New / Save As flows for Chart Editor and Dashboard
Builder (user request 2026-06-27: a flow to save, then start new or save-as).

Drives the real Qt panels via qtbot. Storage is redirected to a tmp file and the
modal dialogs are stubbed so the flow runs headless.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


# ── Chart Editor ────────────────────────────────────────────────────────────

@pytest.fixture
def editor(qtbot, tmp_path, monkeypatch):
    import config.chart_library as cl
    monkeypatch.setattr(cl, "_LIBRARY_FILE", tmp_path / "charts.json")
    from ui.chart_editor_panel import ChartEditorPanel
    cb = {"on_chart_saved": lambda *a, **k: None}
    p = ChartEditorPanel(None, callbacks=cb)
    qtbot.addWidget(p)
    # Minimal valid config so _build_config-dependent code is bypassed; we test the
    # save/new/save-as FLOW, not config building (covered elsewhere).
    monkeypatch.setattr(p, "_build_config",
                        lambda: {"plugin_id": "bar", "title": "My Chart",
                                 "template_id": "bar", "metrics": [{"uid": "x", "name": "X"}]})
    return p


def _stub_dialogs(monkeypatch, name: str, description: str = ""):
    import ui.chart_editor_panel as m
    import ui.save_entity_dialog as sd
    monkeypatch.setattr(sd.SaveEntityDialog, "prompt",
                        staticmethod(lambda *a, **k: (name, description)))
    monkeypatch.setattr(m.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(m.QMessageBox, "question",
                        staticmethod(lambda *a, **k: m.QMessageBox.StandardButton.Yes))


def test_chart_first_save_creates_and_tracks_id(editor, monkeypatch):
    """REQ-SAVE-CHART-01: saving a new chart prompts for a name, creates ONE entry,
    and the editor then tracks that chart's id."""
    from config.chart_library import load_charts
    _stub_dialogs(monkeypatch, "Chart A")
    assert editor._current_chart_id is None
    editor._on_save()
    charts = load_charts()
    assert len(charts) == 1 and charts[0]["name"] == "Chart A"
    assert editor._current_chart_id == charts[0]["id"]
    assert "editing: Chart A" in editor._chart_name_lbl.text()


def test_chart_save_updates_not_duplicates(editor, monkeypatch):
    """REQ-SAVE-CHART-02: Save on an already-tracked chart updates it (no duplicate)."""
    from config.chart_library import load_charts
    _stub_dialogs(monkeypatch, "Chart A")
    editor._on_save()                      # create
    cid = editor._current_chart_id
    editor._title_entry.setText("renamed in editor")
    editor._on_save()                      # update — must NOT prompt or duplicate
    charts = load_charts()
    assert len(charts) == 1
    assert charts[0]["id"] == cid


def test_chart_save_as_creates_second(editor, monkeypatch):
    """REQ-SAVE-CHART-03: Save As always creates a NEW chart with a new id."""
    from config.chart_library import load_charts
    _stub_dialogs(monkeypatch, "Chart A")
    editor._on_save()
    first_id = editor._current_chart_id
    _stub_dialogs(monkeypatch, "Chart B")
    editor._on_save_as()
    charts = load_charts()
    assert len(charts) == 2
    assert editor._current_chart_id != first_id
    assert {c["name"] for c in charts} == {"Chart A", "Chart B"}


def test_chart_new_resets_identity(editor, monkeypatch):
    """REQ-SAVE-CHART-04: New detaches from the saved entity and clears the title."""
    _stub_dialogs(monkeypatch, "Chart A")
    editor._on_save()
    assert editor._current_chart_id is not None
    editor._title_entry.setText("something")
    editor._on_new()
    assert editor._current_chart_id is None
    assert editor._current_chart_name is None
    assert editor._title_entry.text() == ""
    assert "new chart" in editor._chart_name_lbl.text()


# ── Dashboard Builder ─────────────────────────────────────────────────────────

@pytest.fixture
def dash(qtbot, tmp_path, monkeypatch):
    import config.dashboard_library as dl
    monkeypatch.setattr(dl, "_LIBRARY_FILE", tmp_path / "dashboards.json")
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p._choose_mode("ai")                  # ai mode → cards come from self._cards
    p._cards = [{"plugin_id": "bar", "title": "c1"}]
    return p


def _stub_dash_dialogs(monkeypatch, name: str, description: str = ""):
    import ui.dashboard_builder_panel as m
    import ui.save_entity_dialog as sd
    monkeypatch.setattr(sd.SaveEntityDialog, "prompt",
                        staticmethod(lambda *a, **k: (name, description)))
    monkeypatch.setattr(m.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(m.QMessageBox, "question",
                        staticmethod(lambda *a, **k: m.QMessageBox.StandardButton.Yes))


def test_dashboard_save_and_track(dash, monkeypatch):
    """REQ-SAVE-DASH-01: Save (new dashboard) prompts name+description and tracks it."""
    from config.dashboard_library import load_dashboards
    _stub_dash_dialogs(monkeypatch, "Dash A")
    dash._on_save_dashboard()
    dboards = load_dashboards()
    assert len(dboards) == 1 and dboards[0]["name"] == "Dash A"
    assert dash._current_dashboard_name == "Dash A"


def test_dashboard_save_as_creates_second(dash, monkeypatch):
    """REQ-SAVE-DASH-02: Save As saves a copy under a new name."""
    from config.dashboard_library import load_dashboards
    _stub_dash_dialogs(monkeypatch, "Dash A")
    dash._on_save_dashboard()
    _stub_dash_dialogs(monkeypatch, "Dash B")
    dash._on_save_dashboard_as()
    names = {d["name"] for d in load_dashboards()}
    assert names == {"Dash A", "Dash B"}
    assert dash._current_dashboard_name == "Dash B"


def test_dashboard_new_clears(dash, monkeypatch):
    """REQ-SAVE-DASH-03: New clears the canvas and detaches from the saved dashboard."""
    _stub_dash_dialogs(monkeypatch, "Dash A")
    dash._on_save_dashboard()
    dash._on_new_dashboard()
    assert dash._current_dashboard_name is None
    assert dash._cards == []
    assert dash._dashboard_name() == ""


def test_chart_open_loads_for_edit(editor, monkeypatch):
    """REQ-SAVE-CHART-05: Open n: a saved chart back into the editor and tracks its id."""
    from config.chart_library import load_charts
    from PySide6.QtWidgets import QDialog
    _stub_dialogs(monkeypatch, "Chart A")
    editor._on_save()
    saved = load_charts()[0]
    editor._on_new()
    assert editor._current_chart_id is None

    import ui.load_chart_dialog as lcd

    class _FakeDlg:
        def __init__(self, parent, charts):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_selected(self):
            return saved

    monkeypatch.setattr(lcd, "LoadChartDialog", _FakeDlg)
    editor._on_open_chart()
    assert editor._current_chart_id == saved["id"]
    assert "editing: Chart A" in editor._chart_name_lbl.text()


def test_chart_action_buttons_enable_state(editor, monkeypatch):
    """REQ-UI-COMP-06: Save/Save As/Add/Preview disabled until a chart is configured;
    Open disabled until at least one chart is saved."""
    editor._selected_template = None
    monkeypatch.setattr(editor, "_get_selected_des", lambda: [])
    editor._update_action_buttons()
    assert not editor._save_btn.isEnabled()
    assert not editor._save_as_btn.isEnabled()
    assert not editor._preview_btn.isEnabled()
    assert not editor._open_btn.isEnabled()          # nothing saved yet
    assert editor._new_btn.isEnabled()               # New always available

    # Configure a valid chart → action buttons enable.
    editor._selected_template = {"id": "bar"}
    monkeypatch.setattr(editor, "_get_selected_des", lambda: [{"uid": "x", "name": "X"}])
    editor._update_action_buttons()
    assert editor._save_btn.isEnabled()
    assert editor._save_as_btn.isEnabled()
    assert editor._preview_btn.isEnabled()


def test_chart_open_enabled_after_save(editor, monkeypatch):
    """REQ-UI-COMP-06: the Open button becomes enabled once a chart exists on disk."""
    assert not editor._open_btn.isEnabled()
    _stub_dialogs(monkeypatch, "Chart A")
    editor._on_save()
    assert editor._open_btn.isEnabled()


# ── Consistent button order across screens (REQ-UI-COMP-08) ───────────────────

from PySide6.QtWidgets import QPushButton  # noqa: E402


def _buttons_in_layout_order(widget):
    """All QPushButtons under `widget`, in visual (layout) order."""
    out = []

    def walk(lay):
        for i in range(lay.count()):
            it = lay.itemAt(i)
            w = it.widget()
            if isinstance(w, QPushButton):
                out.append(w)
            sub = it.layout()
            if sub is not None:
                walk(sub)
            elif w is not None and w.layout() is not None:
                walk(w.layout())

    if widget.layout() is not None:
        walk(widget.layout())
    return out


def _entity_order(widget):
    """First-occurrence order of the entity actions: returns a list like
    ['new','open','save','save_as'] in the order they appear."""
    seq = []
    for b in _buttons_in_layout_order(widget):
        t = b.text()
        if "New" in t:
            cat = "new"
        elif "Open" in t or "Load" in t:
            cat = "open"
        elif "Save As" in t:
            cat = "save_as"
        elif "Save" in t:
            cat = "save"
        else:
            continue
        if cat not in seq:
            seq.append(cat)
    return seq


def test_chart_editor_button_order_canonical(editor):
    """REQ-UI-COMP-08: Chart Editor actions follow New · Open · Save · Save As."""
    assert _entity_order(editor) == ["new", "open", "save", "save_as"]


def test_dashboard_button_order_canonical(dash):
    """REQ-UI-COMP-08: Dashboard actions follow New · Open · Save · Save As (same as chart).
    Scoped to the ACTIVE workspace toolbar — the landing chooser has its own 'Open existing'
    entry which is not part of the workspace action set."""
    assert _entity_order(dash._stack.currentWidget()) == ["new", "open", "save", "save_as"]


# ── Open restores ALL parameters (REQ-UI-LOAD-01) ─────────────────────────────

_META_RESTORE = {
    "program_stage_data_elements": [
        {"id": "deopt00001", "displayName": "Diagnosis",
         "program": {"id": "PROG1", "displayName": "Malaria"},
         "stage": {"id": "STG1", "displayName": "Stage 1"},
         "optionSet": {"options": [{"code": "PF", "displayName": "P. falciparum"},
                                   {"code": "PV", "displayName": "P. vivax"}]}},
    ],
    "tracked_entity_attributes": [
        {"id": "teagen0001", "displayName": "Gender", "valueType": "TEXT",
         "program": {"id": "PROG1", "displayName": "Malaria"},
         "optionSet": {"options": [{"code": "M", "displayName": "Male"},
                                   {"code": "F", "displayName": "Female"}]}},
    ],
    "data_elements": [], "programs": [], "indicators": [], "program_indicators": [],
}


@pytest.fixture
def editor_md(qtbot, tmp_path, monkeypatch):
    import config.chart_library as cl
    monkeypatch.setattr(cl, "_LIBRARY_FILE", tmp_path / "charts.json")
    from ui.chart_editor_panel import ChartEditorPanel
    p = ChartEditorPanel(None, callbacks={})
    qtbot.addWidget(p)
    p.load_metadata(_META_RESTORE)
    # Metrics/dimensions come only from the in-use set — curate everything for tests.
    p.set_in_use({"deopt00001", "teagen0001"})
    return p


def test_open_restores_all_parameters(editor_md, qtbot):
    """REQ-UI-LOAD-01: loading a saved chart restores chart type, source+stage, metric,
    split-by dimension, filter, plugin option, time grain, sort, title, col width."""
    chart = {
        "id": "c1", "name": "Saved", "template_id": "bar", "title": "Saved Bar",
        "chart_color": "#e74c3c", "col_width": 12,
        "source": {"type": "tracker_option", "prog_uid": "PROG1", "prog_name": "Malaria",
                   "stage_uid": "STG1", "stage_name": "Stage 1"},
        "metrics": [{"uid": "deopt00001", "name": "Diagnosis", "type": "tracker_option",
                     "prog_uid": "PROG1", "stage_uid": "STG1", "agg": "SUM"}],
        "dimensions": {
            "time_grain": "Quarterly",
            "dimension": {"uid": "teagen0001", "name": "Gender", "type": "tracker_option",
                          "is_tea": True, "stage_uid": ""},
            "group_by": [], "row_limit": 20, "sort_by": "Value", "sort_dir": "Desc",
            "filters": [{"de_uid": "deopt00001", "de_name": "Diagnosis",
                         "de_type": "tracker_option", "op": "EQ", "value": "PF"}],
        },
        "plugin_options": {"color_scheme": "Warm"},
    }
    editor_md._load_chart_config(chart)
    qtbot.wait(350)   # let the deferred DE-dependent restore run

    assert editor_md._selected_template["id"] == "bar"
    assert editor_md._title_entry.text() == "Saved Bar"
    assert editor_md._col_width_seg.get() == "Full"
    assert editor_md._time_grain_seg.get() == "Quarterly"
    assert editor_md._sort_by_combo.currentText() == "Value"
    assert editor_md._sort_dir_combo.currentText() == "Desc"
    assert editor_md._row_limit_combo.currentText() == "20"
    # metric restored
    assert "deopt00001" in {d["uid"] for d in editor_md._get_selected_des()}
    # split-by dimension restored
    dim = editor_md._dim_picker.get_first_de()
    assert dim and dim["uid"] == "teagen0001"
    # filter restored (field + option-set value)
    assert len(editor_md._filter_rows) == 1
    rd = editor_md._filter_rows[0]
    assert rd["de_menu"].currentText() == "(DE) Diagnosis"
    assert editor_md._filter_value(rd) == "PF"
    # plugin option restored
    assert editor_md._select_vars["color_scheme"].get() == "Warm"


# ── Dialog footer styling (REQ-UI-COMP-09) ────────────────────────────────────

def test_open_chart_dialog_footer_styled(qtbot):
    """REQ-UI-COMP-09: the Open Chart dialog's OK/Cancel are properly sized, the
    primary (OK) is blue, and both have a hover rule (not flush in a corner)."""
    from ui.load_chart_dialog import LoadChartDialog
    from PySide6.QtWidgets import QDialogButtonBox
    dlg = LoadChartDialog(None, [{"id": "x", "name": "C", "template_label": "Bar"}])
    qtbot.addWidget(dlg)
    dlg.resize(440, 360)
    dlg.show()
    qtbot.waitExposed(dlg)
    boxes = dlg.findChildren(QDialogButtonBox)
    assert boxes, "dialog must use a QDialogButtonBox"
    box = boxes[0]
    ok = next(b for b in box.buttons()
              if box.buttonRole(b) == QDialogButtonBox.ButtonRole.AcceptRole)
    assert ok.minimumWidth() >= 80 and ok.minimumHeight() >= 28
    assert "#1a6fa8" in ok.styleSheet().lower() or "1a6fa8" in ok.styleSheet()
    assert ":hover" in ok.styleSheet()
    for b in box.buttons():
        assert ":hover" in b.styleSheet(), "every dialog button needs a hover state"
    # Real geometry: the OK button must NOT be flush in the bottom-right corner.
    br = ok.mapTo(dlg, ok.rect().bottomRight())
    assert dlg.width() - br.x() >= 8, "OK button flush to the right edge — no margin"
    assert dlg.height() - br.y() >= 6, "OK button flush to the bottom edge — no margin"


def test_open_chart_dialog_table_columns(qtbot):
    """REQ-UI-LOAD-02: Open dialogs are tables with Name · Description · Type · Date
    columns and a per-row delete button."""
    from ui.load_chart_dialog import LoadChartDialog
    charts = [{"id": "c1", "name": "My Bar", "template_label": "Bar — monthly",
               "created_at": "2026-06-20T09:00:00",
               "metrics": [{"name": "Diagnosis", "prog_name": "Malaria"}]}]
    dlg = LoadChartDialog(None, charts)
    qtbot.addWidget(dlg)
    t = dlg._table
    assert [t.horizontalHeaderItem(i).text() for i in range(4)] == \
        ["Name", "Description", "Type", "Date"]
    assert t.item(0, 0).text() == "My Bar"
    assert "Diagnosis" in t.item(0, 1).text() and "Malaria" in t.item(0, 1).text()
    assert t.item(0, 2).text() == "Bar — monthly"
    assert t.item(0, 3).text() == "2026-06-20"
    assert t.cellWidget(0, 4) is not None, "row needs a delete button"


# ── Description captured at Save / Save As (REQ-UI-LOAD-03) ───────────────────

def test_chart_save_captures_description(editor, monkeypatch):
    """REQ-UI-LOAD-03: a chart's description entered at save is persisted + shown in Open."""
    from config.chart_library import load_charts
    from ui.load_chart_dialog import LoadChartDialog
    _stub_dialogs(monkeypatch, "Chart A", "Malaria cases by month")
    editor._on_save()
    saved = load_charts()[0]
    assert saved.get("description") == "Malaria cases by month"
    # The Open table shows the user's description (not the derived summary).
    dlg = LoadChartDialog(None, load_charts())
    assert dlg._table.item(0, 1).text() == "Malaria cases by month"


def test_dashboard_save_captures_description(dash, monkeypatch):
    """REQ-UI-LOAD-03: a dashboard's description is persisted + shown in the Load table."""
    from config.dashboard_library import load_dashboards
    from ui.load_dashboard_dialog import LoadDashboardDialog
    _stub_dash_dialogs(monkeypatch, "Dash A", "Quarterly KPIs")
    dash._on_save_dashboard()
    saved = load_dashboards()[0]
    assert saved.get("description") == "Quarterly KPIs"
    dlg = LoadDashboardDialog(None, load_dashboards())
    assert dlg._table.item(0, 1).text() == "Quarterly KPIs"


def test_dashboard_save_as_captures_description(dash, monkeypatch):
    """REQ-UI-LOAD-03: Save As captures name + description via the dialog."""
    from config.dashboard_library import load_dashboards
    _stub_dash_dialogs(monkeypatch, "Dash B", "From save-as")
    dash._on_save_dashboard_as()
    entry = next(d for d in load_dashboards() if d["name"] == "Dash B")
    assert entry.get("description") == "From save-as"


def test_load_dashboard_no_floating_placeholder(dash, monkeypatch, qtbot):
    """REQ-DASH-LOAD-01: loading a saved dashboard must NOT pop the grid's empty
    placeholder as a separate top-level window (it stays parented + hidden)."""
    from config.dashboard_library import save_dashboard
    # Save a manual dashboard with one card, then load it back.
    save_dashboard("Saved Manual", [{"plugin_id": "bar", "title": "c1",
                                     "layout": {"x": 0, "y": 0, "w": 6, "h": 2}}],
                   mode="manual")
    from config.dashboard_library import get_dashboard
    dash.load_dashboard_entry(get_dashboard("Saved Manual"))
    qtbot.wait(50)
    empty = dash._grid._empty
    assert not empty.isWindow(), "placeholder became a top-level window"
    assert empty.parent() is dash._grid._host
    # With a card present the placeholder is hidden; never a separate window.
    assert not empty.isVisible()


def test_build_config_applies_metric_alias(editor_md, qtbot):
    """REQ-CE-METRIC-ALIAS-04: a metric alias becomes the displayed name in the config
    (render layers read `name`); the real DE name is kept as `orig_name`."""
    from charts.fixed_templates import FIXED_TEMPLATES
    bar = next(t for t in FIXED_TEMPLATES if t["id"] == "bar")
    editor_md._on_chart_type_click(bar)
    editor_md._src_prog_cb.setChecked(True)
    editor_md._prog_menu.setCurrentText("Malaria")
    qtbot.wait(50)
    editor_md._metrics_picker.set_selected_uids(["deopt00001"])
    editor_md._metrics_picker._selected[0]["alias"] = "Cases"
    editor_md._on_de_check()
    cfg = editor_md._build_config()
    assert cfg is not None
    m = cfg["metrics"][0]
    assert m["name"] == "Cases"
    assert m["orig_name"] == "Diagnosis"
