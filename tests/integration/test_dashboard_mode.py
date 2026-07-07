"""
Integration tests — Dashboard Builder mode selection (PART A of docs/DASHBOARD_REQUIREMENTS.md).

Drives the real DashboardBuilderPanel via pytest-qt (qtbot). Each UI test saves a
screenshot to test-evidence/<ts>/ as observable proof the required state actually
rendered — per docs/TESTING_PROCESS.md (no PASS without evidence).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def panel(qtbot):
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p.resize(1100, 720)
    p.show()
    qtbot.waitExposed(p)
    return p


def _shot(widget, evidence_dir, name: str):
    """Grab the widget to an image and persist it as evidence; assert non-empty."""
    pix = widget.grab()
    assert not pix.isNull(), f"{name}: grab returned null pixmap"
    assert pix.width() > 0 and pix.height() > 0, f"{name}: zero-size pixmap"
    out = evidence_dir / f"{name}.png"
    pix.save(str(out))
    assert out.exists() and out.stat().st_size > 0, f"{name}: screenshot not written"
    return out


def test_dashboard_starts_with_mode_chooser(panel, evidence_dir):
    """REQ-DASH-01: entering the dashboard builder shows a mode chooser with Manual + AI Chat."""
    assert panel.current_mode() is None
    assert panel._stack.currentWidget() is panel._chooser_page
    assert panel._manual_btn.isVisible()
    assert panel._ai_btn.isVisible()
    # Labels are correct (proves content even though headless font renders as tofu)
    assert "Manual" in panel._manual_btn.text()
    assert "AI Chat" in panel._ai_btn.text()
    _shot(panel, evidence_dir, "dash_A01_mode_chooser")


def test_choose_manual_switches_to_grid(panel, evidence_dir):
    """REQ-DASH-02: choosing Manual switches the UI to the manual (grid) workspace."""
    panel._manual_btn.click()
    assert panel.current_mode() == "manual"
    assert panel._stack.currentWidget() is panel._manual_page
    _shot(panel, evidence_dir, "dash_A02_manual_workspace")


def test_choose_ai_switches_to_chat(panel, evidence_dir):
    """REQ-DASH-02: choosing AI switches the UI to the chat workspace."""
    panel._ai_btn.click()
    assert panel.current_mode() == "ai"
    assert panel._stack.currentWidget() is panel._ai_page
    assert panel._chat_input is not None and panel._chat_input.isVisible()
    # Chat shell seeded with at least one assistant bubble (minus the trailing stretch)
    assert panel._chat_layout.count() - 1 >= 1
    _shot(panel, evidence_dir, "dash_A02_ai_workspace")


def test_change_mode_returns_to_chooser_when_empty(panel):
    """REQ-DASH-04: 'Change mode' returns to the chooser with no prompt when nothing is unsaved."""
    panel._manual_btn.click()
    assert panel.current_mode() == "manual"
    panel._on_change_mode()          # canvas empty → no confirmation dialog
    assert panel.current_mode() is None
    assert panel._stack.currentWidget() is panel._chooser_page


def test_chooser_embeds_load_dialog_inline(qtbot, monkeypatch, evidence_dir):
    """REQ-DASH-OPEN-01: the saved-dashboards picker (LoadDashboardDialog) is embedded inline
    on the chooser — no Open click — and lists saved dashboards."""
    entry = {"id": "d1", "name": "Malaria Overview", "mode": "manual",
             "cards": [{"title": "C1", "template_id": "bar_monthly", "col_width": 6}],
             "updated_at": "2026-06-30T10:00:00"}
    monkeypatch.setattr("config.dashboard_library.load_dashboards", lambda: [entry])
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    from ui.load_dashboard_dialog import LoadDashboardDialog
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p.resize(1100, 800)
    p._mount_embedded_load()
    # The embedded picker IS the reused LoadDashboardDialog, shown inline (a child widget).
    assert isinstance(p._embedded_load, LoadDashboardDialog)
    assert p._embedded_load.parent() is not None
    assert p._embedded_load._table.rowCount() == 1
    p.show(); qtbot.waitExposed(p)
    _shot(p, evidence_dir, "dash_open_existing_chooser")


def test_embedded_open_loads_dashboard(qtbot, monkeypatch):
    """REQ-DASH-OPEN-01: selecting a row in the embedded picker opens it into its mode."""
    entry = {"id": "d1", "name": "Malaria", "mode": "manual",
             "cards": [{"title": "C1", "template_id": "bar_monthly", "col_width": 6}]}
    monkeypatch.setattr("config.dashboard_library.load_dashboards", lambda: [entry])
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p._mount_embedded_load()
    p._embedded_load._table.selectRow(0)
    p._embedded_load._on_ok()                    # double-click / Open emits accepted → load
    assert p.current_mode() == "manual"
    assert p._stack.currentWidget() is p._manual_page
    assert len(p.get_cards()) == 1


def test_chooser_embedded_empty_hint(qtbot, monkeypatch):
    """REQ-DASH-OPEN-01: with no saved dashboards the inline picker shows a hint, not a table."""
    monkeypatch.setattr("config.dashboard_library.load_dashboards", lambda: [])
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p._mount_embedded_load()
    assert p._embedded_load is None


def test_save_records_mode(tmp_path, monkeypatch):
    """REQ-DASH-03 / REQ-DASH-SAVE-03: a saved dashboard records its creation mode."""
    import config.dashboard_library as lib
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "dash.json")
    entry = lib.save_dashboard("D-ai", [{"title": "c"}], mode="ai")
    assert entry["mode"] == "ai"
    loaded = lib.load_dashboards()
    assert loaded[0]["mode"] == "ai"


def test_save_defaults_mode_manual(tmp_path, monkeypatch):
    """REQ-DASH-SAVE-03: omitting mode defaults to 'manual' (back-compat with old callers)."""
    import config.dashboard_library as lib
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "dash.json")
    entry = lib.save_dashboard("D-default", [{"title": "c"}])
    assert entry["mode"] == "manual"


def test_callbacks_and_context(qtbot):
    """REQ-DASH-05: panel wires on_export/on_deploy callbacks and stores set_context()."""
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    captured = {}
    cbs = {
        "on_export": lambda cards, filters=None, **kw: captured.update(export=cards),
        "on_deploy": lambda name, cards, filters=None, **kw: captured.update(deploy=(name, cards)),
    }
    p = DashboardBuilderPanel(None, cbs)
    qtbot.addWidget(p)
    p.set_context(metadata={"indicators": []}, descriptions={"x": "d"}, base_url="http://h")
    assert p._metadata == {"indicators": []}
    assert p._descriptions == {"x": "d"}
    assert p._base_url == "http://h"

    p.add_card({"title": "C1"})
    p._on_export()
    assert len(captured["export"]) == 1
    assert captured["export"][0]["title"] == "C1"


def test_load_entry_opens_recorded_mode(panel, qtbot):
    """REQ-DASH-03: loading a saved dashboard reopens the workspace for its recorded mode."""
    entry = {"name": "Loaded", "mode": "manual",
             "cards": [{"title": "Chart A", "template_label": "Bar"}]}
    panel.load_dashboard_entry(entry)
    assert panel.current_mode() == "manual"
    assert panel._stack.currentWidget() is panel._manual_page
    assert len(panel.get_cards()) == 1
