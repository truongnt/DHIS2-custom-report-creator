"""Metadata Editor rework — type filter, dual-list transfer, local descriptions,
and the Chart Editor restricting metrics/dimensions to the in-use set (REQ-META-EDIT)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

URL = "https://hmis.gov.la/hmis"

_META = {
    "indicators":                  [{"id": "ind1", "displayName": "TPR"}],
    "program_indicators":          [{"id": "pi1", "displayName": "PI cases"}],
    "data_elements":               [{"id": "de1", "displayName": "Agg DE"}],
    "program_stage_data_elements": [{"id": "de2", "displayName": "Tracker DE"}],
    "tracked_entity_attributes":   [{"id": "pa1", "displayName": "Gender"}],
}


@pytest.fixture
def panel(qtbot, tmp_path, monkeypatch):
    import config.selection as selmod
    import config.descriptions as descmod
    monkeypatch.setattr(selmod, "_CACHE_ROOT", tmp_path)
    monkeypatch.setattr(descmod, "_CACHE_ROOT", tmp_path)
    from ui.metadata_editor_panel import MetadataEditorPanel
    p = MetadataEditorPanel(None)
    qtbot.addWidget(p)
    p.set_context(URL, _META, {})
    for cb in p._filter_cbs.values():   # tests below assume all types are shown
        cb.setChecked(True)
    return p


def test_default_type_filter_shows_nothing(qtbot, tmp_path, monkeypatch):
    """REQ-META-EDIT-01: type checkboxes start UNCHECKED — nothing shows until the user
    picks a type."""
    import config.selection as selmod
    import config.descriptions as descmod
    monkeypatch.setattr(selmod, "_CACHE_ROOT", tmp_path)
    monkeypatch.setattr(descmod, "_CACHE_ROOT", tmp_path)
    from ui.metadata_editor_panel import MetadataEditorPanel
    p = MetadataEditorPanel(None)
    qtbot.addWidget(p)
    p.set_context(URL, _META, {})
    assert all(not cb.isChecked() for cb in p._filter_cbs.values())
    assert p._avail_model.rowCount() == 0        # Available empty until a type is checked
    p._filter_cbs["DE"].setChecked(True)
    assert {p._avail_model.item(r).data(256) for r in range(p._avail_model.rowCount())} == {"de1", "de2"}


def _avail_uids(p):
    m = p._avail_model
    return {m.item(r).data(256) for r in range(m.rowCount())}   # Qt.UserRole == 256


def _inuse_uids(p):
    m = p._inuse_model
    return {m.item(r).data(256) for r in range(m.rowCount())}


def test_flatten_covers_all_four_types(panel):
    """REQ-META-EDIT-01: DE (incl. tracker DE), PA, I, PI all appear as available items."""
    assert _avail_uids(panel) == {"ind1", "pi1", "de1", "de2", "pa1"}
    assert set(panel._filter_cbs) == {"DE", "PA", "I", "PI"}


def test_type_filter_hides_unchecked_kinds(panel):
    """REQ-META-EDIT-01: unchecking PI/PA/I leaves only DE-kind items in Available."""
    for k in ("PA", "I", "PI"):
        panel._filter_cbs[k].setChecked(False)
    assert _avail_uids(panel) == {"de1", "de2"}    # Data Element + Tracker DE


def test_move_to_inuse_and_back(panel):
    """REQ-META-EDIT-02: items move Available→In use and back; get_selection reflects it."""
    panel._add_uids(["de1", "pi1"])
    assert panel.get_selection() == {"de1", "pi1"}
    assert _inuse_uids(panel) == {"de1", "pi1"}
    assert "de1" not in _avail_uids(panel)         # no longer available
    panel._remove_uids(["de1"])
    assert panel.get_selection() == {"pi1"}
    assert "de1" in _avail_uids(panel)


def test_move_all_respects_type_filter(panel):
    """REQ-META-EDIT-02: 'move all shown' only moves items passing the current type filter."""
    for k in ("PA", "I", "PI"):
        panel._filter_cbs[k].setChecked(False)     # only DE-kind shown
    panel._move_all_to_inuse()
    assert panel.get_selection() == {"de1", "de2"}


def test_selection_persists_and_reloads(panel, qtbot):
    """REQ-META-EDIT + REQ-META-SEL: flush saves selection; a fresh panel restores it."""
    panel._add_uids(["de1", "ind1"])
    panel.flush_pending()
    from ui.metadata_editor_panel import MetadataEditorPanel
    p2 = MetadataEditorPanel(None)
    qtbot.addWidget(p2)
    p2.set_context(URL, _META, {})
    assert p2.get_selection() == {"de1", "ind1"}
    for cb in p2._filter_cbs.values():   # show items to inspect the In-use list model
        cb.setChecked(True)
    assert _inuse_uids(p2) == {"de1", "ind1"}


def test_add_metadata_merges_indicators(panel):
    """REQ-META-EDIT-05: lazily-fetched indicators merge into Available without
    disturbing the current in-use selection."""
    panel._add_uids(["de1"])                       # curate something first
    panel.add_metadata({"indicators": [{"id": "lz1", "displayName": "Lazy Ind"}]})
    assert "lz1" in _avail_uids(panel)             # new indicator now selectable
    assert panel.get_selection() == {"de1"}        # selection untouched


def test_selection_persists_immediately_on_move(panel, tmp_path):
    """REQ-META-EDIT-02: a move is saved at once (survives closing without navigating away)."""
    panel._add_uids(["de1", "pa1"])
    from config.selection import load_selection
    assert load_selection(URL) == {"de1", "pa1"}   # already on disk, no flush needed
    panel._remove_uids(["de1"])
    assert load_selection(URL) == {"pa1"}


def test_inuse_filtered_by_type_but_still_saved(panel):
    """REQ-META-EDIT-02: the In-use list obeys the 'Show' type filter (like Available),
    but the full selection is still saved regardless of which types are shown."""
    panel._add_uids(["ind1", "pi1"])
    panel._filter_cbs["PI"].setChecked(False)            # hide PI
    assert _inuse_uids(panel) == {"ind1"}                # only the shown (I) item displays
    assert panel.get_selection() == {"ind1", "pi1"}      # …but both remain selected/saved
    from config.selection import load_selection
    assert load_selection(URL) == {"ind1", "pi1"}        # persisted on disk too


def test_local_description_saves(panel):
    """REQ-META-EDIT-03: a local description is captured and returned by get_descriptions."""
    panel._show_detail(panel._by_uid["de1"])
    panel._desc_edit.setPlainText("Confirmed malaria cases")
    panel._save_current()
    assert panel.get_descriptions()["de1"] == "Confirmed malaria cases"


# ── REQ-META-EDIT-04: Chart Editor pulls metrics/dimensions only from in-use ──

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


def test_chart_editor_empty_when_no_selection(editor):
    """REQ-META-EDIT-04: empty in-use set → NO metrics offered + a 'configure' prompt shown."""
    editor.load_metadata({"data_elements": [{"id": "de1", "displayName": "A"},
                                            {"id": "de2", "displayName": "B"}]})
    editor._src_agg_cb.setChecked(True)
    editor.set_in_use(set())
    assert editor._current_de_items == []
    # The metrics picker prompts the user to configure the Metadata Library.
    assert "Metadata Library" in editor._metrics_picker._search.placeholderText()


def test_chart_editor_restricted_to_in_use(editor):
    """REQ-META-EDIT-04: with an in-use set, only those UIDs are offered as metrics."""
    editor.load_metadata({"data_elements": [{"id": "de1", "displayName": "A"},
                                            {"id": "de2", "displayName": "B"}]})
    editor._src_agg_cb.setChecked(True)
    editor.set_in_use({"de1"})
    uids = {d["uid"] for d in editor._current_de_items}
    assert uids == {"de1"}
