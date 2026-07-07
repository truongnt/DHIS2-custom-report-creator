"""SaveEntityDialog — capture a Name + Description when saving a chart/dashboard."""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QVBoxLayout, QWidget,
)

from ui.qt_utils import DHIS2_BLUE, PANEL_BG, style_dialog_buttons


class SaveEntityDialog(QDialog):
    """Modal asking for a Name (required) and an optional Description."""

    def __init__(self, parent, *, title: str, name: str = "", description: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(440, 200)
        self._build(title, name, description)

    def _build(self, title: str, name: str, description: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QFrame()
        hdr.setFixedHeight(40)
        hdr.setStyleSheet(f"background-color: {DHIS2_BLUE};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 14, 0)
        lbl = QLabel(title)
        lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl.setStyleSheet("color: white; background: transparent;")
        hl.addWidget(lbl)
        root.addWidget(hdr)

        body = QWidget()
        body.setStyleSheet(f"background-color: {PANEL_BG};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 14, 16, 14)
        bl.setSpacing(8)

        _field_qss = (
            "QLineEdit { border:1px solid #c0cdd8; border-radius:4px; padding:4px 8px;"
            "  background:white; color:#1e2d3d; }"
            "QLineEdit:focus { border-color:#1a6fa8; }"
        )

        bl.addWidget(self._lbl("Name"))
        self._name = QLineEdit(name)
        self._name.setPlaceholderText("Required")
        self._name.setStyleSheet(_field_qss)
        bl.addWidget(self._name)

        bl.addWidget(self._lbl("Description (optional)"))
        self._desc = QLineEdit(description)
        self._desc.setPlaceholderText("What does it show? Shown in the Open list.")
        self._desc.setStyleSheet(_field_qss)
        bl.addWidget(self._desc)
        root.addWidget(body, 1)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.button(QDialogButtonBox.StandardButton.Ok).setText("Save")
        box.accepted.connect(self._on_ok)
        box.rejected.connect(self.reject)
        root.addWidget(style_dialog_buttons(box))
        self._name.setFocus()

    @staticmethod
    def _lbl(text: str) -> QLabel:
        w = QLabel(text)
        w.setFont(QFont("Segoe UI", 9))
        w.setStyleSheet("color:#5a7a9a; background:transparent;")
        return w

    def _on_ok(self) -> None:
        if not self._name.text().strip():
            QMessageBox.information(self, self.windowTitle(), "Enter a name.")
            self._name.setFocus()
            return
        self.accept()

    def values(self) -> tuple[str, str]:
        return self._name.text().strip(), self._desc.text().strip()

    @classmethod
    def prompt(cls, parent, *, title: str, name: str = "",
               description: str = "") -> tuple[str, str] | None:
        """Show modally. Returns (name, description) or None if cancelled."""
        dlg = cls(parent, title=title, name=name, description=description)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.values()
        return None
