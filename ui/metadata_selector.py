"""
MetadataSelector — popup window để người dùng search và pin indicator/DE/program indicator
trước khi Generate report. Các item được pin sẽ được ưu tiên trong LLM context.

Usage:
    sel = MetadataSelector(parent, metadata, usage_counts, pinned)
    parent.wait_window(sel)
    new_pinned = sel.result   # dict or None if cancelled
"""
from __future__ import annotations
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk

DHIS2_BLUE = "#1a6fa8"
PIN_COLOR  = "#e8f4fd"
BORDER     = "#d0dde8"

_TABS = [
    ("indicators",         "Indicators"),
    ("program_indicators", "Program Indicators"),
    ("data_elements",      "Data Elements"),
]


class MetadataSelector(ctk.CTkToplevel):
    def __init__(self, parent, metadata: dict, usage_counts: dict, pinned: dict):
        super().__init__(parent)
        self.title("Select & Pin Metadata for Report")
        self.geometry("1000x680")
        self.minsize(800, 500)
        self.grab_set()          # modal
        self.focus_force()

        self._metadata    = metadata
        self._usage       = usage_counts
        # deep copy pinned so we can cancel
        self._pinned: dict[str, set[str]] = {
            k: set(v) for k, v in pinned.items()
        }
        self.result: dict | None = None  # set on OK

        self._search_vars: dict[str, tk.StringVar] = {}
        self._trees:       dict[str, ttk.Treeview]  = {}
        self._all_rows:    dict[str, list[tuple]]   = {}  # kind → [(uid, name, count, extra)]

        self._build()
        self._load_all()

    # ─── Layout ──────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        outer = ctk.CTkFrame(self, fg_color="white", corner_radius=0)
        outer.grid(sticky="nsew")
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        # Left: tabbed search/list
        left = ctk.CTkFrame(outer, fg_color="white", corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 0))
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        # Right: pinned panel
        right = ctk.CTkFrame(outer, width=280, fg_color="#f4f8fc",
                             corner_radius=0, border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_propagate(False)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self._build_tabs(left)
        self._build_pinned_panel(right)
        self._build_buttons(outer)

    def _build_tabs(self, parent):
        tab_view = ctk.CTkTabview(parent, fg_color="white",
                                   segmented_button_fg_color="#e8f0f8",
                                   segmented_button_selected_color=DHIS2_BLUE,
                                   segmented_button_selected_hover_color="#155a8a",
                                   border_width=0)
        tab_view.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        for kind, label in _TABS:
            tab = tab_view.add(label)
            tab.grid_rowconfigure(1, weight=1)
            tab.grid_columnconfigure(0, weight=1)
            self._build_tab_content(tab, kind)

    def _build_tab_content(self, parent, kind: str):
        # Search bar
        search_var = tk.StringVar()
        self._search_vars[kind] = search_var
        search_var.trace_add("write", lambda *_: self._filter(kind))

        search_frame = ctk.CTkFrame(parent, fg_color="transparent")
        search_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        search_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkEntry(search_frame, textvariable=search_var,
                     placeholder_text="Search by name or UID…",
                     height=32, font=ctk.CTkFont(size=12),
                     border_color=BORDER).grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(search_frame, text="Pin Selected", width=110, height=32,
                      fg_color=DHIS2_BLUE, hover_color="#155a8a",
                      command=lambda k=kind: self._pin_selected(k)).grid(
            row=0, column=1, padx=(8, 0))

        # Treeview
        style = ttk.Style()
        style.configure(f"{kind}.Treeview",
                         rowheight=24, font=("Segoe UI", 10),
                         background="white", fieldbackground="white",
                         foreground="#1e2d3d", borderwidth=0)
        style.configure(f"{kind}.Treeview.Heading",
                         background="#e8f0f8", foreground="#1e2d3d",
                         font=("Segoe UI", 10, "bold"), relief="flat")
        style.map(f"{kind}.Treeview",
                  background=[("selected", "#cce0f5")])

        cols = ("uses", "uid", "name", "extra")
        tree = ttk.Treeview(parent, style=f"{kind}.Treeview",
                             columns=cols, show="headings",
                             selectmode="extended")
        tree.heading("uses", text="Uses")
        tree.heading("uid",  text="UID")
        tree.heading("name", text="Name")
        tree.heading("extra", text="Type / Program")
        tree.column("uses",  width=48,  anchor="center", stretch=False)
        tree.column("uid",   width=100, anchor="w",      stretch=False)
        tree.column("name",  width=340, anchor="w")
        tree.column("extra", width=180, anchor="w",      stretch=False)
        tree.grid(row=1, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(parent, orient="vertical",   command=tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=1, column=1, sticky="ns")
        hsb.grid(row=2, column=0, sticky="ew")

        tree.bind("<Double-1>", lambda e, k=kind: self._pin_selected(k))

        self._trees[kind] = tree

    def _build_pinned_panel(self, parent):
        ctk.CTkLabel(parent, text="Pinned for this report",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#1e2d3d").grid(
            row=0, column=0, padx=14, pady=(14, 6), sticky="w")

        self._pin_box = ctk.CTkTextbox(
            parent, font=ctk.CTkFont(family="Consolas", size=10),
            fg_color="white", text_color="#1e2d3d",
            border_width=1, border_color=BORDER,
            state="disabled",
        )
        self._pin_box.grid(row=1, column=0, padx=10, pady=(0, 6), sticky="nsew")

        ctk.CTkButton(parent, text="Clear All Pins", width=120, height=28,
                      fg_color="transparent", border_width=1,
                      border_color="#e74c3c", text_color="#e74c3c",
                      hover_color="#fdecea",
                      command=self._clear_pins).grid(
            row=2, column=0, padx=10, pady=(0, 10))

    def _build_buttons(self, parent):
        btn_row = ctk.CTkFrame(parent, fg_color="#f0f4f8",
                                corner_radius=0, height=50)
        btn_row.grid(row=1, column=0, columnspan=2, sticky="ew")
        btn_row.grid_propagate(False)

        ctk.CTkLabel(btn_row,
                     text="Double-click or select + 'Pin Selected' to add items.",
                     font=ctk.CTkFont(size=11), text_color="#6b8299").pack(
            side="left", padx=16)

        ctk.CTkButton(btn_row, text="Cancel", width=90, height=34,
                      fg_color="transparent", border_width=1,
                      border_color=BORDER, text_color="#4a6278",
                      hover_color="#e8f0f8",
                      command=self._on_cancel).pack(side="right", padx=(0, 16), pady=8)

        ctk.CTkButton(btn_row, text="OK — Use These Pins", width=160, height=34,
                      fg_color=DHIS2_BLUE, hover_color="#155a8a",
                      command=self._on_ok).pack(side="right", padx=(0, 8), pady=8)

    # ─── Data Loading ─────────────────────────────────────────────────────────

    def _load_all(self):
        for kind, _ in _TABS:
            self._all_rows[kind] = self._build_rows(kind)
            self._populate_tree(kind, self._all_rows[kind])
        self._refresh_pin_box()

    def _build_rows(self, kind: str) -> list[tuple]:
        items   = self._metadata.get(kind, [])
        counts  = self._usage.get(kind, {})
        rows = []
        for item in items:
            uid   = item.get("id", "")
            name  = item.get("displayName", "")
            count = counts.get(uid, 0)
            if kind == "indicators":
                extra = item.get("indicatorType", {}).get("displayName", "")
            elif kind == "program_indicators":
                extra = item.get("program", {}).get("displayName", "")
            else:
                extra = item.get("valueType", "")
            rows.append((count, uid, name, extra))
        # Sort: pinned first, then by usage count desc
        pinned = self._pinned.get(kind, set())
        rows.sort(key=lambda r: (r[1] not in pinned, -r[0], r[2].lower()))
        return rows

    def _populate_tree(self, kind: str, rows: list[tuple]):
        tree    = self._trees[kind]
        pinned  = self._pinned.get(kind, set())
        for item in tree.get_children():
            tree.delete(item)
        for count, uid, name, extra in rows:
            tag = "pinned" if uid in pinned else ("used" if count > 0 else "")
            display_count = str(count) if count > 0 else ""
            tree.insert("", "end", iid=uid,
                        values=(display_count, uid, name, extra),
                        tags=(tag,))
        tree.tag_configure("pinned", background="#d4edff", font=("Segoe UI", 10, "bold"))
        tree.tag_configure("used",   background="#f0f8f0")

    def _filter(self, kind: str):
        query = self._search_vars[kind].get().strip().lower()
        if not query:
            self._populate_tree(kind, self._all_rows[kind])
            return
        filtered = [
            r for r in self._all_rows[kind]
            if query in r[2].lower() or query in r[1].lower() or query in r[3].lower()
        ]
        self._populate_tree(kind, filtered)

    # ─── Pin Actions ─────────────────────────────────────────────────────────

    def _pin_selected(self, kind: str):
        tree   = self._trees[kind]
        sel    = tree.selection()
        bucket = self._pinned.setdefault(kind, set())
        for iid in sel:
            bucket.add(iid)
        self._reload_tree(kind)
        self._refresh_pin_box()

    def _clear_pins(self):
        self._pinned = {k: set() for k, _ in _TABS}
        for kind, _ in _TABS:
            self._reload_tree(kind)
        self._refresh_pin_box()

    def _reload_tree(self, kind: str):
        # Rebuild rows (re-sort with new pins at top) and re-apply current filter
        self._all_rows[kind] = self._build_rows(kind)
        self._filter(kind)

    def _refresh_pin_box(self):
        self._pin_box.configure(state="normal")
        self._pin_box.delete("1.0", "end")
        total = 0
        for kind, label in _TABS:
            uids = self._pinned.get(kind, set())
            if not uids:
                continue
            self._pin_box.insert("end", f"── {label} ──\n")
            items_by_uid = {
                item["id"]: item.get("displayName", item["id"])
                for item in self._metadata.get(kind, [])
            }
            for uid in sorted(uids):
                name = items_by_uid.get(uid, uid)
                self._pin_box.insert("end", f"  {uid}\n  {name}\n\n")
                total += 1
        if total == 0:
            self._pin_box.insert("end", "(no items pinned yet)\n\nDouble-click items\nin the list to pin them.")
        self._pin_box.configure(state="disabled")

    # ─── OK / Cancel ─────────────────────────────────────────────────────────

    def _on_ok(self):
        # Convert sets to sorted lists for JSON serialisation
        self.result = {k: sorted(v) for k, v in self._pinned.items()}
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()
