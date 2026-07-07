"""Delete / remove buttons must render a compact red ✕ — the global QDialog QPushButton
QSS previously overrode them into dark, boxed buttons (user report). (REQ-UI-DELICON)"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _red_px(widget) -> int:
    img = widget.grab().toImage()
    return sum(1 for x in range(img.width()) for y in range(img.height())
               if img.pixelColor(x, y).red() > 140
               and img.pixelColor(x, y).green() < 100
               and img.pixelColor(x, y).blue() < 100)


def test_open_chart_delete_icon_is_red_x(qtbot):
    """REQ-UI-DELICON-01: the per-row delete button in the Open Chart dialog is a red ✕."""
    from PySide6.QtWidgets import QApplication
    from ui.qt_utils import APP_QSS
    QApplication.instance().setStyleSheet(APP_QSS)     # global rule that used to clobber it
    from ui.load_chart_dialog import LoadChartDialog
    dlg = LoadChartDialog(None, [{"id": "c1", "name": "Chart A",
                                  "template_label": "Bar", "created_at": "2026-01-01"}])
    qtbot.addWidget(dlg)
    dlg.resize(700, 300)
    cell = dlg._table.cellWidget(0, 4)
    assert _red_px(cell) > 10, "delete icon is not a visible red ✕"


def test_dashboard_remove_icon_is_red_x(qtbot):
    """REQ-UI-DELICON-02: the remove-from-dashboard button is a red ✕."""
    from PySide6.QtWidgets import QApplication
    from ui.qt_utils import APP_QSS
    QApplication.instance().setStyleSheet(APP_QSS)
    from PySide6.QtWidgets import QPushButton
    from ui.dashboard_grid import GridCanvas, _GridCard
    canvas = GridCanvas()
    qtbot.addWidget(canvas)
    canvas.add_card({"title": "A", "template_id": "bar_monthly"}, w=6)
    card = canvas.findChild(_GridCard)
    rm = card.findChild(QPushButton, "cardRemoveBtn")
    assert rm is not None, "remove button not found by objectName"
    assert _red_px(rm) > 8, "remove icon is not a visible red ✕"
