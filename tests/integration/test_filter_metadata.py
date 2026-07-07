"""
Integration tests for the Filter / Metadata config + Description editor —
see docs/METADATA_FILTER_REQUIREMENTS.md.

Drives the real FilterConfigDialog / MetadataEditorDialog and the AppWindow metadata
load flow via pytest-qt, with network mocked.
"""
from contextlib import ExitStack
from unittest.mock import patch, MagicMock

import pytest
from PySide6.QtWidgets import QTabWidget

pytestmark = pytest.mark.integration

OPTS = {
    "programs": [
        {"id": "prog0000001", "displayName": "Malaria", "type": "Tracker"},
        {"id": "prog0000002", "displayName": "TB", "type": "Event"},
    ],
    "datasets": [
        {"id": "ds00000001", "displayName": "Monthly DS", "periodType": "Monthly"},
    ],
    "de_groups": [{"id": "deg0000001", "displayName": "Cases", "count": 5}],
}


def _dialog(qtbot, cfg=None):
    from ui.filter_config_dialog import FilterConfigDialog
    dlg = FilterConfigDialog(None, OPTS, cfg or {})
    qtbot.addWidget(dlg)
    return dlg


# ─── Filter dialog: scope (Tầng 1) ───────────────────────────────────────────

def test_scope_panels_built(qtbot):
    """REQ-FILTER-03: Programs and Datasets panels render a checkbox per item."""
    dlg = _dialog(qtbot)
    assert set(dlg._prg_cbs) == {"prog0000001", "prog0000002"}
    assert set(dlg._ds_cbs) == {"ds00000001"}


def test_select_all_none(qtbot):
    """REQ-FILTER-04: All/None toggles every checkbox in a panel."""
    dlg = _dialog(qtbot)
    dlg._select_all(dlg._prg_cbs, True)
    assert all(cb.isChecked() for cb in dlg._prg_cbs.values())
    dlg._select_all(dlg._prg_cbs, False)
    assert not any(cb.isChecked() for cb in dlg._prg_cbs.values())


def test_summary_updates(qtbot):
    """REQ-FILTER-05: summary warns when empty, shows scope when something is picked."""
    dlg = _dialog(qtbot)
    assert "⚠" in dlg._summary_lbl.text()                 # nothing selected
    dlg._prg_cbs["prog0000001"].setChecked(True)
    assert "Scope: 1 program" in dlg._summary_lbl.text()


def test_clear_all(qtbot):
    """REQ-FILTER-06: Clear All unchecks every scope checkbox."""
    dlg = _dialog(qtbot)
    dlg._prg_cbs["prog0000001"].setChecked(True)
    dlg._ds_cbs["ds00000001"].setChecked(True)
    dlg._clear_all()
    assert not any(cb.isChecked() for cb in dlg._prg_cbs.values())
    assert not any(cb.isChecked() for cb in dlg._ds_cbs.values())


def test_apply_and_cancel(qtbot):
    """REQ-FILTER-06: Apply returns the scope selection; Cancel returns None."""
    dlg = _dialog(qtbot)
    dlg._prg_cbs["prog0000001"].setChecked(True)
    dlg._on_apply()
    assert dlg.result["program_ids"] == ["prog0000001"]
    dlg2 = _dialog(qtbot)
    dlg2._on_cancel()
    assert dlg2.result is None


def test_restore_selection(qtbot):
    """REQ-FILTER-07: opening with an existing filter_cfg restores the checkboxes."""
    dlg = _dialog(qtbot, cfg={"program_ids": ["prog0000002"], "dataset_ids": ["ds00000001"]})
    assert dlg._prg_cbs["prog0000002"].isChecked()
    assert dlg._ds_cbs["ds00000001"].isChecked()
    assert not dlg._prg_cbs["prog0000001"].isChecked()


def test_no_refine_tier(qtbot):
    """REQ-FILTER-08: Tầng 2 (DE groups + keyword) removed; result is scope-only."""
    dlg = _dialog(qtbot)
    assert not hasattr(dlg, "_de_cbs")
    assert not hasattr(dlg, "_de_name_entry")
    assert dlg.findChild(QTabWidget) is None              # no refine tabs
    dlg._on_apply()
    assert set(dlg.result) == {"program_ids", "dataset_ids", "domain_type"}


# ─── Metadata load flow (AppWindow) ──────────────────────────────────────────

def test_open_filter_requires_client(make_window):
    """REQ-FILTER-01: filter config refuses to open before connecting."""
    win = make_window()
    win._client = None
    win._on_open_filter_config()
    assert "connect" in win.status_label.text().lower()


def test_open_filter_applies_and_loads(make_window):
    """REQ-FILTER-02 / REQ-METALOAD-01: Apply stores filter_cfg and starts a load thread."""
    win = make_window()
    win._client = MagicMock()
    win._filter_options = OPTS
    fake_dlg = MagicMock()
    fake_dlg.exec.return_value = 1
    fake_dlg.result = {"program_ids": ["prog0000001"], "dataset_ids": [], "domain_type": "AGGREGATE"}
    with patch("ui.filter_config_dialog.FilterConfigDialog", return_value=fake_dlg), \
         patch("ui.app_window.threading.Thread") as mock_thread:
        win._on_open_filter_config()
        assert win._filter_cfg["program_ids"] == ["prog0000001"]
        assert mock_thread.called
        # Loading state now shows in the Metadata Library's filter summary.
        assert "Loading" in win._metadata_editor._filter_summary.text()


def test_load_metadata_worker_fetches_and_caches(make_window):
    """REQ-METALOAD-01/02/03: worker calls fetch_all with the filter and caches the result."""
    win = make_window()
    win._client = MagicMock()
    win._filter_cfg = {"program_ids": ["prog0000001"], "domain_type": "AGGREGATE"}
    win.url_entry.setText("https://hmis.gov.la/hmis")
    meta = {"indicators": [], "program_indicators": [], "data_elements": [],
            "programs": [], "_filter_config": win._filter_cfg}
    fetch_all = MagicMock(return_value=meta)
    with ExitStack() as es:
        es.enter_context(patch("dhis2.metadata.fetch_all", fetch_all))
        es.enter_context(patch("dhis2.cache.save"))
        es.enter_context(patch("dhis2.cache.save_filter_cfg"))
        es.enter_context(patch.object(win._viz_panel, "load_metadata"))
        win._load_metadata_worker()
    assert fetch_all.call_args[0][1] == win._filter_cfg     # fetched with the filter cfg
    assert win._metadata is meta


def test_metadata_loaded_pushes_to_editor(make_window):
    """REQ-METALOAD-04: after load, metadata is pushed to the chart editor and labelled fresh."""
    win = make_window()
    win._metadata = {"data_elements": [], "programs": []}
    with patch.object(win._viz_panel, "load_metadata") as mock_load:
        win._on_metadata_loaded(0)
        mock_load.assert_called_once()
    assert "fresh" in win.cache_lbl.text().lower()


# ─── Description editor (MetadataEditorPanel) ────────────────────────────────

META = {
    "indicators":                  [{"id": "ind00000001", "displayName": "Incidence"}],
    "program_indicators":          [{"id": "pi000000001", "displayName": "PI A"}],
    "data_elements":               [{"id": "de000000001", "displayName": "Cases"}],
    "program_stage_data_elements": [{"id": "de000000002", "displayName": "Stage DE"}],
    "tracked_entity_attributes":   [{"id": "tea00000001", "displayName": "Age"}],
}
BASE = "https://hmis.gov.la/hmis"


def _editor(qtbot, descriptions=None, show_all=True):
    from ui.metadata_editor_panel import MetadataEditorPanel
    panel = MetadataEditorPanel()
    qtbot.addWidget(panel)
    panel.set_context(BASE, META, descriptions or {})
    if show_all:                       # type filters start unchecked; most tests want items shown
        for cb in panel._filter_cbs.values():
            cb.setChecked(True)
    return panel


def test_editor_flattens_all_kinds(qtbot):
    """REQ-DESC-UI-03: all five metadata kinds appear in one flat list."""
    dlg = _editor(qtbot)
    assert len(dlg._items) == 5
    kinds = {it["kind"] for it in dlg._items}
    assert kinds == {"Indicator", "Program Indicator", "Data Element",
                     "Tracker DE", "Tracked Attribute"}


def test_editor_search_filters(qtbot):
    """REQ-DESC-UI-04: search narrows the Available list by name/UID."""
    dlg = _editor(qtbot)
    dlg._search.setText("Cases")
    assert dlg._avail_model.rowCount() == 1


def test_editor_marks_described(qtbot):
    """REQ-DESC-UI-05: items with a description are marked (✓) in the list."""
    dlg = _editor(qtbot, descriptions={"de000000001": "Confirmed malaria cases"})
    labels = [dlg._avail_model.item(r).text() for r in range(dlg._avail_model.rowCount())]
    assert any(l.startswith("✓") for l in labels)


def test_editor_save_single(qtbot):
    """REQ-DESC-UI-08 / REQ-DESC-UI-10: Save persists one description locally."""
    dlg = _editor(qtbot)
    dlg._current_uid = "de000000001"
    dlg._desc_edit.setPlainText("Confirmed cases")
    with patch("config.descriptions.save_description") as mock_save:
        dlg._save_current()
        mock_save.assert_called_once_with(BASE, "de000000001", "Confirmed cases")


def test_editor_ok_bulk_saves(qtbot):
    """REQ-DESC-UI-08/09: OK bulk-saves pending edits and get_descriptions reflects them."""
    dlg = _editor(qtbot)
    dlg._current_uid = "de000000001"
    dlg._desc_edit.setPlainText("desc A")
    dlg._on_desc_changed()                                  # REQ-DESC-UI-07: held in pending
    assert dlg._pending.get("de000000001") == "desc A"
    with patch("config.descriptions.save_descriptions_bulk") as mock_bulk:
        dlg.flush_pending()
        mock_bulk.assert_called_once()
    assert dlg.get_descriptions().get("de000000001") == "desc A"


# ─── Filter dialog UI (visual + contrast) ────────────────────────────────────

def _contrast(fg, bg):
    def lum(h):
        h = h.lstrip("#"); rgb = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = (f(c) for c in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    a, b = sorted((lum(fg), lum(bg)))
    return (b + 0.05) / (a + 0.05)


_FILTER_PAIRS = [
    ("section header", "#ffffff", "#1a3a52", 4.5),
    ("summary warning", "#a85600", "#ffffff", 4.5),   # REQ-UI fix (was #e67e22)
    ("summary scope",   "#1a6fa8", "#ffffff", 4.5),
    ("apply button",    "#ffffff", "#1a6fa8", 4.5),
    ("cancel text",     "#4a6278", "#f0f4f8", 4.5),
    ("col3 label",      "#5a7286", "#ffffff", 4.5),   # REQ-UI fix (was #8aa3b8)
]


def test_filter_contrast_aa():
    """REQ-UI-COLOR-01/04: filter dialog text/bg pairs meet WCAG AA."""
    bad = [f"{n}: {fg}/{bg}={_contrast(fg, bg):.2f}<{m}"
           for n, fg, bg, m in _FILTER_PAIRS if _contrast(fg, bg) < m]
    assert not bad, "Contrast below AA:\n" + "\n".join(bad)


def test_filter_dialog_renders_screenshot(qtbot, evidence_dir):
    """REQ-UI-LAYOUT-01/03: filter dialog renders to a non-empty image (evidence)."""
    dlg = _dialog(qtbot, cfg={"program_ids": ["prog0000001"]})
    dlg.resize(1000, 700)
    pix = dlg.grab()
    assert not pix.isNull() and pix.width() > 0 and pix.height() > 0
    out = evidence_dir / "filter_dialog.png"
    pix.save(str(out))
    assert out.exists() and out.stat().st_size > 0


def test_metadata_editor_requires_connect(make_window):
    """REQ-DESC-UI-01/02: Metadata Editor is gated until metadata is loaded (local AI context)."""
    win = make_window()
    win._metadata = None
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        win._open_metadata_editor()
        assert mock_info.called


def test_editor_select_shows_detail(qtbot):
    """REQ-DESC-UI-06: selecting an item populates the detail pane and enables editing."""
    dlg = _editor(qtbot)
    dlg._avail_view.setCurrentIndex(dlg._avail_model.index(0, 0))
    assert dlg._detail_name.text()
    assert dlg._desc_edit.isEnabled()
    assert "UID:" in dlg._detail_meta.text()


def test_editor_pending_preserved_on_switch(qtbot):
    """REQ-DESC-UI-07: an unsaved edit survives switching to another item and back."""
    dlg = _editor(qtbot)
    dlg._avail_view.setCurrentIndex(dlg._avail_model.index(0, 0))   # item A
    uid_a = dlg._current_uid
    dlg._desc_edit.setPlainText("draft for A")
    dlg._avail_view.setCurrentIndex(dlg._avail_model.index(1, 0))   # item B
    assert dlg._current_uid != uid_a
    dlg._avail_view.setCurrentIndex(dlg._avail_model.index(0, 0))   # back to A
    assert dlg._desc_edit.toPlainText() == "draft for A"


def test_filter_dialog_fits_screen(qtbot):
    """REQ-UI-LAYOUT-07: dialog fits the screen and the Apply button is never clipped."""
    dlg = _dialog(qtbot)
    assert dlg.minimumHeight() <= 700                      # fits a laptop screen
    dlg.resize(dlg.minimumSize())
    dlg.show()
    qtbot.waitExposed(dlg)
    assert dlg.apply_btn.isVisible()
    bottom = dlg.apply_btn.mapTo(dlg, dlg.apply_btn.rect().bottomLeft()).y()
    assert bottom <= dlg.height() + 1                      # action bar within viewport
    dlg.close()


def test_metadata_editor_list_text_readable(qtbot):
    """REQ-UI-COLOR-05: list items set an explicit dark text colour (not bg-on-bg)."""
    dlg = _editor(qtbot)
    style = dlg._avail_view.styleSheet()
    assert "color: #1e2d3d" in style
    assert _contrast("#1e2d3d", "#f7f9fc") >= 4.5          # text vs PANEL_BG


def test_metadata_editor_opens_as_panel(make_window):
    """REQ-DESC-UI-01: Metadata Editor opens as an embedded right panel (index 3), not a popup."""
    win = make_window()
    win._metadata = META
    win._client = MagicMock()
    win._client.base_url = BASE
    win._open_metadata_editor()
    assert win._content.currentIndex() == 3
    assert win._active_panel == "metadata_editor"
    assert win._content.currentWidget() is win._metadata_editor


def test_metadata_editor_flush_on_leave(make_window):
    """REQ-DESC-UI-08: navigating away from the editor flushes unsaved descriptions."""
    win = make_window()
    win._metadata = META
    win._client = MagicMock()
    win._client.base_url = BASE
    win._open_metadata_editor()
    panel = win._metadata_editor
    panel._current_uid = "de000000001"
    panel._desc_edit.setPlainText("edited on leave")
    with patch("config.descriptions.save_descriptions_bulk") as mock_bulk:
        win._show_panel("chart_editor")
        mock_bulk.assert_called_once()
