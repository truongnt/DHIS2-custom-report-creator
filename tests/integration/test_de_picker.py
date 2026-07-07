"""DEPickerWidget — metric chips: uniform height, styled agg dropdown, drag-reorder
(user report 2026-06-28)."""
import pytest

pytestmark = pytest.mark.integration

from PySide6.QtWidgets import QComboBox  # noqa: E402


def _picker(qtbot, n=3):
    from ui.qt_utils import DEPickerWidget
    p = DEPickerWidget(max_count=8, show_agg=True)
    qtbot.addWidget(p)
    items = [{"uid": f"uid{i:08d}", "name": f"DE {i}", "type": "aggregate"} for i in range(n)]
    p.set_items(items)
    p.set_selected_uids([d["uid"] for d in items])
    return p


def _chips(p):
    return [p._chips_lay.itemAt(i).widget() for i in range(p._chips_lay.count())
            if p._chips_lay.itemAt(i).widget() is not None]


def test_chips_uniform_height(qtbot):
    """REQ-CE-METRIC-UI-01: every metric chip on its row shares one fixed height."""
    p = _picker(qtbot, 3)
    chips = _chips(p)
    assert len(chips) == 3
    assert {c.maximumHeight() for c in chips} == {28}


def test_available_list_caps_rendering(qtbot):
    """REQ-CE-PICKER-CAP-01: a huge item list (thousands of indicators) renders only the
    first _MAX_RENDER rows + a 'type to search' hint, so the picker never freezes."""
    from ui.qt_utils import DEPickerWidget
    p = DEPickerWidget(max_count=8, show_agg=True)
    qtbot.addWidget(p)
    n = p._MAX_RENDER + 500
    p.set_items([{"uid": f"ind{i:08d}", "name": f"Indicator {i}", "type": "indicator"}
                 for i in range(n)])  # nothing selected → all available
    from PySide6.QtWidgets import QLabel
    from ui.qt_utils import _ClickRow      # clickable rich-text rows (were QPushButtons)
    btns = [p._avail_lay.itemAt(i).widget() for i in range(p._avail_lay.count())]
    n_rows = sum(1 for w in btns if isinstance(w, _ClickRow))
    assert n_rows == p._MAX_RENDER, f"expected cap {p._MAX_RENDER}, got {n_rows}"
    # The truncation hint is a plain QLabel (not a clickable row).
    hints = [w.text() for w in btns if isinstance(w, QLabel) and not isinstance(w, _ClickRow)]
    assert any("type to search" in h.lower() for h in hints), "missing truncation hint"
    # Searching narrows below the cap → all matches render, no hint.
    p._search.setText("Indicator 7")     # e.g. 7, 70-79, 700-799, 7000+ (< cap)
    btns2 = [p._avail_lay.itemAt(i).widget() for i in range(p._avail_lay.count())]
    assert all(("type to search" not in w.text().lower())
               for w in btns2 if isinstance(w, QLabel) and not isinstance(w, _ClickRow))


def test_set_selected_uids_known_fallback(qtbot):
    """REQ-CE-RESTORE-IND-01: a saved selection restores from the metric dicts even when the
    item is not in the available list yet (e.g. indicators that load on demand), and survives
    a later set_items once the item is loaded."""
    from ui.qt_utils import DEPickerWidget
    p = DEPickerWidget(max_count=8, show_agg=True)
    qtbot.addWidget(p)
    p.set_items([])                                  # nothing available (indicators not loaded)
    p.set_selected_uids(["ind1"], {"ind1": "SUM"},
                        known={"ind1": {"uid": "ind1", "name": "Cases tested",
                                        "type": "indicator"}})
    sel = p.get_selected_des()
    assert len(sel) == 1 and sel[0]["uid"] == "ind1" and sel[0]["name"] == "Cases tested"
    # When indicators finish loading, the restored chip is preserved (uid now available).
    p.set_items([{"uid": "ind1", "name": "Cases tested", "type": "indicator"},
                 {"uid": "ind2", "name": "Positive", "type": "indicator"}])
    assert [s["uid"] for s in p.get_selected_des()] == ["ind1"]


def test_agg_combo_has_light_popup_style(qtbot):
    """REQ-CE-METRIC-UI-02: the SUM/COUNT dropdown styles its popup (not a black list)."""
    p = _picker(qtbot, 1)
    chip = _chips(p)[0]
    combo = chip.findChild(QComboBox)
    assert combo is not None
    assert "QAbstractItemView" in combo.styleSheet(), "popup view not styled → black popup"
    assert "#ffffff" in combo.styleSheet().lower() or "white" in combo.styleSheet().lower()


def test_drag_grip_only_when_multiple(qtbot):
    """REQ-CE-METRIC-UI-03: a drag handle appears only when reordering is possible (>1)."""
    from ui.qt_utils import _DragGrip
    p1 = _picker(qtbot, 1)
    assert _chips(p1)[0].findChild(_DragGrip) is None
    p3 = _picker(qtbot, 3)
    assert all(c.findChild(_DragGrip) is not None for c in _chips(p3))


def test_reorder_moves_metric(qtbot):
    """REQ-CE-METRIC-REORDER-01: dragging a metric reorders the selection."""
    p = _picker(qtbot, 3)
    assert [s["uid"] for s in p.get_selected_des()] == ["uid00000000", "uid00000001", "uid00000002"]
    p._reorder_to("uid00000000", 3)            # drag the first item to the end
    assert [s["uid"] for s in p.get_selected_des()] == \
        ["uid00000001", "uid00000002", "uid00000000"]
    p._reorder_to("uid00000000", 0)            # drag it back to the front
    assert [s["uid"] for s in p.get_selected_des()][0] == "uid00000000"


def test_set_show_agg_hides_dropdown(qtbot):
    """REQ-CE-METRIC-UI-04: hiding agg (e.g. raw Data Table) removes the SUM/COUNT dropdown."""
    p = _picker(qtbot, 2)
    assert _chips(p)[0].findChild(QComboBox) is not None     # shown by default
    p.set_show_agg(False)
    assert all(c.findChild(QComboBox) is None for c in _chips(p))
    p.set_show_agg(True)
    assert _chips(p)[0].findChild(QComboBox) is not None


def test_long_metric_name_does_not_grow_chip(qtbot):
    """REQ-CE-METRIC-UI-05: a very long metric name must not push controls out (chip keeps
    its fixed height; the label clips instead)."""
    from ui.qt_utils import DEPickerWidget
    p = DEPickerWidget(max_count=8, show_agg=True)
    qtbot.addWidget(p)
    long_name = "Invest: Method of diagnosis - Other specify (very long label) " * 3
    items = [{"uid": "uidlong0001", "name": long_name, "type": "aggregate"}]
    p.set_items(items)
    p.set_selected_uids(["uidlong0001"])
    chip = _chips(p)[0]
    assert chip.maximumHeight() == 28


from PySide6.QtWidgets import QLineEdit  # noqa: E402


def test_alias_field_present_and_updates(qtbot):
    """REQ-CE-METRIC-ALIAS-01: each metric chip has an alias field; typing sets 'alias'."""
    p = _picker(qtbot, 1)
    alias_in = _chips(p)[0].findChild(QLineEdit)
    assert alias_in is not None
    alias_in.setText("My Alias")
    assert p.get_selected_des()[0]["alias"] == "My Alias"


def test_set_selected_restores_alias(qtbot):
    """REQ-CE-METRIC-ALIAS-02: alias_map restores the alias on load."""
    p = _picker(qtbot, 2)
    uids = [s["uid"] for s in p.get_selected_des()]
    p.set_selected_uids(uids, None, {uids[0]: "Alias0"})
    by_uid = {s["uid"]: s for s in p.get_selected_des()}
    assert by_uid[uids[0]]["alias"] == "Alias0"


def test_dim_picker_has_no_alias_field(qtbot):
    """REQ-CE-METRIC-ALIAS-03: show_alias=False (dimension picker) shows no alias field."""
    from ui.qt_utils import DEPickerWidget
    p = DEPickerWidget(max_count=1, show_agg=False, show_alias=False)
    qtbot.addWidget(p)
    p.set_items([{"uid": "u0000000001", "name": "Gender", "type": "tracker_option"}])
    p.set_selected_uids(["u0000000001"])
    assert _chips(p)[0].findChild(QLineEdit) is None
