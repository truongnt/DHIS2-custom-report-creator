"""
Integration tests closing remaining traceability GAPs for shipped behaviour:
library panel (PART B), data model (PART H), AI chat history/refine (PART D),
and the deploy guard (PART G).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration

_META = {"indicators": [
    {"id": "uidAAAAAAAA", "displayName": "Malaria Cases"},
    {"id": "uidBBBBBBBB", "displayName": "Test Positivity"},
]}


def _cfg(title, w=6):
    return {"title": title, "col_width": w, "template_id": "bar_monthly"}


# ── PART B: Chart library ──────────────────────────────────────────────────────

def test_library_lists_saved_charts(qtbot):
    """REQ-DASH-LIB-01: the library lists saved charts from chart_library.load_charts()."""
    charts = [{"id": "1", "name": "Bar A", "template_label": "Bar"},
              {"id": "2", "name": "Line B", "template_label": "Line"}]
    with patch("config.chart_library.load_charts", return_value=charts):
        from ui.dashboard_builder_panel import DashboardBuilderPanel
        p = DashboardBuilderPanel(None, {})
        qtbot.addWidget(p)
        p.refresh_library()
        # cards + trailing stretch
        assert p._lib_layout.count() >= len(charts) + 1


def test_library_empty_placeholder(qtbot):
    """REQ-DASH-LIB-06: an empty library shows a 'no saved charts' placeholder."""
    with patch("config.chart_library.load_charts", return_value=[]):
        from ui.dashboard_builder_panel import DashboardBuilderPanel
        p = DashboardBuilderPanel(None, {})
        qtbot.addWidget(p)
        p.refresh_library()
        from PySide6.QtWidgets import QLabel
        texts = " ".join(w.text() for w in p._lib_container.findChildren(QLabel))
        assert "No saved charts" in texts


def test_library_delete_calls_backend(qtbot, monkeypatch):
    """REQ-DASH-LIB-05: deleting a library chart (confirmed) calls delete_chart(id)."""
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    deleted = {}
    monkeypatch.setattr("config.chart_library.delete_chart",
                        lambda cid: deleted.update(id=cid))
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    p._delete_library_chart({"id": "xyz", "name": "C"})
    assert deleted.get("id") == "xyz"


# ── PART H: Data model ──────────────────────────────────────────────────────────

def test_ai_card_model_fields(qtbot):
    """REQ-DASH-MODEL-01: AI cards carry _ai_generated/_ai_rationale and mode='ai'."""
    from llm.ai_dashboard_planner import recs_to_chart_configs
    de_list = [{"uid": "u1", "name": "Cases", "kind": "indicator"}]
    recs = [{"title": "T", "chart_type": "bar_monthly", "de_uid": "u1", "rationale": "why"}]
    cfg = recs_to_chart_configs(recs, de_list)[0]
    assert cfg["_ai_generated"] is True and cfg["_ai_rationale"] == "why"
    assert cfg["template_id"] == "bar_monthly" and cfg["metrics"][0]["uid"] == "u1"


def test_dashboard_entry_model(tmp_path, monkeypatch):
    """REQ-DASH-MODEL-02: a saved entry has id/name/mode/cards/created_at/updated_at."""
    import config.dashboard_library as lib
    monkeypatch.setattr(lib, "_LIBRARY_FILE", tmp_path / "d.json")
    e = lib.save_dashboard("D", [_cfg("A")], mode="manual")
    for key in ("id", "name", "mode", "cards", "created_at", "updated_at"):
        assert key in e


# ── PART D: chat history + refine ───────────────────────────────────────────────

def test_chat_history_grows(qtbot):
    """REQ-DASH-AI-01: the conversation keeps a multi-turn history (user bubbles persist)."""
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p.set_context(metadata=_META, descriptions={})
    p._ai_btn.click()
    before = p._chat_layout.count()
    p._add_chat_message("user", "first")
    p._add_chat_message("user", "second")
    assert p._chat_layout.count() == before + 2


def test_chat_refine_includes_current_state(qtbot):
    """REQ-DASH-AI-04: a follow-up turn passes the current dashboard as context."""
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p.set_context(metadata=_META, descriptions={})
    p._ai_btn.click()
    p._ai_add_card(_cfg("Existing Chart"))
    p._chat_input.setText("add a map")
    p._on_chat_send()
    assert p._chat_worker is not None
    assert "Existing Chart" in p._chat_worker._intent
    p._chat_worker.wait(3000)          # let the thread finish cleanly


def test_library_search_filters(qtbot):
    """REQ-DASH-LIB-03: the library search box filters cards by name."""
    charts = [{"id": "1", "name": "Malaria bar", "template_label": "Bar"},
              {"id": "2", "name": "Stock line", "template_label": "Line"}]
    with patch("config.chart_library.load_charts", return_value=charts):
        from ui.dashboard_builder_panel import DashboardBuilderPanel
        from PySide6.QtWidgets import QLabel
        p = DashboardBuilderPanel(None, {})
        qtbot.addWidget(p)
        p._lib_search.setText("malaria")
        qtbot.wait(50)        # let deleteLater() drop the unfiltered cards
        names = " ".join(w.text() for w in p._lib_container.findChildren(QLabel))
        assert "Malaria bar" in names and "Stock line" not in names


def test_library_drop_adds_to_grid(qtbot):
    """REQ-DASH-LIB-04 / REQ-DASH-GRID-02: dropping a library chart id onto the grid adds it."""
    charts = [{"id": "abc", "name": "Dropped chart", "template_id": "bar", "col_width": 6}]
    with patch("config.chart_library.load_charts", return_value=charts):
        from ui.dashboard_builder_panel import DashboardBuilderPanel
        p = DashboardBuilderPanel(None, {})
        qtbot.addWidget(p)
        p._manual_btn.click()
        # Simulate the grid's external_drop signal (what dropEvent emits)
        p._grid.external_drop.emit("abc")
        assert [c["title"] if "title" in c else c["name"] for c in p.get_cards()] == ["Dropped chart"]
        assert p._grid.count() == 1


def test_load_dialog_lists_and_deletes(qtbot, monkeypatch):
    """REQ-DASH-SAVE-04/06: the load dialog lists saved dashboards and can delete one."""
    from ui.load_dashboard_dialog import LoadDashboardDialog
    from PySide6.QtWidgets import QPushButton
    dashes = [{"id": "d1", "name": "Dash One", "cards": [1, 2], "updated_at": "2026-06-25T10:00:00"},
              {"id": "d2", "name": "Dash Two", "cards": [], "updated_at": "2026-06-24T10:00:00"}]
    dlg = LoadDashboardDialog(None, dashes)
    qtbot.addWidget(dlg)
    assert dlg._table.rowCount() == 2
    assert dlg._table.item(0, 0).text() == "Dash One"
    assert "2 charts" in dlg._table.item(0, 1).text()    # REQ-DASH-SAVE-04 description col

    deleted = {}
    monkeypatch.setattr("config.dashboard_library.delete_dashboard",
                        lambda did: deleted.update(id=did))
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    dlg._table.cellWidget(0, 4).findChild(QPushButton).click()   # row delete button
    assert deleted.get("id") == "d1"
    assert dlg._table.rowCount() == 1


# ── PART G: deploy guard ─────────────────────────────────────────────────────────

def test_deploy_requires_connection(make_window):
    """REQ-DASH-DEP-01: deploying without a DHIS2 connection reports an error."""
    win = make_window()
    win._client = None
    win._on_deploy_dashboard("Report", [_cfg("A")])
    assert "connect" in win.status_label.text().lower()
