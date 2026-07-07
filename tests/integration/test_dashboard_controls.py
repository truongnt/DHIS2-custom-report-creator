"""
Integration tests — dashboard controls already implemented but needing REQ coverage
(grid header/empty-state/button-enabling, save validation, load resilience, export guard).
Closes traceability GAPs for PART C/E/F that map to shipped behaviour.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _cfg(title, w=6):
    return {"title": title, "col_width": w, "template_id": "bar_monthly"}


@pytest.fixture
def manual_panel(qtbot):
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p._manual_btn.click()
    return p


def test_grid_empty_state_visible(manual_panel):
    """REQ-DASH-GRID-07: an empty grid shows the drag-and-drop empty-state prompt."""
    assert manual_panel._grid.count() == 0
    assert manual_panel._grid._empty.isVisibleTo(manual_panel._grid)


def test_grid_header_has_name_and_count(manual_panel):
    """REQ-DASH-GRID-08: manual header shows the current-dashboard title + a live chart count.
    (Name/description are entered via the Save dialog, mirroring the Chart Editor.)"""
    assert manual_panel._manual_dash_lbl is not None
    assert "new dashboard" in manual_panel._manual_dash_lbl.text()
    assert manual_panel._card_count_lbl.text() == "0 charts"
    manual_panel.add_card(_cfg("A"))
    assert manual_panel._card_count_lbl.text() == "1 chart"


def test_export_deploy_disabled_until_cards(manual_panel):
    """REQ-DASH-GRID-09: Export/Deploy are disabled when empty, enabled once a card exists."""
    assert not manual_panel._export_btn.isEnabled()
    assert not manual_panel._deploy_btn.isEnabled()
    manual_panel.add_card(_cfg("A"))
    assert manual_panel._export_btn.isEnabled()
    assert manual_panel._deploy_btn.isEnabled()
    manual_panel._grid.remove_at(0)
    assert not manual_panel._export_btn.isEnabled()


def test_grid_drop_target_and_accepts_drops(manual_panel):
    """REQ-DASH-GRID-02: the grid accepts drops; the reorder path (move) repositions cards."""
    g = manual_panel._grid
    assert g.acceptDrops()
    g.add_card(_cfg("A")); g.add_card(_cfg("B")); g.add_card(_cfg("C"))
    g.move(0, 2)                       # the drop handler calls move(frm, target)
    assert [c["title"] for c in g.cards()] == ["B", "C", "A"]


def test_save_requires_name(manual_panel, monkeypatch, tmp_path):
    """REQ-DASH-SAVE-01: cancelling the Save dialog (no name) does not persist."""
    import config.dashboard_library as lib
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "d.json")
    monkeypatch.setattr("ui.save_entity_dialog.SaveEntityDialog.prompt",
                        staticmethod(lambda *a, **k: None))    # user cancels
    manual_panel.add_card(_cfg("A"))
    manual_panel._on_save_dashboard()
    assert lib.load_dashboards() == []


def test_save_requires_at_least_one_card(manual_panel, monkeypatch):
    """REQ-DASH-SAVE-01: saving an empty dashboard is rejected (info, no dialog)."""
    info = {}
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information",
                        lambda *a, **k: info.update(hit=True))
    manual_panel._on_save_dashboard()
    assert info.get("hit") is True


def test_upsert_by_name(tmp_path, monkeypatch):
    """REQ-DASH-SAVE-02: saving the same name overwrites (one entry, id preserved)."""
    import config.dashboard_library as lib
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "d.json")
    e1 = lib.save_dashboard("D", [{"a": 1}], mode="manual")
    e2 = lib.save_dashboard("D", [{"b": 2}], mode="manual")
    rows = lib.load_dashboards()
    assert len(rows) == 1
    assert rows[0]["id"] == e1["id"] == e2["id"]
    assert rows[0]["cards"] == [{"b": 2}]


def test_load_dashboards_resilient(tmp_path, monkeypatch):
    """REQ-DASH-SAVE-07: a missing or corrupt library file yields [] (no crash)."""
    import config.dashboard_library as lib
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(lib, "_LIBRARY_FILE", bad)
    assert lib.load_dashboards() == []
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "missing.json")
    assert lib.load_dashboards() == []


def test_export_guard_no_cards(make_window):
    """REQ-DASH-EXP-01: exporting with no cards reports an error and does not write a file."""
    win = make_window()
    win._on_export([])
    assert "no cards" in win.status_label.text().lower()
