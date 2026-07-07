"""
Integration tests — manual 12-column grid (PART C of docs/DASHBOARD_REQUIREMENTS.md).

Covers the GridCanvas layout model (auto-flow, reflow on resize/remove/reorder) and
its rendering, plus the panel wiring (manual add_card → grid). Screenshot evidence
proves cards render at varied column widths in the grid.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def grid(qtbot):
    from ui.dashboard_grid import GridCanvas
    g = GridCanvas()
    qtbot.addWidget(g)
    g.resize(800, 500)
    return g


def _cfg(title, w=6):
    return {"title": title, "col_width": w, "template_label": "Bar"}


def test_autoflow_layout_wraps_at_12(grid):
    """REQ-DASH-GRID-01: cards auto-flow left-to-right and wrap at 12 columns."""
    grid.add_card(_cfg("A", 6))
    grid.add_card(_cfg("B", 6))
    grid.add_card(_cfg("C", 6))      # 6+6=12 full → C wraps to row 1
    specs = grid.layout_specs()
    assert specs[0] == {"x": 0, "y": 0, "w": 6, "h": 1}
    assert specs[1] == {"x": 6, "y": 0, "w": 6, "h": 1}
    assert specs[2] == {"x": 0, "y": 1, "w": 6, "h": 1}


def test_set_width_reflows(grid):
    """REQ-DASH-GRID-03/04: widening a card reflows the ones after it."""
    grid.add_card(_cfg("A", 6))
    grid.add_card(_cfg("B", 6))
    grid.set_width(0, 8)             # A=8 → B (w6) no longer fits row0 → wraps
    specs = grid.layout_specs()
    assert specs[0] == {"x": 0, "y": 0, "w": 8, "h": 1}
    assert specs[1] == {"x": 0, "y": 1, "w": 6, "h": 1}


def test_width_clamped_1_to_12(grid):
    """REQ-DASH-GRID-03: column span stays within 1..12."""
    i = grid.add_card(_cfg("A", 6))
    grid.set_width(i, 99); assert grid.layout_specs()[0]["w"] == 12
    grid.set_width(i, 0);  assert grid.layout_specs()[0]["w"] == 1


def test_remove_reflows(grid):
    """REQ-DASH-GRID-05: removing a card reflows the rest and updates count."""
    grid.add_card(_cfg("A")); grid.add_card(_cfg("B")); grid.add_card(_cfg("C"))
    grid.remove_at(0)
    assert grid.count() == 2
    assert [c["title"] for c in grid.cards()] == ["B", "C"]


def test_move_reorders(grid):
    """REQ-DASH-GRID-04: reordering moves a card to a new index."""
    grid.add_card(_cfg("A")); grid.add_card(_cfg("B")); grid.add_card(_cfg("C"))
    grid.move(2, 0)
    assert [c["title"] for c in grid.cards()] == ["C", "A", "B"]


def test_cards_with_layout_merges_layout(grid):
    """REQ-DASH-GRID-10 / REQ-DASH-SAVE-03: persisted cards carry their grid layout."""
    grid.add_card(_cfg("A", 4))
    out = grid.cards_with_layout()
    assert out[0]["title"] == "A"
    assert out[0]["layout"] == {"x": 0, "y": 0, "w": 4, "h": 1}


def test_changed_signal_fires(grid, qtbot):
    """The grid emits `changed` on mutation (drives count + button enabling)."""
    with qtbot.waitSignal(grid.changed, timeout=1000):
        grid.add_card(_cfg("A"))


def test_grid_renders_cards_screenshot(qtbot, evidence_dir):
    """REQ-DASH-GRID-06: manual workspace renders cards in the grid at varied widths."""
    from ui.dashboard_builder_panel import DashboardBuilderPanel
    from ui.dashboard_grid import _GridCard
    p = DashboardBuilderPanel(None, {})
    qtbot.addWidget(p)
    p.resize(1100, 720)
    p._manual_btn.click()                        # enter manual workspace
    p.add_card(_cfg("Wide chart", 12))
    p.add_card(_cfg("Half A", 6))
    p.add_card(_cfg("Half B", 6))
    p.add_card(_cfg("Third", 4))
    p.show(); qtbot.waitExposed(p)

    cards = p._grid._host.findChildren(_GridCard)
    assert len(cards) == 4
    assert p.get_cards()[0]["title"] == "Wide chart"      # manual cards come from the grid
    assert p._card_count_lbl.text() == "4 charts"
    assert p._export_btn.isEnabled()

    pix = p.grab()
    out = evidence_dir / "dash_C_manual_grid.png"
    pix.save(str(out))
    assert out.exists() and out.stat().st_size > 0


def test_clear_empties_grid(grid):
    """REQ-DASH-GRID: clear removes all cards and shows the empty state."""
    grid.add_card(_cfg("A")); grid.add_card(_cfg("B"))
    grid.clear()
    assert grid.count() == 0
    assert grid.cards() == []


def test_pm_buttons_resize_card(grid, qtbot):
    """REQ-DASH-GRID-03: the ⊟/⊞ controls on a card change its column width."""
    grid.add_card(_cfg("A", 6))
    card = grid._items[0]["card"]
    assert card is not None
    grid.nudge_width_of(card, 3)
    assert grid.layout_specs()[0]["w"] == 9
    grid.nudge_width_of(card, -5)
    assert grid.layout_specs()[0]["w"] == 4


def test_card_has_edge_and_corner_grips(grid):
    """REQ-DASH-GRID-03: a card exposes width (↔), height (↕) and corner (↘) resize grips."""
    from PySide6.QtCore import Qt
    from ui.dashboard_grid import _EdgeGrip
    grid.add_card(_cfg("A"))
    grips = grid._items[0]["card"].findChildren(_EdgeGrip)
    shapes = {g.cursor().shape() for g in grips}
    assert Qt.CursorShape.SizeHorCursor in shapes      # right edge → width
    assert Qt.CursorShape.SizeVerCursor in shapes      # bottom edge → height
    assert Qt.CursorShape.SizeFDiagCursor in shapes    # corner → both


def test_vertical_resize_changes_height(grid):
    """REQ-DASH-GRID-03: height (row units) is resizable and persists in layout."""
    grid.add_card(_cfg("A", 6))
    assert grid.layout_specs()[0]["h"] == 1
    grid.set_height(0, 3)
    assert grid.layout_specs()[0]["h"] == 3
    grid.set_height(0, 99)                             # clamped to MAX_ROWS
    from ui.dashboard_grid import MAX_ROWS
    assert grid.layout_specs()[0]["h"] == MAX_ROWS


def test_set_height_stamps_cfg_for_export(grid):
    """REQ-DASH-GRID-HEIGHT: a height change must reach the cfg/layout so export &
    deploy (which serialize cfg layout into chart_h) match Preview & Save.
    Regression: set_height previously updated only the internal it['h'], so deploy
    read a stale layout.h → two same-height cards deployed at different heights."""
    grid.add_card(_cfg("A", 6))
    grid.add_card(_cfg("B", 6))
    grid.set_height(0, 2)
    grid.set_height(1, 2)
    # cards_with_layout (Preview/Save path) reflects it
    cwl = grid.cards_with_layout()
    assert cwl[0]["layout"]["h"] == 2 and cwl[1]["layout"]["h"] == 2
    # raw cards() cfg is now also stamped (Export/Deploy robustness)
    assert (grid.cards()[0].get("layout") or {}).get("h") == 2
    assert (grid.cards()[1].get("layout") or {}).get("h") == 2


def test_equal_heights_deploy_equal_chart_h(grid):
    """REQ-DASH-GRID-HEIGHT: two cards set to the same grid height assemble to the
    same chart_h in the deployed HTML."""
    from charts.fixed_templates import generate_card_fragment
    import re
    grid.add_card({"title": "A", "col_width": 6, "plugin_id": "bar",
                   "metrics": [{"uid": "U", "name": "x", "type": "aggregate", "agg": "SUM"}]})
    grid.add_card({"title": "B", "col_width": 6, "plugin_id": "bar",
                   "metrics": [{"uid": "U", "name": "y", "type": "aggregate", "agg": "SUM"}]})
    grid.set_height(0, 2)
    grid.set_height(1, 2)
    cards = grid.cards_with_layout()
    heights = []
    for i, c in enumerate(cards, 1):
        frag = generate_card_fragment(i, c)
        heights.append(int(re.search(r"chart-wrapper\" style=\"position:relative;height:(\d+)px", frag).group(1)))
    assert heights[0] == heights[1], heights


def test_card_edit_button_emits_open_chart(grid, qtbot):
    """REQ-DASH-GRID-EDIT-01: each card has an 'Edit' button that emits open_chart(cfg)
    so the host can open the chart in the editor."""
    from PySide6.QtWidgets import QPushButton
    grid.add_card({"title": "Cases", "plugin_id": "bar", "col_width": 6,
                   "metrics": [{"uid": "d1", "name": "Cases"}]})
    card = grid._items[0]["card"]
    btns = [b for b in card.findChildren(QPushButton) if b.text() == "Edit"]
    assert btns, "no Edit button on card"
    captured = []
    grid.open_chart.connect(lambda cfg: captured.append(cfg))
    btns[0].click()
    assert captured and captured[0].get("plugin_id") == "bar", captured
