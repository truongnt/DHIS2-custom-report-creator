"""UI regression for the Chart Editor panel (user report 2026-06-26):
dropdown popup rendered dark/unreadable, filter-row controls had mismatched heights."""
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def editor(qtbot):
    from ui.chart_editor_panel import ChartEditorPanel
    cb = {"on_chart_saved": lambda *a, **k: None,
          "on_add_to_dashboard": lambda *a, **k: None,
          "on_generate_ai": lambda *a, **k: None,
          "on_switch_to_dashboard": lambda *a, **k: None,
          "get_api_key": lambda: "",
          "get_model": lambda: "claude-haiku-4-5-20251001"}
    p = ChartEditorPanel(None, callbacks=cb)
    qtbot.addWidget(p)
    return p


def test_filter_row_controls_same_height(editor):
    """REQ-UI-LAYOUT-08: every control on a filter row shares one height."""
    editor._add_filter_row()
    rd = editor._filter_rows[-1]
    heights = {rd["de_menu"].maximumHeight(), rd["op_menu"].maximumHeight(),
               rd["val_entry"].maximumHeight()}
    assert heights == {26}, f"filter-row heights differ: {heights}"


def test_filter_combobox_popup_renders_light(editor, qtbot):
    """REQ-UI-COLOR-05: the filter DE dropdown popup RENDERS with a light background.

    NOTE: the first version of this test only asserted the panel's stylesheet *string*
    and passed while the popup was still black (a false pass). This version opens the
    popup and samples its actual rendered pixels — the only honest check.
    """
    editor._add_filter_row()
    de = editor._filter_rows[-1]["de_menu"]
    for i in range(8):                       # ensure the popup has items to show
        de.addItem(f"Invest: item {i}")
    de.showPopup()
    qtbot.wait(80)
    view = de.view()
    img = view.viewport().grab().toImage()
    assert img.width() > 4 and img.height() > 4, "popup did not render"
    # Sample background pixels on the right edge of NON-selected rows (mid/lower —
    # the top row is the highlighted current item, legitimately blue).
    w, h = img.width(), img.height()
    lums = []
    for y in (h // 2, 2 * h // 3, h - 4):
        c = img.pixelColor(w - 3, y)
        lums.append((c.red() + c.green() + c.blue()) / 3)
    de.hidePopup()
    assert min(lums) > 150, f"popup background too dark (lums={lums}) — black-popup bug"


# ── Feature tests (user report 2026-06-26): PA, searchable filter, optionset value ──

from PySide6.QtCore import Qt  # noqa: E402

_META = {
    "program_stage_data_elements": [
        {"id": "deopt00001", "displayName": "Diagnosis",
         "program": {"id": "PROG1", "displayName": "Malaria"},
         "stage": {"id": "STG1", "displayName": "Stage 1"},
         "optionSet": {"options": [{"code": "PF", "displayName": "P. falciparum"},
                                   {"code": "PV", "displayName": "P. vivax"}]}},
        {"id": "denum00001", "displayName": "Temperature",
         "program": {"id": "PROG1", "displayName": "Malaria"},
         "stage": {"id": "STG1", "displayName": "Stage 1"}},
    ],
    "tracked_entity_attributes": [
        {"id": "teagen0001", "displayName": "Gender", "valueType": "TEXT",
         "program": {"id": "PROG1", "displayName": "Malaria"},
         "optionSet": {"options": [{"code": "M", "displayName": "Male"},
                                   {"code": "F", "displayName": "Female"}]}},
        {"id": "teaage0001", "displayName": "Age", "valueType": "INTEGER",
         "program": {"id": "PROG1", "displayName": "Malaria"}},
    ],
    "data_elements": [], "programs": [], "indicators": [],
    "program_indicators": [
        {"id": "pi00000001", "displayName": "Malaria incidence (PI)",
         "program": {"id": "PROG1", "displayName": "Malaria"}},
    ],
}


def _select_bar(editor):
    from charts.fixed_templates import FIXED_TEMPLATES
    editor._on_chart_type_click(next(t for t in FIXED_TEMPLATES if t["id"] == "bar"))


def _all_uids(meta: dict) -> set[str]:
    """Every metadata UID in a fixture — used to curate the in-use set for tests."""
    uids: set[str] = set()
    for key in ("program_stage_data_elements", "tracked_entity_attributes",
                "program_indicators", "data_elements", "indicators"):
        uids |= {it["id"] for it in meta.get(key, [])}
    return uids


def _load_malaria(editor):
    editor.load_metadata(_META)
    editor._src_prog_cb.setChecked(True)
    editor._prog_menu.setCurrentText("Malaria")
    editor.set_in_use(_all_uids(_META))    # metrics/dims now come only from in-use
    return editor


def test_program_attributes_available(editor):
    """REQ-CE-PA-01: tracked-entity attributes (gender/age) appear as selectable items."""
    _load_malaria(editor)
    by_uid = {d["uid"]: d for d in editor._current_de_items}
    assert "teagen0001" in by_uid and "teaage0001" in by_uid, "PA/TEA missing from items"
    assert by_uid["teagen0001"]["type"] == "tracker_option"   # gender → option set
    assert by_uid["teaage0001"]["type"] == "tracker_numeric"  # age INTEGER → numeric
    assert by_uid["teagen0001"]["is_tea"] is True


def test_filter_field_dropdown_searchable(editor):
    """REQ-CE-FILTER-SEARCH-01: filter field dropdown is type-to-search (contains match)."""
    editor._add_filter_row()
    de = editor._filter_rows[-1]["de_menu"]
    assert de.isEditable()
    assert de.completer().filterMode() == Qt.MatchFlag.MatchContains
    assert de.completer().caseSensitivity() == Qt.CaseSensitivity.CaseInsensitive


def test_filter_optionset_value_dropdown(editor):
    """REQ-CE-FILTER-VALUE-01: option-set field → value chosen from captured option set."""
    _load_malaria(editor)
    editor._add_filter_row()
    rd = editor._filter_rows[-1]
    rd["de_menu"].setCurrentText("(DE) Diagnosis")     # option-set DE (app-wide "(DE) Name")
    assert rd["use_combo"] is True
    codes = [rd["val_combo"].itemData(i) for i in range(rd["val_combo"].count())]
    assert "PF" in codes and "PV" in codes
    rd["val_combo"].setCurrentIndex(codes.index("PF"))
    assert editor._filter_value(rd) == "PF"            # value = option CODE
    rd["de_menu"].setCurrentText("(DE) Temperature")   # numeric → free text
    assert rd["use_combo"] is False


def test_dimension_picker_hidden_for_maps(editor):
    """REQ-CE-DIM-01: the split-by picker shows only for chart types that support a
    dimension; maps (no dimension controls) hide it (it was being ignored before)."""
    from charts.fixed_templates import FIXED_TEMPLATES
    bar = next(t for t in FIXED_TEMPLATES if t["id"] == "bar")
    amap = next(t for t in FIXED_TEMPLATES if t["id"] == "area_map")
    editor._on_chart_type_click(bar)
    assert editor._dim_picker_row.isVisibleTo(editor) is True
    editor._on_chart_type_click(amap)
    assert editor._dim_picker_row.isVisibleTo(editor) is False


def test_custom_html_shows_html_editor(editor):
    """REQ-HTML-EDIT-01: selecting Custom HTML renders a tall HTML editor (TextAreaControl)
    and the dimension picker becomes multi-select with aliases (table-like data model)."""
    from charts.fixed_templates import FIXED_TEMPLATES
    html_t = next(t for t in FIXED_TEMPLATES if t["id"] == "custom_html")
    editor._on_chart_type_click(html_t)
    assert "html" in editor._textarea_vars, "no HTML editor rendered for custom_html"
    ed = editor._textarea_vars["html"]
    ed.setPlainText("<b>{{Cases}}</b>")
    assert ed.toPlainText() == "<b>{{Cases}}</b>"
    # The HTML editor is a tall box (not a one-line field).
    assert ed.minimumHeight() >= 200
    # Dimensions behave like metrics: multi-select + alias.
    assert editor._dim_picker._max_count >= 2
    assert editor._dim_picker._show_alias is True
    # Syntax highlighter attached for the HTML editor, tracking known {{variable}} columns.
    assert editor._html_highlighter is not None
    known = editor._html_known_vars()
    assert "Event date" in known and "Org unit" in known
    # "Generate from image" (AI vision) button is present for Custom HTML.
    assert hasattr(editor, "_html_ai_btn") and editor._html_ai_btn is not None


def test_html_highlighter_known_vars(qtbot):
    """REQ-HTML-HL-01: the highlighter accepts known column names and rehighlights without
    crashing (green for known {{var}}, red for unknown)."""
    from PySide6.QtGui import QTextDocument
    from ui.html_highlighter import HtmlTemplateHighlighter
    doc = QTextDocument("<div>{{Cases}} {{Typo}}</div>")
    hl = HtmlTemplateHighlighter(doc, {"Cases"})
    assert "Cases" in hl._known
    hl.set_known_vars({"Cases", "Sex"})
    assert hl._known == {"Cases", "Sex"}


def test_program_indicators_available(editor):
    """REQ-CE-PI-01: program indicators appear as selectable metrics (type 'indicator',
    kind 'PI') under the Program source."""
    _select_bar(editor)
    _load_malaria(editor)
    by_uid = {d["uid"]: d for d in editor._current_de_items}
    assert "pi00000001" in by_uid, "program indicator missing from items"
    assert by_uid["pi00000001"]["type"] == "indicator"
    assert by_uid["pi00000001"]["kind"] == "PI"
    assert by_uid["pi00000001"].get("is_pi") is True


_META_AGG = {
    "data_elements": [{"id": "de_agg_1", "displayName": "ANC visits"}],
    "indicators": [{"id": "ind00000001", "displayName": "ANC coverage (Ind)"}],
    "programs": [], "program_indicators": [],
}


def test_indicators_independent_source(editor):
    """REQ-CE-IND-01: indicators are their OWN source (not under Aggregate Dataset) — ticking
    'Indicators' alone, with Aggregate OFF, lists them (type 'indicator', no prog_uid)."""
    _select_bar(editor)
    editor.load_metadata(_META_AGG)
    editor.set_in_use({"ind00000001", "de_agg_1"})
    editor._src_agg_cb.setChecked(False)        # aggregate OFF
    editor._src_ind_cb.setChecked(True)         # indicators source ON
    by_uid = {d["uid"]: d for d in editor._current_de_items}
    assert "ind00000001" in by_uid, "indicator missing — should not require Aggregate source"
    assert by_uid["ind00000001"]["type"] == "indicator"
    assert by_uid["ind00000001"]["prog_uid"] == ""
    assert "de_agg_1" not in by_uid             # aggregate DEs NOT pulled in


def test_indicators_source_off_by_default(editor):
    """REQ-CE-IND-02: the Indicators source is OFF by default (loaded only on demand)."""
    _select_bar(editor)
    editor.load_metadata(_META_AGG)
    assert editor._src_ind_cb.isChecked() is False
    by_uid = {d["uid"]: d for d in editor._current_de_items}
    assert "ind00000001" not in by_uid


def test_indicators_lazy_load_offline_noop(editor):
    """REQ-CE-IND-03: ticking 'Indicators' with no client (fixture mode) and no cached
    indicators is a safe no-op — nothing loaded, no crash."""
    _select_bar(editor)
    editor.load_metadata({"data_elements": [], "indicators": [],
                          "programs": [], "program_indicators": []})
    editor._dhis2_client = None
    editor._src_ind_cb.setChecked(True)         # → _ensure_indicators_loaded
    assert editor._indicators_loading is False
    assert editor._agg_indicators == []


def test_indicators_lazy_fetch(editor, monkeypatch):
    """REQ-CE-IND-04: when indicators were NOT in connect-time metadata, ticking 'Indicators'
    fetches them on demand via the client, then they appear in the picker."""
    _select_bar(editor)
    editor.load_metadata({"data_elements": [], "indicators": [],
                          "programs": [], "program_indicators": []})
    assert editor._indicators_loaded is False
    import dhis2.metadata as md
    monkeypatch.setattr(md, "fetch_indicators",
                        lambda client, cfg=None: [{"id": "lz0000001", "displayName": "Lazy Ind"}])
    editor.set_in_use({"lz0000001"})           # curate the soon-to-be-fetched indicator
    editor._dhis2_client = object()            # non-None → fetch path
    editor._src_ind_cb.setChecked(True)
    # Run the worker synchronously; its _call_main.emit runs the GUI callback in-thread.
    editor._load_indicators_worker(editor._dhis2_client, "")
    assert editor._indicators_loaded is True
    by_uid = {d["uid"]: d for d in editor._current_de_items}
    assert "lz0000001" in by_uid, "lazily-fetched indicator missing from items"


def test_open_chart_autoselects_type_from_plugin_id(editor):
    """REQ-CE-OPEN-01: opening a saved chart that has only plugin_id (no template_id) still
    auto-selects the chart-type tile (template id == plugin id)."""
    editor.load_metadata(_META)
    chart = {"name": "Prog indicator card", "plugin_id": "bar",
             "metrics": [{"uid": "pi00000001", "name": "Malaria incidence",
                          "type": "indicator", "agg": "SUM"}],
             "dimensions": {}, "plugin_options": {},
             "source": {"type": "indicator"}}
    editor._load_chart_config(chart)
    assert editor._selected_template is not None, "chart type not selected"
    assert editor._selected_template.get("id") == "bar"


def test_restore_indicator_metric_before_load(editor):
    """REQ-CE-RESTORE-IND-02: opening a saved chart whose metric is an aggregate indicator
    restores the metric even though indicators load on demand (not yet in the list)."""
    _select_bar(editor)
    editor.load_metadata({"data_elements": [], "indicators": [],
                          "programs": [], "program_indicators": []})
    # Saved with name == alias and the real name in orig_name (how the editor saves aliases).
    chart = {"metrics": [{"uid": "indX", "name": "cases tested", "alias": "cases tested",
                          "orig_name": "MAL T: Cases tested",
                          "type": "indicator", "agg": "SUM"}],
             "dimensions": {}}
    editor._restore_selection(chart)
    sel = editor._metrics_picker.get_selected_des()
    m = next((s for s in sel if s["uid"] == "indX"), None)
    assert m is not None, "indicator metric not restored before load"
    # Chip shows the REAL name, alias kept separately (not the alias masquerading as name).
    assert m["name"] == "MAL T: Cases tested", m
    assert m.get("alias") == "cases tested"


def test_kind_filter_de_pa_pi(editor):
    """REQ-CE-KIND-01: the DE/PA/PI checkboxes filter the item list independently."""
    _select_bar(editor)
    _load_malaria(editor)
    kinds = lambda: {d.get("kind") for d in editor._current_de_items}
    assert {"DE", "PA", "PI"} <= kinds()                   # all shown by default
    editor._kind_cbs["PI"].setChecked(False)
    assert "PI" not in kinds() and "DE" in kinds()         # PI hidden
    editor._kind_cbs["DE"].setChecked(False)
    editor._kind_cbs["PA"].setChecked(False)               # only PI re-enabled below
    editor._kind_cbs["PI"].setChecked(True)
    assert kinds() == {"PI"}, kinds()


def test_worker_result_marshals_to_gui_thread(editor, qtbot):
    """REQ-AI-THREAD-01: worker threads must return results via the _call_main signal —
    QTimer.singleShot does NOT cross threads (no Qt event loop in a plain thread), which
    previously left the 'Generate from image' button stuck on '⏳ Generating…' forever."""
    import threading
    got = []
    threading.Thread(target=lambda: editor._call_main.emit(lambda: got.append(42)),
                     daemon=True).start()
    qtbot.waitUntil(lambda: got == [42], timeout=2000)
    assert got == [42]
