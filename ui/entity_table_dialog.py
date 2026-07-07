"""EntityTableDialog — pick a saved chart/dashboard to open, shown as a table
with Name · Description · Type · Date columns and a per-row delete button.

Subclassed by LoadChartDialog and LoadDashboardDialog so both look identical.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QVBoxLayout,
    QWidget,
)

from ui.qt_utils import DHIS2_BLUE, PANEL_BG, BORDER_CLR, style_dialog_buttons

_COLUMNS = ["Name", "Description", "Type", "Date", ""]   # last col = delete button


class EntityTableDialog(QDialog):
    """Generic 'open a saved entity' dialog rendered as a table.

    Subclasses implement:
      _row_for(entity)  -> (name, description, type, date) tuple of strings
      _delete(entity)   -> remove it from storage
    and pass window_title / intro to __init__.
    """

    def __init__(self, parent: QWidget, entities: list[dict], *,
                 window_title: str, intro: str):
        super().__init__(parent)
        self.setWindowTitle(window_title)
        self.resize(680, 400)
        self._entities = list(entities)
        self._intro = intro
        self._selected: dict | None = None
        self._build()
        self._populate()

    # ── subclass hooks ──────────────────────────────────────────────────────
    def _row_for(self, entity: dict) -> tuple[str, str, str, str]:
        raise NotImplementedError

    def _delete(self, entity: dict) -> None:
        raise NotImplementedError

    # ── build ────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QFrame()
        hdr.setFixedHeight(40)
        hdr.setStyleSheet(f"background-color: {DHIS2_BLUE};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 14, 0)
        lbl = QLabel(self.windowTitle())
        lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl.setStyleSheet("color: white; background: transparent;")
        hl.addWidget(lbl)
        root.addWidget(hdr)

        body = QWidget()
        body.setStyleSheet(f"background-color: {PANEL_BG};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(14, 10, 14, 10)
        bl.setSpacing(6)

        intro = QLabel(self._intro)
        intro.setFont(QFont("Segoe UI", 9))
        intro.setStyleSheet("color: #5a7a9a;")
        bl.addWidget(intro)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setStyleSheet(
            "QTableWidget {"
            f" background:white; border:1px solid {BORDER_CLR}; border-radius:4px;"
            "  color:#1e2d3d; gridline-color:#eef2f6; }"
            "QTableWidget::item { padding:4px 6px; }"
            f"QTableWidget::item:selected {{ background:{DHIS2_BLUE}; color:white; }}"
            "QTableWidget::item:hover:!selected { background:#dce8f4; }"
            "QHeaderView::section {"
            "  background:#eef3f8; color:#3a5068; border:none;"
            f" border-bottom:1px solid {BORDER_CLR}; padding:5px 6px; font-weight:bold; }}"
        )
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 150)
        self._table.setColumnWidth(2, 130)
        self._table.setColumnWidth(3, 92)
        self._table.setColumnWidth(4, 40)
        self._table.doubleClicked.connect(lambda _i: self._on_ok())
        bl.addWidget(self._table, 1)

        root.addWidget(body, 1)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("Open")
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self.reject)
        root.addWidget(style_dialog_buttons(btn_box))

    def _populate(self) -> None:
        self._table.setRowCount(0)
        for entity in self._entities:
            name, desc, typ, date = self._row_for(entity)
            r = self._table.rowCount()
            self._table.insertRow(r)
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, entity)
            self._table.setItem(r, 0, name_item)
            self._table.setItem(r, 1, QTableWidgetItem(desc))
            self._table.setItem(r, 2, QTableWidgetItem(typ))
            self._table.setItem(r, 3, QTableWidgetItem(date))
            self._table.setCellWidget(r, 4, self._make_delete_btn(entity))
        if self._table.rowCount():
            self._table.selectRow(0)

    def _make_delete_btn(self, entity: dict) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(2, 2, 2, 2)
        btn = QPushButton("✕")
        btn.setObjectName("rowDeleteBtn")   # ID selector below beats the global QDialog QPushButton rule
        btn.setFixedSize(24, 24)
        btn.setToolTip("Delete")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton#rowDeleteBtn { background:transparent; border:1px solid #e0a0a0;"
            "  border-radius:3px; color:#c0392b; font-size:13px; font-weight:bold;"
            "  min-width:0px; padding:0px; }"
            "QPushButton#rowDeleteBtn:hover { background:#fdecea; }"
            "QPushButton#rowDeleteBtn:pressed { background:#f5c6c0; }"
        )
        btn.clicked.connect(lambda _=False, e=entity: self._delete_entity(e))
        lay.addWidget(btn)
        return wrap

    # ── actions ──────────────────────────────────────────────────────────────
    def _row_of(self, entity: dict) -> int:
        # data(UserRole) may not preserve object identity across the Qt boundary, so
        # match on the id field (fall back to identity/equality).
        target_id = entity.get("id")
        for r in range(self._table.rowCount()):
            it = self._table.item(r, 0)
            e = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
            if e is entity or (target_id is not None and isinstance(e, dict)
                               and e.get("id") == target_id):
                return r
        return -1

    def _delete_entity(self, entity: dict) -> None:
        name = entity.get("name") or entity.get("title", "?")
        if QMessageBox.question(
            self, "Delete", f"Delete '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._delete(entity)
        r = self._row_of(entity)
        if r >= 0:
            self._table.removeRow(r)
        if entity in self._entities:
            self._entities.remove(entity)

    def _selected_entity(self) -> dict | None:
        r = self._table.currentRow()
        if r < 0:
            return None
        it = self._table.item(r, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _on_ok(self) -> None:
        ent = self._selected_entity()
        if ent is None:
            QMessageBox.information(self, self.windowTitle(), "Select a row first.")
            return
        self._selected = ent
        self.accept()

    def get_selected(self) -> dict | None:
        return self._selected
