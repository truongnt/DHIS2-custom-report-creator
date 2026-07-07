"""MetadataEditorPanel — curate which metadata is "in use" and edit local descriptions.

Embedded right-side panel (QStackedWidget index 3). Two jobs:
  1. Filter metadata by type (DE / PA / I / PI) and move items between an
     "Available" list and an "In use" list (dual-list transfer). The Chart Editor
     then offers metrics & dimensions ONLY from the in-use list.
  2. Add a local description for the focused item (used as AI context).

Both the in-use selection and the descriptions are stored per-instance
(config.selection / config.descriptions), keyed by the DHIS2 UID.

Lifecycle:
  set_context(base_url, metadata, descriptions)  — call each time the panel is opened
  flush_pending()                                — call when navigating away (bulk save)
  get_descriptions()                             — current {uid: text}
  get_selection()                                — current set of in-use UIDs
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListView, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

DHIS2_BLUE = "#1a6fa8"
PANEL_BG   = "#f7f9fc"
BORDER_CLR = "#d0dde8"
TEXT_DARK  = "#1e2d3d"

# Flattened `kind` label → short type-filter key shown as a checkbox.
_KIND_TO_FILTER = {
    "Data Element":       "DE",
    "Tracker DE":         "DE",
    "Tracked Attribute":  "PA",
    "Indicator":          "I",
    "Program Indicator":  "PI",
}
# Filter keys in display order, with their checkbox labels.
_FILTERS = [("DE", "DE — data elements"),
            ("PA", "PA — attributes"),
            ("I",  "I — indicators"),
            ("PI", "PI — program indicators")]


class MetadataEditorPanel(QWidget):

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._base_url = ""
        self._descriptions: dict[str, str] = {}
        self._pending: dict[str, str] = {}
        self._current_uid: str | None = None
        self._items: list[dict] = []           # all flattened {uid,name,kind}
        self._by_uid: dict[str, dict] = {}
        self._in_use: list[str] = []           # ordered in-use uids
        self._filter_cb = None                 # app_window handler for "⚙ Filters" (scope load)
        self._build()

    # ─── Metadata-scope filter (moved here from the login screen) ──────────────

    def set_filter_callback(self, fn) -> None:
        """app_window installs the handler that opens the scope-filter dialog + reloads."""
        self._filter_cb = fn
        self._filter_btn.setEnabled(fn is not None)

    def set_filter_summary(self, text: str) -> None:
        self._filter_summary.setText(text or "")

    # ─── Public API ──────────────────────────────────────────────────────────

    def set_context(self, base_url: str, metadata: dict, descriptions: dict[str, str]) -> None:
        self._base_url = base_url
        self._descriptions = dict(descriptions or {})
        self._pending.clear()
        self._current_uid = None
        self._items = self._flatten_metadata(metadata or {})
        self._by_uid = {it["uid"]: it for it in self._items}
        try:
            from config.selection import load_selection
            saved = load_selection(base_url) if base_url else set()
        except Exception:
            saved = set()
        # Keep only uids that still exist, preserving a stable (name) order.
        self._in_use = [it["uid"] for it in self._items if it["uid"] in saved]
        self._search.clear()
        self._repopulate()
        self._show_detail(None)

    def flush_pending(self) -> None:
        """Persist unsaved descriptions AND the in-use selection (call when leaving)."""
        if self._current_uid is not None:
            self._pending[self._current_uid] = self._desc_edit.toPlainText()
        if self._pending:
            from config.descriptions import save_descriptions_bulk
            save_descriptions_bulk(self._base_url, self._pending)
            for uid, desc in self._pending.items():
                if desc.strip():
                    self._descriptions[uid] = desc.strip()
                else:
                    self._descriptions.pop(uid, None)
            self._pending.clear()
        try:
            from config.selection import save_selection
            if self._base_url:
                save_selection(self._base_url, self._in_use)
        except Exception:
            pass

    def get_descriptions(self) -> dict[str, str]:
        return dict(self._descriptions)

    def get_selection(self) -> set[str]:
        return set(self._in_use)

    def add_metadata(self, md_subset: dict) -> None:
        """Merge extra metadata (e.g. lazily-fetched indicators) into the lists WITHOUT
        disturbing the current in-use selection or in-progress edits (REQ-META-EDIT-05)."""
        added = False
        for it in self._flatten_metadata(md_subset):
            if it["uid"] not in self._by_uid:
                self._items.append(it)
                self._by_uid[it["uid"]] = it
                added = True
        if added:
            self._items.sort(key=lambda r: r["name"].lower())
            self._repopulate()

    # ─── Data ────────────────────────────────────────────────────────────────

    def _flatten_metadata(self, md: dict) -> list[dict]:
        rows: list[dict] = []
        seen: set[str] = set()

        def _add(items: list, kind_label: str) -> None:
            for item in items or []:
                uid = item.get("id", "")
                if not uid or uid in seen:
                    continue
                seen.add(uid)
                rows.append({"uid": uid,
                             "name": item.get("displayName", "") or uid,
                             "kind": kind_label})

        _add(md.get("indicators", []),                  "Indicator")
        _add(md.get("program_indicators", []),          "Program Indicator")
        _add(md.get("data_elements", []),               "Data Element")
        _add(md.get("program_stage_data_elements", []), "Tracker DE")
        _add(md.get("tracked_entity_attributes", []),   "Tracked Attribute")
        rows.sort(key=lambda r: r["name"].lower())
        return rows

    def _filter_key(self, item: dict) -> str:
        return _KIND_TO_FILTER.get(item.get("kind", ""), "DE")

    def _active_filters(self) -> set[str]:
        # No type checked → show nothing; the user picks which types to show.
        return {k for k, cb in self._filter_cbs.items() if cb.isChecked()}

    # ─── UI ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(46)
        hdr.setStyleSheet(f"background-color: {DHIS2_BLUE};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        title = QLabel("Metadata Library")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        hl.addWidget(title)
        sub = QLabel("Pick which metadata is in use; the Chart Editor offers only these.")
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet("color: rgba(255,255,255,0.75); background: transparent;")
        hl.addWidget(sub)
        hl.addStretch(1)
        # Scope filter (which programs / datasets / groups to fetch) — moved here from login.
        self._filter_btn = QPushButton("⚙ Filters && Load")
        self._filter_btn.setFixedHeight(28)
        self._filter_btn.setEnabled(False)
        self._filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._filter_btn.setToolTip("Choose which programs / datasets / groups to load, then refetch")
        self._filter_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.15); color: white; border: 1px solid"
            "  rgba(255,255,255,0.5); border-radius: 4px; padding: 0 12px; font-size: 11px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.28); }"
            "QPushButton:disabled { color: rgba(255,255,255,0.4); border-color: rgba(255,255,255,0.2); }")
        self._filter_btn.clicked.connect(self._on_filters_clicked)
        hl.addWidget(self._filter_btn)
        root.addWidget(hdr)

        # Type filter + search row
        tools = QFrame()
        tools.setStyleSheet(f"background-color: {PANEL_BG}; border-bottom: 1px solid {BORDER_CLR};")
        tl = QHBoxLayout(tools)
        tl.setContentsMargins(12, 6, 12, 6)
        tl.setSpacing(14)
        show_lbl = QLabel("Show:")
        show_lbl.setStyleSheet(f"color: {TEXT_DARK}; background: transparent; font-weight: 600;")
        tl.addWidget(show_lbl)
        self._filter_cbs: dict[str, QCheckBox] = {}
        for key, label in _FILTERS:
            cb = QCheckBox(label)
            cb.setChecked(False)   # nothing shown until the user picks a type
            cb.setStyleSheet(f"color: {TEXT_DARK}; background: transparent; font-size: 11px;")
            cb.stateChanged.connect(self._repopulate)
            self._filter_cbs[key] = cb
            tl.addWidget(cb)
        tl.addSpacing(12)
        self._filter_summary = QLabel("")
        self._filter_summary.setFont(QFont("Segoe UI", 9))
        self._filter_summary.setStyleSheet("color: #a85600; background: transparent;")
        tl.addWidget(self._filter_summary)
        tl.addStretch(1)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search available by name or UID…")
        self._search.setFixedWidth(240)
        self._search.setFixedHeight(28)
        self._search.setStyleSheet(
            f"QLineEdit {{ border: 1px solid {BORDER_CLR}; border-radius: 4px;"
            f"  padding: 0 8px; background-color: white; color: {TEXT_DARK}; }}"
            "QLineEdit:focus { border-color: #1a6fa8; }")
        self._search.textChanged.connect(self._repopulate)
        tl.addWidget(self._search)
        root.addWidget(tools)

        # Body splitter: [Available] [move buttons] [In use]  //  Description
        body = QSplitter(Qt.Orientation.Vertical)
        body.setHandleWidth(1)
        body.setStyleSheet(f"QSplitter::handle {{ background-color: {BORDER_CLR}; }}")

        transfer = QWidget()
        txl = QHBoxLayout(transfer)
        txl.setContentsMargins(10, 8, 10, 8)
        txl.setSpacing(8)

        self._avail_view, self._avail_model, avail_col = self._make_list("Available")
        self._inuse_view, self._inuse_model, inuse_col = self._make_list("In use")
        self._avail_lbl = avail_col["label"]
        self._inuse_lbl = inuse_col["label"]
        self._avail_view.doubleClicked.connect(lambda *_: self._move_to_inuse())
        self._inuse_view.doubleClicked.connect(lambda *_: self._move_to_available())
        self._avail_view.selectionModel().selectionChanged.connect(
            lambda *_: self._on_row_focus(self._avail_view, self._avail_model))
        self._inuse_view.selectionModel().selectionChanged.connect(
            lambda *_: self._on_row_focus(self._inuse_view, self._inuse_model))

        # Middle move buttons
        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(6)
        ml.addStretch(1)
        self._add_btn     = self._move_btn("→",  "Move selected to In use",   self._move_to_inuse)
        self._add_all_btn = self._move_btn("»",  "Move all shown to In use",  self._move_all_to_inuse)
        self._rem_btn     = self._move_btn("←",  "Remove selected from In use", self._move_to_available)
        self._rem_all_btn = self._move_btn("«",  "Remove all from In use",    self._move_all_to_available)
        for b in (self._add_btn, self._add_all_btn, self._rem_btn, self._rem_all_btn):
            ml.addWidget(b)
        ml.addStretch(1)

        txl.addWidget(avail_col["widget"], 1)
        txl.addWidget(mid)
        txl.addWidget(inuse_col["widget"], 1)
        body.addWidget(transfer)

        # Description editor
        detail = QWidget()
        detail.setStyleSheet("background-color: white;")
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(14, 10, 14, 10)
        dl.setSpacing(6)
        self._detail_name = QLabel("Select an item to add a description")
        self._detail_name.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._detail_name.setStyleSheet(f"color: {TEXT_DARK};")
        self._detail_name.setWordWrap(True)
        dl.addWidget(self._detail_name)
        self._detail_meta = QLabel("")
        self._detail_meta.setStyleSheet("color: #52708c;")
        dl.addWidget(self._detail_meta)

        desc_lbl = QLabel("Description (stored locally — used as AI context):")
        desc_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        desc_lbl.setStyleSheet("color: #3a5068;")
        dl.addWidget(desc_lbl)
        self._desc_edit = QPlainTextEdit()
        self._desc_edit.setPlaceholderText(
            "Enter a description for this data element / indicator.\n"
            "Example: 'Number of confirmed malaria cases (blood smear positive)'.")
        self._desc_edit.setFixedHeight(90)
        self._desc_edit.setStyleSheet(
            "QPlainTextEdit { border: 1px solid #c0cdd8; border-radius: 4px; padding: 6px;"
            f"  background-color: white; color: {TEXT_DARK}; }}"
            "QPlainTextEdit:focus { border-color: #1a6fa8; }")
        self._desc_edit.setEnabled(False)
        self._desc_edit.textChanged.connect(self._on_desc_changed)
        dl.addWidget(self._desc_edit)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self._save_btn = QPushButton("Save description")
        self._save_btn.setFixedHeight(28)
        self._save_btn.setEnabled(False)
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background-color: {DHIS2_BLUE}; border: none; border-radius: 4px;"
            "  color: white; padding: 0 14px; }"
            "QPushButton:hover { background-color: #155a8a; }"
            "QPushButton:disabled { background-color: #a8c8e8; color: #e0eaf4; }")
        self._save_btn.clicked.connect(self._save_current)
        save_row.addWidget(self._save_btn)
        dl.addLayout(save_row)
        body.addWidget(detail)

        body.setSizes([460, 200])
        root.addWidget(body, 1)

    def _make_list(self, title: str):
        col = QWidget()
        cl = QVBoxLayout(col)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)
        lbl = QLabel(f"{title} (0)")
        lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: #3a5068; background: transparent;")
        cl.addWidget(lbl)
        model = QStandardItemModel()
        view = QListView()
        view.setModel(model)
        from ui.metadata_display import TypePrefixDelegate
        view.setItemDelegate(TypePrefixDelegate(view))
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        view.setStyleSheet(
            f"QListView {{ background-color: {PANEL_BG}; color: {TEXT_DARK};"
            f"  border: 1px solid {BORDER_CLR}; border-radius: 4px; }}"
            f"QListView::item {{ color: {TEXT_DARK}; padding: 3px 6px; }}"
            f"QListView::item:selected {{ background-color: {DHIS2_BLUE}; color: white; }}"
            f"QListView::item:hover:!selected {{ background-color: #dce8f4; color: {TEXT_DARK}; }}")
        cl.addWidget(view, 1)
        return view, model, {"widget": col, "label": lbl}

    def _move_btn(self, text: str, tip: str, slot) -> QPushButton:
        b = QPushButton(text)
        b.setFixedSize(38, 30)
        b.setToolTip(tip)
        b.setStyleSheet(
            "QPushButton { background: white; border: 1px solid #7a9ab0; border-radius: 4px;"
            "  color: #2c4257; font-size: 14px; font-weight: 700; }"
            "QPushButton:hover { background: #e0ecf4; }")
        b.clicked.connect(slot)
        return b

    # ─── Populate ──────────────────────────────────────────────────────────────

    def _label_for(self, item: dict) -> str:
        # App-wide format "(DE) Name" (prefix colour-coded by TypePrefixDelegate); a
        # leading ✓ marks items that already have a local description.
        from ui.metadata_display import plain_label
        mark = "✓ " if self._desc_for(item["uid"]) else ""
        return f"{mark}{plain_label(item)}"

    def _desc_for(self, uid: str) -> str:
        return self._pending.get(uid, self._descriptions.get(uid, "")).strip()

    def _repopulate(self, *_) -> None:
        active = self._active_filters()
        in_use_set = set(self._in_use)
        query = self._search.text().strip().lower()

        self._avail_model.clear()
        avail_n = 0
        for it in self._items:
            if it["uid"] in in_use_set or self._filter_key(it) not in active:
                continue
            if query and query not in it["name"].lower() and query not in it["uid"].lower():
                continue
            self._avail_model.appendRow(self._std_item(it))
            avail_n += 1

        # In-use is filtered by the same "Show" type checkboxes as Available (search
        # stays Available-only). It still auto-saves the full selection regardless.
        self._inuse_model.clear()
        inuse_n = 0
        for uid in self._in_use:
            it = self._by_uid.get(uid)
            if not it or self._filter_key(it) not in active:
                continue
            self._inuse_model.appendRow(self._std_item(it))
            inuse_n += 1

        self._avail_lbl.setText(f"Available ({avail_n})")
        self._inuse_lbl.setText(f"In use ({inuse_n} shown / {len(self._in_use)} total)")

    def _std_item(self, it: dict) -> QStandardItem:
        std = QStandardItem(self._label_for(it))
        std.setData(it["uid"], Qt.ItemDataRole.UserRole)
        return std

    # ─── Move logic ─────────────────────────────────────────────────────────────

    def _selected_uids(self, view: QListView, model: QStandardItemModel) -> list[str]:
        return [model.itemFromIndex(i).data(Qt.ItemDataRole.UserRole)
                for i in view.selectedIndexes()]

    def _shown_uids(self, model: QStandardItemModel) -> list[str]:
        return [model.item(r).data(Qt.ItemDataRole.UserRole) for r in range(model.rowCount())]

    def _move_to_inuse(self) -> None:
        self._add_uids(self._selected_uids(self._avail_view, self._avail_model))

    def _move_all_to_inuse(self) -> None:
        self._add_uids(self._shown_uids(self._avail_model))

    def _move_to_available(self) -> None:
        self._remove_uids(self._selected_uids(self._inuse_view, self._inuse_model))

    def _move_all_to_available(self) -> None:
        self._remove_uids(self._shown_uids(self._inuse_model))

    def _add_uids(self, uids: list[str]) -> None:
        cur = set(self._in_use)
        for u in uids:
            if u and u not in cur:
                self._in_use.append(u)
                cur.add(u)
        self._persist_selection()
        self._repopulate()

    def _remove_uids(self, uids: list[str]) -> None:
        drop = set(uids)
        self._in_use = [u for u in self._in_use if u not in drop]
        self._persist_selection()
        self._repopulate()

    def _on_filters_clicked(self) -> None:
        if self._filter_cb:
            self._filter_cb()

    def _persist_selection(self) -> None:
        """Save the in-use set immediately so it survives even if the app is closed
        without navigating away from the panel."""
        try:
            from config.selection import save_selection
            if self._base_url:
                save_selection(self._base_url, self._in_use)
        except Exception:
            pass

    # ─── Description editing ─────────────────────────────────────────────────────

    def _on_row_focus(self, view: QListView, model: QStandardItemModel) -> None:
        idxs = view.selectedIndexes()
        if not idxs:
            return
        uid = model.itemFromIndex(idxs[0]).data(Qt.ItemDataRole.UserRole)
        self._show_detail(self._by_uid.get(uid))

    def _show_detail(self, item: dict | None) -> None:
        # Stash the edit in progress before switching.
        if self._current_uid is not None:
            self._pending[self._current_uid] = self._desc_edit.toPlainText()
        if not item:
            self._current_uid = None
            self._detail_name.setText("Select an item to add a description")
            self._detail_meta.setText("")
            self._desc_edit.blockSignals(True)
            self._desc_edit.clear()
            self._desc_edit.blockSignals(False)
            self._desc_edit.setEnabled(False)
            self._save_btn.setEnabled(False)
            return
        self._current_uid = item["uid"]
        self._detail_name.setText(item["name"])
        self._detail_meta.setText(f"UID: {item['uid']}  ·  {item['kind']}")
        desc = self._pending.get(item["uid"], self._descriptions.get(item["uid"], ""))
        self._desc_edit.blockSignals(True)
        self._desc_edit.setPlainText(desc)
        self._desc_edit.blockSignals(False)
        self._desc_edit.setEnabled(True)
        self._save_btn.setEnabled(True)

    def _on_desc_changed(self) -> None:
        if self._current_uid:
            self._pending[self._current_uid] = self._desc_edit.toPlainText()

    def _save_current(self) -> None:
        if self._current_uid is None:
            return
        text = self._desc_edit.toPlainText().strip()
        from config.descriptions import save_description
        save_description(self._base_url, self._current_uid, text)
        if text:
            self._descriptions[self._current_uid] = text
        else:
            self._descriptions.pop(self._current_uid, None)
        self._pending.pop(self._current_uid, None)
        self._repopulate()   # refresh ✓ markers
