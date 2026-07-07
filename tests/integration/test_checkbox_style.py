"""Checkbox / radio indicators must show a tick / dot, not just a filled colour box
(user report: 'toàn bôi màu cả ô'). QSS data: URIs don't load — must be a real file. (REQ-UI-CHECK)"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_app_qss_uses_svg_file_not_data_uri():
    """REQ-UI-CHECK-01: the checked-indicator image is a real .svg path, not a data: URI."""
    from ui.qt_utils import APP_QSS
    assert "__CHECK_IMG__" not in APP_QSS and "__DOT_IMG__" not in APP_QSS  # substituted
    assert "checkbox_tick.svg" in APP_QSS
    assert "image: url(data:" not in APP_QSS                                # the broken form


def _white_px(widget):
    img = widget.grab().toImage()
    n = 0
    for x in range(2, 18):
        for y in range(3, 22):
            c = img.pixelColor(x, y)
            if c.red() > 200 and c.green() > 200 and c.blue() > 200:
                n += 1
    return n


def test_checked_checkbox_shows_tick(qtbot):
    """REQ-UI-CHECK-02: a checked box paints a white tick over the blue fill."""
    from PySide6.QtWidgets import QCheckBox
    from ui.qt_utils import APP_QSS
    cb = QCheckBox("Option")
    qtbot.addWidget(cb)
    cb.setStyleSheet(APP_QSS)
    cb.setChecked(True)
    cb.resize(120, 26)
    assert _white_px(cb) > 20, "no tick pixels — indicator is a solid colour box"


def test_checked_radio_shows_dot(qtbot):
    """REQ-UI-CHECK-03: a selected radio paints a white centre dot."""
    from PySide6.QtWidgets import QRadioButton
    from ui.qt_utils import APP_QSS
    rb = QRadioButton("Option")
    qtbot.addWidget(rb)
    rb.setStyleSheet(APP_QSS)
    rb.setChecked(True)
    rb.resize(120, 26)
    assert _white_px(rb) > 20, "no dot pixels — radio is a solid colour circle"
