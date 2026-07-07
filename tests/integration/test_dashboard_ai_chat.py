"""
Integration tests — AI chat workspace (PART D of docs/DASHBOARD_REQUIREMENTS.md).

Drives the real DashboardBuilderPanel chat in mock mode (no AI client, offline).
Each behavioural test that produces a visible state saves a screenshot to
test-evidence/<ts>/ per docs/TESTING_PROCESS.md.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QPushButton

pytestmark = pytest.mark.integration

# Metadata so build_context.de_list is non-empty → mock placeholders resolve.
_META = {"indicators": [
    {"id": "uidAAAAAAAA", "displayName": "Malaria Cases"},
    {"id": "uidBBBBBBBB", "displayName": "Test Positivity"},
]}


@pytest.fixture
def ai_panel(qtbot):
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p.resize(900, 700)
    p.set_context(metadata=_META, descriptions={})
    p._ai_btn.click()                      # enter AI chat workspace
    p.show()
    qtbot.waitExposed(p)
    return p


def _shot(widget, evidence_dir, name):
    pix = widget.grab()
    assert not pix.isNull() and pix.width() > 0 and pix.height() > 0
    out = evidence_dir / f"{name}.png"
    pix.save(str(out))
    assert out.exists() and out.stat().st_size > 0
    return out


def test_presets_seed_input(ai_panel):
    """REQ-DASH-AI-02: choosing a quick-start preset fills the chat input."""
    ai_panel._preset_combo.setCurrentIndex(1)      # "Malaria overview"
    assert ai_panel._chat_input.text() != ""
    assert "malaria" in ai_panel._chat_input.text().lower()


def test_send_renders_suggestions(ai_panel, qtbot, evidence_dir):
    """REQ-DASH-AI-03/05: sending a message runs the planner off-thread and shows suggestion cards."""
    ai_panel._chat_input.setText("monthly malaria cases and a district map")
    ai_panel._on_chat_send()
    qtbot.waitUntil(lambda: len(ai_panel._suggestion_cards) > 0, timeout=5000)
    # At least one '+ Add' button rendered
    add_btns = [b for h in ai_panel._suggestion_cards
                for b in h.findChildren(QPushButton) if "Add" in b.text()]
    assert add_btns, "no suggestion '+ Add' buttons rendered"
    _shot(ai_panel, evidence_dir, "dash_D_ai_suggestions")


def test_add_suggestion_marks_ai_and_adds_card(ai_panel, qtbot, evidence_dir):
    """REQ-DASH-AI-06/13: adding a suggestion appends a card tagged mode='ai' and shows a chip."""
    ai_panel._chat_input.setText("monthly malaria cases")
    ai_panel._on_chat_send()
    qtbot.waitUntil(lambda: len(ai_panel._suggestion_cards) > 0, timeout=5000)

    cfg0 = ai_panel._last_suggestion_configs[0]
    ai_panel._ai_add_card(dict(cfg0))

    cards = ai_panel.get_cards()
    assert len(cards) == 1
    assert cards[0]["mode"] == "ai"                # REQ-DASH-AI-13
    assert ai_panel._ai_cards_bar.isVisible()      # added-charts strip shown
    assert ai_panel._ai_export_btn.isEnabled()
    _shot(ai_panel, evidence_dir, "dash_D_ai_added_card")


def test_remove_ai_card(ai_panel, qtbot):
    """REQ-DASH-AI-06: a user can remove an added AI card; controls disable when empty."""
    ai_panel._chat_input.setText("monthly malaria cases")
    ai_panel._on_chat_send()
    qtbot.waitUntil(lambda: len(ai_panel._suggestion_cards) > 0, timeout=5000)

    cfg = dict(ai_panel._last_suggestion_configs[0])
    ai_panel._ai_add_card(cfg)
    assert len(ai_panel.get_cards()) == 1
    ai_panel._ai_remove_card(cfg)
    assert ai_panel.get_cards() == []
    assert not ai_panel._ai_export_btn.isEnabled()


def test_no_suggestions_when_no_metadata(qtbot):
    """REQ-DASH-AI-05: with no resolvable data elements the chat reports no matches (no crash)."""
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p.set_context(metadata={}, descriptions={})
    p._ai_btn.click()
    p._chat_input.setText("anything")
    p._on_chat_send()
    qtbot.waitUntil(lambda: p._chat_worker is not None and p._chat_worker.isFinished(),
                    timeout=5000)
    qtbot.wait(80)                      # let the queued finished-signal slot run
    assert p.get_cards() == []
    assert p._chat_send_btn.isEnabled()
    assert len(p._suggestion_cards) == 0


def test_ai_mode_has_dashboard_title_label(ai_panel):
    """REQ-DASH-AI footer: the AI workspace shows the current dashboard title (name +
    description are entered via the Save dialog, mirroring the Chart Editor)."""
    assert ai_panel._ai_dash_lbl is not None
    assert "new dashboard" in ai_panel._ai_dash_lbl.text()


def test_mock_key_from_intent(ai_panel):
    """REQ-DASH-AI-07: with no AI client the chat picks a mock scenario from intent keywords."""
    assert ai_panel._mock_key_for("supply chain stock levels") == "supply_chain"
    assert ai_panel._mock_key_for("performance compare indicators") == "performance_review"
    assert ai_panel._mock_key_for("monthly malaria cases") == "malaria_overview"


def test_defaults_to_mock_haiku(ai_panel, qtbot):
    """REQ-DASH-AI-08: no AI client → mock mode; default model is Haiku."""
    assert ai_panel._ai_client is None
    assert ai_panel._ai_model == "claude-haiku-4-5-20251001"
    ai_panel._chat_input.setText("monthly malaria cases")
    ai_panel._on_chat_send()
    assert ai_panel._chat_worker._mock_key is not None      # mock, not a live call
    ai_panel._chat_worker.wait(3000)
