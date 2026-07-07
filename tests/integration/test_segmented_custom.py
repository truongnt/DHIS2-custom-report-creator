"""SegmentedButton custom-value support (user 2026-06-28): custom only where useful,
and the input is INLINE (type directly, no popup)."""
import pytest

pytestmark = pytest.mark.integration

from PySide6.QtWidgets import QPushButton, QLineEdit  # noqa: E402


def _seg(qtbot, **kw):
    from ui.qt_utils import SegmentedButton
    w = SegmentedButton(["Small", "Medium", "Large"], default="Medium", **kw)
    qtbot.addWidget(w)
    return w


def test_no_custom_by_default(qtbot):
    """REQ-UI-OPT-01: no custom input unless requested (enum controls stay clean)."""
    plain = _seg(qtbot)
    assert plain.findChild(QLineEdit) is None
    assert not any(b.text() == "🎨" for b in plain.findChildren(QPushButton))


def test_number_custom_is_inline_input(qtbot):
    """REQ-UI-OPT-02: a number/size custom uses an INLINE field (no popup)."""
    w = _seg(qtbot, custom="number")
    inp = w.findChild(QLineEdit)
    assert inp is not None
    captured = []
    w.changed.connect(captured.append)
    inp.setText("48")
    w._on_input()                       # editingFinished (focus-out / Enter)
    assert w.get() == "48"
    assert captured == ["48"]
    assert all(not b.isChecked() for b in w.findChildren(QPushButton))


def test_color_custom_uses_colordialog(qtbot, monkeypatch):
    """REQ-UI-OPT-01: a colour control opens the colour picker and stores the hex."""
    import ui.qt_utils as m
    from PySide6.QtGui import QColor
    monkeypatch.setattr(m.QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor("#ab12cd")))
    w = _seg(qtbot, custom="color")
    assert any(b.text() == "🎨" for b in w.findChildren(QPushButton))
    w._pick_color()
    assert w.get() == "#ab12cd"


def test_set_restores_custom_value(qtbot):
    """REQ-UI-OPT-01: a saved custom value is restored into the inline field."""
    w = _seg(qtbot, custom="number")
    w.set("99")
    assert w.get() == "99"
    assert w.findChild(QLineEdit).text() == "99"


def test_preset_click_after_custom_restores_selection(qtbot):
    """Selecting a preset after a custom value re-checks it and clears the input."""
    w = _seg(qtbot, custom="number")
    w.set("99")
    w._on_click("Large")
    assert w.get() == "Large"
    assert w._btns["Large"].isChecked()
    assert w.findChild(QLineEdit).text() == ""
